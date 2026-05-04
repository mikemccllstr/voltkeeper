# ABOUTME: MQTT client — publishes device state and handles MQTT commands with Home Assistant auto-discovery.

import asyncio
from dataclasses import dataclass
from enum import auto, Enum, unique
import json
import logging
import re
from typing import List, Optional

from aiomqtt import Client, MqttError

from .bus import CommandMessage, EventBus, ParserMessage
from .core.commands import DeviceCommand
from .core.devices.bluetti_device import BluettiDevice


@unique
class MqttFieldType(Enum):
    NUMERIC = auto()
    BOOL = auto()
    ENUM = auto()
    BUTTON = auto()


@dataclass(frozen=True)
class MqttFieldConfig:
    type: MqttFieldType
    setter: bool
    advanced: bool
    home_assistant_extra: dict
    id_override: Optional[str] = None
    topic_name: Optional[str] = None


COMMAND_TOPIC_RE = re.compile(r"^bluetti/command/(\w+)-(\d+)/([a-z_]+)$")

NORMAL_DEVICE_FIELDS = {
    "packTotalSoc": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="total_battery_percent",
        home_assistant_extra={
            "name": "Total Battery Percent",
            "unit_of_measurement": "%",
            "device_class": "battery",
            "state_class": "measurement",
        },
    ),
    "packTotalVoltage": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=True,
        topic_name="total_battery_voltage",
        home_assistant_extra={
            "name": "Total Battery Voltage",
            "unit_of_measurement": "V",
            "device_class": "voltage",
            "state_class": "measurement",
            "force_update": True,
        },
    ),
    "packTotalCurrent": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=True,
        topic_name="total_battery_current",
        home_assistant_extra={
            "name": "Total Battery Current",
            "unit_of_measurement": "A",
            "device_class": "current",
            "state_class": "measurement",
            "force_update": True,
        },
    ),
    "packChargingStatus": MqttFieldConfig(
        type=MqttFieldType.ENUM,
        setter=False,
        advanced=False,
        topic_name="pack_charging_status",
        home_assistant_extra={
            "name": "Charging Status",
            "options": ["IDLE", "CHARGING", "DISCHARGING", "FLOATING"],
        },
    ),
    "chargingMode": MqttFieldConfig(
        type=MqttFieldType.ENUM,
        setter=False,
        advanced=False,
        topic_name="charging_mode",
        home_assistant_extra={
            "name": "Charging Mode",
            "icon": "mdi:battery-charging",
            "options": ["STANDARD", "TURBO", "SILENT"],
        },
    ),
    "packChgFullTime": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="time_to_full_minutes",
        home_assistant_extra={
            "name": "Time to Full",
            "unit_of_measurement": "min",
            "state_class": "measurement",
        },
    ),
    "packDsgEmptyTime": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="time_to_empty_minutes",
        home_assistant_extra={
            "name": "Time to Empty",
            "unit_of_measurement": "min",
            "state_class": "measurement",
        },
    ),
    "totalPVPower": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="dc_input_power",
        home_assistant_extra={
            "name": "PV Input Power",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "force_update": True,
        },
    ),
    "totalACPower": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="total_ac_power",
        home_assistant_extra={
            "name": "AC Output Power",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "force_update": True,
        },
    ),
    "totalDCPower": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="dc_output_power",
        home_assistant_extra={
            "name": "DC Output Power",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "force_update": True,
        },
    ),
    "totalGridPower": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=True,
        topic_name="total_grid_power",
        home_assistant_extra={
            "name": "Grid Power",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
            "force_update": True,
        },
    ),
    "totalPVChargingEnergy": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="total_pv_charging_energy",
        home_assistant_extra={
            "name": "Total PV Charging Energy",
            "unit_of_measurement": "Wh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    ),
    "totalGridChargingEnergy": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="total_grid_charging_energy",
        home_assistant_extra={
            "name": "Total Grid Charging Energy",
            "unit_of_measurement": "Wh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    ),
    "totalFeedbackEnergy": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=False,
        topic_name="total_feedback_energy",
        home_assistant_extra={
            "name": "Total Grid Feedback Energy",
            "unit_of_measurement": "Wh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    ),
    "totalDCEnergy": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=True,
        topic_name="total_dc_energy",
        home_assistant_extra={
            "name": "Total DC Output Energy",
            "unit_of_measurement": "Wh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    ),
    "totalACEnergy": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=True,
        topic_name="total_ac_energy",
        home_assistant_extra={
            "name": "Total AC Output Energy",
            "unit_of_measurement": "Wh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    ),
    "packDsgEnergyTotal": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=True,
        topic_name="total_discharged_energy",
        home_assistant_extra={
            "name": "Total Discharged Energy",
            "unit_of_measurement": "Wh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    ),
    "ambientTemp": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=True,
        topic_name="ambient_temperature",
        home_assistant_extra={
            "name": "Ambient Temperature",
            "unit_of_measurement": "\u00b0C",
            "device_class": "temperature",
            "state_class": "measurement",
        },
    ),
    "invMaxTemp": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=False,
        advanced=True,
        topic_name="inverter_temperature",
        home_assistant_extra={
            "name": "Inverter Max Temperature",
            "unit_of_measurement": "\u00b0C",
            "device_class": "temperature",
            "state_class": "measurement",
        },
    ),
    "ac_output": MqttFieldConfig(
        type=MqttFieldType.BOOL,
        setter=True,
        advanced=False,
        topic_name="ac_output_on",
        home_assistant_extra={
            "name": "AC Output",
            "device_class": "outlet",
        },
    ),
    "dc_output": MqttFieldConfig(
        type=MqttFieldType.BOOL,
        setter=True,
        advanced=False,
        topic_name="dc_output_on",
        home_assistant_extra={
            "name": "DC Output",
            "device_class": "outlet",
        },
    ),
    "power_off": MqttFieldConfig(
        type=MqttFieldType.BUTTON,
        setter=True,
        advanced=False,
        topic_name="power_off",
        home_assistant_extra={
            "name": "Power Off",
            "payload_press": "ON",
        },
    ),
    "dc_eco_mode": MqttFieldConfig(
        type=MqttFieldType.BOOL,
        setter=True,
        advanced=False,
        topic_name="dc_eco_mode",
        home_assistant_extra={
            "name": "DC ECO Mode",
            "icon": "mdi:sprout",
        },
    ),
    "ac_eco_mode": MqttFieldConfig(
        type=MqttFieldType.BOOL,
        setter=True,
        advanced=True,
        topic_name="ac_eco_mode",
        home_assistant_extra={
            "name": "AC ECO Mode",
            "icon": "mdi:sprout",
        },
    ),
    "charging_mode": MqttFieldConfig(
        type=MqttFieldType.ENUM,
        setter=True,
        advanced=False,
        topic_name="charging_mode",
        home_assistant_extra={
            "name": "Charging Mode",
            "icon": "mdi:battery-charging",
            "options": ["STANDARD", "TURBO", "SILENT"],
        },
    ),
    "power_lifting": MqttFieldConfig(
        type=MqttFieldType.BOOL,
        setter=True,
        advanced=True,
        topic_name="power_lifting_on",
        home_assistant_extra={
            "name": "Power Lifting",
            "icon": "mdi:arm-flex",
        },
    ),
    "battery_range_start": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=True,
        advanced=True,
        topic_name="battery_range_start",
        home_assistant_extra={
            "name": "Battery Range Start",
            "min": 0,
            "max": 100,
            "unit_of_measurement": "%",
        },
    ),
    "battery_range_end": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=True,
        advanced=True,
        topic_name="battery_range_end",
        home_assistant_extra={
            "name": "Battery Range End",
            "min": 0,
            "max": 100,
            "unit_of_measurement": "%",
        },
    ),
    "soc_low": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=True,
        advanced=True,
        topic_name="soc_low",
        home_assistant_extra={
            "name": "SOC Low Threshold",
            "min": 0,
            "max": 100,
            "unit_of_measurement": "%",
        },
    ),
    "soc_high": MqttFieldConfig(
        type=MqttFieldType.NUMERIC,
        setter=True,
        advanced=True,
        topic_name="soc_high",
        home_assistant_extra={
            "name": "SOC High Threshold",
            "min": 0,
            "max": 100,
            "unit_of_measurement": "%",
        },
    ),
}

