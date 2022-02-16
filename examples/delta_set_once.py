#!/usr/bin/env python3

from acsys import daq_lib


daq = daq_lib.DeviceData(roles=['testing'])

initial_reading = daq.read('Z:CUBE_X')

daq.set('Z:CUBE_X', initial_reading + 1)

# There's not technical reason you must read the value back, but conventionally
# it's a good practice to verify that the value was set.
print(f'X position: {daq.read("Z:CUBE_X").value}')
