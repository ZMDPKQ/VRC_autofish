import dxcam
import win32api
import re
import logging

def detect_active_dxcam_device(logger=None):
    """
    自动检测当前主屏幕对应的 dxcam 设备和输出索引
    返回 (device_idx, output_idx)，找不到则返回 (0,0)
    """
    outputs = dxcam.output_info()
    # dxcam.

    if logger:
        logger.info(f"dxcam outputs: {outputs}")
        text ='Device[0] Output[0]: Res:(1920, 1080) Rot:0 Primary:True\nDevice[0] Output[1]: Res:(1920, 1080) Rot:0 Primary:False\n'
    pattern = re.compile(r'Device\[(\d+)\]\s+Output\[(\d+)\]:.*?Primary:(True|False)')
    
    results = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = pattern.search(line)
        if match:
            device = int(match.group(1))
            output = int(match.group(2))
            primary = match.group(3) == 'True'
            if primary:
                results.append((device, output))
    return results

    if logger:
        logger.warning("No output exactly matches primary screen, fallback to device 0 output 0")
    return 0, 0

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("dxcam_detect")

    device_idx, output_idx = detect_active_dxcam_device(logger)
    print("Selected DXCam device:", device_idx)
    print("Selected DXCam output:", output_idx)