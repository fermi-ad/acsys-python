#!/usr/bin/env python3

from datetime import date

from acsys import daq_lib


daq = daq_lib.DeviceData()

# Request historical data isn't much different than the live data requests.
# The context for the request determines what the data source is.
# In this example, all the data is fetched from data loggers for the given day.
request = daq.read(
    'Z:CUBE_X',
    start=date.fromisoformat('2021-12-04'),
    end=date.fromisoformat('2021-12-05')
)

for response in request:
    print(f'temp: {response.value}')

# In this example, we leave off the end date implicitly indicating that we want
# to read all data up to the current time and continuing indefinitely.
request = daq.read(
    'Z:CUBE_X',
    start=date.fromisoformat('2021-12-04'),
)

for response in request:
    print(f'temp: {response.value}')
