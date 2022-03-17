#!/usr/bin/env python3

from acsys import daq_lib


daq = daq_lib.DeviceDataAcquisition(role='testing')

daq.set('Z:CUBE_X', 4.0)

# There's not technical reason you must read the value back, but conventionally
# it's a good practice to verify that the value was set.
print(f'X position: {daq.read("Z:CUBE_X").value}')
