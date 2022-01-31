from abc import abstractmethod, ABC
from enum import IntEnum

class Status(ABC):
    """An ACSys status type."""
    class Codes(IntEnum):
        """ACNET common status codes"""
        ACNET_SUCCESS = 1 + 256 * 0 
        """ACNET success code"""
        ACNET_PEND = 1 + 256 * 1
        """operation is pending"""
        ACNET_ENDMULT = 1 + 256 * 2
        """end multiple replies (on final reply)"""
        ACNET_RETRY = 1 + 256 * -1
        """retryable I/O error"""
        ACNET_NOLCLMEM = 1 + 256 * -2
        """no local memory available"""
        ACNET_NOREMMEM = 1 + 256 * -3
        """no remote memory available"""
        ACNET_RPLYPACK = 1 + 256 * -4
        """reply message packet assembly error"""
        ACNET_REQPACK = 1 + 256 * -5
        """request message packet assembly error"""
        ACNET_REQTMO = 1 + 256 * -6
        """request timeout with queued at destination"""
        ACNET_QUEFULL = 1 + 256 * -7
        """request failed, destination queue full"""
        ACNET_BUSY = 1 + 256 * -8
        """request failed, destination task busy"""
        ACNET_NOT_CONNECTED = 1 + 256 * -21
        """not connected to the network"""
        ACNET_ARG = 1 + 256 * -22
        """missing arguments"""
        ACNET_IVM = 1 + 256 * -23
        """invalid message length or buffer address"""
        ACNET_NO_SUCH = 1 + 256 * -24
        """no such request or reply"""
        ACNET_REQREJ = 1 + 256 * -25
        """request to destination task was rejected"""
        ACNET_CANCELLED = 1 + 256 * -26
        """request has been cancelled"""
        ACNET_NAME_IN_USE = 1 + 256 * -27
        """task name already in use"""
        ACNET_NCR = 1 + 256 * -28
        """not connected as a RUM task"""
        ACNET_NO_NODE = 1 + 256 * -30
        """no such logical node"""
        ACNET_TRUNC_REQUEST = 1 + 256 * -31
        """truncated request"""
        ACNET_TRUNC_REPLY = 1 + 256 * -32
        """truncated reply"""
        ACNET_NO_TASK = 1 + 256 * -33
        """no such destination task"""
        ACNET_DISCONNECTED = 1 + 256 * -34
        """replier task being disconnected"""
        ACNET_LEVEL2 = 1 + 256 * -35
        """ACNET level II function error"""
        ACNET_HARD_IO = 1 + 256 * -41
        """hard I/O error"""
        ACNET_NODE_DOWN = 1 + 256 * -42
        """logical node down or offline"""
        ACNET_SYS = 1 + 256 * -43
        """system service error"""
        ACNET_NXE = 1 + 256 * -44
        """untranslatable error"""
        ACNET_BUG = 1 + 256 * -45
        """network internal error"""
        ACNET_NE1 = 1 + 256 * -46
        """VMS exceeded some quota or limit"""
        ACNET_NE2 = 1 + 256 * -47
        """VMS no address for request/reply ID word"""
        ACNET_NE3 = 1 + 256 * -48
        """VMS buffer/control block vector in use or block already locked"""
        ACNET_UTIME = 1 + 256 * -49
        """user-generated network timeout"""
        ACNET_INVARG = 1 + 256 * -50
        """invalid argument passed"""
        ACNET_MEMFAIL = 1 + 256 * -51
        """memory allocation failed"""
        ACNET_NO_HANDLE = 1 + 256 * -52
        """requested handle doesn't exist"""

    @abstractmethod
    def __init__(self) -> None:
        """
        Use Status.create(val), or specific AcnetXXX() class instead.
        """
        pass

    def _set_val(self, val):
        """Set's supplied value, which must be in the range of signed, 16-bit
        integers. 
        Do not use this method directly, use Status.create(val), or
        specific AcnetXXX() class instead.
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
            st = _SuccessStatus()
            st._set_val(Status.Codes.ACNET_SUCCESS)
            return st
        # Non-error codes
        elif val == Status.Codes.ACNET_SUCCESS or \
                val == Status.Codes.ACNET_PEND or \
                val == Status.Codes.ACNET_ENDMULT:
            st = _SuccessStatus()
            st._set_val(val)
            return st
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

class _SuccessStatus(Status):
    def __init__(self) -> None:
        pass

# Clases that specialize Status - based on code, that can be captured on different except clauses
class AcnetException(Status, Exception):
    """Use this to capture error statuses"""
    pass

class AcnetRetryIOError(AcnetException):
    """retryable I/O error"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_RETRY)
        Exception.__init__(self)

class AcnetNoLocalMemory(AcnetException):
    """no local memory available"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NOLCLMEM)
        Exception.__init__(self)

class AcnetNoRemoteMemory(AcnetException):
    """no remote memory available"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NOREMMEM)
        Exception.__init__(self)

class AcnetReplyMessagePacketAssemblyError(AcnetException):
    """reply message packet assembly error"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_RPLYPACK)
        Exception.__init__(self)

class AcnetRequestMessagePacketAssemblyError(AcnetException):
    """request message packet assembly error"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_REQPACK)
        Exception.__init__(self)

