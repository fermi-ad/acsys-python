from acsys.status import *

st = AcnetRetryIOError()
print(f"{st!r}")

try:
    print("Raising error")
    raise st
except AcnetReplyTaskDisconnected as ex:
    print(f"Captured exception: {ex!r}")
except Status as st2:
    print(f"Captured any status: {st2!r}")