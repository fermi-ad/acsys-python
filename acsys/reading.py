"""Result type returned by acsys read and subscribe operations."""

from __future__ import annotations

import datetime
from typing import Any


class Reading:
    """Holds the result of a single device read.

    Attributes
    ----------
    device : str
        The device name as supplied in the DRF string.
    value :
        The sampled value.  The Python type depends on the device and the
        field requested:

        * ``float``       – scaled scalar reading (most common)
        * ``list[float]`` – scaled array reading
        * ``bytes``       – raw (unscaled) reading
        * ``str``         – text reading
        * ``list[str]``   – text-array reading
        * ``int``         – ACNET status code (on error)

    timestamp : datetime.datetime
        When the reading was sampled, expressed in UTC.

    Examples
    --------
    ::

        reading = acsys.read('Z:BTE200MUON4')
        print(reading.value, reading.timestamp)
    """

    __slots__ = ('device', 'value', 'timestamp')

    def __init__(self, device: str, value: Any,
                 timestamp: datetime.datetime) -> None:
        self.device = device
        self.value = value
        self.timestamp = timestamp

    def __repr__(self) -> str:
        return (
            f'Reading(device={self.device!r}, value={self.value!r}, '
            f'timestamp={self.timestamp.isoformat()!r})'
        )

    def __str__(self) -> str:
        return (
            f'{self.device} = {self.value} '
            f'@ {self.timestamp.isoformat()}'
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Reading):
            return NotImplemented
        return (self.device == other.device
                and self.value == other.value
                and self.timestamp == other.timestamp)
