#!/usr/bin/env python3

from acsys import daq_lib


daq = daq_lib.DeviceData()

# This uses the context manager to automatically close the connection
# when leaving the block.
# The [:] syntax requests all indexes in the array.
# https://www-bd.fnal.gov/controls/public/drf2/
for response in daq.start('Z:TSTDEV[:]@P,20H'):
    print(response)

# OR

response_queue = daq.start('Z:TSTDEV[:]@P,20H')

print(next(response_queue))  # First response
print(next(response_queue))  # Second response
print(next(response_queue))  # Third response
print(next(response_queue))  # Fourth response
print(next(response_queue))  # Fifth response

# When using the queue strategy, you must close the queue before exiting.
response_queue.close()
