#!/usr/bin/env python3

import asyncio

from acsys import daq_lib


# This async function monitors two weather-related devices and uses
# callbacks to print the value.

async def monitor_weather(daq_chan):
    # We can put acquisition "in the background" and let a callback
    # handle the data.

    daq_lib.handle_readings(daq_chan, 'M:OUTTMP@p,10000',
                            cb=lambda res: print(f'{res} degF'))

    # Or we can create a Device object and process the stream of
    # readings.

    humid = daq_lib.Device(daq_chan, 'G:HUMID@p,60000')

    async for reading in humid:
        print(f'{reading.value} %')

# This async function sets ACNET devices that are used in the
# "Rotating Cube" web page. It updates the angles of rotation at 5 hz.


async def rotate_cube(daq_chan):
    cube_x = daq_lib.Device(daq_chan, 'Z:CUBE_X.SETTING@N', role=['rotating'])
    cube_y = daq_lib.Device(daq_chan, 'Z:CUBE_Y.SETTING@N', role=['rotating'])
    cube_z = daq_lib.Device(daq_chan, 'Z:CUBE_Z.SETTING@N', role=['rotating'])

    x_pos = 0
    y_pos = 0
    z_pos = 0

    while True:
        await asyncio.gather(
            cube_x.set(x_pos),
            cube_y.set(y_pos),
            cube_z.set(z_pos)
        )

        x_pos = (x_pos + 5) % 360
        y_pos = (y_pos + 2) % 360
        z_pos = (z_pos + 1) % 360

        await asyncio.sleep(0.2)

# This is the main entry point for our data acquisition loop. When
# this method exits, the connection to DPM will be closed.


async def daq_entry(daq_chan, **kwds):
    await asyncio.gather(monitor_weather(daq_chan),
                         rotate_cube(daq_chan))

# Main entry point for someone's async script.


async def main():

    # Do whatever initialization.

    pass

    # Now we're ready to enter data acquisition. This runs the
    # specified function. When the function exits, the acquisition is
    # canceled.

    await daq_lib.enter_acquisition(daq_entry)