class AcnetRequestTimeOutQueuedAtDestination(AcnetException):
    """request timeout with queued at destination"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_REQTMO)
        Exception.__init__(self)

class AcnetDestinationQueueFull(AcnetException):
    """request failed, destination queue full"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_QUEFULL)
        Exception.__init__(self)

class AcnetDestinationBusy(AcnetException):
    """request failed, destination task busy"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_BUSY)
        Exception.__init__(self)

class AcnetNotConnected(AcnetException):
    """not connected to the network"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NOT_CONNECTED)
        Exception.__init__(self)

class AcnetMissingArguments(AcnetException):
    """missing arguments"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_ARG)
        Exception.__init__(self)

class AcnetInvalidMessageLengthOrBufferAddress(AcnetException):
    """invalid message length or buffer address"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_IVM)
        Exception.__init__(self)

class AcnetNoSuchRequestOrReply(AcnetException):
    """no such request or reply"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NO_SUCH)
        Exception.__init__(self)

class RequestToDestinationTaskRejected(AcnetException):
    """request to destination task was rejected"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_REQREJ)
        Exception.__init__(self)

class RequestedCancelled(AcnetException):
    """request has been cancelled"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_CANCELLED)
        Exception.__init__(self)

class AcnetNameAlreadyInUse(AcnetException):
    """task name already in use"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NAME_IN_USE)
        Exception.__init__(self)

class AcnetNotConnectedAsRumTask(AcnetException):
    """not connected as a RUM task"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NCR)
        Exception.__init__(self)

class AcnetNoSuchLogicalNode(AcnetException):
    """no such logical node"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NO_NODE)
        Exception.__init__(self)

class AcnetTruncatedRequest(AcnetException):
    """truncated request"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_TRUNC_REQUEST)
        Exception.__init__(self)

class AcnetTruncatedReply(AcnetException):
    """truncated reply"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_TRUNC_REPLY)
        Exception.__init__(self)

class AcnetNoSuchDestinationTask(AcnetException):
    """no such destination task"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NO_TASK)
        Exception.__init__(self)

class AcnetReplyTaskDisconnected(AcnetException):
    """replier task being disconnected"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_DISCONNECTED)
        Exception.__init__(self)

class AcnetLevel2FunctionError(AcnetException):
    """ACNET level II function error"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_LEVEL2)
        Exception.__init__(self)

class AcnetHardIOError(AcnetException):
    """hard I/O error"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_HARD_IO)
        Exception.__init__(self)

class AcnetLogicalNodeDownOffline(AcnetException):
    """logical node down or offline"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NODE_DOWN)
        Exception.__init__(self)

class AcnetSystemServiceError(AcnetException):
    """system service error"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_SYS)
        Exception.__init__(self)

class AcnetUntranslatableError(AcnetException):
    """untranslatable error"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NXE)
        Exception.__init__(self)

class AcnetNetworkInternalError(AcnetException):
    """network internal error"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_BUG)
        Exception.__init__(self)

class AcnetNE1_VMSExceededQuota(AcnetException):
    """VMS exceeded some quota or limit"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NE1)
        Exception.__init__(self)

class AcnetNE2_VMSNoAdressForRequestOrReply(AcnetException):
    """VMS no address for request/reply ID word"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NE2)
        Exception.__init__(self)

class AcnetNE3_VMSBufferInUse(AcnetException):
    """VMS buffer/control block vector in use or block already locked"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NE3)
        Exception.__init__(self)

class AcnetUserGeneratedNetworkTimeout(AcnetException):
    """user-generated network timeout"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_UTIME)
        Exception.__init__(self)

class AcnetInvalidArgumentPassed(AcnetException):
    """invalid argument passed"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_INVARG)
        Exception.__init__(self)

class AcnetMemoryAllocationFailed(AcnetException):
    """memory allocation failed"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_MEMFAIL)
        Exception.__init__(self)

class AcnetNoRequestHandle(AcnetException):
    """requested handle doesn't exist"""
    def __init__(self):
        self._set_val(Status.Codes.ACNET_NO_HANDLE)
        Exception.__init__(self)

# Objects that represent an instance of each status, so they can be compared
# inside an except clause.
ACNET_SUCCESS = Status.create(Status.Codes.ACNET_SUCCESS)
ACNET_PEND = Status.create(Status.Codes.ACNET_PEND)
ACNET_ENDMULT = Status.create(Status.Codes.ACNET_ENDMULT)

