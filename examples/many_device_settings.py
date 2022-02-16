#!/usr/bin/env python3

from acsys import daq_lib


long_list_of_device_strings = [...]
long_list_of_device_settings = [...]
daq = daq_lib.DeviceData()

try:
    daq_lib.apply_settings(
        zip(long_list_of_device_strings, long_list_of_device_settings),
        roles=['rotating']
    )
except daq_lib.DeviceError as error:
    print(f'Error setting devices: {error}')
