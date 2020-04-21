class Status(Exception):
    """An ACNET status type."""

    def __init__(self, val):
        """Creates a status value which is initialized with the supplied
        value.
        """
        self.value = val

    @property
    def facility(self):
        """Returns the 'facility' code of a status value."""
        return self.value & 255

    @property
    def errCode(self):
        """Returns the 'error' code of a status value."""
        return self.value / 256

    def isSuccess(self):
        """Returns True if the status represents a success status."""
        return self.errCode == 0

    def isFatal(self):
        """Returns True if the status represents a fatal status."""
        return self.errCode < 0

    def isWarning(self):
        """Returns True if the status represents a warning status."""
        return self.errCode > 0

    def __eq__(self, other): return self.value == other.value

    def __ne__(self, other): return self.value != other.value

    def __str__(self):
        return '[' + str(self.facility) + ' ' + str(self.errCode) + ']'

# This section associates common ACNET status codes with the
# acnet.Status class.

Status.ACNET_SUCCESS =  Status(1 + 256 * 0)
Status.ACNET_PEND =     Status(1 + 256 * 1)
Status.ACNET_ENDMULT =  Status(1 + 256 * 2)

Status.ACNET_RETRY =    Status(1 + 256 * -1)
Status.ACNET_NOLCLMEM = Status(1 + 256 * -2)
Status.ACNET_NOREMMEM = Status(1 + 256 * -3)
Status.ACNET_RPLYPACK = Status(1 + 256 * -4)
Status.ACNET_REQPACK =  Status(1 + 256 * -5)
Status.ACNET_REQTMO =   Status(1 + 256 * -6)
