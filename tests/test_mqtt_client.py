# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.

import asyncio
import json

import pytest

from voltkeeper.bus import EventBus, ParserMessage
from voltkeeper.mqtt_client import (
    CHARGING_STATUS_MAP,
    COMMAND_TOPIC_RE,
    NORMAL_DEVICE_FIELDS,
    MQTTClient,
    MqttFieldType,
)


class TestMqttClient:
    def test_command_topic_re_matches(self):
        m = COMMAND_TOPIC_RE.match("bluetti/command/AC2A-12345678/ac_output")
        assert m is not None
        assert m[1] == "AC2A"
        assert m[2] == "12345678"
        assert m[3] == "ac_output"

    def test_command_topic_re_non_matches(self):
        assert COMMAND_TOPIC_RE.match("bluetti/state/AC2A-123/total_battery_percent") is None
        assert COMMAND_TOPIC_RE.match("other/command/AC2A-123/ac_output") is None
        assert COMMAND_TOPIC_RE.match("bluetti/command/abc") is None

    def test_normal_fields_have_battery_keys(self):
        assert "packTotalSoc" in NORMAL_DEVICE_FIELDS
        assert "packTotalVoltage" in NORMAL_DEVICE_FIELDS
        assert "packChargingStatus" in NORMAL_DEVICE_FIELDS

    def test_normal_fields_have_power_keys(self):
        assert "totalPVPower" in NORMAL_DEVICE_FIELDS
        assert "totalACPower" in NORMAL_DEVICE_FIELDS
        assert "totalDCPower" in NORMAL_DEVICE_FIELDS

    def test_normal_fields_have_control_keys(self):
        assert "ac_output" in NORMAL_DEVICE_FIELDS
        assert "dc_output" in NORMAL_DEVICE_FIELDS
        assert "charging_mode" in NORMAL_DEVICE_FIELDS
        assert "power_off" in NORMAL_DEVICE_FIELDS

    def test_bool_field_config(self):
        config = NORMAL_DEVICE_FIELDS["ac_output"]
        assert config.type == MqttFieldType.BOOL
        assert config.setter is True
        assert config.advanced is False

    def test_enum_field_config(self):
        config = NORMAL_DEVICE_FIELDS["charging_mode"]
        assert config.type == MqttFieldType.ENUM
        assert config.setter is True
        assert "options" in config.home_assistant_extra

    def test_button_field_config(self):
        config = NORMAL_DEVICE_FIELDS["power_off"]
        assert config.type == MqttFieldType.BUTTON
        assert config.home_assistant_extra["payload_press"] == "ON"

    def test_ha_payload_has_device_info(self, ac2a_device):
        from unittest.mock import MagicMock

        bus = MagicMock()
        mqtt = MQTTClient(bus, "localhost", "none")
        config = NORMAL_DEVICE_FIELDS["packTotalSoc"]
        payload = mqtt._ha_config_payload("packTotalSoc", ac2a_device, config)

        data = json.loads(payload)
        assert "device" in data
        assert data["device"]["manufacturer"] == "Bluetti"
        assert data["device"]["model"] == "AC2A"
        assert "TEST" in data["device"]["identifiers"]

    def test_ha_payload_setter_has_command_topic(self, ac2a_device):
        from unittest.mock import MagicMock

        bus = MagicMock()
        mqtt = MQTTClient(bus, "localhost", "none")
        config = NORMAL_DEVICE_FIELDS["ac_output"]
        payload = mqtt._ha_config_payload("ac_output", ac2a_device, config)

        data = json.loads(payload)
        assert "command_topic" in data
        # command_topic must use the field key ("ac_output"), not topic_name
        # ("ac_output_on"), so that _handle_command can match it in
        # NORMAL_DEVICE_FIELDS and dispatch the write correctly.
        assert data["command_topic"] == "bluetti/command/AC2A-TEST/ac_output"

    def test_ha_payload_nonsetter_no_command_topic(self, ac2a_device):
        from unittest.mock import MagicMock

        bus = MagicMock()
        mqtt = MQTTClient(bus, "localhost", "none")
        config = NORMAL_DEVICE_FIELDS["packTotalSoc"]
        payload = mqtt._ha_config_payload("packTotalSoc", ac2a_device, config)

        data = json.loads(payload)
        assert "command_topic" not in data
        assert data["state_topic"] == "bluetti/state/AC2A-TEST/total_battery_percent"

    def test_charging_status_map(self):
        assert CHARGING_STATUS_MAP[0] == "IDLE"
        assert CHARGING_STATUS_MAP[1] == "CHARGING"
        assert CHARGING_STATUS_MAP[2] == "DISCHARGING"
        assert CHARGING_STATUS_MAP[3] == "FLOATING"

    def test_all_fields_have_topic_name(self):
        for name, config in NORMAL_DEVICE_FIELDS.items():
            assert config.topic_name is not None, f"{name} missing topic_name"

    def test_topic_names_are_snake_case(self):
        for name, config in NORMAL_DEVICE_FIELDS.items():
            topic = config.topic_name
            assert topic, f"{name} has empty topic_name"
            assert "_" in topic or topic.islower(), f"{name} topic '{topic}' not snake_case"
            assert topic == topic.lower(), f"{name} topic '{topic}' has uppercase"

    def test_battery_fields_match_bluetti_mqtt(self):
        assert NORMAL_DEVICE_FIELDS["packTotalSoc"].topic_name == "total_battery_percent"
        assert NORMAL_DEVICE_FIELDS["packTotalVoltage"].topic_name == "total_battery_voltage"
        assert NORMAL_DEVICE_FIELDS["packTotalCurrent"].topic_name == "total_battery_current"

    def test_control_fields_match_bluetti_mqtt(self):
        assert NORMAL_DEVICE_FIELDS["ac_output"].topic_name == "ac_output_on"
        assert NORMAL_DEVICE_FIELDS["dc_output"].topic_name == "dc_output_on"
        assert NORMAL_DEVICE_FIELDS["chargingMode"].topic_name == "charging_mode"
        assert NORMAL_DEVICE_FIELDS["power_lifting"].topic_name == "power_lifting_on"

    def test_listener_registered_exactly_once_at_init(self):
        """MQTTClient must register its listener at construction, not inside run()."""
        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        # Exactly one listener after construction — not zero (added too late)
        # and not growing on every reconnect.
        assert len(bus.parser_listeners) == 1
        assert bus.parser_listeners[0] == mqtt.handle_message

    # ── _handle_message publish path ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_handle_message_publishes_numeric(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"packTotalSoc": 85}),
        )

        mock_client.publish.assert_called_once()
        (topic,) = [c.args[0] for c in mock_client.publish.call_args_list]
        assert topic == "bluetti/state/AC2A-TEST/total_battery_percent"
        payload = mock_client.publish.call_args.kwargs["payload"]
        assert payload == b"85"

    @pytest.mark.asyncio
    async def test_handle_message_publishes_bool_on_off(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"ac_output": True}),
        )
        payload = mock_client.publish.call_args.kwargs["payload"]
        assert payload == b"ON"

        mock_client.publish.reset_mock()
        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"ac_output": False}),
        )
        payload = mock_client.publish.call_args.kwargs["payload"]
        assert payload == b"OFF"

    @pytest.mark.asyncio
    async def test_handle_message_time_to_full_scaled(self, ac2a_device):
        """packChgFullTime raw value is ×6 to convert 0.1h units to minutes."""
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        # charging → time_to_full should be published, time_to_empty skipped
        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"packChargingStatus": 1, "packChgFullTime": 10}),
        )
        calls = {c.args[0]: c.kwargs["payload"] for c in mock_client.publish.call_args_list}
        assert "bluetti/state/AC2A-TEST/time_to_full_minutes" in calls
        assert calls["bluetti/state/AC2A-TEST/time_to_full_minutes"] == b"60"
        assert "bluetti/state/AC2A-TEST/time_to_empty_minutes" not in calls

    @pytest.mark.asyncio
    async def test_handle_message_time_to_empty_skipped_when_charging(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        # discharging → time_to_empty published, time_to_full skipped
        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"packChargingStatus": 2, "packDsgEmptyTime": 20}),
        )
        calls = {c.args[0]: c.kwargs["payload"] for c in mock_client.publish.call_args_list}
        assert "bluetti/state/AC2A-TEST/time_to_empty_minutes" in calls
        assert calls["bluetti/state/AC2A-TEST/time_to_empty_minutes"] == b"120"
        assert "bluetti/state/AC2A-TEST/time_to_full_minutes" not in calls

    @pytest.mark.asyncio
    async def test_handle_message_charging_status_enum(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"packChargingStatus": 2}),
        )
        calls = {c.args[0]: c.kwargs["payload"] for c in mock_client.publish.call_args_list}
        assert calls["bluetti/state/AC2A-TEST/pack_charging_status"] == b"DISCHARGING"

    @pytest.mark.asyncio
    async def test_handle_message_unknown_field_skipped(self, ac2a_device):
        from unittest.mock import AsyncMock, MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mock_client = MagicMock()
        mock_client.publish = AsyncMock()

        await mqtt._handle_message(
            mock_client,
            ParserMessage(ac2a_device, {"notAKnownField": 99}),
        )
        mock_client.publish.assert_not_called()

    # ── _handle_command dispatch path ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_handle_command_bool_on_puts_write_command(self, ac2a_device_num):
        from unittest.mock import MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mqtt.devices.append(ac2a_device_num)

        received = []
        bus.add_command_listener(lambda msg: received.append(msg))

        mock_msg = MagicMock()
        mock_msg.topic = MagicMock()
        mock_msg.topic.__str__ = lambda self: "bluetti/command/AC2A-12345678/ac_output"
        mock_msg.payload = b"ON"

        bus_task = asyncio.create_task(bus.run())
        await mqtt._handle_command(mock_msg)
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].command.address == 2011
        assert received[0].command.value == 1

    @pytest.mark.asyncio
    async def test_handle_command_bool_off(self, ac2a_device_num):
        from unittest.mock import MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        mqtt.devices.append(ac2a_device_num)

        received = []
        bus.add_command_listener(lambda msg: received.append(msg))

        mock_msg = MagicMock()
        mock_msg.topic.__str__ = lambda self: "bluetti/command/AC2A-12345678/dc_output"
        mock_msg.payload = b"OFF"

        bus_task = asyncio.create_task(bus.run())
        await mqtt._handle_command(mock_msg)
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 1
        assert received[0].command.address == 2012
        assert received[0].command.value == 0

    @pytest.mark.asyncio
    async def test_handle_command_unknown_topic_ignored(self, ac2a_device_num):
        from unittest.mock import MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")

        received = []
        bus.add_command_listener(lambda msg: received.append(msg))

        mock_msg = MagicMock()
        mock_msg.topic.__str__ = lambda self: "bluetti/command/bad-topic"
        mock_msg.payload = b"ON"

        bus_task = asyncio.create_task(bus.run())
        await mqtt._handle_command(mock_msg)
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_handle_command_unknown_device_ignored(self, ac2a_device_num):
        from unittest.mock import MagicMock

        bus = EventBus()
        mqtt = MQTTClient(bus, "localhost", "none")
        # ac2a_device_num NOT added to mqtt.devices — valid format but unknown device

        received = []
        bus.add_command_listener(lambda msg: received.append(msg))

        mock_msg = MagicMock()
        mock_msg.topic.__str__ = lambda self: "bluetti/command/AC2A-99999999/ac_output"
        mock_msg.payload = b"ON"

        bus_task = asyncio.create_task(bus.run())
        await mqtt._handle_command(mock_msg)
        await asyncio.sleep(0.05)
        bus_task.cancel()

        assert len(received) == 0
