import win32api
import win32con
import win32gui
import win32ui
import ctypes
import threading
import config
import os
from ctypes import windll

FR_PRIVATE = 0x10


class Overlay:

    def __init__(self):
        self.hwnd = None
        self.running = False
        self.text_lines = ["等待启动...",
                f"双击 {config.HOTKEY_START} 开始/停止",
                f"双击 {config.HOTKEY_STOP} 退出程序"]
        self._lock = threading.Lock()
        self.hFont = None
        self.font_loaded = False

    # ===============================
    # 对外接口
    # ===============================

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False

        if self.hwnd and win32gui.IsWindow(self.hwnd):
            win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)

        if self.font_loaded:
            windll.gdi32.RemoveFontResourceExW(
                config.FONTPATH, FR_PRIVATE, 0
            )
        if self.hFont:
            win32gui.DeleteObject(self.hFont)

    def update(self, lines):
        if not self.running:   # 窗口已销毁，直接返回
            return
        with self._lock:
            self.text_lines = lines.copy()

        if self.hwnd:
            win32gui.InvalidateRect(self.hwnd, None, False)

    # ===============================
    # 字体加载
    # ===============================

    def load_font_from_file(self, font_path):
        if not os.path.exists(font_path):
            print("字体文件不存在:", font_path)
            return None

        if not windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0):
            print("字体加载失败")
            return None

        self.font_loaded = True

        # 默认使用文件名作为字体名
        font_name = os.path.splitext(os.path.basename(font_path))[0]
        print("字体加载成功:", font_name)
        return font_name

    # ===============================
    # 主线程
    # ===============================

    def _run(self):

        hInstance = win32api.GetModuleHandle()
        className = "OverlayWindow"

        wndClass = win32gui.WNDCLASS()
        wndClass.lpfnWndProc = self.wndProc
        wndClass.hInstance = hInstance
        wndClass.lpszClassName = className
        wndClass.hbrBackground = 0

        try:
            win32gui.RegisterClass(wndClass)
        except:
            pass

        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        exStyle = (
            win32con.WS_EX_LAYERED |
            win32con.WS_EX_TRANSPARENT |
            win32con.WS_EX_TOPMOST |
            win32con.WS_EX_NOACTIVATE
        )

        style = win32con.WS_POPUP

        self.hwnd = win32gui.CreateWindowEx(
            exStyle,
            className,
            None,
            style,
            0,
            0,
            screen_w,
            screen_h,
            None,
            None,
            hInstance,
            None
        )

        # 黑色作为透明色
        win32gui.SetLayeredWindowAttributes(
            self.hwnd,
            win32api.RGB(0, 0, 0),
            0,
            win32con.LWA_COLORKEY
        )

        # ===== 加载字体 =====
        font_name = self.load_font_from_file(config.FONTPATH)

        lf = win32gui.LOGFONT()
        lf.lfHeight = -20
        lf.lfWeight = win32con.FW_NORMAL
        lf.lfFaceName = font_name if font_name else "Arial"

        self.hFont = win32gui.CreateFontIndirect(lf)

        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        win32gui.UpdateWindow(self.hwnd)

        win32gui.PumpMessages()

    # ===============================
    # 绘制（双缓冲）
    # ===============================

    def wndProc(self, hwnd, msg, wParam, lParam):

        if msg == win32con.WM_PAINT:

            hdc, ps = win32gui.BeginPaint(hwnd)
            rect = win32gui.GetClientRect(hwnd)

            width = rect[2]
            height = rect[3]

            # ===== 创建内存 DC（双缓冲）=====
            memdc = win32gui.CreateCompatibleDC(hdc)
            bmp = win32gui.CreateCompatibleBitmap(hdc, width, height)
            win32gui.SelectObject(memdc, bmp)

            # 填充黑色背景（透明）
            brush = win32gui.GetStockObject(win32con.BLACK_BRUSH)
            win32gui.FillRect(memdc, rect, brush)

            # 设置文字样式
            win32gui.SetTextColor(memdc, win32api.RGB(0, 255, 0))
            win32gui.SetBkMode(memdc, win32con.TRANSPARENT)

            if self.hFont:
                win32gui.SelectObject(memdc, self.hFont)

            # 复制文本数据
            with self._lock:
                lines = self.text_lines.copy()

            y = 10
            for line in lines:
                win32gui.DrawText(
                    memdc,
                    line,
                    -1,
                    (10, y, width - 10, y + 30),
                    win32con.DT_LEFT
                )
                y += 24

            # ===== 一次性拷贝到屏幕 =====
            win32gui.BitBlt(
                hdc,
                0,
                0,
                width,
                height,
                memdc,
                0,
                0,
                win32con.SRCCOPY
            )

            win32gui.DeleteObject(bmp)
            win32gui.DeleteDC(memdc)

            win32gui.EndPaint(hwnd, ps)
            return 0

        if msg == win32con.WM_DESTROY:
            self.running = False
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wParam, lParam)