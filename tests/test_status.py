from acsys.status import *


try:
    print("Raising error")
    raise AcnetRetryIOError()
except AcnetReplyTaskDisconnected as ex:
    print(f"Captured specific exception: {ex!r}")
except AcnetException as ex:
    print(f"Captured general exception: {ex!r}")

try:
    raise Status.create(1+256*-6)
except AcnetRequestTimeOutQueuedAtDestination as ex:
    print(f"Captured specific exception: {ex!r}")
except AcnetException as ex:
    print(f"Captured general exception: {ex!r}")


try:
    try:
        raise AcnetRetryIOError()
    except AcnetException as ex:
        raise AcnetReplyTaskDisconnected() from ex
except Exception as ex2:
    print("Exception captured!")
    print(f"Captured general exception: {ex2!r}")
    raise
