import keyboard
import time
import config

class KeyController:
    def __init__(self):
        self.interval_in_press = config.INTERVAL_IN_PRESS
        self.is_enable = True
    
    def perss_key(self,key,press_time=None):
        '''
        :param key: 'Speace'  not None
        '''
        if key is not None:
            keyboard.press(key)
            if press_time is None:
                press_time = self.interval_in_press
            time.sleep(press_time)
            keyboard.release(key)
        