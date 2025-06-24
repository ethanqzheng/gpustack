import asyncio
import logging
import re
import subprocess
from gpustack.detectors.base import GPUDetector
from gpustack.schemas.workers import (
    GPUCoreInfo,
    GPUDeviceInfo,
    GPUDevicesInfo,
    MemoryInfo,
    VendorEnum,
)
from gpustack.utils.command import is_command_available
from gpustack.utils import platform

logger = logging.getLogger(__name__)


class EFSMI(GPUDetector):
    def is_available(self) -> bool:
        return is_command_available("efsmi")

    def gather_gpu_info(self) -> GPUDevicesInfo:
        return self._gather_gpu_info()
       
     
    def _run_command(self, command):
        result = None
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8"
            )

            if result is None or result.stdout is None:
                return None

            output = result.stdout
            if "no devices" in output.lower():
                return None

            if result.returncode != 0:
                raise Exception(f"Unexpected return code: {result.returncode}")

            if output == "" or output is None:
                raise Exception(f"Output is empty, return code: {result.returncode}")

            return output
        except Exception as e:
            error_message = f"Failed to execute {command}: {e}"
            if result:
                error_message += f", stdout: {result.stdout}, stderr: {result.stderr}"
            raise Exception(error_message)

    def _get_gpu_info(self, command) -> dict[int, dict[str, any]]:
        output = self._run_command(command)
        if output is None:
            raise Exception("Failed to get GPU base info")
        
        devices = dict()
        current_device = {}
    
        # 正则表达式模式
        dev_id_pattern = re.compile(r"DEV ID (\d+)")
        property_pattern = re.compile(r"^\s*(\w+(?:\s\w+)*)\s*:\s*(.*)$")
        
        # 逐行处理输出
        for line in output.splitlines():
            # 检查设备ID行
            dev_id_match = dev_id_pattern.match(line)
            if dev_id_match:
                # 保存上一个设备信息
                if current_device:
                    devices[current_device["DEV_ID"]]= current_device
                    
                # 开始新设备
                current_device = {"DEV_ID": int(dev_id_match.group(1))}
                continue
            
            # 检查属性行
            prop_match = property_pattern.match(line)
            if prop_match and current_device:
                key = prop_match.group(1).replace(" ", "_")  # 替换空格为下划线
                value = prop_match.group(2).strip()
                if key.endswith("_Size"):
                    value = int(value.split()[0])*1024*1024
                if key == "GCU_Temp"  :
                    value = float(value.split()[0])
                if key == "GCU_Usage" :
                    value = float(value.split()[0])
                
                current_device[key] = value
        
        # 添加最后一个设备
        if current_device:
            devices[current_device["DEV_ID"]]= current_device
        
        return devices

    def _gather_gpu_info(self) -> GPUDevicesInfo: 
        devices = []
        device_info, memory_info, temperature_info, usage_info = (
            self._get_gpu_info(["efsmi", "-q", "-d", "DEVICE"]),
            self._get_gpu_info(["efsmi", "-q", "-d", "MEMORY"]),
            self._get_gpu_info(["efsmi", "-q", "-d", "TEMP"]),
            self._get_gpu_info(["efsmi", "-q", "-d", "USAGE"]),
        )
        
        logging.debug(f"DEVICE: {device_info} \nMEMORY:{memory_info} \n TEMP:{temperature_info} \n USAGE:{usage_info}")
        for key, item in device_info.items():
            device = GPUDeviceInfo(
                index = item["DEV_ID"],
                device_index = item["DEV_ID"],
                device_chip_index = item["DEV_ID"],
                name = item["Dev_Name"],
                uuid = item["Dev_UUID"],
                vendor = VendorEnum.Enflame.value,
                type = platform.DeviceTypeEnum.GPU.value,
                core = GPUCoreInfo(
                    utilization_rate = usage_info[key]["GCU_Usage"],
                ),
                memory = MemoryInfo(
                    is_unified_memory = False,
                    total = memory_info[key]["Total_Size"],
                    used = memory_info[key]["Used_Size"],
                    utilization_rate = usage_info[key]["GCU_Usage"],
                ),
                temperature = temperature_info[key]["GCU_Temp"],
            )
            devices.append(device)
        print(devices)
        return devices



