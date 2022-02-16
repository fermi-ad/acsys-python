#!/usr/bin/env python3

from acsys import daq_lib


daq = daq_lib.DeviceData()

while True:
    # $02 event fires every 5 seconds.
    # This only returns when the event fires.
    # We are using this request to time the loop.
    cube_x = daq.read('Z:CUBE_X@E,02')
    cube_y = daq.read('Z:CUBE_Y')
    cube_z = daq.read('Z:CUBE_Z')

    try:
        daq.set('Z:CUBE_X', cube_x.value + 12, roles=['rotating'])
        daq.set('Z:CUBE_Y', cube_y.value + 12, roles=['rotating'])
        daq.set('Z:CUBE_Z', cube_z.value + 12, roles=['rotating'])
    except daq_lib.DeviceError as error:
        print(f'Error setting devices: {error}')
