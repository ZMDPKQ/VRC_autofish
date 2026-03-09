--- 写点什么好呢 QwQ 干脆让ds来写吧、反正九成都是他写的 皮卡丘完成了一成的工作真是太辛苦了 T_T
--- ds就是史！ 还得我自己写！

 # CUDA 12.9
 ` pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu129 `

 TensorRT
 下载对应的版本 系统和cuda
 https://developer.nvidia.com/tensorrt/download
 执行TensorRT-10.14.1.48\python中的三个文件、选择对应的python本版本 3.10->CP310
把lib、bin添加到环境变量：$env:PATH="Lib\TensorRT-8.6.1.6\lib;Lib\TensorRT-8.6.1.6\bin;$env:PATH"

# bug
识别不到时警告：WARNING 'source' is missing. Using 'source=C:\Users\45587\Desktop\vrc_autofish\vrc_autofish\Lib\site-packages\ultralytics\assets'.
已解决

另一台电脑dxcam 报错
已部分解决 ： 可能还是要换掉前台dxcam这个方法

停止不全
已解决

python .\src\main.py
python .\screentool.py
python .\model_to_TensorRT.py