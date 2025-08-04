from dataclasses import dataclass
from typing import Optional, Union, Iterable
from python_graphql_client import GraphqlClient

class ACSysApiError(Exception):
    def __init__(self, message: str):
        super().__init__(message)

# A GraphQL query to return a "one-shot" read. The list of device
# names can only represent device information -- not sample event or
# data logger parameters.

_READ_DEVICES_ = """
query ReadDevices ($devs: [String!]!) {
    acceleratorData (deviceList: $devs) {
        data {
            timestamp
            result {
                ... on Scalar {
                    scalarValue
                }
                ... on ScalarArray {
                   scalarArrayValue
                }
                ... on Raw {
                   rawValue
                }
            }
        }
    }
}
"""

@dataclass(frozen=True)
class Reading:
    """Holds information related to a device reading.

    A reading consists of a timestamp and value. `timestamp` is in UTC
    time and is seconds (and fractional seconds) since the UNIX Epoch.
    `value` is the device value when it was sampled. It can be of any
    type that devices can return.

    """

    timestamp: float
    value: float

# Class that interacts with the ACSys GraphQL API.

class ACSys:
    """Interact with Fermilab's ACSys GraphQL API

    This object cn be used to access accelerator information including
    device meta-information, readings, and historical data. If proper
    credentials are provided, it also allows control of devices.

    """

    def __init__(self, jwt: Optional[str] = None):
        """Creates an instance of `ACSys`.

        Arg:

            jwt (str): A Javascript Web Token (JWT). How this token is
                obtained is beyond the scope of this package. The JWT
                holds authorization infomation for a user.
        """

        # If the caller has a JWT, use it for all the requests.

        if jwt is None or (not isinstance(jwt, str)):
            headers = {}
        else:
            headers = { 'Authorization': f"Bearer {jwt}" }

        # Create the two connections to the GraphQL service.

        self._query = GraphqlClient(
            endpoint="https://acsys-proxy.fnal.gov:8001/acsys",
            headers=headers
        )
        self._subscription = GraphqlClient(
            endpoint="https://acsys-proxy.fnal.gov:8001/acsys/s",
            headers=headers
        )

    # Private method to convert an item of a reading reply. It knows
    # all the possible types that can be returned an converts them
    # into native Python types.

    def _convertItem(item):
        timestamp = item['timestamp']
        result = item['result']

        if 'scalarValue' in result:
            value = result['scalarValue']
        elif 'scalarArrayValue' in result:
            value = result['scalarArrayValue']
        elif 'rawValue' in result:
            value = bytearray(result['rawValue'])
        elif 'textValue' in result:
            value = result['textValue']
        elif 'textArrayValue' in result:
            value = result['textArrayValue']
        else:
            value = None

        return Reading(timestamp = timestamp, value = value)

    # Private method to convert the entire reading reply. This is a
    # generator function.

    def _convertReply(reply):
        if 'acceleratorData' in reply['data']:
            for item in reply['data']['acceleratorData']:
                data = item['data']

                if len(data) == 1:
                    yield ACSys._convertItem(data[0])
                elif len(data) > 1:
                    yield [ACSys._convertItem(point) for point in data]
                else:
                    yield None
        else:
            raise ACSysApiError(message=reply['error'])

    # Method that does a "one-shot" on a set of devices.

    def readDevices(self, devices: Union[str, Iterable[str]]) -> Union[Reading, tuple[Reading, ...]]:
        """Return the current reading for one or more devices.

        This function returns the latest reading for the specified
        devices. `devices` can be a list, a tuple, or an iterator of
        strings. If `devices` is a string, it specifies a single
        device to read.

        Each element of `devices` is a "device specification" as
        defined in the DRF spec. Only the device portion of DRF is
        used -- no event or data logger specification is allowed. This
        means you can use the array notation for array devices, you
        can specify different properties (used by ACNET devices), use
        PV names (for EPICS devices), and use field names.

        Examples:

            acsys = ACSys()

            # Read outdoor temperature

            temp = acsys.readDevices("M:OUTTMP")
            print(f"{temp.timestamp} : {temp.value} F")

            # Read all elements of Z:CUBE

            cube = acsys.readDevices("Z:CUBE[]")
            print(f"{cube.timestamp} : {cube.value}")

            # Read both with one request (much more efficient than
            # making separate requests!)

            (temp, cube) = acsys.readDevices(("M:OUTTMP", "Z:CUBE[]"))

        Arg:
            devices: A list of strings or a single string, each
                representing a device specification.

        Returns:
            tuple: A tuple containing the readings. The size of the
                tuple will match the number of device specifications.
                If there is only one device, it returns the reading
                instead of 1-tuple.

        """

        # If the parameter is a string, we need to wrap it in a
        # list. Strings are iterable so, if we don't do this, we end
        # up with an iterator yielding device names consisting of
        # single characters. This is not what the user wants.

        if isinstance(devices, str):
            devices = [devices]

        # Perform the query and process the results.

        reply = self._query.execute(
            query=_READ_DEVICES_,
            variables={ "devs": list(devices) }
        )
        result = tuple(ACSys._convertReply(reply))

        # Don't return a 1-tuple.

        if len(result) == 1:
            return result[0]
        else:
            return result
