import dxcam
import time


class ScreenGrabber:

    def __init__(self, roi=None):
        self.roi = roi
        self.camera = None
        self._create_camera()

    def _create_camera(self):
        try:
            del self.camera
            self.camera = dxcam.create(output_color="BGR")
            # self.camera.start(target_fps=120, video_mode=True)
            self.camera.start(target_fps=120)
        except Exception as e:
            print("DXCAM init error:", e)
            self.camera = None

    def grab(self, roi=None):

        if roi is not None:
            self.roi = roi

        if self.camera is None:
            self._create_camera()
            return None

        try:
            frame = self.camera.get_latest_frame()

        except Exception as e:
            print("DXCAM crash, restarting:", e)
            try:
                self.camera.stop()
                del self.camera
            except:
                pass

            self.camera = None
            time.sleep(0.001)
            self._create_camera()

            return None

        if frame is None:
            return None

        if self.roi is None:
            return frame

        left, top, width, height = self.roi
        return frame[top:top + height, left:left + width]

    def release(self):
        if self.camera is not None:
            try:
                self.camera.stop()
            except:
                pass
        self.camera = None