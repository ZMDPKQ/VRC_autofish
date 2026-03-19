# main.py
import torch
from logging.handlers import RotatingFileHandler
import re
import threading
import time
import sys
import os
from utils.hotkey import HotkeyManager
import config
import tkinter as tk
import logging
import dxcam
from utils.screenshot import ScreenGrabber
from ui.overlay_win32 import Overlay
from ui.settings import SettingsTk

from detection.yolo_detector import YOLODetector
from core.fisher import Fisher
# from utils.re_ui import 


torch.backends.cudnn.benchmark = True
    


# print("Start module load:", time.time())

# 配置根日志记录器
logging.basicConfig(
    level=logging.INFO,                # 全局日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',  # 日志格式
    datefmt='%Y-%m-%d %H:%M:%S',        # 时间格式
    handlers=[
        # logging.StreamHandler(),         # 输出到控制台
        # logging.FileHandler('QwQ.log') # 可选：输出到文件
        RotatingFileHandler('QwQ.log', maxBytes=1024*1024*20, backupCount=3)
    ],
    encoding='gbk'
)


logger = logging.getLogger('main') 

def handle_exception(exc_type, exc_value, exc_traceback):
    logger.error(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )

sys.excepthook = handle_exception


# print("# 检查模型文件前:", time.time())
# 检查模型文件
if not os.path.exists(config.MODEL_PATH):
    logger.error(f"错误：模型文件不存在 {config.MODEL_PATH}")
    sys.exit(1)
else:
    logger.info(f"模型文件已找到: {config.MODEL_PATH}")
    pass

start_fishing_state = False
pause_fishing_state = False


# 全局事件
stop_event = threading.Event()
fisher_thread = None
debug_thread = None
exit_event = threading.Event()


# 初始化各模块
grabber = ScreenGrabber()
detector = YOLODetector()
overlay = Overlay()
settings_ui = None
hm = HotkeyManager(start_key=config.HOTKEY_START, stop_key=config.HOTKEY_STOP,pause_key=config.HOTKEY_PAUSE)

def detect_active_dxcam_device():
        try:
            outputs = dxcam.output_info()
        except Exception as e:
            logger.error(f"detect_active_dxcam_device(): dxcam.output_info() raised exception: {e}", exc_info=True)
            logger.warning("detect_active_dxcam_device(): fallback to default (0, 0)")
            return 0, 0

        logger.info(f"detect_active_dxcam_device(): raw dxcam outputs:\n{outputs}")
        pattern = re.compile(r'Device\[(\d+)\]\s+Output\[(\d+)\]:.*?Primary:(True|False)')

        results = ()
        for line in outputs.splitlines():
            line = line.strip()
            if not line:
                continue
            logger.info(f"detect_active_dxcam_device(): parsing line: {line}")
            match = pattern.search(line)
            if match:
                device = int(match.group(1))
                output = int(match.group(2))
                primary = match.group(3) == 'True'
                logger.info(f"detect_active_dxcam_device(): parsed device={device}, output={output}, primary={primary}")
                if primary:
                    results = (device, output)
                    logger.info(f"detect_active_dxcam_device(): found primary output -> device={device}, output={output}")
        if not results:
            logger.warning("detect_active_dxcam_device(): no primary output found in dxcam.output_info(), fallback to (0, 0)")
            return 0, 0
        logger.info(f"detect_active_dxcam_device(): final result={results}")
        return results

def debug_loop():
    global  exit_event
    overlay.start()

def start_debug():
    global debug_thread
    if debug_thread and debug_thread.is_alive():
        print("调试窗口已经打开了！")
        pass
    debug_thread = threading.Thread(target=debug_loop)
    debug_thread.start()
    # print("调试窗口已打开")

def stop_debug():
    global exit_event
    exit_event.set()

def fisher_thread_entry():
    global stop_event
    logger.info("fisher_thread_entry() called, starting Fisher.run() in worker thread")
    try:
        fisher.run(stop_event)
        logger.info("fisher_thread_entry() Fisher.run() returned normally")
    except Exception as e:
        logger.error(f"fisher_thread_entry() Fisher.run() raised exception: {e}", exc_info=True)
    
def start_fishing():
    global fisher_thread, stop_event,fisher
    logger.info("start_fishing() called (request to start fishing loop)")
    if fisher_thread and fisher_thread.is_alive():
        logger.info("start_fishing(): existing fisher_thread is alive, requesting stop and join")
        stop_event.set()
        fisher_thread.join(timeout=1)
    stop_event.clear()
    logger.info("start_fishing(): creating new fisher_thread")
    fisher_thread = threading.Thread(target=fisher_thread_entry)
    fisher_thread.start()
    logger.info("start_fishing(): fisher_thread started")

def stop_fishing():
    global fisher
    logger.info("stop_fishing() called, signalling stop_event and calling fisher.stop()")
    stop_event.set()
    try:
        fisher.stop()
    except Exception as e:
        logger.error(f"stop_fishing(): fisher.stop() raised exception: {e}", exc_info=True)

def start_fishing_state_change():
    global start_fishing_state,settings_ui
    if not start_fishing_state:
        logger.info("start_fishing_state_change(): switching to START state, will call start_fishing()")
        start_fishing_state = True
        start_fishing()
    else:
        logger.info("start_fishing_state_change(): switching to STOP state, will call stop_fishing()")
        start_fishing_state = False
        stop_fishing()
        # 这里只能通知主线程显示窗口，不能在热键线程里直接 mainloop
        # settings_ui.show()
        edit_config()

