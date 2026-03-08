# utils/hotkey.py
import time
import keyboard

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
        if event.event_type != 'up':
            return
        # print(self.start_key,event.name,type(self.start_key),type(event.name))
        if event.name == self.start_key:
            # print(event.name)
            now = time.time()
            if now - self.last_press_start < 1.0:
                self.press_count_start += 1
            else:
                self.press_count_start = 1
            self.last_press_start = now
            if self.press_count_start == 2:
                if self.on_start:
                    self.on_start()
                self.press_count_start = 0
        elif event.name == self.stop_key:
            now_stop = time.time()
            if now_stop - self.last_press_stop < 1.0:
                self.press_count_stop += 1
            else:
                self.press_count_stop = 1
            self.last_press_stop = now_stop
            if self.press_count_stop == 2:
                if self.on_stop:
                    print("on_stop()")
                    self.on_stop()
                    
                self.press_count_stop = 0