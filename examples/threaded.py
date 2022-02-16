#!/usr/bin/env python3

from time import sleep
from threading import Thread

from acsys import daq_lib


def monitor_weather(daq_chan):
    """This function monitors two weather-related devices and uses
    callbacks to print the value."""
    # We can put acquisition "in the background" and let a callback
    # handle the data.

    daq_lib.handle_readings(daq_chan, 'M:OUTTMP@p,10000',
                            callback=lambda res: print(f'{res} degF'))

    # Or we can create a Device object and process the stream of
    # readings.

    humid = daq_lib.Device(daq_chan, 'G:HUMID@p,60000')

    for reading in humid:
        print(f'{reading.value} %')


def rotate_cube(daq_chan):
    """This function sets ACNET devices that are used in the
    "Rotating Cube" web page. It updates the angles of rotation at 5 hz."""
    cube_x=daq_lib.Device(daq_chan, 'Z:CUBE_X.SETTING@N')
    cube_y=daq_lib.Device(daq_chan, 'Z:CUBE_Y.SETTING@N')
    cube_z=daq_lib.Device(daq_chan, 'Z:CUBE_Z.SETTING@N')

    x_pos=0
    y_pos=0
    z_pos=0

    while True:
        # Opposed to the async example, these are happening synchronously.
        # These are blocking calls.
        cube_x.set(x_pos)
        cube_y.set(y_pos)
        cube_z.set(z_pos)

        x_pos=(x_pos + 5) % 360
        y_pos=(y_pos + 2) % 360
        z_pos=(z_pos + 1) % 360

        sleep(0.2)


def main():
    """Main entry point for a script."""
    # Do whatever initialization.

    pass

    # Now we're ready to enter data acquisition. This runs the
    # specified function. When the function exits, the acquisition is
    # canceled.

    daq=daq_lib.DeviceData()

    # create two new threads
    thread_1=Thread(target=monitor_weather, args=(daq,))
    thread_2=Thread(target=rotate_cube, args=(daq,))
    # Sharing data between threads gets tricky. We don't discuss this.

    # start the threads
    thread_1.start()
    thread_2.start()

    # wait for the threads to complete
    thread_1.join()
    thread_2.join()
