"""Unit tests for device abstractions."""

from unittest.mock import MagicMock, patch

import pytest

from beamline.daq.client import DeviceClient
from beamline.daq.device import Detector, Motor, MotorStatus, Shutter
from beamline.daq.exceptions import ProtocolError, TimeoutError


class TestMotor:
    """Test Motor class."""

    def test_init(self) -> None:
        """Test motor initialization."""
        client = MagicMock(spec=DeviceClient)
        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        assert motor.pv == "BL02:SAMPLE:X"
        assert motor.client == client

    def test_readback_pv(self) -> None:
        """Test readback PV property."""
        client = MagicMock(spec=DeviceClient)
        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        assert motor.readback_pv == "BL02:SAMPLE:X.RBV"

    def test_position(self) -> None:
        """Test reading motor position."""
        client = MagicMock(spec=DeviceClient)
        client.get.return_value = 1000.0

        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        position = motor.position()

        assert position == 1000.0
        client.get.assert_called_once_with("BL02:SAMPLE:X.RBV")

    def test_status_idle(self) -> None:
        """Test motor status IDLE."""
        client = MagicMock(spec=DeviceClient)
        client.status.return_value = "IDLE"

        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        status = motor.status()

        assert status == MotorStatus.IDLE
        client.status.assert_called_once_with("BL02:SAMPLE:X")

    def test_status_moving(self) -> None:
        """Test motor status MOVING."""
        client = MagicMock(spec=DeviceClient)
        client.status.return_value = "MOVING"

        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        status = motor.status()

        assert status == MotorStatus.MOVING

    def test_move_to_with_wait(self) -> None:
        """Test move_to with wait=True."""
        client = MagicMock(spec=DeviceClient)
        client.status.return_value = "IDLE"

        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        motor.move_to(1000.0, wait=True)

        client.move.assert_called_once_with("BL02:SAMPLE:X", 1000.0)
        client.status.assert_called()

    def test_move_to_without_wait(self) -> None:
        """Test move_to with wait=False."""
        client = MagicMock(spec=DeviceClient)

        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        motor.move_to(1000.0, wait=False)

        client.move.assert_called_once_with("BL02:SAMPLE:X", 1000.0)
        client.status.assert_not_called()

    def test_wait_for_idle_success(self) -> None:
        """Test wait_for_idle success."""
        client = MagicMock(spec=DeviceClient)
        client.status.side_effect = ["MOVING", "MOVING", "IDLE"]

        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        motor.wait_for_idle(timeout=10.0, poll_interval=0.01)

        assert client.status.call_count == 3

    def test_wait_for_idle_timeout(self) -> None:
        """Test wait_for_idle timeout."""
        client = MagicMock(spec=DeviceClient)
        client.status.return_value = "MOVING"

        motor = Motor(pv="BL02:SAMPLE:X", client=client)
        with pytest.raises(TimeoutError, match="did not reach IDLE"):
            motor.wait_for_idle(timeout=0.1, poll_interval=0.01)

    def test_pv_validation(self) -> None:
        """Test PV name validation."""
        client = MagicMock(spec=DeviceClient)

        with pytest.raises(ValueError, match="Invalid PV name"):
            Motor(pv="", client=client)

        with pytest.raises(ValueError, match="Invalid PV name"):
            Motor(pv="INVALID", client=client)


class TestDetector:
    """Test Detector class."""

    def test_read(self) -> None:
        """Test detector read."""
        client = MagicMock(spec=DeviceClient)
        client.get.return_value = 500000.0

        detector = Detector(pv="BL02:DET:I0", client=client)
        value = detector.read()

        assert value == 500000.0
        client.get.assert_called_once_with("BL02:DET:I0")

    def test_read_multiple(self) -> None:
        """Test read_multiple."""
        from unittest.mock import patch

        client = MagicMock(spec=DeviceClient)
        client.get.side_effect = [100.0, 101.0, 102.0]

        detector = Detector(pv="BL02:DET:I0", client=client)
        with patch("beamline.daq.device.time.sleep"):
            readings = detector.read_multiple(3, dwell_time=0.1)

        assert len(readings) == 3
        assert readings[0] == 100.0
        assert readings[1] == 101.0
        assert readings[2] == 102.0


class TestShutter:
    """Test Shutter class."""

    def test_open(self) -> None:
        """Test shutter open."""
        client = MagicMock(spec=DeviceClient)

        shutter = Shutter(client=client)
        shutter.open()

        client.put.assert_called_once_with("BL02:SHUTTER:CMD", 1.0)

    def test_close(self) -> None:
        """Test shutter close."""
        client = MagicMock(spec=DeviceClient)

        shutter = Shutter(client=client)
        shutter.close()

        client.put.assert_called_once_with("BL02:SHUTTER:CMD", 0.0)

    def test_is_open_true(self) -> None:
        """Test is_open returns True."""
        client = MagicMock(spec=DeviceClient)
        client.get.return_value = 1.0

        shutter = Shutter(client=client)
        assert shutter.is_open() is True
        client.get.assert_called_once_with("BL02:SHUTTER:STATUS")

    def test_is_open_false(self) -> None:
        """Test is_open returns False."""
        client = MagicMock(spec=DeviceClient)
        client.get.return_value = 0.0

        shutter = Shutter(client=client)
        assert shutter.is_open() is False