# TODO these globals can be used but are redundant.
# Should be deleted on subsequent versions
ACNET_RETRY = Status.create(Status.Codes.ACNET_RETRY) 
""" @deprecated: Use AcnetRetryIOError() instead """
ACNET_NOLCLMEM = Status.create(Status.Codes.ACNET_NOLCLMEM)
""" @deprecated: Use AcnetNoLocalMemory() instead """
ACNET_NOREMMEM = Status.create(Status.Codes.ACNET_NOREMMEM)
""" @deprecated: Use AcnetNoRemoteMemory() instead """
ACNET_RPLYPACK = Status.create(Status.Codes.ACNET_RPLYPACK)
""" @deprecated: Use AcnetReplyMessagePacketAssemblyError() instead """
ACNET_REQPACK = Status.create(Status.Codes.ACNET_REQPACK)
""" @deprecated: Use AcnetRequestMessagePacketAssemblyError() instead """
ACNET_REQTMO = Status.create(Status.Codes.ACNET_REQTMO)
""" @deprecated: Use AcnetRequestTimeOutQueuedAtDestination() instead """
ACNET_QUEFULL = Status.create(Status.Codes.ACNET_QUEFULL)
""" @deprecated: Use AcnetDestinationQueueFull() instead """
ACNET_BUSY = Status.create(Status.Codes.ACNET_BUSY)
""" @deprecated: Use AcnetDestinationBusy() instead """
ACNET_NOT_CONNECTED = Status.create(Status.Codes.ACNET_NOT_CONNECTED)
""" @deprecated: Use AcnetNotConnected() instead """
ACNET_ARG = Status.create(Status.Codes.ACNET_ARG)
""" @deprecated: Use AcnetMissingArguments() instead """
ACNET_IVM = Status.create(Status.Codes.ACNET_IVM)
""" @deprecated: Use AcnetInvalidMessageLengthOrBufferAddress() instead """
ACNET_NO_SUCH = Status.create(Status.Codes.ACNET_NO_SUCH)
""" @deprecated: Use AcnetNoSuchRequestOrReply() instead """
ACNET_REQREJ = Status.create(Status.Codes.ACNET_REQREJ)
""" @deprecated: Use RequestToDestinationTaskRejected() instead """
ACNET_CANCELLED = Status.create(Status.Codes.ACNET_CANCELLED)
""" @deprecated: Use RequestedCancelled() instead """
ACNET_NAME_IN_USE = Status.create(Status.Codes.ACNET_NAME_IN_USE)
""" @deprecated: Use AcnetNameAlreadyInUse() instead """
ACNET_NCR = Status.create(Status.Codes.ACNET_NCR)
""" @deprecated: Use AcnetNotConnectedAsRumTask() instead """
ACNET_NO_NODE = Status.create(Status.Codes.ACNET_NO_NODE)
""" @deprecated: Use AcnetNoSuchLogicalNode() instead """
ACNET_TRUNC_REQUEST = Status.create(Status.Codes.ACNET_TRUNC_REQUEST)
""" @deprecated: Use AcnetTruncatedRequest() instead """
ACNET_TRUNC_REPLY = Status.create(Status.Codes.ACNET_TRUNC_REPLY)
""" @deprecated: Use AcnetTruncatedReply() instead """
ACNET_NO_TASK = Status.create(Status.Codes.ACNET_NO_TASK)
""" @deprecated: Use AcnetNoSuchDestinationTask() instead """
ACNET_DISCONNECTED = Status.create(Status.Codes.ACNET_DISCONNECTED)
""" @deprecated: Use AcnetReplyTaskDisconnected() instead """
ACNET_LEVEL2 = Status.create(Status.Codes.ACNET_LEVEL2)
""" @deprecated: Use AcnetLevel2FunctionError() instead """
ACNET_HARD_IO = Status.create(Status.Codes.ACNET_HARD_IO)
""" @deprecated: Use AcnetHardIOError() instead """
ACNET_NODE_DOWN = Status.create(Status.Codes.ACNET_NODE_DOWN)
""" @deprecated: Use AcnetLogicalNodeDownOffline() instead """
ACNET_SYS = Status.create(Status.Codes.ACNET_SYS)
""" @deprecated: Use AcnetSystemServiceError() instead """
ACNET_NXE = Status.create(Status.Codes.ACNET_NXE)
""" @deprecated: Use AcnetUntranslatableError() instead """
ACNET_BUG = Status.create(Status.Codes.ACNET_BUG)
""" @deprecated: Use AcnetNetworkInternalError() instead """
ACNET_NE1 = Status.create(Status.Codes.ACNET_NE1)
""" @deprecated: Use AcnetNE1_VMSExceededQuota() instead """
ACNET_NE2 = Status.create(Status.Codes.ACNET_NE2)
""" @deprecated: Use AcnetNE2_VMSNoAdressForRequestOrReply() instead """
ACNET_NE3 = Status.create(Status.Codes.ACNET_NE3)
""" @deprecated: Use AcnetNE3_VMSBufferInUse() instead """
ACNET_UTIME = Status.create(Status.Codes.ACNET_UTIME)
""" @deprecated: Use AcnetUserGeneratedNetworkTimeout() instead """
ACNET_INVARG = Status.create(Status.Codes.ACNET_INVARG)
""" @deprecated: Use AcnetInvalidArgumentPassed() instead """
ACNET_MEMFAIL = Status.create(Status.Codes.ACNET_MEMFAIL)
""" @deprecated: Use AcnetMemoryAllocationFailed() instead """
ACNET_NO_HANDLE = Status.create(Status.Codes.ACNET_NO_HANDLE)
""" @deprecated: Use AcnetNoRequestHandle() instead """
