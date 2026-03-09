# config.py
import os
import sys

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 路径配置
BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'best.pt')
ROI_MODEL_PATH = os.path.join(BASE_DIR,'models', 'ROI.pt')

# 检测阈值
CONFIDENCE_THRESHOLD = 0.6
PROGRESS_GREEN_LOWER = (40, 40, 40)   # HSV
PROGRESS_GREEN_UPPER = (80, 255, 255)

# 进度条判定阈值
PROGRESS_SUCCESS = 0.95
PROGRESS_FAIL = 0.05

# 鼠标控制
MOUSE_BUTTON = 'left'        # 左键

# 热键设置
HOTKEY_START = 'f1'   
HOTKEY_PAUSE = 'f2'   
HOTKEY_STOP = 'f3'    

# 运行参数
FPS = 30
MAX_NO_GAME_FRAMES = 60       # 连续无游戏区域帧数上限
USE_ROI = False               # 是否使用手动ROI


# 类别ID（与训练时一致）
CLASS_NAMES = ["exclamation", "totalbar", "targetbar", "fish",
               "progressbar", "progressbar_indicator", "game_area"]

# 字体
FONTPATH = 'src\\assets\\fonts\\ShangShouYingFengShouXieTi-2.ttf'

RECAST_WAIT_TIME           = 2      # 重新抛竿间隔时间
MAX_WAIT_EXCLAMATIONE_TIME = 20.0   # 等待感叹号最大时间（秒）
MAX_WAIT_EXCLAMATION_COUNT = 3      # 最大等待抛竿后没有等到感叹号并且没出现游戏区域次数
MAX_WAIT_GAME_APPEARA_TIME = 1.233  # 最大等出现感叹号点击后或等待感叹号超时后待游戏出现时间
MAX_FISH_FINISH_WAIT_TIME  = 1.888  # 最大游戏界面消失判断结束时间
MAX_TARGETBAR_FALL_TIME    = 2.5    # 最大目标条下坠时间
MAX_MOUSE_HOLD_TIME        = 1.5    # 最大鼠标长按时间
MIN_MOUSE_INTERVAL         = 0.0125  # 最小鼠标点击间隔
KP_FISH_TARGET             = 0.1    # 比例系数
INTERVAL_IN_CLICK          = 0.05   # 鼠标点击时按下到松开的间隔时间

FISH_PID_CONTROL_KP = 0.325 # 比例增益（影响按住力度）
FISH_PID_CONTROL_KD = 0.08 # 微分增益（速度阻尼）
FISH_PID_CONTROL_KF = 0.00038 # 鱼速度前馈
FISH_PID_CONTROL_MAX_KD = 0.20 # 速度项限幅
FISH_PID_CONTROL_THRESHOLD = 0.082 # 按住阈值（目标力大于此则按）
FISH_PID_CONTROL_DEAD_ZONE = 0.015 # 误差死区
FISH_PID_CONTROL_FORCE_THRESHOLD = 0.10 # 强制区域阈值（误差超过此值直接强制动作）
FISH_PID_CONTROL_MIN_SWITCH_INTERVAL = 0.01 # 最小切换间隔（秒

TIMING_START = False
TIMING_START_TIME = 0   # 小时
TIMING_STOP = False
TIMING_START_TIME = 0   # 小时

TIME_FORG_HARVEST = 1   # 青蛙频率