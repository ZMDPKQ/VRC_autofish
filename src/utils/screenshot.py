import mss
import numpy as np
import logging
import time
from typing import Optional, Tuple

import cv2

logger = logging.getLogger(__name__)

class ScreenGrabber:

    def __init__(
        self,
        monitor: int = 1,
        output_color: str = "BGR",
    ):
        self.monitor_idx = monitor
        self.output_color = output_color.upper()
        self.roi: Optional[Tuple[int, int, int, int]] = None

        self.sct = mss.mss()
        self.monitor_info = self.sct.monitors[self.monitor_idx]

        self._grab_region = self.monitor_info

    def set_roi(self, roi: Optional[Tuple[int, int, int, int]]):

        self.roi = roi

        if roi is None:
            self._grab_region = self.monitor_info
        else:
            left, top, width, height = roi

            self._grab_region = {
                "left": self.monitor_info["left"] + left,
                "top": self.monitor_info["top"] + top,
                "width": width,
                "height": height,
            }

    def grab(self):
        # logger.debug(self.roi)
        try:
            sct_img = self.sct.grab(self._grab_region)
            frame = np.frombuffer(
                sct_img.raw,
                dtype=np.uint8
            ).reshape(sct_img.height, sct_img.width, 4)
            # # 调试：用已解析好的 numpy 保存一次截图（避免 mss raw 的 stride 导致条纹/重复）
            # if not getattr(self, "_debug_saved", False):
            #     cv2.imwrite(str(time.time()) + ".png", frame)
            #     self._debug_saved = True

            if self.output_color == "BGRA":
                return frame

            elif self.output_color == "BGR":
                return frame[:, :, :3]

            elif self.output_color == "RGB":
                return frame[:, :, [2, 1, 0]]

            return frame[:, :, :3]

        except Exception as e:
            logger.error(f"MSS grab failed: {e}", exc_info=True)
            return None

    def release(self):
        if self.sct:
            self.sct.close()