# utils/hotkey.py
import time
import keyboard
import logging

logger = logging.getLogger('hotkey') 

class HotkeyManager:
    def __init__(self, start_key='f1', pause_key='f2',stop_key='f3'):
        self.start_key = start_key
        self.pause_key = pause_key
        self.stop_key = stop_key
        self.last_press_start = 0
        self.last_press_stop = 0
        self.press_count_start = 0
        self.press_count_stop = 0
        self.on_start = None
        self.on_stop = None

    def start_listening(self):
        keyboard.hook(self._on_event)
    
    def stop_listening(self):
        print("stop_listening")
        keyboard.unhook_all()

    def _on_event(self, event):
        # 只在按键抬起时触发逻辑
        if event.event_type != 'up':
            return

        # 有些机器上 event.name 可能是 None 或奇怪的名字，先打印出来方便排查
        try:
            key_name = str(event.name)
        except Exception:
            key_name = repr(event.name)
        # print(f"[HotkeyManager] key up: raw_name={key_name}")

        if key_name == self.start_key:
            now = time.time()
            # print(f"[HotkeyManager] detected start_key={self.start_key}, now={now}")
            if now - self.last_press_start < 1.0:
                self.press_count_start += 1
            else:
                self.press_count_start = 1
            self.last_press_start = now
            # print(f"[HotkeyManager] press_count_start={self.press_count_start}")
            if self.press_count_start == 2:
                logger.info('触发开始/暂停键')
                # print("[HotkeyManager] start_key double-pressed, invoking on_start()")
                if self.on_start:
                    self.on_start()
                self.press_count_start = 0
        elif key_name == self.stop_key:
            now_stop = time.time()
            # print(f"[HotkeyManager] detected stop_key={self.stop_key}, now={now_stop}")
            if now_stop - self.last_press_stop < 1.0:
                self.press_count_stop += 1
            else:
                self.press_count_stop = 1
            self.last_press_stop = now_stop
            # print(f"[HotkeyManager] press_count_stop={self.press_count_stop}")
            if self.press_count_stop == 2:
                # print("[HotkeyManager] stop_key double-pressed, invoking on_stop()")
                logger.info('触发退出键')
                if self.on_stop:
                    self.on_stop()

                self.press_count_stop = 0