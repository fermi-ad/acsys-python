#!/usr/bin/env python3

from acsys import daq_lib

long_list_of_strings = [...]
daq = daq_lib.DeviceDataAcquisition()
cube_x = daq_lib.Device(daq, 'Z:CUBE_X')
device_list = [cube_x]

cube_x.handle_readings(callback=lambda res: print(f'{res.value} degF'))

# This only returns after the slowest reading is complete.
print(cube_x.read())  # {device: "Z:CUBE_X", value: 4.0}
# Our callback is called with the value as well.
# "4.0 degF"

cube_x.set(12)

try:
    daq_lib.apply_settings(device_list, roles=['rotating'])
except daq_lib.DeviceError as error:
    print(f'Error setting devices: {error}')

print(cube_x.read())  # {device: "Z:CUBE_X", value: 12.0}
