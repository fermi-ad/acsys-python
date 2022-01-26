from enum import IntEnum

class Status:
    """An ACSys status type."""

    class Codes(IntEnum):
        """ACNET common status codes"""
        ACNET_SUCCESS = 1 + 256 * 0
        ACNET_PEND = 1 + 256 * 1
        ACNET_ENDMULT = 1 + 256 * 2
        ACNET_RETRY = 1 + 256 * -1
        ACNET_NOLCLMEM = 1 + 256 * -2
        ACNET_NOREMMEM = 1 + 256 * -3
        ACNET_RPLYPACK = 1 + 256 * -4
        ACNET_REQPACK = 1 + 256 * -5
        ACNET_REQTMO = 1 + 256 * -6
        ACNET_QUEFULL = 1 + 256 * -7
        ACNET_BUSY = 1 + 256 * -8
        ACNET_NOT_CONNECTED = 1 + 256 * -21
        ACNET_ARG = 1 + 256 * -22
        ACNET_IVM = 1 + 256 * -23
        ACNET_NO_SUCH = 1 + 256 * -24
        ACNET_REQREJ = 1 + 256 * -25
        ACNET_CANCELLED = 1 + 256 * -26
        ACNET_NAME_IN_USE = 1 + 256 * -27
        ACNET_NCR = 1 + 256 * -28
        ACNET_NO_NODE = 1 + 256 * -30
        ACNET_TRUNC_REQUEST = 1 + 256 * -31
        ACNET_TRUNC_REPLY = 1 + 256 * -32
        ACNET_NO_TASK = 1 + 256 * -33
        ACNET_DISCONNECTED = 1 + 256 * -34
        ACNET_LEVEL2 = 1 + 256 * -35
        ACNET_HARD_IO = 1 + 256 * -41
        ACNET_NODE_DOWN = 1 + 256 * -42
        ACNET_SYS = 1 + 256 * -43
        ACNET_NXE = 1 + 256 * -44
        ACNET_BUG = 1 + 256 * -45
        ACNET_NE1 = 1 + 256 * -46
        ACNET_NE2 = 1 + 256 * -47
        ACNET_NE3 = 1 + 256 * -48
        ACNET_UTIME = 1 + 256 * -49
        ACNET_INVARG = 1 + 256 * -50
        ACNET_MEMFAIL = 1 + 256 * -51
        ACNET_NO_HANDLE = 1 + 256 * -52

    def __init__(self, val):
        """Creates a status value which is initialized with the supplied
        value. The value must be in the range of signed, 16-bit
        integers.
        Do not use this method directly, use Status.create(val) instead.
        """
        if -0x8000 < val <= 0x7fff:
            self.value = val
        else:
            raise ValueError('raw status values are 16-bit, signed integers')

    @property
    def facility(self):
        """Returns the 'facility' code of a status value."""
        return self.value & 255

    @property
    def err_code(self):
        """Returns the 'error' code of a status value."""
        return self.value // 256

    @property
    def is_success(self):
        """Returns True if the status represents a success status."""
        return self.err_code == 0

    @property
    def is_fatal(self):
        """Returns True if the status represents a fatal status."""
        return self.err_code < 0

    @property
    def is_warning(self):
        """Returns True if the status represents a warning status."""
        return self.err_code > 0

    def __eq__(self, other):
        return self.value == other.value \
            if isinstance(other, Status) else False

    def __ne__(self, other):
        return self.value != other.value \
            if isinstance(other, Status) else True

    def __str__(self):
        return f'[{self.facility} {self.err_code}]'

    @staticmethod
    def create(val):
        """
        Factory method to build ACNET Status codes. If given an error
        code, it will build a raisable (AcnetException) object.
        """
        # In case zero is given as a value / zero facility code
        if val == 0:
            return Status(Status.Codes.ACNET_SUCCESS)
        # Non-error codes
        elif val == Status.Codes.ACNET_SUCCESS or \
                val == Status.Codes.ACNET_PEND or \
                val == Status.Codes.ACNET_ENDMULT:
            return Status(val)
        # Error codes build an exception
        elif val == Status.Codes.ACNET_RETRY:
            return AcnetRetryIOError()
        elif val == Status.Codes.ACNET_NOLCLMEM:
            return AcnetNoLocalMemory()
        elif val == Status.Codes.ACNET_NOREMMEM:
            return AcnetNoRemoteMemory()
        elif val == Status.Codes.ACNET_RPLYPACK:
            return AcnetReplyMessagePacketAssemblyError()
        elif val == Status.Codes.ACNET_REQPACK:
            return AcnetRequestMessagePacketAssemblyError()
        elif val == Status.Codes.ACNET_REQTMO:
            return AcnetRequestTimeOutQueuedAtDestination()
        elif val == Status.Codes.ACNET_QUEFULL:
            return AcnetDestinationQueueFull()
        elif val == Status.Codes.ACNET_BUSY:
            return AcnetDestinationBusy()
        elif val == Status.Codes.ACNET_NOT_CONNECTED:
            return AcnetNotConnected()
        elif val == Status.Codes.ACNET_ARG:
            return AcnetMissingArguments()
        elif val == Status.Codes.ACNET_IVM:
            return AcnetInvalidMessageLengthOrBufferAddress()
        elif val == Status.Codes.ACNET_NO_SUCH:
            return AcnetNoSuchRequestOrReply()
        elif val == Status.Codes.ACNET_REQREJ:
            return RequestToDestinationTaskRejected()
        elif val == Status.Codes.ACNET_CANCELLED:
            return RequestedCancelled()
        elif val == Status.Codes.ACNET_NAME_IN_USE:
            return AcnetNameAlreadyInUse()
        elif val == Status.Codes.ACNET_NCR:
            return AcnetNotConnectedAsRumTask()
        elif val == Status.Codes.ACNET_NO_NODE:
            return AcnetNoSuchLogicalNode()
        elif val == Status.Codes.ACNET_TRUNC_REQUEST:
            return AcnetTruncatedRequest()
        elif val == Status.Codes.ACNET_TRUNC_REPLY:
            return AcnetTruncatedReply()
        elif val == Status.Codes.ACNET_NO_TASK:
            return AcnetNoSuchDestinationTask()
        elif val == Status.Codes.ACNET_DISCONNECTED:
            return AcnetReplyTaskDisconnected()
        elif val == Status.Codes.ACNET_LEVEL2:
            return AcnetLevel2FunctionError()
        elif val == Status.Codes.ACNET_HARD_IO:
            return AcnetHardIOError()
        elif val == Status.Codes.ACNET_NODE_DOWN:
            return AcnetLogicalNodeDownOffline()
        elif val == Status.Codes.ACNET_SYS:
            return AcnetSystemServiceError()
        elif val == Status.Codes.ACNET_NXE:
            return AcnetUntranslatableError()
        elif val == Status.Codes.ACNET_BUG:
            return AcnetNetworkInternalError()
        elif val == Status.Codes.ACNET_NE1:
            return AcnetNE1_VMSExceededQuota()
        elif val == Status.Codes.ACNET_NE2:
            return AcnetNE2_VMSNoAdressForRequestOrReply()
        elif val == Status.Codes.ACNET_NE3:
            return AcnetNE3_VMSBufferInUse()
        elif val == Status.Codes.ACNET_UTIME:
            return AcnetUserGeneratedNetworkTimeout()
        elif val == Status.Codes.ACNET_INVARG:
            return AcnetInvalidArgumentPassed()
        elif val == Status.Codes.ACNET_MEMFAIL:
            return AcnetMemoryAllocationFailed()
        elif val == Status.Codes.ACNET_NO_HANDLE:
            return AcnetNoRequestHandle()
        else:
            raise ValueError(f"Invalid ACNET Status code: {val}")


