#!/usr/bin/env python3

from acsys import daq_lib


daq = daq_lib.DeviceData()

print(f'temp: {daq.read("Z:TSTDEV[:]").value}')