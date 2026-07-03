# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from voltkeeper.core.devices.bluetti_device import BluettiDevice


def test_decode_ctrl_event_default_returns_none():

    class MinimalDevice(BluettiDevice):
        def parse(self, address, data):
            return {}

        def has_field(self, field):
            return False

        def has_field_setter(self, field):
            return False

        def build_setter_command(self, field, value):
            raise NotImplementedError

        @property
        def polling_commands(self):
            return []

        @property
        def logging_commands(self):
            return []

    d = MinimalDevice("00:00:00:00:00:00", "TEST", "123")
    assert d.decode_ctrl_event(0) is None


def test_deviceresult2():
    from voltkeeper.core.devices.v2_base import V2_CTRL_EVENT_BITS, decode_ctrl_event

    caps = decode_ctrl_event(0)
    assert all(not v for v in caps.values())
    assert len(caps) == len(V2_CTRL_EVENT_BITS)


def test_decode_ctrl_event_all_on():
    from voltkeeper.core.devices.v2_base import V2_CTRL_EVENT_BITS, decode_ctrl_event

    max_val = (1 << len(V2_CTRL_EVENT_BITS)) - 1
    caps = decode_ctrl_event(max_val)
    assert all(caps.values())


def test_device_registry_is_public():
    from voltkeeper.bluetooth import device_registry

    reg = device_registry()
    assert "AC2A" in reg


def test_is_supported_device_type():
    from voltkeeper.bluetooth import is_supported_device_type

    assert is_supported_device_type("AC2A") is True
    assert is_supported_device_type("BOGUS") is False
