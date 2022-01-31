import acsys.status

if __name__ == '__main__':
    try:
        print("Raising error")
        raise acsys.status.AcnetRetryIOError()
    except acsys.status.AcnetReplyTaskDisconnected as ex:
        print(f"Captured specific exception: {ex!r}")
    except acsys.status.AcnetException as ex:
        print(f"Captured general exception: {ex!r}")

    try:
        raise acsys.status.Status.create(1+256*-6)
    except acsys.status.AcnetRequestTimeOutQueuedAtDestination as ex:
        print(f"Captured specific exception: {ex!r}")
    except acsys.status.AcnetException as ex:
        print(f"Captured general exception: {ex!r}")

    l = acsys.status.ACNET_RETRY
    dex = acsys.status.AcnetNoRequestHandle()
    try:
        try:
            raise acsys.status.AcnetRetryIOError()
        except acsys.status.AcnetNoRequestHandle as ex:
            raise
        except acsys.status.AcnetException as ex:
            raise acsys.status.AcnetReplyTaskDisconnected() from ex
        
    except Exception as ex2:
        print("Exception captured!")
        print(f"Captured general exception: {ex2!r}")
        # raise

