"""Unit tests for DeviceClient."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from beamline.daq.client import DeviceClient
from beamline.daq.exceptions import ConnectionError, ProtocolError, TimeoutError


class TestDeviceClient:
    """Test DeviceClient functionality."""

    def test_init(self) -> None:
        """Test client initialization."""
        client = DeviceClient(host="localhost", port=5064, timeout=5.0)
        assert client.host == "localhost"
        assert client.port == 5064
        assert client.timeout == 5.0
        assert not client._connected

    def test_context_manager(self) -> None:
        """Test context manager support."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock

            with DeviceClient("localhost", 5064) as client:
                assert client._connected
                mock_sock.connect.assert_called_once_with(("localhost", 5064))

            mock_sock.close.assert_called_once()
            assert not client._connected

    def test_connect_success(self) -> None:
        """Test successful connection."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            client.connect()

            assert client._connected
            mock_sock.connect.assert_called_once_with(("localhost", 5064))
            mock_sock.settimeout.assert_called_once_with(5.0)

    def test_connect_failure(self) -> None:
        """Test connection failure."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = socket.error("Connection refused")
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            with pytest.raises(ConnectionError, match="Failed to connect"):
                client.connect()

            assert not client._connected

    def test_get_success(self) -> None:
        """Test successful GET command."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"OK:350.5\n", b""]
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            client._socket = mock_sock
            client._connected = True

            value = client.get("BL02:RING:CURRENT")
            assert value == 350.5
            mock_sock.sendall.assert_called_once_with(b"GET:BL02:RING:CURRENT\n")

    def test_get_error(self) -> None:
        """Test GET command with error response."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"ERR:UNKNOWN_PV\n", b""]
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            client._socket = mock_sock
            client._connected = True

            with pytest.raises(ProtocolError, match="UNKNOWN_PV"):
                client.get("BL02:INVALID:PV")

    def test_put_success(self) -> None:
        """Test successful PUT command."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"OK:PUT\n", b""]
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            client._socket = mock_sock
            client._connected = True

            client.put("BL02:MONO:ENERGY", 7112.0)
            mock_sock.sendall.assert_called_once_with(b"PUT:BL02:MONO:ENERGY:7112.0\n")

    def test_move_success(self) -> None:
        """Test successful MOVE command."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"OK:MOVING\n", b""]
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            client._socket = mock_sock
            client._connected = True

            client.move("BL02:SAMPLE:X", 1000.0)
            mock_sock.sendall.assert_called_once_with(b"MOVE:BL02:SAMPLE:X:1000.0\n")

    def test_status_success(self) -> None:
        """Test successful STATUS command."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"OK:IDLE\n", b""]
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            client._socket = mock_sock
            client._connected = True

            status = client.status("BL02:SAMPLE:X")
            assert status == "IDLE"
            mock_sock.sendall.assert_called_once_with(b"STATUS:BL02:SAMPLE:X\n")

    def test_list_pvs(self) -> None:
        """Test LIST command."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [
                b"OK:BL02:RING:CURRENT,BL02:MONO:ENERGY,BL02:DET:I0\n",
                b"",
            ]
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            client._socket = mock_sock
            client._connected = True

            pvs = client.list_pvs()
            assert len(pvs) == 3
            assert "BL02:RING:CURRENT" in pvs
            assert "BL02:MONO:ENERGY" in pvs
            assert "BL02:DET:I0" in pvs

    def test_list_pvs_with_pattern(self) -> None:
        """Test LIST command with pattern."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [b"OK:BL02:DET:I0,BL02:DET:IT,BL02:DET:IF\n", b""]
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064)
            client._socket = mock_sock
            client._connected = True

            pvs = client.list_pvs("BL02:DET:*")
            assert len(pvs) == 3
            mock_sock.sendall.assert_called_once_with(b"LIST:BL02:DET:*\n")

    def test_timeout(self) -> None:
        """Test timeout handling."""
        with patch("beamline.daq.client.socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.sendall.side_effect = socket.timeout("Operation timed out")
            mock_socket.return_value = mock_sock

            client = DeviceClient("localhost", 5064, timeout=1.0)
            client._socket = mock_sock
            client._connected = True

            with pytest.raises(TimeoutError, match="timed out"):
                client.get("BL02:RING:CURRENT")

    def test_not_connected(self) -> None:
        """Test operations when not connected."""
        client = DeviceClient("localhost", 5064)

        with pytest.raises(ConnectionError, match="Not connected"):
            client.get("BL02:RING:CURRENT")

        with pytest.raises(ConnectionError, match="Not connected"):
            client.put("BL02:MONO:ENERGY", 7112.0)
