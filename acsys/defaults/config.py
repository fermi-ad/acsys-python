from dataclasses import dataclass
from dataclasses import field
from dataclasses import InitVar

@dataclass
class Defaults:
    """ Defaults is an class that when instantiated, contains defaults for 
        external parameters such as the hostname for the public proxy to
        connect to.  Parameters can be accessed and modified as properties
        of the class.
    
        Additional config items can be passed via a keyword argument to the
        constructor (init).  Example:

        config = Defaults(additional_config={'foo': 'bar'})

        NB: We need to override the "setter" for the environment data field.
            This is because we want to set defaults for all the other data 
            fields when the environment changes.  There is no easy way to 
            override a Dataclass "setter".  We need to define a property, but
            that isn't an intuititive process.  See:

            https://florimond.dev/en/posts/2018/10/reconciling-dataclasses-and-properties-in-python/

            for an explanation of the technique used in this class.
    """
    _environment: str = field(init=False, repr=False)
    proxy_hostname: str = field(default="")
    proxy_port: int = field(default=0)
    request_timeout_ms: int = field(default=0)
    async_timeout_ms: int = field(default=0)
    additional_config: dict = field(default_factory=dict)
    default_environment: InitVar[str] = "production"

    """ An enumeration of default configuration items.
    
       The top level key is the environment.  Switching environments will 
       overwrite all config values with the defaults for the selected 
       environment.  Items are exposed as properties and can be individually
       overridden using the property syntax.

       example:
            config = Defaults()
            # read a property:
            print(config.environment)

            # override a single value
            config.hostname = "foo"

            # switch environments (reset all values to default for environment)
            config.environment = "test"
    """
    default_enumeration = {
        "production": {
            "proxy_hostname": "prod.fnal.gov",
            "proxy_port": 80,
            "request_timeout_ms":  2000,
            "async_timeout_ms": 1000
        },
        "test": {
            "proxy_hostname": "test.fnal.gov",
            "proxy_port": 80,
            "request_timeout_ms": 2000,
            "async_timeout_ms": 1000
        }
    }

    """ A list of supported output types to return the contents of the current 
        configuration state
    """
    dump_formats = ['json']

    def __post_init__(self, default_environment, additional_config={}):
        """ Initializes the configuration object with defaults

        If environment is not specified in the init arguments, the environment
        will default to "production".
        """
        self.hostname = ""
        self.port = 0
        self.request_timeout = 0
        self.async_timeout = 0
        self.environment = default_environment

        [setattr(self, k, v) for k, v in self.additional_config.items()]

    def dump(self, format="json"):
        """ Outputs the current state of the configuration in the format specified
 
        The default format is JSON.  The method will check for valid format types.
        NB: Currently the ONLY supported output format is JSON
        """
        output = ""
        output_format = format.lower()
        
        if not output_format in Defaults.dump_formats: 
            raise ValueError("Argument value for format, '{format}', is not a valid value".format(format=format))

        if output_format == "json":
            template =  "{{ '{environment}': {{ 'proxy_hostname': '{hostname}', 'proxy_port': {port}, " \
                        "'request_timeout_ms': {request_timeout}, 'async_timeout_ms': {async_timeout} }} }}"
            output = template.format(environment=self.environment, hostname=self.hostname, port=self.port, \
                                     request_timeout=self.request_timeout, async_timeout=self.async_timeout)
        
        return output

    @property
    def environment(self):
        return self._environment

    @environment.setter
    def environment(self, environment):
        """ Sets the environment property.
        
        Switching environments will overwrite all config values with the 
        defaults for the selected environment.  Items are exposed as properties
        and can be individually overridden using the property syntax.
        """
        valid_environments = Defaults.default_enumeration.keys()
        if environment in valid_environments:
            self._environment = environment
            self.hostname = Defaults.default_enumeration[environment]["proxy_hostname"]
            self.port = Defaults.default_enumeration[environment]["proxy_port"]
            self.request_timeout =  Defaults.default_enumeration[environment]["request_timeout_ms"]
            self.async_timeout =  Defaults.default_enumeration[environment]["async_timeout_ms"]
        else:
            raise ValueError("Environment '{env}' is not a valid environment".format(env=environment))