CHARGING_STATUS_MAP = {0: "IDLE", 1: "CHARGING", 2: "DISCHARGING", 3: "FLOATING"}
CHARGING_MODE_MAP = {0: "STANDARD", 1: "TURBO", 2: "SILENT"}


class MQTTClient:
    def __init__(
        self,
        bus: EventBus,
        hostname: str,
        home_assistant_mode: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.bus = bus
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.home_assistant_mode = home_assistant_mode
        self.devices: List[BluettiDevice] = []
        self.message_queue: asyncio.Queue = None

    async def run(self):
        while True:
            logging.info("Connecting to MQTT broker...")
            try:
                async with Client(
                    hostname=self.hostname,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                ) as client:
                    logging.info("Connected to MQTT broker")
                    self.message_queue = asyncio.Queue()
                    self.bus.add_parser_listener(self.handle_message)

                    await asyncio.gather(
                        self._handle_commands(client),
                        self._handle_messages(client),
                    )
            except MqttError:
                logging.exception("MQTT error:")
                await asyncio.sleep(5)

    async def handle_message(self, msg: ParserMessage):
        await self.message_queue.put(msg)

    async def _handle_commands(self, client: Client):
        await client.subscribe("bluetti/command/#")
        async for mqtt_message in client.messages:
            if str(mqtt_message.topic).startswith("bluetti/command/"):
                await self._handle_command(mqtt_message)

    async def _handle_messages(self, client: Client):
        while True:
            msg: ParserMessage = await self.message_queue.get()
            if msg.device not in self.devices:
                await self._init_device(msg.device, client)
            await self._handle_message(client, msg)
            self.message_queue.task_done()

    async def _init_device(self, device: BluettiDevice, client: Client):
        self.devices.append(device)

        if self.home_assistant_mode == "none":
            return

        for name, field in NORMAL_DEVICE_FIELDS.items():
            if not device.has_field(name):
                continue
            if field.advanced and self.home_assistant_mode != "advanced":
                continue

            if field.type == MqttFieldType.NUMERIC:
                ha_type = "number" if field.setter else "sensor"
            elif field.type == MqttFieldType.BOOL:
                ha_type = "switch" if field.setter else "binary_sensor"
            elif field.type == MqttFieldType.ENUM:
                ha_type = "select" if field.setter else "sensor"
            elif field.type == MqttFieldType.BUTTON:
                ha_type = "button"

            topic_field = field.topic_name or name
            await client.publish(
                f"homeassistant/{ha_type}/{device.sn}_{topic_field}/config",
                payload=self._ha_config_payload(name, device, field).encode(),
                retain=True,
            )

        logging.info(
            f"Sent Home Assistant discovery for {device.type}-{device.sn}"
        )

    def _ha_config_payload(self, name: str, device: BluettiDevice, field: MqttFieldConfig) -> str:
        topic_field = field.topic_name or name
        ha_id = topic_field if not field.id_override else field.id_override
        payload_dict = {
            "state_topic": f"bluetti/state/{device.type}-{device.sn}/{topic_field}",
            "device": {
                "identifiers": [device.sn],
                "manufacturer": "Bluetti",
                "name": f"{device.type} {device.sn}",
                "model": device.type,
            },
            "unique_id": f"{device.sn}_{ha_id}",
            "object_id": f"{device.type}_{ha_id}",
        }
        if field.setter:
            payload_dict["command_topic"] = (
                f"bluetti/command/{device.type}-{device.sn}/{topic_field}"
            )
        payload_dict.update(field.home_assistant_extra)
        return json.dumps(payload_dict, separators=(",", ":"))

    async def _handle_command(self, mqtt_message):
        topic = str(mqtt_message.topic)
        m = COMMAND_TOPIC_RE.match(topic)
        if not m:
            logging.warning(f"Unknown command topic: {topic}")
            return

        device = next(
            (d for d in self.devices if d.type == m[1] and d.sn == m[2]), None
        )
        if not device:
            logging.warning(f"Unknown device: {m[1]} {m[2]}")
            return

        if not device.has_field_setter(m[3]):
            logging.warning(f"Field not writable: {m[3]} — {topic}")
            return

        field = NORMAL_DEVICE_FIELDS[m[3]]
        cmd: DeviceCommand = None

        if field.type == MqttFieldType.ENUM:
            value = mqtt_message.payload.decode("ascii")
            cmd = device.build_setter_command(m[3], value)
        elif field.type in (MqttFieldType.BOOL, MqttFieldType.BUTTON):
            value = mqtt_message.payload == b"ON"
            cmd = device.build_setter_command(m[3], value)
        elif field.type == MqttFieldType.NUMERIC:
            value = int(mqtt_message.payload.decode("ascii"))
            cmd = device.build_setter_command(m[3], value)

        if cmd:
            await self.bus.put(CommandMessage(device, cmd))

    async def _handle_message(self, client: Client, msg: ParserMessage):
        topic_prefix = f"bluetti/state/{msg.device.type}-{msg.device.sn}/"
        published = 0

        for name, value in msg.parsed.items():
            if name not in NORMAL_DEVICE_FIELDS:
                continue

            field = NORMAL_DEVICE_FIELDS[name]
            if field.type == MqttFieldType.NUMERIC:
                payload = str(value)
            elif field.type in (MqttFieldType.BOOL, MqttFieldType.BUTTON):
                payload = "ON" if value else "OFF"
            elif field.type == MqttFieldType.ENUM:
                if name == "packChargingStatus":
                    payload = CHARGING_STATUS_MAP.get(value, str(value))
                elif name == "chargingMode":
                    payload = CHARGING_MODE_MAP.get(value, str(value))
                elif hasattr(value, "name"):
                    payload = value.name
                else:
                    payload = str(value)
            else:
                continue

            topic_field = field.topic_name or name
            await client.publish(f"{topic_prefix}{topic_field}", payload=payload.encode())
            published += 1

        if published:
            logging.info(f"Published {published} fields for {msg.device.type}-{msg.device.sn}")
