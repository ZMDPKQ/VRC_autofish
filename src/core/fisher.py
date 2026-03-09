# core/fisher.py
import time

import numpy as np
from utils.screenshot import ScreenGrabber
from detection.yolo_detector import YOLODetector
from core.mouse_controller import MouseController
import config
import win32api
import cv2
import json
import os
from collections import Counter


class FishingState:
    CAST = "抛竿"                           # 抛竿
    WAIT_EXCLAMATION = "等待感叹号"   # 等待感叹号
    # CLICK_EXCLAMATION = "CLICK_EXCLAMATION" # 点击感叹号
    WAIT_GAME_START = "等待游戏开始"     # 等待游戏区域出现
    FISHING = "激烈的搏斗"                     # 钓鱼小游戏进行中
    FINISH = "结束"                       # 收鱼/重抛
    FORG = "收青蛙"                           # 收青蛙
    SELL = "卖鱼"                           # 卖鱼
    ERROR = "未知错误、重试"                   # 错误状态，需要人工干预
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
    MAGENTA = "粉色"
    COLOURS = "彩色"
    UNKNOWN = "未知"


class Fisher:
    def __init__(self, roi=None, overlay=None):
        self.init_time = time.time()
        self.full_grabber = ScreenGrabber(roi)
        self.detector = YOLODetector()
        self.mouse = MouseController()
        self.overlay = overlay
        
        self.stop_event = None

        # 预留ROI game_area
        self.current_roi = None  # (x, y, w, h)

        self.is_pause = False
        self.accumulated_run_time = 0.0      # 累计运行时间（秒）
        self._run_start_time = None       # 当前这次启动时间点
        self.total_runtime_this = None
        self.screen_width = win32api.GetSystemMetrics(0)
        self.screen_height = win32api.GetSystemMetrics(1)
        

        # 状态机
        self.state = None
        self.change_state(FishingState.CAST,self.init_time)
        # self.state = FishingState.QWE
        
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
        self.forg_countdown = 1  # 收青蛙倒计时
        self.sell_countdown = 1  # 卖鱼倒计时
        
        self.mouse_hold_start_time = -1 # 鼠标开始长按的时间
        self.mouse_hold_remaining  = 0  # 鼠标还需要长按多少秒
        self.fish_location_befor = 0    # 鱼上一帧的位置
        self.fish_location_now = 0      # 鱼当前的位置
        self.recast_wait_time = config.RECAST_WAIT_TIME
        self.recast_wait = 0
        self.last_cast_time = -1
        self.finsh_catch_click_time = 0
        self.mouse_move_list = []
        self.mouse_move_onfinish_list = []

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
        self.bar_smooth_cy = None
        self.fish_smooth_norm = None
        self.bar_prev_norm = None
        self.fish_prev_norm = None

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
                FishColor.RED:{'success': 0, 'fail': 0},
                FishColor.GOLDEN:{'success': 0, 'fail': 0},
                FishColor.MAGENTA:{'success': 0, 'fail': 0},
                FishColor.COLOURS:{'success': 0, 'fail': 0},
                FishColor.UNKNOWN:{'success': 0, 'fail': 0}
            }    # 钓鱼统计
        }
        self.load_statistics()


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
        self._run_start_time = time.time()

        self.load_statistics()
        self.accumulated_run_time = float(self.statistics['total_run_time'])
        self.fish_success_count = int(self.statistics['successful_catches'])
        self.fish_fail_count = int(self.statistics['fail_catches'])
        if self.total_runtime_this:
            self.accumulated_run_time += self.total_runtime_this
        self.total_runtime_this = self.accumulated_run_time

        
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
                print(f"frame{frame_count} is None")
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

            exclamation_conf = float(exclamation[1]) if exclamation else None
            totalbar_conf = float(totalbar[1]) if totalbar else None
            targetbar_conf = float(targetbar[1]) if targetbar else None
            fish_conf = float(fish[1]) if fish else None
            progressbar_conf = float(progressbar[1]) if progressbar else None
            progressbar_indicator_conf = float(progressbar_indicator[1]) if progressbar_indicator else None
            game_area_conf = float(game_area[1]) if game_area else None
            
            lines.append(f"exclamation: {float(exclamation_conf):.2%}" if exclamation_conf else 'exclamation:')
            lines.append(f"fish: {float(fish_conf):.2%}" if fish_conf else 'fish:')
            lines.append(f"totalbar: {float(totalbar_conf):.2%}" if totalbar_conf else 'totalbar:')
            lines.append(f"progressbar: {float(progressbar_conf):.2%}" if progressbar_conf else 'progressbar:')
            lines.append(f"progressbar_indicator: {float(progressbar_indicator_conf):.2%}" if progressbar_indicator_conf else 'progressbar_indicator:')
            lines.append(f"targetbar: {float(targetbar_conf):.2%}" if targetbar_conf else 'targetbar:')
            lines.append(f"game_area: {float(game_area_conf):.2%}" if game_area_conf else 'game_area:')
            lines.append(f"状态: {self.state}")

            
            

            # 核心逻辑
            # =================状态机=================
            state_machine_start_time = time.time()
            if self.state == FishingState.CAST:
                if state_machine_start_time-self.finsh_catch_click_time>=self.recast_wait_time:
                    if self.recast_wait <= 0:
                        # lines.append(f"抛竿")
                        self.mouse.click()
                        self.mouse.move_LR()
                        self.change_state(FishingState.WAIT_EXCLAMATION,state_machine_start_time)
                        self.fish_color = None
                        self.last_cast_time = state_machine_start_time
                        self.recast_wait = self.recast_wait_time
                    else:
                        self.recast_wait -= (state_machine_start_time-self.last_cast_time)
            
            elif self.state == FishingState.WAIT_EXCLAMATION:
                remaining_wait_exclamation_time = self.max_wait_exclamatione_time - (state_machine_start_time - self.state_start_time)
                lines.append(f"等待感叹号:{remaining_wait_exclamation_time:.2f}")
                if exclamation:
                    # lines.append("出现感叹号！")
                    if self.mouse.click():
                        self.change_state(FishingState.WAIT_GAME_START,time.time())
                        self.wait_exclamation_count = config.MAX_WAIT_EXCLAMATION_COUNT
                elif remaining_wait_exclamation_time <= 0:
                    self.wait_exclamation_count -= 1
                    if self.wait_exclamation_count <= 0:
                        # lines.append("连续三次抛竿失败！")
                        self.change_state(FishingState.CAST,state_machine_start_time)
                        self.wait_exclamation_count = 3
                        # 连续三次失败的处理
                        pass
                    else:
                        # lines.append("等不及了！")
                        if self.mouse.click():
                            self.change_state(FishingState.WAIT_GAME_START,state_machine_start_time)
                if game_area:
                    self.change_state(FishingState.FISHING,state_machine_start_time)
                    self.wait_exclamation_count = config.MAX_WAIT_EXCLAMATION_COUNT

            elif self.state == FishingState.WAIT_GAME_START:
                if targetbar and fish:
                    # lines.append("出现啦！")
                    self.change_state(FishingState.FISHING,state_machine_start_time)
                    self.wait_exclamation_count = 0
                else:
                    if state_machine_start_time-self.state_start_time >= self.max_wait_game_appeara_time:
                        # lines.append("我的鱼呢？")
                        self.change_state(FishingState.CAST,state_machine_start_time)
                    
            elif self.state == FishingState.FISHING:
                # ================== 动态调整ROI ==================
                if game_area:
                    game_area_box, _ = game_area
                    gx1, gy1, gx2, gy2 = game_area_box
                    add_per = 0.2 / 2
                    margin_w = (gx2 - gx1) * add_per
                    margin_h = (gy2 - gy1) * add_per
                    left = int(max(0, gx1 - margin_w))
                    top = int(max(0, gy1 - margin_h))
                    
                    right = int(min(gx2 + margin_w, self.screen_width))
                    bottom = int(min(gy2 + margin_h, self.screen_height))
                    width = right - left
                    height = bottom - top
                    self.current_roi = (left, top, width, height)
                
                if fish:
                    self.update_fish_color(frame,fish[0])
                    lines.append(f"这条鱼的颜色是：{self.fish_color}")
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
                        # lines.append(f"钓鱼进度:{self.fish_progress:.2%}")

                # ================== 关键检测缺失处理（保留） ==================
                if not (targetbar and fish and totalbar):
                    # lines.append("等下我没看清QwQ")
                    temp_varaibles = [totalbar, targetbar, fish, progressbar, progressbar_indicator, game_area]
                    temp_empty_count = sum(1 for t_v in temp_varaibles if not t_v)
                    if temp_empty_count == 6:
                        temp_time_1 = time.time()
                        if self.fish_finish_wait_time == -1:
                            self.fish_finish_wait_time = temp_time_1
                        if temp_time_1 - self.fish_finish_wait_time >= self.max_fish_finish_wait_time:
                            self.fish_is_success = (self.fish_progress >= 0.8)
                            self.change_state(FishingState.FINISH,temp_time_1)
                            self.fish_finish_wait_time = -1
                            self.current_roi = None
                            # print(f"钓鱼结束：{self.fish_is_success}")
                    elif temp_empty_count >= 3:
                        # lines.append("移动视角保持UI完全露出！")
                        pass
                        '''
                        if totalbar:
                            ttb_dx = (total_box[2] + total_box[0])/2 - self.screen_width/2
                            ttb_dy = (total_box[3] + total_box[1])/1 - self.screen_height/2
                            if abs(ttb_dx) <= ttb_dx/(self.screen_width/2)*0.2:
                                ttb_dx = 0
                            if abs(ttb_dy) <= ttb_dy/(self.screen_height/2)*0.2:
                                ttb_dy = 0
                            if not(ttb_dx == ttb_dy == 0):
                                self.mouse_move_onfinish_list.append([-ttb_dx,-ttb_dy])
                                # self.mouse.move_by_list([ttb_dx,ttb_dy])
                                # print(ttb_dx,ttb_dy)
                        '''
                        
                else:
                    
                    self.fish_finish_wait_time = -1
                    # --- 坐标解析（保持不变）---
                    f_box, f_conf = fish
                    target_box, target_conf = targetbar
                    total_box, total_conf = totalbar

                    fx1, fy1, fx2, fy2 = f_box
                    tx1, ty1, tx2, ty2 = target_box
                    ttx1, tty1, ttx2, tty2 = total_box
                    h_pix_tr = self.screen_height/1440
                    w_pix_tr = self.screen_width/2560
                    fx1 = fx1 * w_pix_tr
                    fy1 = fy1 * h_pix_tr
                    fx2 = fx2 * w_pix_tr
                    fy2 = fy2 * h_pix_tr
                    tx1 = tx1 * w_pix_tr
                    ty1 = ty1 * h_pix_tr
                    tx2 = tx2 * w_pix_tr
                    ty2 = ty2 * h_pix_tr
                    ttx1 = ttx1 * w_pix_tr
                    tty1 = tty1 * h_pix_tr
                    ttx2 = ttx2 * w_pix_tr
                    tty2 = tty2 * h_pix_tr

                    fish_cy = (fy1 + fy2) / 2
                    bar_cy = (ty1 + ty2) / 2
                    bar_h = ty2 - ty1
                    
                    # --- 鱼平滑（可保持快速）---
                    if self.fish_smooth_cy is None:
                        self.fish_smooth_cy = fish_cy
                    else:
                        self.fish_smooth_cy = 0.9 * fish_cy + 0.1 * self.fish_smooth_cy

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
                            self.bar_velocity = 0.9 * raw_vel + 0.1 * self.bar_velocity
                    else:
                        self.bar_velocity = 0.0
                    self.bar_prev_cy = bar_cy
                    self.bar_prev_time = now

                    # --- 鱼速度估算（新增）---
                    if self.fish_prev_cy is not None and self.fish_prev_time is not None:
                        dt_fish = now - self.fish_prev_time
                        if dt_fish > 0.001:
                            raw_fish_vel = (fish_cy - self.fish_prev_cy) / dt_fish
                            self.fish_velocity = 0.9 * raw_fish_vel + 0.1 * self.fish_velocity
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
                    if self.fish_smooth_cy < tty1+bar_h/2:
                        self.fish_smooth_cy = tty1+bar_h/2
                    elif self.fish_smooth_cy > tty2-bar_h/2:
                        self.fish_smooth_cy = tty2-bar_h/2

                    error_pixel = self.fish_smooth_cy - bar_cy
                    error_norm = error_pixel / max(bar_h, 1)

                    # --- PD + 前馈参数（建议初始值）---
                    kp = self.kp
                    kd = self.kd
                    kf = self.kf          # 鱼速度前馈系数（正数，公式中用 -kf * fish_velocity）
                    threshold = self.threshold
                    # dead_zone = self.dead_zone
                    # # 暂时不用强制区域，或阈值设大如 0.6
                    # force_threshold = self.force_threshold   # 加大避免干扰

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
                            self.mouse.hold()
                            self.mouse_down = True
                        else:
                            if self.mouse_down:
                                self.last_action_time = now
                            self.mouse.release()
                            self.mouse_down = False

                    # 8. 更新上一帧鱼位置（如果需要）
                    # self.fish_location_befor = self.fish_location_now  # 如果保留原变量用于其他用途
                    
            elif self.state == FishingState.FINISH:
                if self.fish_color is None:
                    self.fish_color = FishColor.UNKNOWN
                finish_time = state_machine_start_time
                finish_click_is_success = False
                if self.fish_is_success:
                    if  self.mouse.click():
                        finish_time_success = time.time()
                        self.finsh_catch_click_time = finish_time_success
                        self.last_fish_success_time = finish_time_success
                        self.change_state(FishingState.CAST,finish_time_success)
                        self.fish_success_count += 1
                        finish_click_is_success = True
                        self.statistics['fish_Statistics'][self.fish_color]['success'] += 1
                else:
                    self.change_state(FishingState.CAST,finish_time)
                    self.fish_fail_count += 1
                    finish_click_is_success = True
                    self.statistics['fish_Statistics'][self.fish_color]['fail'] += 1
                if finish_click_is_success:    
                    if self.mouse_move_onfinish_list:
                        # self.mouse.move_by_list(self.mouse_move_onfinish_list)
                        # self.mouse_move_onfinish_list = []
                        pass
                else:
                    pass

            elif self.state == FishingState.FORG:
                self.state = FishingState.CAST
            elif self.state == FishingState.SELL:
                self.state = FishingState.CAST
            
            
            elif self.state == FishingState.ERROR:
                self.change_state(FishingState.CAST,state_machine_start_time)
                print("State ERROR")


            tmp_end_time = time.time()
            # 统计数据
            frame_count += 1
            if frame is None:
                # print(f"frame {frame_count} is none")
                pass
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
      
            ttt =  tmp_end_time - self._run_start_time 
            self.total_runtime_this = ttt
            # lines.append(f"截图平均帧: {fps_grab:.2f}")
            # lines.append(f"检测平均帧: {fps_dete:.2f}")
            lines.append(f"脚本帧数: {fps_run:.2f}, {self.detector.get_model_running_device()}模式")
            lines.append(f"运行时间: {self.format_time(ttt+self.accumulated_run_time)}")
            lines.append(f"距离上次成功钓鱼:{self.format_time(tmp_end_time - self.last_fish_success_time if self.last_fish_success_time>0 else 0)}")  
            lines.append("\t")
            lines.append(f"{FishColor.BLACK}: 成功:{self.statistics['fish_Statistics'][FishColor.BLACK]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.BLACK]['fail']}")
            lines.append(f"{FishColor.BROWN}: 成功:{self.statistics['fish_Statistics'][FishColor.BROWN]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.BROWN]['fail']}")
            lines.append(f"{FishColor.WHITE}: 成功:{self.statistics['fish_Statistics'][FishColor.WHITE]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.WHITE]['fail']}")
            lines.append(f"{FishColor.GREEN}: 成功:{self.statistics['fish_Statistics'][FishColor.GREEN]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.GREEN]['fail']}")
            lines.append(f"{FishColor.BLUE}: 成功:{self.statistics['fish_Statistics'][FishColor.BLUE]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.BLUE]['fail']}")
            lines.append(f"{FishColor.PURPLE}: 成功:{self.statistics['fish_Statistics'][FishColor.PURPLE]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.PURPLE]['fail']}")
            lines.append(f"{FishColor.GOLDEN}: 成功:{self.statistics['fish_Statistics'][FishColor.GOLDEN]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.GOLDEN]['fail']}")
            lines.append(f"{FishColor.RED}: 成功:{self.statistics['fish_Statistics'][FishColor.RED]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.RED]['fail']}")
            lines.append(f"{FishColor.MAGENTA}: 成功:{self.statistics['fish_Statistics'][FishColor.MAGENTA]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.MAGENTA]['fail']}")
            lines.append(f"{FishColor.COLOURS}: 成功:{self.statistics['fish_Statistics'][FishColor.COLOURS]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.COLOURS]['fail']}")
            lines.append(f"{FishColor.UNKNOWN}: 成功:{self.statistics['fish_Statistics'][FishColor.UNKNOWN]['success']}, 失败:{self.statistics['fish_Statistics'][FishColor.UNKNOWN]['fail']}")
            lines.append(f"累计: 成功:{self.fish_success_count} 失败:{self.fish_fail_count} ")
            # print(ttt,self.accumulated_run_time)
            self.overlay.update(lines)
        
        self.statistics['total_run_time'] = self.accumulated_run_time + self.total_runtime_this
        self.statistics['successful_catches'] = self.fish_success_count
        self.statistics['fail_catches'] = self.fish_fail_count
        self.save_statistics(self.statistics)

    def update_fish_color(self, roi, box):
        """
        更新鱼的颜色采样。当收集到5个样本后，根据一致性确定颜色。
        应在每帧检测到鱼时调用。
        :param roi: 当前检测用的图像区域（BGR numpy数组）。若为None，则尝试截取全屏。
        :param box: 鱼的边界框 (x1, y1, x2, y2) 相对于 roi
        """
        # 颜色已确定则直接返回
        if self.fish_color:
            return

        now = time.time()

        # 如果 roi 为 None，尝试截屏
        if roi is None:
            if hasattr(self, '_capture_screen'):
                roi = self._capture_screen()  # 需自行实现，返回BGR numpy数组
            else:
                # print("警告：roi 为 None 且未定义 _capture_screen 方法，无法获取图像")
                return

        # 确保 roi 是有效的 numpy 图像数组
        if not isinstance(roi, np.ndarray) or roi.size == 0:
            # print("错误：roi 不是有效的图像数组")
            return

        # 采样条件：未满5个，且距离上次采样至少0.555秒
        if len(self.frame_fish_color) < 30 and (now - self.last_color_time) >= 0.0543:
            hsv = self._extract_fish_hsv(roi, box)
            if hsv is not None:
                color = self._hsv_to_color(hsv)
                # 可选：过滤掉未知颜色，避免样本污染
                if color != FishColor.UNKNOWN:
                    self.frame_fish_color.append(color)
            self.last_color_time = now  # 无论提取成功与否，都更新采样时间

        # 如果样本数达到5，进行一致性判断
        if len(self.frame_fish_color) == 30:
            counter = Counter(self.frame_fish_color)
            most_color,count = counter.most_common(1)[0]
            if count >=20:
                self.fish_color = most_color
            elif count <= 10 and len(set(self.frame_fish_color))>=5:
                self.fish_color = FishColor.COLOURS
            else:
                self.fish_color = FishColor.UNKNOWN
            self.fish_color_determined = True
            self.frame_fish_color.clear()  # 清空样本，释放内存

    def _extract_fish_hsv(self, roi, box, shrink_ratio=0.8):
        """
        从鱼的边界框中提取中心区域的HSV均值
        :param roi: BGR图像 (numpy数组)
        :param box: 边界框 (x1, y1, x2, y2)
        :param shrink_ratio: 中心区域收缩比例 (0~1)
        :return: (h, s, v) 均值元组，若无效则返回None
        """
        x1, y1, x2, y2 = map(int, box)
        h, w = roi.shape[:2]  # 正确获取图像高度和宽度

        # 确保边界框在图像范围内
        x1 = max(0, min(x1, w-1))
        y1 = max(0, min(y1, h-1))
        x2 = max(x1+1, min(x2, w))
        y2 = max(y1+1, min(y2, h))

        width = x2 - x1
        height = y2 - y1
        if width <= 2 or height <= 2:   # 区域太小，无法提取有效颜色
            return None

        # 计算中心缩小区域
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
        # print(cy1,cx1)
        # print(cy2,cx2)
        # print("------")
        # 提取中心ROI
        center_roi = roi[cy1:cy2, cx1:cx2]
        if center_roi.size == 0:
            return None

        # BGR -> HSV
        hsv = cv2.cvtColor(center_roi, cv2.COLOR_BGR2HSV)

        # 展平
        h = hsv[:,:,0].flatten()
        s = hsv[:,:,1].flatten()
        v = hsv[:,:,2].flatten()

        # 过滤黑色和白色像素
        mask = (v > 40) & (s > 30)

        h = h[mask]
        s = s[mask]
        v = v[mask]

        if len(h) == 0:
            return None

        # 统计 H 的直方图
        hist = np.bincount(h, minlength=180)

        # 找出现最多的色相
        main_h = np.argmax(hist)

        # S V 还是用平均
        mean_s = np.mean(s)
        mean_v = np.mean(v)

        return (main_h, mean_s, mean_v)

    def _hsv_to_color(self, hsv):

        h, s, v = hsv
        # print(h,s,v)

        # 黑色     
        if 80<h<120 and 70<s<100 and 70<v<100:
            return FishColor.BLACK

        # 白色
        if (110<h<140 and 70<s<90 and 90<v<110) or (0<h<20 and 65<s<85 and 145<v<165):
            return FishColor.WHITE
        
        # 红色
        if h<10 or h>175:
            return FishColor.RED

        # 棕色
        if 0<h<20 and 120<s<140 and 100<v<120:
            return FishColor.BROWN
            
        # 金色偏黄
        if 22 < h <= 32:
            return FishColor.GOLDEN

        # 绿色
        if 40<h<60:
            return FishColor.GREEN

        # 蓝色
        if 105<h<125:
            return FishColor.BLUE

        # 紫色
        if 130<h<150:
            return FishColor.PURPLE

        # 品红
        if 160 < h <= 170:
            return FishColor.MAGENTA

        return FishColor.UNKNOWN

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def change_state(self, new_state,_time=None):
        # if self.forg_countdown:
        if self.state == FishingState.FINISH and new_state == FishingState.CAST and self.forg_countdown <= 0:
            self.state = FishingState.FORG
        elif self.state == FishingState.FINISH and new_state == FishingState.CAST and self.sell_countdown <= 0:
            self.state = FishingState.SELL
        else:
            self.state = new_state
        if _time:
            self.state_start_time = _time
        else:
            self.state_start_time = time.time()

    def stop(self):
        self.mouse.release()
        self.full_grabber.release()
    
    def set_mouse_enable(self,is_enbale):
        self.set_mouse_enable = is_enbale

    def set_mouse_move(self,move_list=None):
        self.mouse_move_list  = move_list

    def save_statistics(self,statistics, path="./src/statistics.json"):
        print(1)
        with open(path, "w", encoding="utf-8") as f:
            print(2)
            json.dump(statistics, f, ensure_ascii=False, indent=2)
            print('json write success')

    def load_statistics(self,path="./src/statistics.json"):
        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as f:
            print('json open success')
            self.statistics = json.load(f)


