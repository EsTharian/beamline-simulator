"""Unit tests for scan engine."""

from unittest.mock import MagicMock, patch

import pytest

from beamline.daq.client import DeviceClient
from beamline.daq.scan import (
    LinearScanConfig,
    MeshScanConfig,
    ScanEngine,
    XAFSScanConfig,
)


class TestScanConfigs:
    """Test scan configuration models."""

    def test_linear_scan_config(self) -> None:
        """Test LinearScanConfig validation."""
        config = LinearScanConfig(
            motor="BL02:SAMPLE:X",
            start=-1000.0,
            stop=1000.0,
            steps=100,
            detectors=["BL02:DET:I0"],
            dwell_time=0.1,
        )
        assert config.scan_type == "linear"
        assert config.motor == "BL02:SAMPLE:X"
        assert len(config.positions) == 100

    def test_linear_scan_config_invalid_range(self) -> None:
        """Test LinearScanConfig with invalid range."""
        with pytest.raises(ValueError, match="stop must be greater"):
            LinearScanConfig(
                motor="BL02:SAMPLE:X",
                start=1000.0,
                stop=-1000.0,  # Invalid: stop < start
                steps=100,
                detectors=["BL02:DET:I0"],
            )

    def test_mesh_scan_config(self) -> None:
        """Test MeshScanConfig validation."""
        config = MeshScanConfig(
            motor1=("BL02:SAMPLE:X", -500.0, 500.0, 50),
            motor2=("BL02:SAMPLE:Y", -500.0, 500.0, 50),
            detectors=["BL02:DET:IF"],
        )
        assert config.scan_type == "mesh"
        assert len(config.positions1) == 50
        assert len(config.positions2) == 50

    def test_xafs_scan_config(self) -> None:
        """Test XAFSScanConfig validation."""
        config = XAFSScanConfig(
            edge=7112.0,
            regions=[(-150.0, -20.0, 5.0), (-20.0, 30.0, 0.5), (30.0, 500.0, 2.0)],
            detectors=["BL02:DET:I0", "BL02:DET:IT"],
        )
        assert config.scan_type == "xafs"
        assert config.edge == 7112.0
        energies = config.generate_energies()
        assert len(energies) > 0
        assert energies[0] < energies[-1]  # Should be increasing

    def test_xafs_scan_config_invalid_regions(self) -> None:
        """Test XAFSScanConfig with invalid regions."""
        with pytest.raises(ValueError, match="step_size must be > 0"):
            XAFSScanConfig(
                edge=7112.0,
                regions=[(-150.0, -20.0, -5.0)],  # Invalid: negative step
                detectors=["BL02:DET:I0"],
            )

        with pytest.raises(ValueError, match="overlaps"):
            XAFSScanConfig(
                edge=7112.0,
                regions=[
                    (-150.0, -20.0, 5.0),
                    (-30.0, 30.0, 0.5),  # Overlaps with first region
                ],
                detectors=["BL02:DET:I0"],
            )


class TestScanEngine:
    """Test ScanEngine execution."""

    def test_run_linear(self) -> None:
        """Test linear scan execution."""
        client = MagicMock(spec=DeviceClient)
        client.get.side_effect = [100.0, 101.0, 102.0]  # Detector readings
        client.status.return_value = "IDLE"
        client.move.return_value = None

        engine = ScanEngine(client)
        config = LinearScanConfig(
            motor="BL02:SAMPLE:X",
            start=-100.0,
            stop=100.0,
            steps=3,
            detectors=["BL02:DET:I0"],
            dwell_time=0.01,
        )

        with patch("beamline.daq.device.time.sleep"), patch("time.time", return_value=1000.0):
            data = engine.run_linear(config)

        assert len(data.timestamps) == 3
        assert len(data.motor_positions["BL02:SAMPLE:X"]) == 3
        assert len(data.detector_readings["BL02:DET:I0"]) == 3
        assert data.metadata["scan_type"] == "linear"

    def test_run_mesh(self) -> None:
        """Test mesh scan execution."""
        client = MagicMock(spec=DeviceClient)
        client.get.return_value = 50.0  # Detector readings
        client.status.return_value = "IDLE"
        client.move.return_value = None

        engine = ScanEngine(client)
        config = MeshScanConfig(
            motor1=("BL02:SAMPLE:X", -10.0, 10.0, 3),
            motor2=("BL02:SAMPLE:Y", -10.0, 10.0, 3),
            detectors=["BL02:DET:IF"],
            dwell_time=0.01,
        )

        with patch("beamline.daq.device.time.sleep"), patch("time.time", return_value=1000.0):
            data = engine.run_mesh(config)

        assert len(data.timestamps) == 9  # 3x3 grid
        assert "BL02:SAMPLE:X" in data.motor_positions
        assert "BL02:SAMPLE:Y" in data.motor_positions
        assert data.metadata["scan_type"] == "mesh"

    def test_run_xafs(self) -> None:
        """Test XAFS scan execution."""
        client = MagicMock(spec=DeviceClient)
        client.get.return_value = 100.0  # Detector readings
        client.status.return_value = "IDLE"
        client.move.return_value = None

        engine = ScanEngine(client)
        config = XAFSScanConfig(
            edge=7112.0,
            regions=[(-10.0, 10.0, 5.0)],  # Small region for testing
            detectors=["BL02:DET:I0"],
            dwell_time=0.01,
        )

        with patch("beamline.daq.device.time.sleep"), patch("time.time", return_value=1000.0):
            data = engine.run_xafs(config)

        assert len(data.timestamps) > 0
        assert "BL02:MONO:ENERGY" in data.motor_positions
        assert data.metadata["scan_type"] == "xafs"
        assert data.metadata["edge"] == 7112.0

    def test_run_dispatch(self) -> None:
        """Test run() method dispatch."""
        client = MagicMock(spec=DeviceClient)
        client.get.return_value = 100.0
        client.status.return_value = "IDLE"

        engine = ScanEngine(client)

        linear_config = LinearScanConfig(
            motor="BL02:SAMPLE:X",
            start=-100.0,
            stop=100.0,
            steps=3,
            detectors=["BL02:DET:I0"],
        )

        with patch("beamline.daq.device.time.sleep"), patch("time.time", return_value=1000.0):
            data = engine.run(linear_config)

        assert data.metadata["scan_type"] == "linear"
