#!/usr/bin/env python3

import logging
import acsys.dpm
from acsys.dpm import (ItemData, ItemStatus)

FORMAT = '%(asctime)-15s [%(levelname)s] %(message)s'
logging.basicConfig(format=FORMAT)

log = logging.getLogger('acsys')
log.setLevel(logging.INFO)

async def my_app(con, **kwargs):
    log.info(f"args: {kwargs['a']}, {kwargs['b']}")
    async with acsys.dpm.DPMContext() as dpm:
        await dpm.enable_settings(role='testing')

        # Set-up our two devices. The second device uses the $FF event,
        # which never fires, so it won't generate replies.

        await dpm.add_entry(0, 'Z:CUBE_X.SETTING@N')
        await dpm.apply_settings([(0, 1.0)])

        async for ii in dpm.replies():
            print(ii)
            break

acsys.run_client(my_app, a=1, b="hello")
