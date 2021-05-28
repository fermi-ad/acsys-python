#!/usr/bin/env python3

import acsys.sync
import logging

FORMAT = '%(asctime)-15s [%(levelname)s] %(message)s'
logging.basicConfig(format=FORMAT)

log = logging.getLogger('acsys')
log.setLevel(logging.DEBUG)

# This function calls 'acsys.sync.get_events' to register for
# the two clock events. The return value is a generator which
# is iterated across in the 'async-for-loop'.


async def my_client(con):
    async for event in acsys.sync.get_events(con, ['e,2', 'e,8f']):
        event_type = type(event)
        assert event_type is acsys.sync.StateEvent \
            or event_type is acsys.sync.ClockEvent
        assert event.event == 0x02 or event.event == 0x8f
        break

# Start the 'async' framework. Specify 'my_client' to be the
# function to be run in the async environment.


def test_sync():
    acsys.run_client(my_client)

test_sync()
