# ABOUTME: Unit tests for voltkeeper — see test class docstrings for specifics.


from voltkeeper.core.devices.ac2a import AC2A


class TestTopologyDiscovery:
    def test_discover_topology_finds_packs(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        assert not v2._topology_discovered
        assert v2._discovered_packs == []

        tlv_data = bytearray(TLV_MAGIC)
        tlv_data.append(0x29)
        tlv_data.extend(b"\x17\x70\x00\x20")
        tlv_data.extend(b"\x00" * 32)
        tlv_data.extend(b"\x00\x00")
        v2.discover_topology(bytes(tlv_data))
        assert v2._topology_discovered
        assert 0x29 in v2._discovered_packs

    def test_discover_topology_empty_response(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2.discover_topology(bytes(TLV_MAGIC))
        assert v2._topology_discovered
        assert v2._discovered_packs == []

    def test_discover_topology_no_magic(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2.discover_topology(b"\x00\x00\x00\x00")
        assert v2._topology_discovered
        assert v2._discovered_packs == []

    def test_polling_commands_includes_packs_when_discovered(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        initial = {cmd.starting_address for cmd in v2.polling_commands}
        assert 6000 not in initial

        tlv_data = bytearray(TLV_MAGIC)
        tlv_data.append(0x29)
        tlv_data.extend(b"\x17\x70\x00\x20")
        tlv_data.extend(b"\x00" * 32)
        tlv_data.extend(b"\x00\x00")
        v2.discover_topology(bytes(tlv_data))
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 6000 in addrs

    def test_polling_commands_no_packs_by_default(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 6000 not in addrs

    def test_topology_discovered_property_false_before_node_info(self):
        # A device declaring has_battery_packs must not claim topology is
        # discovered before NODE_INFO has actually arrived — the previous
        # precedence bug returned True here, hiding the not-yet-discovered
        # state and skipping per-pack polling.
        from voltkeeper.core.devices.v2_base import V2Base

        class _StubWithPacks(V2Base):
            has_battery_packs = True

        v2 = _StubWithPacks("AA:BB:CC:DD:EE:FF", "TEST", "0")
        assert v2.topology_discovered is False

    def test_topology_discovered_property_true_after_node_info(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        tlv_data = bytearray(TLV_MAGIC)
        tlv_data.append(0x29)
        tlv_data.extend(b"\x17\x70\x00\x20")
        tlv_data.extend(b"\x00" * 32)
        tlv_data.extend(b"\x00\x00")
        v2.discover_topology(bytes(tlv_data))
        assert v2.topology_discovered is True

    def test_tlv_sections_includes_node_info_before_discovery(self):
        # NODE_INFO must keep being polled until the device actually
        # responds — verify it stays in the main bundle for a
        # has_sub_devices device whose topology isn't discovered yet.
        from voltkeeper.core.devices.v2_base import V2Base

        class _StubWithSubDevices(V2Base):
            has_sub_devices = True

        v2 = _StubWithSubDevices("AA:BB:CC:DD:EE:FF", "TEST", "0")
        assert v2.topology_discovered is False
        sections = v2._tlv_sections()
        addrs = [a for a, _ in sections]
        assert 21000 in addrs  # NODE_INFO


class TestTlvBundledPolling:
    def test_use_tlv_polling_true_for_v2(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        assert v2.use_tlv_polling is True

    def test_tlv_polling_commands_returns_list(self):
        from voltkeeper.core.commands import TlvReadHoldingRegisters
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        cmds = v2.tlv_polling_commands
        assert len(cmds) == 1
        assert isinstance(cmds[0], TlvReadHoldingRegisters)

    def test_tlv_polling_commands_has_home_and_base(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        cmd = v2.tlv_polling_commands[0]
        addrs = {a for a, _ in cmd.sections}
        assert 100 in addrs
        assert 1100 in addrs

    def test_tlv_polling_single_bundle_for_ac2a(self):
        # AC2A has no packs and no sub-devices: a single bundle on slave 1.

        ac2a = AC2A("AA:BB:CC:DD:EE:FF", "1234567")
        cmds = ac2a.tlv_polling_commands
        assert len(cmds) == 1
        assert cmds[0].slave_addr == 1

    def test_tlv_polling_per_slave_bundles_for_discovered_packs(self):
        # A device with discovered pack slaves emits one bundle per slave.
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        # Inject discovered packs without going through TLV parsing.
        v2._discovered_packs = [41, 42]
        v2._topology_discovered = True
        cmds = v2.tlv_polling_commands
        assert [c.slave_addr for c in cmds] == [1, 41, 42]
        # Each pack bundle carries only the PACK_MAIN_INFO section.
        for c in cmds[1:]:
            assert [a for a, _ in c.sections] == [6000]
            assert all(count == 32 for _, count in c.sections)

    def test_tlv_polling_pre_discovery_fallback_for_battery_packs(self):
        # has_battery_packs=True but no NODE_INFO yet: a single bundle on
        # slave 1 that includes PACK_MAIN_INFO so the home screen has data
        # on the first poll.
        from voltkeeper.core.devices.v2_base import V2Base

        class _StubWithPacks(V2Base):
            has_battery_packs = True

        v2 = _StubWithPacks("AA:BB:CC:DD:EE:FF", "TEST", "0")
        cmds = v2.tlv_polling_commands
        assert len(cmds) == 1
        assert cmds[0].slave_addr == 1
        addrs = [a for a, _ in cmds[0].sections]
        assert 6000 in addrs

    def test_parse_tlv_dispatches_home_data(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        tlv_data = bytearray(TLV_MAGIC)
        tlv_data.append(0x00)
        tlv_data.extend(b"\x00\x64")
        tlv_data.extend(bytes([0, 124]))
        tlv_data.extend(b"\x00" * 124)
        tlv_data.extend(b"\x00\x00")
        result = v2.parse_tlv(bytes(tlv_data))
        assert "packTotalVoltage" in result or len(result) > 0

    def test_parse_tlv_empty_response(self):
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        result = v2.parse_tlv(bytes(TLV_MAGIC))
        assert result == {}

    def test_polling_commands_still_works_for_non_tlv(self):
        from voltkeeper.core.commands import ReadHoldingRegisters
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        cmds = v2.polling_commands
        assert len(cmds) >= 6
        for cmd in cmds:
            assert isinstance(cmd, ReadHoldingRegisters)


class TestTimeSlicedPolling:
    def test_counter_1_excludes_slow(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 1
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 1100 not in addrs
        assert 100 in addrs

    def test_counter_3_includes_slow(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 3
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 1100 in addrs
        assert 1200 in addrs
        assert 100 in addrs

    def test_force_full_poll_includes_slow(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 1
        v2._force_full_poll = True
        addrs = {cmd.starting_address for cmd in v2.polling_commands}
        assert 1100 in addrs

    def test_counter_wraps_at_10000(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 9999
        v2.tick_poll_counter()
        assert v2._poll_counter == 0

    def test_tick_poll_counter_increments(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 5
        v2.tick_poll_counter()
        assert v2._poll_counter == 6

    def test_force_full_poll_resets_counter(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 5
        v2.force_full_poll()
        assert v2._force_full_poll is True
        assert v2._poll_counter == 3

    def test_tlv_sections_exclude_slow_on_counter_1(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 1
        sections = v2._tlv_sections()
        addrs = {a for a, _ in sections}
        assert 100 in addrs
        assert 1100 not in addrs

    def test_tlv_sections_include_slow_on_counter_3(self):
        from voltkeeper.core.devices.v2_base import V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        v2._poll_counter = 3
        sections = v2._tlv_sections()
        addrs = {a for a, _ in sections}
        assert 1100 in addrs


class TestV2AlarmDecoding:
    """Tests for _fill_v2_alarms and _fill_v2_pack_alarms on V2Base."""

    def _home_data(self, alarm_word1=0, fault_word1=0):
        """Build an APP_HOME_DATA payload with specific alarm/fault bits set."""
        data = bytearray(78)  # covers alarmInfo (52–59) and faultInfo (66–77)
        # alarmInfo: 4 × 16-bit words, big-endian, at bytes 52–59
        data[52] = (alarm_word1 >> 8) & 0xFF
        data[53] = alarm_word1 & 0xFF
        # faultInfo: 6 × 16-bit words, big-endian, at bytes 66–77
        data[66] = (fault_word1 >> 8) & 0xFF
        data[67] = fault_word1 & 0xFF
        return bytes(data)

    def test_no_alarms_when_all_bytes_zero(self):
        """All-zero alarm/fault bytes yield no alarm.* or fault.* keys (task 6.1)."""
        from voltkeeper.core.devices.v2_base import APP_HOME_DATA, V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        result = v2.parse(APP_HOME_DATA, self._home_data())
        alarm_keys = [k for k in result if k.startswith("alarm.") or k.startswith("fault.")]
        assert alarm_keys == []

    def test_alarm_word1_bit0_low_power(self):
        """Alarm word 1 bit 0 set on low_power device yields exactly one alarm key (task 6.2)."""
        from voltkeeper.core.devices.v2_base import APP_HOME_DATA, V2Base

        v2 = V2Base("AA:BB:CC:DD:EE:FF", "TEST", "0")
        result = v2.parse(APP_HOME_DATA, self._home_data(alarm_word1=0x0001))
        alarm_keys = [k for k in result if k.startswith("alarm.")]
        fault_keys = [k for k in result if k.startswith("fault.")]
        assert alarm_keys == ["alarm.Grid voltage high"]
        assert fault_keys == []

    def test_profile_switch_changes_alarm_names(self):
        """Same bytes produce different names on low_power vs high_power devices (task 6.3)."""
        from voltkeeper.core.devices.v2_base import APP_HOME_DATA, V2Base

        class _HighPower(V2Base):
            V2_ALARM_PROFILE = "high_power"

        low = V2Base("AA:BB:CC:DD:EE:FF", "LOW", "0")
        high = _HighPower("AA:BB:CC:DD:EE:FF", "HIGH", "0")
        data = self._home_data(alarm_word1=0x0001)
        result_low = low.parse(APP_HOME_DATA, data)
        result_high = high.parse(APP_HOME_DATA, data)
        # low_power word 1 bit 0 = "Grid voltage high" (lowercase v)
        assert "alarm.Grid voltage high" in result_low
        # high_power word 1 bit 0 = "Grid Voltage High" (uppercase V)
        assert "alarm.Grid Voltage High" in result_high
        assert "alarm.Grid voltage high" not in result_high
        assert "alarm.Grid Voltage High" not in result_low

    def test_pack_alarm_prefixed_with_sub_addr(self):
        """Pack alarm bit decoded via _parse_node_info gets sub[N]. prefix (task 6.4)."""
        from voltkeeper.core.devices.v2_base import V2Base
        from voltkeeper.core.tlv import TLV_MAGIC

        class _HighVolt(V2Base):
            PACK_ALARM_PROFILE = "high_volt"

        dev = _HighVolt("AA:BB:CC:DD:EE:FF", "TEST", "0")

        # PACK_MAIN_INFO payload: 84 bytes with packHighVoltAlarm bit 0 set.
        # packHighVoltAlarm at bytes 82–83 → PACK_HIGH_VOLT_ALARM_NAMES word 1 bit 0.
        pack_data = bytearray(84)
        pack_data[82] = 0x00
        pack_data[83] = 0x01  # bit 0 → "Overall Overvoltage Alarm"

        tlv = bytearray(TLV_MAGIC)
        tlv.append(0x29)  # slave_addr = 41
        tlv.append(0x17)  # reg_addr hi: 0x1770 = 6000 (PACK_MAIN_INFO)
        tlv.append(0x70)  # reg_addr lo
        length = len(pack_data)
        tlv.append(length >> 8)
        tlv.append(length & 0xFF)
        tlv.extend(pack_data)
        tlv.extend(b"\x00\x00")  # placeholder CRC16 (not validated by parser)

        result = dev._parse_node_info(bytes(tlv))
        assert result.get("sub[41].alarm.Overall Overvoltage Alarm") is True

    def test_v1_alarm_decoding_regression(self):
        """V1 _fill_alarms still decodes a set alarm bit correctly after V2 changes (task 6.5)."""
        from voltkeeper.core.devices.ep500 import EP500

        ep = EP500("AA:BB:CC:DD:EE:FF", "12345678")
        # BASE_REAL_DATA=10; alarm word 1 at reg 54 → byte offset (54-10)*2=88
        data = bytearray(220)
        data[88] = 0x00
        data[89] = 0x01  # bit 0 → CONNECT_CONSTANTS_ALARM_NAMES[1][0] = "Grid voltage high"
        result = ep.parse(10, bytes(data))
        assert result.get("alarm.Grid voltage high") is True
