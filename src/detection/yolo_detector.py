import torch
from ultralytics import YOLO
import config
import logging

logger = logging.getLogger(__name__) 

class YOLODetector:
    def __init__(self,
                 model_path=config.MODEL_PATH,
                 roi_model_path=config.ROI_MODEL_PATH,
                 conf_threshold=config.CONFIDENCE_THRESHOLD):

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # self.device = "cpu"
        # logger.info(f"yolo 运行在: {self.device}")

        self.base_model = YOLO(model_path)
        self.base_model.to(self.device)

        self.roi_model = YOLO(roi_model_path)
        self.roi_model.to(self.device)

        self.conf_threshold = conf_threshold
        self.class_names = config.CLASS_NAMES
        # self.use_half = torch.cuda.is_available()
        self.use_half = (self.device == "cuda")
        self.using_model = None

    def detect(self, frame, roi=None,classes=None):
        
        # 如果传入 ROI，说明在局部模式
        if roi is not None:
            model = self.roi_model
            imgsz = 640
            self.using_model = 'roi_model'
        else:
            model = self.base_model
            imgsz = 960
            self.using_model = 'base_model'
        logger.debug(f'using_model:{self.using_model}')
        results = model(
            frame,
            conf=self.conf_threshold,
            verbose=False,
            imgsz=imgsz,
            half=self.use_half,
            classes=classes
        )

        return self._parse_results(results)

    def _parse_results(self, results):

        detections = {name: [] for name in self.class_names}

        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()

                class_name = self.class_names[cls_id]
                detections[class_name].append((xyxy, conf))

        for name in detections:
            detections[name].sort(key=lambda x: x[1], reverse=True)
        # logger.debug(f'detections:{detections}')
        return detections
    
    def get_running_model_name(self):
        return self.using_model
    def get_model_running_device(self):
        return self.device