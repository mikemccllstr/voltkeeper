# ABOUTME: Unit tests for MdnsAdvertiser — service name format, start/stop, loopback guard.
# ABOUTME: Mocks zeroconf to avoid network activity in tests.

from unittest.mock import MagicMock, patch

from voltkeeper.mdns import MdnsAdvertiser


class TestMdnsAdvertiser:
    def test_service_name_includes_hostname(self):
        with patch("socket.gethostname", return_value="homelab"):
            adv = MdnsAdvertiser(host="192.168.1.10", port=8080)
        assert "voltkeeper-homelab" in adv.service_name

    def test_service_name_format(self):
        with patch("socket.gethostname", return_value="myhost"):
            adv = MdnsAdvertiser(host="192.168.1.10", port=8080)
        assert adv.service_name == "voltkeeper-myhost._http._tcp.local."

    def test_start_registers_service(self):
        mock_zc = MagicMock()
        mock_zeroconf_cls = MagicMock(return_value=mock_zc)
        mock_info = MagicMock()
        mock_info_cls = MagicMock(return_value=mock_info)

        with (
            patch("socket.gethostname", return_value="myhost"),
            patch("voltkeeper.mdns.Zeroconf", mock_zeroconf_cls),
            patch("voltkeeper.mdns.ServiceInfo", mock_info_cls),
        ):
            adv = MdnsAdvertiser(host="192.168.1.10", port=8080)
            adv.start()

        mock_zc.register_service.assert_called_once_with(mock_info)

    def test_stop_unregisters_and_closes(self):
        mock_zc = MagicMock()
        mock_info = MagicMock()

        with (
            patch("socket.gethostname", return_value="myhost"),
            patch("voltkeeper.mdns.Zeroconf", return_value=mock_zc),
            patch("voltkeeper.mdns.ServiceInfo", return_value=mock_info),
        ):
            adv = MdnsAdvertiser(host="192.168.1.10", port=8080)
            adv.start()
            adv.stop()

        mock_zc.unregister_service.assert_called_once_with(mock_info)
        mock_zc.close.assert_called_once()

    def test_stop_before_start_is_noop(self):
        with patch("socket.gethostname", return_value="myhost"):
            adv = MdnsAdvertiser(host="192.168.1.10", port=8080)
        adv.stop()  # should not raise


class TestDaemonMdnsIntegration:
    def test_mdns_not_started_when_host_is_loopback(self):
        import asyncio

        from voltkeeper.config import Config, ScanConfig, ServerConfig
        from voltkeeper.daemon import Daemon

        cfg = Config(
            server=ServerConfig(api_key="key", host="127.0.0.1", port=0, mdns=True),
            devices=[],
            scan=ScanConfig(),
        )
        with patch("voltkeeper.daemon.MdnsAdvertiser") as mock_advertiser_cls:
            daemon = Daemon(cfg)
            asyncio.run(daemon._shutdown())

        mock_advertiser_cls.assert_not_called()

    def test_mdns_not_started_when_mdns_is_false(self):
        import asyncio

        from voltkeeper.config import Config, ScanConfig, ServerConfig
        from voltkeeper.daemon import Daemon

        cfg = Config(
            server=ServerConfig(api_key="key", host="0.0.0.0", port=0, mdns=False),
            devices=[],
            scan=ScanConfig(),
        )
        with patch("voltkeeper.daemon.MdnsAdvertiser") as mock_advertiser_cls:
            daemon = Daemon(cfg)
            asyncio.run(daemon._shutdown())

        mock_advertiser_cls.assert_not_called()

    def test_mdns_started_when_mdns_true_and_non_loopback(self):
        import asyncio

        from voltkeeper.config import Config, ScanConfig, ServerConfig
        from voltkeeper.daemon import Daemon

        cfg = Config(
            server=ServerConfig(api_key="key", host="0.0.0.0", port=0, mdns=True),
            devices=[],
            scan=ScanConfig(),
        )
        mock_advertiser = MagicMock()
        mock_advertiser_cls = MagicMock(return_value=mock_advertiser)

        with patch("voltkeeper.daemon.MdnsAdvertiser", mock_advertiser_cls):
            daemon = Daemon(cfg)
            asyncio.run(daemon._shutdown())

        mock_advertiser_cls.assert_called_once_with(host="0.0.0.0", port=0)
        mock_advertiser.start.assert_called_once()
        mock_advertiser.stop.assert_called_once()
