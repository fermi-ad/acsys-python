#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import acsys.dpm


async def my_client(con):
    # Setup context
    async with acsys.dpm.DPMContext(con) as dpm:
        # Add acquisition requests
        await dpm.add_entry(0, 'Z:CUBE_X.SETTING@I')

        # Start acquisition
        await dpm.start()

        # Process incoming data
        async for evt_res in dpm:
            assert evt_res.is_reading_for(0)
            break


def test_dpm():
    acsys.run_client(my_client)
