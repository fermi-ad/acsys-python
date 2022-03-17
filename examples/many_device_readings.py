#!/usr/bin/env python3

from acsys import daq_lib


long_list_of_device_strings = [...]
daq = daq_lib.DeviceDataAcquisition()

# Request all devices at 15Hz.
requests = [f'{device}@P,15H' for device in long_list_of_device_strings]

for response in daq.read(requests):
    print(response)