# Clases that specialize Status - based on code, that can be captured on different except clauses
class AcnetException(Status, Exception):
    pass

class AcnetRetryIOError(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_RETRY)

class AcnetNoLocalMemory(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NOLCLMEM)

class AcnetNoRemoteMemory(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NOREMMEM)

class AcnetReplyMessagePacketAssemblyError(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_RPLYPACK)

class AcnetRequestMessagePacketAssemblyError(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_REQPACK)

class AcnetRequestTimeOutQueuedAtDestination(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_REQTMO)

class AcnetDestinationQueueFull(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_QUEFULL)

class AcnetDestinationBusy(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_BUSY)

class AcnetNotConnected(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NOT_CONNECTED)

class AcnetMissingArguments(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_ARG)

class AcnetInvalidMessageLengthOrBufferAddress(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_IVM)

class AcnetNoSuchRequestOrReply(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NO_SUCH)

class RequestToDestinationTaskRejected(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_REQREJ)

class RequestedCancelled(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_CANCELLED)

class AcnetNameAlreadyInUse(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NAME_IN_USE)

class AcnetNotConnectedAsRumTask(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NCR)

class AcnetNoSuchLogicalNode(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NO_NODE)

class AcnetTruncatedRequest(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_TRUNC_REQUEST)

class AcnetTruncatedReply(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_TRUNC_REPLY)

