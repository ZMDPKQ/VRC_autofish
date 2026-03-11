import keyboard
import time
import config

class KeyController:
    def __init__(self):
        self.interval_in_press = config.INTERVAL_IN_PRESS
        self.is_enable = True
    
    def perss_key(self,key):
        '''
        :param key: 'Speace'  not None
        '''
        if key is not None:
            keyboard.press(key)
            time.sleep(self.interval_in_press)
            keyboard.release(key)
        