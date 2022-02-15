# Basic data reading from Python REPL

```py
>>> from acsys import daq_lib
>>> daq = daq_libDeviceData()
>>> daq.read('M:OUTTMP')
{
    "M:OUTTMP": {
        "value": 56.98726345,
        "timestamp": 1528897881.0
    }
}
```