class AcnetNoSuchDestinationTask(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NO_TASK)

class AcnetReplyTaskDisconnected(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_DISCONNECTED)

class AcnetLevel2FunctionError(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_LEVEL2)

class AcnetHardIOError(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_HARD_IO)

class AcnetLogicalNodeDownOffline(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NODE_DOWN)

class AcnetSystemServiceError(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_SYS)

class AcnetUntranslatableError(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NXE)

class AcnetNetworkInternalError(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_BUG)

class AcnetNE1_VMSExceededQuota(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NE1)

class AcnetNE2_VMSNoAdressForRequestOrReply(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NE2)

class AcnetNE3_VMSBufferInUse(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NE3)

class AcnetUserGeneratedNetworkTimeout(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_UTIME)

class AcnetInvalidArgumentPassed(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_INVARG)

class AcnetMemoryAllocationFailed(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_MEMFAIL)

class AcnetNoRequestHandle(AcnetException):
    def __init__(self):
        Status.__init__(self, Status.Codes.ACNET_NO_HANDLE)


# Objects that represent an instance of each status, so they can be compared
# inside an except clause.
ACNET_SUCCESS = Status.create(Status.Codes.ACNET_SUCCESS)
ACNET_PEND = Status.create(Status.Codes.ACNET_PEND)
ACNET_ENDMULT = Status.create(Status.Codes.ACNET_ENDMULT)

# TODO deprecate this globals
ACNET_RETRY = Status.create(Status.Codes.ACNET_RETRY)
ACNET_NOLCLMEM = Status.create(Status.Codes.ACNET_NOLCLMEM)
ACNET_NOREMMEM = Status.create(Status.Codes.ACNET_NOREMMEM)
ACNET_RPLYPACK = Status.create(Status.Codes.ACNET_RPLYPACK)
ACNET_REQPACK = Status.create(Status.Codes.ACNET_REQPACK)
ACNET_REQTMO = Status.create(Status.Codes.ACNET_REQTMO)
ACNET_QUEFULL = Status.create(Status.Codes.ACNET_QUEFULL)
ACNET_BUSY = Status.create(Status.Codes.ACNET_BUSY)
ACNET_NOT_CONNECTED = Status.create(Status.Codes.ACNET_NOT_CONNECTED)
ACNET_ARG = Status.create(Status.Codes.ACNET_ARG)
ACNET_IVM = Status.create(Status.Codes.ACNET_IVM)
ACNET_NO_SUCH = Status.create(Status.Codes.ACNET_NO_SUCH)
ACNET_REQREJ = Status.create(Status.Codes.ACNET_REQREJ)
ACNET_CANCELLED = Status.create(Status.Codes.ACNET_CANCELLED)
ACNET_NAME_IN_USE = Status.create(Status.Codes.ACNET_NAME_IN_USE)
ACNET_NCR = Status.create(Status.Codes.ACNET_NCR)
ACNET_NO_NODE = Status.create(Status.Codes.ACNET_NO_NODE)
ACNET_TRUNC_REQUEST = Status.create(Status.Codes.ACNET_TRUNC_REQUEST)
ACNET_TRUNC_REPLY = Status.create(Status.Codes.ACNET_TRUNC_REPLY)
ACNET_NO_TASK = Status.create(Status.Codes.ACNET_NO_TASK)
ACNET_DISCONNECTED = Status.create(Status.Codes.ACNET_DISCONNECTED)
ACNET_LEVEL2 = Status.create(Status.Codes.ACNET_LEVEL2)
ACNET_HARD_IO = Status.create(Status.Codes.ACNET_HARD_IO)
ACNET_NODE_DOWN = Status.create(Status.Codes.ACNET_NODE_DOWN)
ACNET_SYS = Status.create(Status.Codes.ACNET_SYS)
ACNET_NXE = Status.create(Status.Codes.ACNET_NXE)
ACNET_BUG = Status.create(Status.Codes.ACNET_BUG)
ACNET_NE1 = Status.create(Status.Codes.ACNET_NE1)
ACNET_NE2 = Status.create(Status.Codes.ACNET_NE2)
ACNET_NE3 = Status.create(Status.Codes.ACNET_NE3)
ACNET_UTIME = Status.create(Status.Codes.ACNET_UTIME)
ACNET_INVARG = Status.create(Status.Codes.ACNET_INVARG)
ACNET_MEMFAIL = Status.create(Status.Codes.ACNET_MEMFAIL)
ACNET_NO_HANDLE = Status.create(Status.Codes.ACNET_NO_HANDLE)