def pause_fishing_state_change():
    global pause_fishing_state,fisher
    if pause_fishing_state:
        # 停止控制鼠标
        # print("停止控制鼠标")
        pause_fishing_state = False
    else:
        # 控制鼠标
        # print("继续控制鼠标")
        pause_fishing_state = True
    fisher.set_mouse_enable(pause_fishing_state)

def edit_config():
    # 配置文件路径（与脚本同级）
    config_path = os.path.join(os.path.dirname(sys.argv[0]), 'config.py')
    vars_list = [
        ('TIME_FORG_HARVEST','收青蛙间隔: 小时每次'),
        ('MAX_WAIT_EXCLAMATIONE_TIME','抛竿后等待感叹号出现的时间: 秒'),
        ('ROI_ENABLE_THRESHOLD_FRAME','启用ROI的最低帧数: 帧'),
        ('CAST_LR_PIX','抛竿摆头幅度:  像素'),
        ('CAST_LR_MOVE','抛竿移动时间: 秒')

        ]
    
    # 读取文件并提取当前值
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    values = {}
    for line in lines:
        for var,_ in vars_list:
            if line.strip().startswith(var):
                parts = line.split('=', 1)
                if len(parts) > 1:
                    after_eq = parts[1]
                    if '#' in after_eq:
                        val = after_eq.split('#')[0].strip()
                    else:
                        val = after_eq.strip()
                    values[var] = val
    
    # 创建窗口
    root = tk.Tk()
    root.title("QwQ参数修改")
    root.attributes('-topmost', True)   # 使窗口置顶
    root.lift()                         # 提升到最前
    root.focus_force()                  # 强制获得焦点
    entries = {}
    
    for i, (var,prd_text) in enumerate(vars_list):
        tk.Label(root, text=prd_text).grid(row=i, column=0, sticky='w')
        entry = tk.Entry(root)
        entry.insert(0, values.get(var, ''))
        entry.grid(row=i, column=1)
        entries[var] = entry
    
    def save():
        new_lines = []
        for line in lines:
            for (var,_) in vars_list:
                if line.strip().startswith(var):
                    # 重建该行：保留等号前的部分和注释，仅替换值
                    before_eq = line.split('=', 1)[0] + '='
                    after_eq = line.split('=', 1)[1]
                    if '#' in after_eq:
                        after_val, comment = after_eq.split('#', 1)
                        comment = '\t\t\t'+'#' + comment
                    else:
                        after_val = after_eq
                        comment = ''
                    new_val = entries[var].get().strip()
                    line = f"{before_eq} {new_val} {comment}\n"
                    break
            new_lines.append(line)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        root.destroy()
    
    # 按钮
    tk.Button(root, text="保存", command=save).grid(row=len(vars_list), column=0)
    tk.Button(root, text="取消", command=root.destroy).grid(row=len(vars_list), column=1)
    
    root.mainloop()

def timing_start():
    now = time.time()
    timeing_start= config.TIMING_START
    timeing_start_time = config.TIMING_START_TIME
    lines = []
    if timeing_start:
        if timeing_start_time>0:
            tar_time = now + float(timeing_start_time)*3600
            while True:
                if now < tar_time:
                    lines.append(f'还剩{(tar_time - now):.1f}秒启动')
                else:
                    break




    
if __name__ == "__main__":
    print('main')
    t0 = time.time()
    # global fisher,hm,exit_event,stop_event,fisher_thread,debug_thread,overlay
    device_idx,output_idx = detect_active_dxcam_device()
    try:
        logger.info("dxcam实例成功")
        dxcam_camera = dxcam.create(device_idx=device_idx,output_idx=output_idx,output_color='BGR')
    except Exception as e:
        logger.error(f"dxcam实例失败: {e}", exc_info=True)
        logger.warning("DXCAM 在此设备上不可用，本会话将全程使用 MSS 截图")
    fisher = Fisher(overlay=overlay,dxcam_camera=dxcam_camera)
    # settings_ui = SettingsTk()
    
    # print(f"1:{t0:.2f}s")
    start_debug()
    # print(f"2:{time.time()-t0:.2f}s")
    # 如果需要ROI，可在此调用选择函数（略）
    hm.on_start = start_fishing_state_change
    # hm.on_pause = pause_fishing_state_change
    hm.on_stop = stop_debug
    hm.start_listening()
    # print(f"3:{time.time()-t0:.2f}s")
    
    try:
        # 保持主线程运行
        while not exit_event.is_set():
            # 在主线程中处理设置窗口的 GUI 队列，避免在热键线程里直接操作 Tk
            # if settings_ui is not None:
            #     try:
            #         # settings_ui.force_process_queue()
            #         # 让 Tk 处理重绘/事件，这里不用 mainloop 也能正常刷新
            #         # settings_ui.root.update_idletasks()
            #         # settings_ui.root.update()
            #     except Exception:
            #         pass
            time.sleep(0.1)
        stop_event.set()
        if fisher_thread and fisher_thread.is_alive():
            fisher_thread.join(timeout=1)    # 等待最多1秒，避免卡死
        if debug_thread and debug_thread.is_alive():
            debug_thread.join(timeout=1)      
        if overlay:
            overlay.stop()
        hm.stop_listening()
        sys.exit(0)
    except KeyboardInterrupt:
        stop_debug()
        # print("退出")
        sys.exit(0)
