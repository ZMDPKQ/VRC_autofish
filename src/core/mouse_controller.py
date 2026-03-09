import win32api
import win32con
import time
import config

class MouseController:
    def __init__(self):
        self.is_down = False
        self.last_click_time = 0
        self.min_interval = config.MIN_MOUSE_INTERVAL
        self.is_enable = True
        self.interval_in_click = config.INTERVAL_IN_CLICK

    def hold(self):
        if not self.is_enable:
            return False
        if time.time() - self.last_click_time < self.min_interval :
            return False
        
        if not self.is_down:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
            self.is_down = True
            self.last_click = time.time()
            # print("hold(self)",time.time())

    def release(self):
        # if not self.is_enable:
        #     return False
        if time.time() - self.last_click_time < (self.min_interval/2):
            return False
        
        if self.is_down:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
            self.is_down = False
            self.last_click = time.time()
            # print("release(self)",time.time())

    def click(self):
        if not self.is_enable:
            return False
        if time.time() - self.last_click_time < self.min_interval:
            return False
        # print("点击鼠标")
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        time.sleep(self.interval_in_click)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        self.last_click = time.time()
        return True

    def enable(self,is_enable):
        self.is_enable = is_enable
        return is_enable
       

    def move_relative_smooth(self,dx, dy, steps=20, delay=0.01):
        """
        dx, dy: 总移动距离
        steps: 分多少步完成
        delay: 每步间隔时间（越大越慢）
        """
        if not self.is_enable:
            return False
        step_x = dx / steps
        step_y = dy / steps

        for _ in range(steps):
            win32api.mouse_event(
                win32con.MOUSEEVENTF_MOVE,
                int(step_x),
                int(step_y),
                0,
                0
            )
            time.sleep(delay)
        return True
    
    def move_LR(self):
        self.move_relative_smooth(-16, 0, steps=16, delay=0.01)
        self.move_relative_smooth(16, 0, steps=16, delay=0.01)
    
    def move_by_list(self,move_list):
        if move_list:
            self.move_relative_smooth(move_list[0],move_list[1])