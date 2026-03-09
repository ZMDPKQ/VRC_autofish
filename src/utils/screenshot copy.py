import dxcam

class ScreenGrabber:
    def __init__(self, roi=None):
        if roi:
            self.roi = roi
        else:
            self.roi = None
        self.camera = dxcam.create(output_color="BGR")

    def grab(self, roi=None):
        if roi is not None:
            self.roi = roi
        if self.camera is None:
            self.camera = dxcam.create(output_color="BGR")
        try:
            frame = self.camera.grab()
        except Exception as e:
            # DX 状态异常时重建
            print(e)
            try:
                self.camera = dxcam.create(output_color="BGR")
                frame = self.camera.grab()
            except:
                return None

        if frame is None:
            return None

        if self.roi is None:
            return frame

        left, top, width, height = self.roi
        return frame[top:top+height, left:left+width]
    
    def release(self):
        if self.camera is not None:
            try:
                self.camera.stop()
                del self.camera
            except:
                pass
            self.camera = None