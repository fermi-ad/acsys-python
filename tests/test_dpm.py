#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import acsys.dpm

FORMAT = '%(asctime)-15s [%(levelname)s] %(message)s'
logging.basicConfig(format=FORMAT)

log = logging.getLogger('acsys')
log.setLevel(logging.DEBUG)

async def my_client(con):
    log.info('entered main')

    # Setup context

    async with acsys.dpm.DPMContext() as dpm:

        # Add acquisition requests

        await dpm.add_entry(0, 'Z:CUBE_X.SETTING@I')

        # Start acquisition

        await dpm.start()

        # Process incoming data

        async for evt_res in dpm.replies():
            print(f'received: {evt_res}')
            assert evt_res.is_reading_for(0)
            break


acsys.run_client(my_client)
