#!/usr/bin/env python3


from ctypes import Union
from datetime import date
from typing import AsyncIterable, Callable, Iterable, Iterator, List, Optional

from grpc import Channel


class DeviceReading:
    """A reading from a device"""
    time: int
    value: float


class Device(Iterable, AsyncIterable):
    """Device class doc"""

    def __init__(
        self,
        data_source_channel: Channel,
        request_string: str,
        roles: Optional[List[str]] = None
    ) -> Iterator[DeviceReading]:
        self.channel = data_source_channel
        self.request_string = request_string
        self.roles = roles if roles is not None else []

        raise NotImplementedError

    def __iter__(self) -> Iterator[DeviceReading]:
        """Provide data in an iterator."""
        raise NotImplementedError

    def __next__(self) -> Iterator[DeviceReading]:
        """Provide data in an iterator."""
        raise NotImplementedError

    def __aiter__(self) -> Iterator[DeviceReading]:
        """Provide data in an iterator."""
        raise NotImplementedError

    def __anext__(self) -> Iterator[DeviceReading]:
        """Provide data in an iterator."""
        raise NotImplementedError

    def read(self) -> DeviceReading:
        """Get reading of a device."""
        raise NotImplementedError

    def set(self, value: float) -> None:
        """Set the value of a device."""
        raise NotImplementedError

    def handle_readings(self, callback: Callable[[DeviceReading], None]) -> None:
        """Handle readings of a device."""
        raise NotImplementedError


class DeviceData:
    """DeviceData class doc"""

    def __init__(self, roles: Optional[List[str]] = None) -> None:
        self.roles = roles if roles is not None else []

    def read(
        self,
        request_string: str,
        start: Optional[date] = None,
        end: Optional[date] = None
    ) -> DeviceReading:
        """Get reading of a device."""
        raise NotImplementedError

    def set(
        self,
        device_name: str,
        value: float,
        roles: Optional[List[str]] = None
    ) -> None:
        """Set the value of a device."""
        raise NotImplementedError

    def start(
        self,
        request_string: str,
        start: Optional[date] = None,
        end: Optional[date] = None
    ) -> Iterator[DeviceReading]:
        """Start reading a device."""
        raise NotImplementedError

class DeviceError(Exception):
    """DeviceError class doc"""
    ...


def enter_acquisition(entry_fn: Callable[..., None]) -> None:
    """Enter acquisition mode"""
    raise NotImplementedError


def handle_readings(
    data_source_channel: Channel,
    request_string: str,
    callback: Callable[[DeviceReading], None]
) -> None:
    """Enter acquisition mode"""
    raise NotImplementedError

def apply_settings(
    # There's not good support for zip typing here. I think Iterator works.
    device_list: Union[List[Device], Iterator[Device]],
    roles: Optional[List[str]] = None
) -> None:
    """Apply settings to devices"""
    raise NotImplementedError
