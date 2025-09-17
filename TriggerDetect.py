import sys
import time
from ctypes import *

sys.path.append("../MvImport")
from MvImport.MvCameraControl_class import *

class TriggerDetector:
    def __init__(self):
        self.cam = MvCamera()
        self.b_open_device = False
        self.trigger_count = 0

    def open_device(self):
        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
        if ret != 0:
            print(f"Enum devices fail! ret[0x{ret:x}]")
            return ret

        if deviceList.nDeviceNum == 0:
            print("No camera found!")
            return -1

        stDeviceList = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents

        ret = self.cam.MV_CC_CreateHandle(stDeviceList)
        if ret != 0:
            print(f"Create handle fail! ret[0x{ret:x}]")
            return ret

        ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            print(f"Open device fail! ret[0x{ret:x}]")
            return ret

        print("Open device successfully!")
        self.b_open_device = True

        # 設置觸發模式為 On
        ret = self.cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_ON)
        if ret != 0:
            print(f"Set trigger mode fail! ret[0x{ret:x}]")
        
        # 設置觸發源為硬件觸發（根據實際情況選擇）
        ret = self.cam.MV_CC_SetEnumValue("TriggerSource", MV_TRIGGER_SOURCE_LINE0)
        if ret != 0:
            print(f"Set trigger source fail! ret[0x{ret:x}]")

        return 0

    def close_device(self):
        if self.b_open_device:
            ret = self.cam.MV_CC_CloseDevice()
            self.cam.MV_CC_DestroyHandle()
            self.b_open_device = False
            print("Close device successfully!")
            return ret
        return 0

    def check_trigger(self):
        if not self.b_open_device:
            print("Device not open!")
            return False

        stFrameInfo = MV_FRAME_OUT_INFO_EX()
        pData = (c_ubyte * 1)()
        messages = ["Waiting...................", "Waiting for ...............", "Waiting for trigger..."]

        while True:
            for message in messages:
                sys.stdout.write("\r" + message)
                sys.stdout.flush()
                time.sleep(0.5)

                # 在這裡檢查觸發信號
                ret = self.cam.MV_CC_GetOneFrameTimeout(pData, 1, stFrameInfo, 1000)
                if ret == 0:
                    self.trigger_count += 1
                    sys.stdout.write(f"\rTrigger received. Count: {self.trigger_count}\n")
                    sys.stdout.flush()
                    return True
                else:
                    sys.stdout.write("\rWaiting for trigger...")  # 顯示等待訊息
                    sys.stdout.flush()

def main():
    detector = TriggerDetector()
    
    if detector.open_device() != 0:
        return

    print("Start detecting triggers. Press Ctrl+C to stop.")
    try:
        while True:
            detector.check_trigger()
            time.sleep(0.1)  # 短暫休息，避免 CPU 使用率過高
    except KeyboardInterrupt:
        print("\nStopping trigger detection.")
    finally:
        detector.close_device()

if __name__ == "__main__":
    main()