def test_read_property():
    config = Defaults()
    assert config.hostname == "prod.fnal.gov", "test_read_property: Incorrect hostname"
    assert config.port == 80, "test_read_property: Incorrect port"
    assert config.request_timeout == 2000, "test_read_property: Incorrect request_timeout"
    assert config.async_timeout == 1000, "test_read_property: async_timeout hostname"

def test_set_property():
    """ Test that all properties are set correctly 
        (except the environment property, this is a special case)
    """
    config = Defaults()

    # Test hostname
    assert config.hostname == "prod.fnal.gov", "test_set_property: Incorrect hostname (initial value)"
    config.hostname = "whatever.fnal.gov"
    assert config.hostname == "whatever.fnal.gov", "test_set_property: Incorrect hostname (post value)"

    # Test port
    assert config.port == 80, "test_set_property: Incorrect port (initial value)"
    config.port = 81
    assert config.port == 81, "test_set_property: Incorrect port (post value)"

    # Test request_timeout
    assert config.request_timeout == 2000, "test_set_property: Incorrect request_timeout (initial value)"
    config.request_timeout = 2001
    assert config.request_timeout == 2001, "test_set_property: Incorrect request_timeout (post value)"

    # Test async_timeout
    assert config.async_timeout == 1000, "test_set_property: Incorrect async_timeout (initial value)"
    config.async_timeout = 1001
    assert config.async_timeout == 1001, "test_set_property: Incorrect async_timeout (post value)"

def test_dump_valid_format():
    """Do we want to be more pedantic with this test?
    e.g., do we want to validate the syntax of the format selected?
    """
    config = Defaults()
    expected_output = "{ 'production': { 'proxy_hostname': 'prod.fnal.gov', 'proxy_port': 80, 'request_timeout_ms': 2000, 'async_timeout_ms': 1000 } }"
    
    assert (config.dump(format="json") == expected_output), "test_dump_valid_format: JSON output did not match expected output"

def test_dump_invalid_format():
    """ Test that an exception is thrown when an invalid format is specified """
    config = Defaults()
    
    try:
        config.dump(format="garbage")
        assert False, "test_dump_invalid_format: did not throw an exception as expected"
    except ValueError:
        assert True

def test_set_valid_environment():
    config = Defaults()
    config.environment = "test"

    assert config.environment == "test", "test_set_valid_environment: Incorrect environment"
    assert config.hostname == "test.fnal.gov", "test_set_valid_environment: Incorrect hostname"
    assert config.port == 80, "test_set_valid_environment: Incorrect port"
    assert config.request_timeout == 2000, "test_set_valid_environment: Incorrect request_timeout"
    assert config.async_timeout == 1000, "test_set_valid_environment: Incorrect async_timeout"

def test_set_invalid_environment():
    config = Defaults()
    
    try:
        config.environment = "garbage"
        assert False, "test_set_invalid_environment: did not throw an exception as expected"
    except ValueError:
        assert True

def test_set_additional_config():
    config = Defaults(additional_config={'foo': 'bar'})
    assert (config.foo == 'bar'), "test_set_additional_config: Additional config 'baz' did not equal 'bar'"

def test_set_initial_environment():
    config = Defaults(default_environment="test")
    assert config.environment == "test", "test_set_valid_environment: Incorrect environment"
    assert config.hostname == "test.fnal.gov", "test_set_valid_environment: Incorrect hostname"
    assert config.port == 80, "test_set_valid_environment: Incorrect port"
    assert config.request_timeout == 2000, "test_set_valid_environment: Incorrect request_timeout"
    assert config.async_timeout == 1000, "test_set_valid_environment: Incorrect async_timeout"

if __name__ == "__main__":
    # Run tests
    test_read_property()
    test_set_property()
    test_dump_valid_format()
    test_dump_invalid_format()
    test_set_valid_environment()    
    test_set_invalid_environment()
    test_set_additional_config()
