#!/usr/bin/env python3

from acsys import daq_lib


daq = daq_lib.DeviceDataAcquisition()

print(f'temp: {daq.read("M:OUTTMP").value}')
