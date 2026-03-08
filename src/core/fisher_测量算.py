# core/fisher.py
import time
from utils.screenshot import ScreenGrabber
from detection.yolo_detector import YOLODetector
from core.mouse_controller import MouseController
import config
import win32api
import cv2
import csv

class FishingState:
    CAST = "CAST"                           # 抛竿
    WAIT_EXCLAMATION = "WAIT_EXCLAMATION"   # 等待感叹号
    # CLICK_EXCLAMATION = "CLICK_EXCLAMATION" # 点击感叹号
    WAIT_GAME_START = "WAIT_GAME_START"     # 等待游戏区域出现
    FISHING = "FISHING"                     # 钓鱼小游戏进行中
    FINISH = "FINISH"                       # 收鱼/重抛
    ERROR = "ERROR"                   # 错误状态，需要人工干预
    QWE = "QWE" # 调试

class FishColor:
    BLACK = "黑色"
    BROWN = "棕色"
    WHITE = "白色"
    GREEN = "绿色"
    BLUE  = "蓝色"
    PURPLE= "紫色"
    GOLDEN= "金色"
    RED   = "红色"
    COLOURS = "彩色"
    UNKNOWN = "未知"


class Fisher:
    def __init__(self, roi=None, overlay=None):
        self.full_grabber = ScreenGrabber(roi)
        self.detector = YOLODetector()
        self.mouse = MouseController()
        self.overlay = overlay
        
        self.stop_event = None

        # 预留ROI game_area
        self.current_roi = None  # (x, y, w, h)

        self.is_pause = False
        self.accumulated_run_time = 0.0      # 累计运行时间（秒）
        self._run_start_time = None       # 当前这次启动时间
        

        # 状态机
        self.state = FishingState.CAST      # 初始状态
        # self.state = FishingState.QWE
        self.state_start_time = time.time() # 状态开始时间
        self.wait_exclamation_count = config.MAX_WAIT_EXCLAMATION_COUNT
        self.max_wait_game_appeara_time = config.MAX_WAIT_GAME_APPEARA_TIME
        self.fish_progress = 0
        self.max_fish_finish_wait_time = config.MAX_FISH_FINISH_WAIT_TIME
        self.fish_finish_wait_time = -1
        self.fish_is_success = False
        self.mouse_click_time = 0
        self.max_targetbar_fall_time = config.MAX_TARGETBAR_FALL_TIME
        self.max_mouse_hold_time = config.MAX_MOUSE_HOLD_TIME
        self.max_wait_exclamatione_time = config.MAX_WAIT_EXCLAMATIONE_TIME
        
        self.mouse_hold_start_time = -1 # 鼠标开始长按的时间
        self.mouse_hold_remaining  = 0  # 鼠标还需要长按多少秒
        self.fish_location_befor = 0    # 鱼上一帧的位置
        self.fish_location_now = 0      # 鱼当前的位置
        self.recast_wait_time = config.RECAST_WAIT_TIME
        self.recast_wait = 0
        self.last_cast_time = -1
        self.finsh_catch_click_time = 0

        # --- 控制状态变量 ---
        self.mouse_down = False           # 当前鼠标是否按住（True=按住，False=松开）
        self.last_action_time = 0         # 上次切换动作的时间戳（用于最小间隔）
        self.bar_prev_cy = None           # 上一帧白条中心Y
        self.bar_prev_time = None         # 上一帧时间戳
        self.bar_velocity = 0.0           # 白条速度（像素/秒）
        self.fish_smooth_cy = None        # 平滑后的鱼中心Y
        self.fish_prev_cy = None          # 上一帧鱼中心Y，用于计算鱼速度
        self.fish_velocity = 0.0           # 鱼的速度（像素/秒，正=向下）
        self.bar_accel = 0.0                # 白条的加速度（像素/秒²）
        self.prev_bar_velocity = 0.0        # 上一帧白条速度，用于计算加速度

        # --- PD参数（可调整）---
        self.kp =config.FISH_PID_CONTROL_KP                         # 比例增益（影响按住力度）
        self.kd =config.FISH_PID_CONTROL_MAX_KD                     # 微分增益（速度阻尼）
        self.kf =config.FISH_PID_CONTROL_KF                         # 鱼速度前馈
        self.max_kd =config.FISH_PID_CONTROL_MAX_KD                 # 速度项限幅
        self.threshold =config.FISH_PID_CONTROL_THRESHOLD               # 按住阈值（目标力大于此则按）
        self.dead_zone =config.FISH_PID_CONTROL_DEAD_ZONE               # 误差死区
        self.force_threshold =config.FISH_PID_CONTROL_FORCE_THRESHOLD           # 强制区域阈值（误差超过此值直接强制动作）
        self.min_switch_interval =config.FISH_PID_CONTROL_MIN_SWITCH_INTERVAL   # 最小切换间隔（秒）

        # 数据统计
        self.grab_time = 0.0      # 最近截图平均耗时
        self.dete_time = 0.0      # 最近检测平均耗时
        self.run_time  = 0.0      # 最近整个循环平均耗时
        self.fish_success_count = 0
        self.fish_fail_count    = 0
        self.last_fish_success_time = 0 # 上次成功钓鱼时间
        self.run_start_time = 0
        self.fish_color = None  # 循环开始时置空
        self.frame_fish_color = []
        self.last_color_time = 0
        self.statistics = {
            'successful_catches': 0,    # 成功钓鱼次数
            'fail_catches'      : 0,    # 失败钓鱼次数
            'total_run_time'    : 0,    # 脚本运行时间
            'fish_Statistics'   : {
                FishColor.BLACK:{'success': 0, 'fail': 0},
                FishColor.BROWN:{'success': 0, 'fail': 0},
                FishColor.WHITE:{'success': 0, 'fail': 0},
                FishColor.GREEN:{'success': 0, 'fail': 0},
                FishColor.BLUE:{'success': 0, 'fail': 0},
                FishColor.PURPLE:{'success': 0, 'fail': 0},
                FishColor.GOLDEN:{'success': 0, 'fail': 0},
                FishColor.COLOURS:{'success': 0, 'fail': 0},
                FishColor.UNKNOWN:{'success': 0, 'fail': 0}
            }    # 钓鱼统计
        }


        self.test_data_fish_y1 = None
        self.test_data_fish_y2 = None
        self.test_data_tb_y1 = None
        self.test_data_tb_y2 = None
        self.test_data_tt_y1 = None
        self.test_data_tt_y2 = None
        self.test_data_mouse_press = None
        self.test_data_dt = None            # 本次循环从开始到结束所花费的时间
        self.test_data_id = 0
        self.test_data_csv_item = []
        self.test_data_last_analysis_time = 0  # 上次循环时间





    def run(self, stop_event):
        self.stop_event = stop_event
        frame_count = 0
        t11 = 0
        t22 = 0
        t33 = 0
        fps_grab_time = 0
        fps_dete_time = 0
        t_star = time.time()
        self.run_start_time = t_star
        self._run_start_time = t_star

        # 调试
        # --- PD参数（可调整）---
        self.kp =config.FISH_PID_CONTROL_KP                         # 比例增益（影响按住力度）
        self.kd =config.FISH_PID_CONTROL_MAX_KD                     # 微分增益（速度阻尼）
        self.kf =config.FISH_PID_CONTROL_KF                         # 鱼速度前馈
        self.max_kd =config.FISH_PID_CONTROL_MAX_KD                 # 速度项限幅
        self.threshold =config.FISH_PID_CONTROL_THRESHOLD               # 按住阈值（目标力大于此则按）
        self.dead_zone =config.FISH_PID_CONTROL_DEAD_ZONE               # 误差死区
        self.force_threshold =config.FISH_PID_CONTROL_FORCE_THRESHOLD           # 强制区域阈值（误差超过此值直接强制动作）
        self.min_switch_interval =config.FISH_PID_CONTROL_MIN_SWITCH_INTERVAL   # 最小切换间隔（秒）
        
        with open('_data.csv','w',newline='',encoding='utf-8') as f:
            test_data_writer = csv.writer(f)
            while not stop_event.is_set():
                tmp_start_time = time.time()  
                lines = []
                lines.append(f"双击 {config.HOTKEY_START} 开始/停止")
                lines.append(f"双击 {config.HOTKEY_STOP} 退出程序")   

                if self.is_pause:
                    self.mouse.enable(False)
                else:
                    self.mouse.enable(True)

                t0 = time.time()
                # print(self.current_roi)
                
                frame = self.full_grabber.grab()
                t1 = time.time()
                if frame is None:
                    dets = {
                        "exclamation": [],
                        "totalbar": [],
                        "targetbar": [],
                        "fish": [],
                        "progressbar": [],
                        "progressbar_indicator": [],
                        "game_area": []
                    }
                else:
                    # dets = self.detector.detect(frame,self.current_roi)
                    dets = self.detector.detect(frame)
                t2 = time.time()
                
                # print("detections:", dets)
                # print(self.detector.get_running_model_name())
                

                exclamation = dets["exclamation"][0] if dets["exclamation"] else None
                totalbar = dets["totalbar"][0] if dets["totalbar"] else None
                targetbar = dets["targetbar"][0] if dets["targetbar"] else None
                fish = dets["fish"][0] if dets["fish"] else None
                progressbar = dets["progressbar"][0] if dets["progressbar"] else None
                progressbar_indicator = dets["progressbar_indicator"][0] if dets["progressbar_indicator"] else None
                game_area = dets["game_area"][0] if dets["game_area"] else None

                
                lines.append(f"exclamation: {exclamation}")
                lines.append(f"fish: {fish}")
                lines.append(f"totalbar: {totalbar}")
                lines.append(f"progressbar: {progressbar}")
                lines.append(f"progressbar_indicator: {progressbar_indicator}")
                lines.append(f"targetbar: {targetbar}")
                lines.append(f"game_area: {game_area}")
                lines.append(f"状态: {self.state}")

                
                

                # 核心逻辑
                # =================状态机=================
                if self.state == FishingState.CAST:
                    if time.time()-self.finsh_catch_click_time>=self.recast_wait_time:
                        if self.recast_wait <= 0:
                            lines.append(f"抛竿")
                            self.mouse.click()
                            self.mouse.move_LR()
                            self.state = FishingState.WAIT_EXCLAMATION
                            self.state_start_time = time.time()
                            self.last_cast_time = time.time()
                            self.recast_wait = self.recast_wait_time
                        else:
                            self.recast_wait -= (time.time()-self.last_cast_time)
                
                elif self.state == FishingState.WAIT_EXCLAMATION:
                    remaining_wait_exclamation_time = self.max_wait_exclamatione_time - (time.time() - self.state_start_time)
                    lines.append(f"等待感叹号:{remaining_wait_exclamation_time}")
                    if exclamation:
                        lines.append("出现感叹号！")
                        self.mouse.click()
                        self.state = FishingState.WAIT_GAME_START
                        self.state_start_time = time.time()
                        self.wait_exclamation_count = config.MAX_WAIT_EXCLAMATION_COUNT
                    elif remaining_wait_exclamation_time <= 0:
                        self.wait_exclamation_count -= 1
                        if self.wait_exclamation_count <= 0:
                            lines.append("连续三次抛竿失败！")
                            self.state = FishingState.CAST
                            self.state_start_time = time.time()
                            self.wait_exclamation_count = 3
                        else:
                            lines.append("等不及了！")
                            self.mouse.click()
                            # 这里后续要补充一个判断：如果点击后没有出现游戏区域则回到CAST
                            self.state = FishingState.WAIT_GAME_START
                            self.state_start_time = time.time()
                    if game_area:
                        self.state = FishingState.FISHING
                        self.state_start_time = time.time()
                        self.wait_exclamation_count = config.MAX_WAIT_EXCLAMATION_COUNT

                elif self.state == FishingState.WAIT_GAME_START:
                    if targetbar and fish:
                        lines.append("出现啦！")
                        self.state = FishingState.FISHING
                        self.state_start_time = time.time()
                        self.wait_exclamation_count = 0
                    else:
                        if time.time()-self.state_start_time >= self.max_wait_game_appeara_time:
                            lines.append("我的鱼呢？")
                            self.state = FishingState.CAST
                            self.state_start_time = time.time()
                        
                elif self.state == FishingState.FISHING:
                    # ================== 动态调整ROI（可选，保留你原有的区域调整逻辑） ==================
                    if game_area:
                        game_area_box, _ = game_area
                        gx1, gy1, gx2, gy2 = game_area_box
                        add_per = 0.2 / 2
                        margin_w = (gx2 - gx1) * add_per
                        margin_h = (gy2 - gy1) * add_per
                        left = int(max(0, gx1 - margin_w))
                        top = int(max(0, gy1 - margin_h))
                        screen_width = win32api.GetSystemMetrics(0)
                        screen_height = win32api.GetSystemMetrics(1)
                        right = int(min(gx2 + margin_w, screen_width))
                        bottom = int(min(gy2 + margin_h, screen_height))
                        width = right - left
                        height = bottom - top
                        self.current_roi = (left, top, width, height)
                    if fish:
                        # self.update_fish_color(self.current_roi,fish[0])
                        # lines.append(f"这条鱼的颜色是：{self.fish_color}")
                        pass
                    # ================== 进度条显示（保留） ==================
                    if progressbar and progressbar_indicator:
                        progressbar_box, _ = progressbar
                        progressbar_indicator_box, _ = progressbar_indicator
                        progressbarx1, progressbary1, progressbarx2, progressbary2 = progressbar_box
                        progressbar_indicatorx1, progressbar_indicatory1, progressbar_indicatorx2, progressbar_indicatory2 = progressbar_indicator_box
                        tmp_pi_y = progressbar_indicatory2 - progressbar_indicatory1
                        tmp_p_y = progressbary2 - progressbary1
                        tmp_pi_cen = (progressbar_indicatory2 + progressbar_indicatory1) / 2
                        if tmp_pi_y / tmp_p_y <= 1 / 6:
                            self.fish_progress = (progressbary2 - tmp_pi_cen) / tmp_p_y
                            lines.append(f"钓鱼进度:{self.fish_progress:.2%}")

                    # ================== 关键检测缺失处理（保留） ==================
                    if not (targetbar and fish and totalbar):
                        # lines.append("等下我没看清QwQ")
                        temp_varaibles = [totalbar, targetbar, fish, progressbar, progressbar_indicator, game_area]
                        temp_empty_count = sum(1 for t_v in temp_varaibles if not t_v)
                        if temp_empty_count == 6:
                            temp_empty_count_time = time.time()
                            if self.fish_finish_wait_time == -1:
                                self.fish_finish_wait_time = temp_empty_count_time
                            if temp_empty_count_time - self.fish_finish_wait_time >= self.max_fish_finish_wait_time:
                                self.fish_is_success = (self.fish_progress >= 0.8)
                                self.state = FishingState.FINISH
                                self.state_start_time = temp_empty_count_time
                                self.fish_finish_wait_time = -1
                                self.current_roi = None
                                print(f"钓鱼结束：{self.fish_is_success}")
                        elif temp_empty_count >= 3:
                            lines.append("移动视角保持UI完全露出！")
                        # 继续下一帧
                    else:
                        
                        self.fish_finish_wait_time = -1
                        # --- 坐标解析（保持不变）---
                        fish_box, fish_conf = fish
                        target_box, target_conf = targetbar
                        total_box, total_conf = totalbar

                        fx1, fy1, fx2, fy2 = fish_box
                        tx1, ty1, tx2, ty2 = target_box
                        ttx1, tty1, ttx2, tty2 = total_box

                        fish_cy = (fy1 + fy2) / 2
                        bar_cy = (ty1 + ty2) / 2
                        bar_h = ty2 - ty1

                        self.test_data_fish_y1 = fy1
                        self.test_data_fish_y2 = fy2
                        self.test_data_tb_y1 = ty1
                        self.test_data_tb_y2 = ty2
                        self.test_data_tt_y1 = tty1
                        self.test_data_tt_y2 = tty2
                        tmp_analysis_time = time.time()
                        self.test_data_dt = tmp_analysis_time - self.test_data_last_analysis_time
                        self.test_data_last_analysis_time = tmp_analysis_time

                        # --- 鱼平滑（可保持快速）---
                        if self.fish_smooth_cy is None:
                            self.fish_smooth_cy = fish_cy
                        else:
                            self.fish_smooth_cy = 0.8 * fish_cy + 0.2 * self.fish_smooth_cy

                        # --- 时间相关 ---
                        now = time.time()
                        if not hasattr(self, 'last_time'):
                            self.last_time = now
                        dt = now - self.last_time
                        self.last_time = now

                        # --- 白条速度估算（同前）---
                        if self.bar_prev_cy is not None and self.bar_prev_time is not None:
                            dt_bar = now - self.bar_prev_time
                            if dt_bar > 0.001:
                                raw_vel = (bar_cy - self.bar_prev_cy) / dt_bar
                                self.bar_velocity = 0.2 * raw_vel + 0.8 * self.bar_velocity
                        else:
                            self.bar_velocity = 0.0
                        self.bar_prev_cy = bar_cy
                        self.bar_prev_time = now

                        # --- 鱼速度估算（新增）---
                        if self.fish_prev_cy is not None and self.fish_prev_time is not None:
                            dt_fish = now - self.fish_prev_time
                            if dt_fish > 0.001:
                                raw_fish_vel = (fish_cy - self.fish_prev_cy) / dt_fish
                                self.fish_velocity = 0.8 * raw_fish_vel + 0.2 * self.fish_velocity
                        else:
                            self.fish_velocity = 0.0
                        self.fish_prev_cy = fish_cy
                        self.fish_prev_time = now

                        # --- 白条加速度估算（可选，先不加，如果需要再加）---
                        # if hasattr(self, 'prev_bar_velocity'):
                        #     if dt > 0.001:
                        #         raw_accel = (self.bar_velocity - self.prev_bar_velocity) / dt
                        #         self.bar_accel = 0.3 * raw_accel + 0.7 * self.bar_accel
                        # self.prev_bar_velocity = self.bar_velocity

                        # --- 误差计算 ---
                        error_pixel = self.fish_smooth_cy - bar_cy
                        error_norm = error_pixel / max(bar_h, 1)

                        # --- PD + 前馈参数（建议初始值）---
                        kp = self.kp
                        kd = self.kd
                        kf = self.kf          # 鱼速度前馈系数（正数，公式中用 -kf * fish_velocity）
                        threshold = self.threshold
                        dead_zone = self.dead_zone
                        # 暂时不用强制区域，或阈值设大如 0.6
                        force_threshold = self.force_threshold   # 加大避免干扰

                        # --- 计算目标力 ---
                        # 基础项：比例 + 微分
                        base_force = -kp * error_norm + kd * self.bar_velocity
                        # 前馈项：鱼速度（注意符号）
                        ff_force = -kf * self.fish_velocity
                        target_force = base_force + ff_force

                        # 速度项限幅（可选）
                        max_kd_term = self.max_kd
                        kd_term = kd * self.bar_velocity
                        kd_term = max(-max_kd_term, min(max_kd_term, kd_term))
                        target_force = -kp * error_norm + kd_term - kf * self.fish_velocity

                        # # --- 强制区域（可选，阈值设大）---
                        # if error_norm > force_threshold:
                        #     target_force = -1.0
                        # elif error_norm < -force_threshold:
                        #     target_force = 1.0

                        # --- 最小切换间隔 ---
                        self.test_data_mouse_press = self.mouse_down
                        if now - self.last_action_time < self.min_switch_interval:
                            # 保持当前状态
                            if self.mouse_down:
                                self.mouse.hold()
                            else:
                                self.mouse.release()
                        else:
                            if target_force > threshold:
                                if not self.mouse_down:
                                    self.last_action_time = now
                                    lines.append(f"按住 err={error_norm:.2f} vel={self.bar_velocity:.1f} fvel={self.fish_velocity:.1f} force={target_force:.2f}")
                                self.mouse.hold()
                                self.mouse_down = True
                            else:
                                if self.mouse_down:
                                    self.last_action_time = now
                                    lines.append(f"松开 err={error_norm:.2f} vel={self.bar_velocity:.1f} fvel={self.fish_velocity:.1f} force={target_force:.2f}")
                                self.mouse.release()
                                self.mouse_down = False

                        # 日志
                        self.test_data_csv_item.append([self.test_data_id,self.test_data_fish_y1,self.test_data_fish_y2,self.test_data_tb_y1,self.test_data_tb_y2,self.test_data_tt_y1,self.test_data_tt_y2,self.test_data_dt,self.test_data_mouse_press])
                        lines.append(f"鱼Y={fish_cy:.1f} 条Y={bar_cy:.1f} err={error_norm:.2f} v={self.bar_velocity:.1f} fv={self.fish_velocity:.1f}")
                        # 8. 更新上一帧鱼位置（如果需要）
                        # self.fish_location_befor = self.fish_location_now  # 如果保留原变量用于其他用途
                        


                elif self.state == FishingState.FINISH:
                    finish_time = time.time()
                    if self.fish_is_success:
                        self.mouse.click()
                        self.finsh_catch_click_time = finish_time
                        self.last_fish_success_time = finish_time
                        self.state = FishingState.CAST
                        self.state_start_time = finish_time
                        self.fish_success_count += 1
                        if self.fish_color is None:
                            self.fish_color = FishColor.UNKNOWN
                        self.statistics['fish_Statistics'][self.fish_color]['success'] += 1
                    else:
                        self.state = FishingState.CAST
                        self.state_start_time = finish_time
                        self.fish_fail_count += 1
                        if self.fish_color is None:
                            self.fish_color = FishColor.UNKNOWN
                        self.statistics['fish_Statistics'][self.fish_color]['fail'] += 1
                    self.fish_color = None
                    test_data_writer.writerows(self.test_data_csv_item)
                    self.test_data_id += 1 
                    self.test_data_csv_item = []
                    self.test_data_dt = 0
                    self.test_data_last_analysis_time = 0
                    

                elif self.state == FishingState.ERROR:
                    self.state = FishingState.CAST
                    self.state_start_time = time.time()
                    print("ERROR")
   

                tmp_end_time = time.time()
                # 统计数据
                frame_count += 1
                t11 += (t1 - t0)
                t22 += (t2 - t1)
                t33 += (tmp_end_time - tmp_start_time)
                if tmp_end_time - t_star >=1:
                    t_star = time.time()
                    self.grab_time = t11/frame_count
                    self.dete_time = t22/frame_count
                    self.run_time  = t33/frame_count
                    frame_count = 0
                    t11 = 0
                    t22 = 0
                    t33 = 0
                    t_star = tmp_end_time
                # 计算帧率（避免除零）
                fps_grab = 1.0 / self.grab_time if self.grab_time > 0 else 0
                fps_dete = 1.0 / self.dete_time if self.dete_time > 0 else 0
                fps_run  = 1.0 / self.run_time  if self.run_time  > 0 else 0

                # current_session_time = tmp_end_time - self._run_start_time
                # total_runtime = self.accumulated_run_time + current_session_time

                self.accumulated_run_time += tmp_end_time - self._run_start_time
                self._run_start_time = tmp_end_time

                lines.append(f"截图平均帧: {fps_grab}")
                lines.append(f"检测平均帧: {fps_dete}")
                lines.append(f"脚本帧数: {fps_run}")
                lines.append(f"本次运行钓到{self.fish_success_count}条鱼，放跑了{self.fish_fail_count}条鱼")
                lines.append(f"距离上次成功钓鱼:{self.format_time(tmp_end_time - self.last_fish_success_time if self.last_fish_success_time>0 else 0)}")  
                lines.append(f"总运行时间: {self.format_time(self.accumulated_run_time)}")
                self.overlay.update(lines)

                # if self._run_start_time is not None:
                #     self.accumulated_run_time += tmp_end_time - self._run_start_time
                    # self._run_start_time = None
                    


    def update_fish_color(self, roi, box):
        """
        更新鱼的颜色采样。当收集到5个样本后，根据一致性确定颜色。
        应在每帧检测到鱼时调用。
        :param roi: 当前检测用的图像区域（可能全屏或ROI）
        :param box: 鱼的边界框 (x1, y1, x2, y2) 相对于 roi
        """
        now = time.time()
        # 如果颜色已经确定，直接返回
        if self.fish_color:
            return
        # print('roi:',roi)
        # if roi is None:
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1) 
        roi = [0,0,screen_width,screen_height]

        # 采样条件：未满5个，且距离上次采样至少0.555秒
        if len(self.frame_fish_color) < 5 and (now - self.last_color_time) >= 0.555:
            hsv = self._extract_fish_hsv(roi, box)
            if hsv is not None:
                color = self._hsv_to_color(hsv)
                self.frame_fish_color.append(color)
            self.last_color_time = now  # 必须更新采样时间

        # 如果样本数达到5，进行一致性判断
        if len(self.frame_fish_color) == 5:
            first = self.frame_fish_color[0]
            if all(c == first for c in self.frame_fish_color):
                self.fish_color = first
            else:
                self.fish_color = FishColor.COLOURS
            self.fish_color_determined = True
            # 可选：清空样本，释放内存
            self.frame_fish_color.clear()


    def _extract_fish_hsv(self, roi, box, shrink_ratio=0.6):
        x1, y1, x2, y2 = map(int, box)
        h, w = roi[:2]
        x1 = max(0, min(x1, w-1))
        y1 = max(0, min(y1, h-1))
        x2 = max(x1+1, min(x2, w))
        y2 = max(y1+1, min(y2, h))

        width = x2 - x1
        height = y2 - y1
        if width <= 2 or height <= 2:
            return None

        # 中心区域
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        half_w = int(width * shrink_ratio / 2)
        half_h = int(height * shrink_ratio / 2)

        cx1 = max(x1, cx - half_w)
        cx2 = min(x2, cx + half_w)
        cy1 = max(y1, cy - half_h)
        cy2 = min(y2, cy + half_h)

        if cx2 <= cx1 or cy2 <= cy1:
            return None

        center_roi = roi[cy1:cy2, cx1:cx2]
        if center_roi.size == 0:
            return None

        hsv = cv2.cvtColor(center_roi, cv2.COLOR_BGR2HSV)
        mean_h, mean_s, mean_v = cv2.mean(hsv)[:3]
        return (mean_h, mean_s, mean_v)
    

    def _hsv_to_color(self, hsv):
        h, s, v = hsv

        # 黑色
        if v < 40:
            return FishColor.BLACK
        # 白色
        if v > 220 and s < 30:
            return FishColor.WHITE
        # 低饱和度（灰色/银色/极淡色）
        if s < 30:
            return FishColor.UNKNOWN

        # 彩色
        if h <= 10 or h >= 160:
            return FishColor.RED
        elif 10 < h <= 25:
            if s > 100 and v > 150:
                return FishColor.GOLDEN
            else:
                return FishColor.BROWN
        elif 25 < h <= 35:
            if s > 100 and v > 150:
                return FishColor.GOLDEN
            else:
                return FishColor.BROWN
        elif 35 < h <= 85:
            return FishColor.GREEN
        elif 85 < h <= 125:
            return FishColor.BLUE
        elif 125 < h <= 155:
            return FishColor.PURPLE
        else:
            return FishColor.UNKNOWN
    

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


    def stop(self):
        self.statistics['total_run_time'] = self.accumulated_run_time
        self.mouse.release()
        self.full_grabber.release()
    

    def set_mouse_enable(self,is_enbale):
        self.set_mouse_enable = is_enbale






