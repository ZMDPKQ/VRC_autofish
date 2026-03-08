# main.py
import threading
import time
import sys
import os
from utils.hotkey import HotkeyManager
from core.fisher import Fisher
import config
import tkinter as tk
import re

from utils.screenshot import ScreenGrabber
from detection.yolo_detector import YOLODetector
from ui.overlay_win32 import Overlay

import torch
torch.backends.cudnn.benchmark = True


# 检查模型文件
if not os.path.exists(config.MODEL_PATH):
    print(f"错误：模型文件不存在 {config.MODEL_PATH}")
    print("请将训练好的 best.pt 放入 models/ 文件夹")
    sys.exit(1)
else:
    print(f"模型文件已找到: {config.MODEL_PATH}")

start_fishing_state = False
pause_fishing_state = False


# 全局事件
stop_event = threading.Event()
fisher_thread = None
debug_thread = None
exit_event = threading.Event()


# 初始化各模块
print("初始化截图模块...")
grabber = ScreenGrabber()  # 全屏截图

print("初始化YOLO检测器...")
detector = YOLODetector()

print("初始化覆盖层...")
overlay = Overlay()

fisher = Fisher(roi=None,overlay=overlay)  # 如需要ROI，可先选择

hm = HotkeyManager(start_key=config.HOTKEY_START, stop_key=config.HOTKEY_STOP,pause_key=config.HOTKEY_PAUSE)

def debug_loop():
    overlay.start()


def start_debug():
    global debug_thread
    if debug_thread and debug_thread.is_alive():
        print("调试窗口已经打开了！")
        pass
    debug_thread = threading.Thread(target=debug_loop)
    debug_thread.start()
    print("调试窗口已打开")

def stop_debug():
    global exit_event
    exit_event.set()

def start_fishing():
    global fisher_thread, stop_event,fisher
    if fisher_thread and fisher_thread.is_alive():
        stop_event.set()
        fisher_thread.join()
    stop_event.clear()
    # 创建Fisher实例（可根据config.USE_ROI决定是否传入roi）
    fisher_thread = threading.Thread(target=fisher.run, args=(stop_event,))
    fisher_thread.start()

def stop_fishing():
    global fisher
    stop_event.set()
    fisher.stop()

def start_fishing_state_change():
    global start_fishing_state
    if not start_fishing_state:
        print("开始检测并自动钓鱼")
        start_fishing_state = True
        start_fishing()
    else:
        print("暂停中")
        start_fishing_state = False
        stop_fishing()
        # edit_config()


def pause_fishing_state_change():
    global pause_fishing_state,fisher
    if pause_fishing_state:
        # 停止控制鼠标
        print("停止控制鼠标")
        pause_fishing_state = False
    else:
        # 控制鼠标
        print("继续控制鼠标")
        pause_fishing_state = True
    fisher.set_mouse_enable(pause_fishing_state)


def edit_config():
    # 配置文件路径（与脚本同级）
    config_path = os.path.join(os.path.dirname(sys.argv[0]), 'config.py')
    vars_list = ['FISH_PID_CONTROL_KP',
        'FISH_PID_CONTROL_KD',
        'FISH_PID_CONTROL_KF',
        'FISH_PID_CONTROL_MAX_KD',
        'FISH_PID_CONTROL_THRESHOLD',
        'FISH_PID_CONTROL_DEAD_ZONE',
        'FISH_PID_CONTROL_FORCE_THRESHOLD',
        'FISH_PID_CONTROL_MIN_SWITCH_INTERVAL']
    
    # 读取文件并提取当前值
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    values = {}
    for line in lines:
        for var in vars_list:
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
    root.title("修改配置")
    entries = {}
    
    for i, var in enumerate(vars_list):
        tk.Label(root, text=var).grid(row=i, column=0)
        entry = tk.Entry(root)
        entry.insert(0, values.get(var, ''))
        entry.grid(row=i, column=1)
        entries[var] = entry
    
    def save():
        new_lines = []
        for line in lines:
            for var in vars_list:
                if line.strip().startswith(var):
                    # 重建该行：保留等号前的部分和注释，仅替换值
                    before_eq = line.split('=', 1)[0] + '='
                    after_eq = line.split('=', 1)[1]
                    if '#' in after_eq:
                        after_val, comment = after_eq.split('#', 1)
                        comment = '#' + comment
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
    tk.Button(root, text="保存", command=save).grid(row=len(vars_list), column=0, columnspan=2)
    tk.Button(root, text="取消", command=root.destroy).grid(row=len(vars_list)+1, column=0, columnspan=2)
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
    start_debug()
    # 如果需要ROI，可在此调用选择函数（略）
    hm.on_start = start_fishing_state_change
    # hm.on_pause = pause_fishing_state_change
    hm.on_stop = stop_debug
    hm.start_listening()
    try:
        # 保持主线程运行
        while not exit_event.is_set():
            time.sleep(0.1)
        stop_event.set()
        if fisher_thread and fisher_thread.is_alive():
            print("fisher_thread")
            fisher_thread.join(timeout=1)    # 等待最多1秒，避免卡死
        if debug_thread and debug_thread.is_alive():
            print("debug_thread")
            debug_thread.join(timeout=1)      
        if overlay:
            print("overlay")
            overlay.stop()
        hm.stop_listening()
        sys.exit(0)
    except KeyboardInterrupt:
        stop_debug()
        print("退出")
        sys.exit(0)