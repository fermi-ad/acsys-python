#!/usr/bin/env python3

import acsys.dpm
import acsys.scaling


async def update_ramp_slot(con, device, index, value):
    # If the device is passed as a device index, convert it to the
    # "device index name".

    if isinstance(device, int):
        device = f'0:{device}'

    drf = f'{device}.SETTING[{index}].RAW@i'

    # Scale the caller's new value.

    raw = await acsys.scaling.convert_data(con, drf, value)

    # Get the current value of the F(t) slot.

    async with acsys.dpm.DPMContext(con) as dpm:
        await dpm.add_entry(0, drf)
        await dpm.start()
        async for reply in dpm.replies():
            if reply.isReadingFor(0):
                return raw + reply.data[-2:]
            elif reply.isStatusFor(0):
                raise reply.status
    return None


async def my_client(con):
    async with acsys.dpm.DPMContext(con) as dpm:
        device = 'M:OUTTMP'
        rate = 'I'
        await dpm.add_entry(0, f'{device}@{rate}')
        await dpm.start()

        async for reply in dpm:
            raw = await acsys.scaling.convert_data(con, f'{device}.RAW@{rate}', reply.data)
            scaled = await acsys.scaling.convert_data(con, f'{device}@{rate}', raw)
            assert abs(reply.data - scaled[0]) < 0.1
            break


def test_scaling():
    acsys.run_client(my_client)
