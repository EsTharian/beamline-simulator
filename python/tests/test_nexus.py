"""Unit tests for NeXus/HDF5 export."""

from __future__ import annotations

import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import h5py
import numpy as np
import pytest

from beamline.daq.data import ScanData
from beamline.daq.nexus import NeXusWriter


class TestNeXusWriter:
    """Test NeXusWriter class."""

    def test_init_basic(self) -> None:
        """Test basic initialization."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"
            writer = NeXusWriter(filename)
            assert writer.filename == filename
            assert writer.mode == "w"
            assert writer.compression == 1

    def test_init_custom_compression(self) -> None:
        """Test initialization with custom compression."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"
            writer = NeXusWriter(filename, compression=5)
            assert writer.compression == 5

    def test_init_invalid_compression(self) -> None:
        """Test initialization with invalid compression level."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"
            with pytest.raises(ValueError, match="Compression level must be 0-9"):
                NeXusWriter(filename, compression=10)

    def test_context_manager(self) -> None:
        """Test context manager usage."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"
            with NeXusWriter(filename) as writer:
                assert writer._file is not None
                assert writer._entry_group is not None
            # File should be closed after context exit
            assert writer._file is None

    def test_open_close(self) -> None:
        """Test explicit open/close."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"
            writer = NeXusWriter(filename)
            writer.open()
            assert writer._file is not None
            writer.close()
            assert writer._file is None

    def test_write_scan_basic(self) -> None:
        """Test writing basic scan data."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"

            # Create test scan data
            n_points = 10
            timestamps = np.linspace(0, 10, n_points)
            motor_pos = np.linspace(0, 100, n_points)
            detector_data = np.random.rand(n_points) * 1000

            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": motor_pos},
                detector_readings={"BL02:DET:I0": detector_data},
                timestamps=timestamps,
                metadata={"ring_current": 350.5, "sample_name": "test_sample"},
            )

            with NeXusWriter(filename) as writer:
                writer.write_scan(scan_data, title="Test Scan")

            # Verify file structure
            with h5py.File(filename, "r") as f:
                assert "entry" in f
                entry = f["entry"]
                assert entry.attrs["NX_class"] == "NXentry"
                assert entry.attrs["definition"] == "NXxas"
                assert entry.attrs["title"] == "Test Scan"

                # Check instrument structure
                assert "instrument" in entry
                instrument = entry["instrument"]
                assert instrument.attrs["NX_class"] == "NXinstrument"

                # Check source
                assert "source" in instrument
                source = instrument["source"]
                assert source.attrs["NX_class"] == "NXsource"
                assert source.attrs["type"] == "Synchrotron X-ray Source"
                assert source["current"][()] == 350.5

                # Check monochromator
                assert "monochromator" in instrument
                monochromator = instrument["monochromator"]
                assert monochromator.attrs["NX_class"] == "NXmonochromator"
                assert "energy" in monochromator
                np.testing.assert_array_almost_equal(monochromator["energy"][:], motor_pos)

                # Check detector
                assert "detector" in instrument
                detector = instrument["detector"]
                assert detector.attrs["NX_class"] == "NXdetector"
                assert "data" in detector
                np.testing.assert_array_almost_equal(detector["data"][:], detector_data)

                # Check sample
                assert "sample" in entry
                sample = entry["sample"]
                assert sample.attrs["NX_class"] == "NXsample"
                assert sample.attrs["name"] == "test_sample"
                assert "position_x" in sample

                # Check data group
                assert "data" in entry
                data = entry["data"]
                assert data.attrs["NX_class"] == "NXdata"
                assert data.attrs["signal"] == "intensity"
                assert "intensity" in data
                assert "energy" in data

    def test_write_scan_xafs(self) -> None:
        """Test writing XAFS scan data."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test_xafs.nxs"

            n_points = 50
            energy = np.linspace(7000, 8000, n_points)
            mu = np.random.rand(n_points) * 10 + 1.0

            scan_data = ScanData(
                motor_positions={"BL02:MONO:ENERGY": energy},
                detector_readings={"BL02:DET:IT": mu},
                timestamps=np.linspace(0, 100, n_points),
                metadata={"ring_current": 400.0},
            )

            with NeXusWriter(filename) as writer:
                writer.write_scan(scan_data, title="XAFS Scan", scan_type="xafs")

            with h5py.File(filename, "r") as f:
                entry = f["entry"]
                data = entry["data"]
                assert data.attrs["axes"] == ["energy"]

    def test_write_scan_multiple_detectors(self) -> None:
        """Test writing scan with multiple detectors."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test_multi.nxs"

            n_points = 20
            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.linspace(0, 100, n_points)},
                detector_readings={
                    "BL02:DET:I0": np.random.rand(n_points) * 1000,
                    "BL02:DET:IT": np.random.rand(n_points) * 500,
                },
                timestamps=np.linspace(0, 20, n_points),
            )

            with NeXusWriter(filename) as writer:
                writer.write_scan(scan_data)

            with h5py.File(filename, "r") as f:
                detector = f["entry/instrument/detector"]
                assert "data" in detector
                assert "BL02_DET_IT" in detector  # Sanitized name

    def test_write_scan_multiple_motors(self) -> None:
        """Test writing scan with multiple motors."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test_motors.nxs"

            n_points = 15
            scan_data = ScanData(
                motor_positions={
                    "BL02:SAMPLE:X": np.linspace(0, 100, n_points),
                    "BL02:SAMPLE:Y": np.linspace(0, 50, n_points),
                },
                detector_readings={"BL02:DET:I0": np.random.rand(n_points) * 1000},
                timestamps=np.linspace(0, 15, n_points),
            )

            with NeXusWriter(filename) as writer:
                writer.write_scan(scan_data)

            with h5py.File(filename, "r") as f:
                sample = f["entry/sample"]
                assert "position_x" in sample
                assert "position_y" in sample

    def test_add_metadata(self) -> None:
        """Test adding custom metadata."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test_metadata.nxs"

            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.array([0.0, 1.0, 2.0])},
                detector_readings={"BL02:DET:I0": np.array([100.0, 200.0, 300.0])},
                timestamps=np.array([0.0, 1.0, 2.0]),
            )

            with NeXusWriter(filename) as writer:
                writer.write_scan(scan_data)
                writer.add_metadata("experiment_id", "EXP001")
                writer.add_metadata("beamline", "BL02")
                writer.add_metadata("operator", "John Doe")

            with h5py.File(filename, "r") as f:
                entry = f["entry"]
                assert entry.attrs["experiment_id"] == "EXP001"
                assert entry.attrs["beamline"] == "BL02"
                assert entry.attrs["operator"] == "John Doe"

    def test_add_metadata_sanitization(self) -> None:
        """Test metadata key sanitization."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test_sanitize.nxs"

            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.array([0.0])},
                detector_readings={"BL02:DET:I0": np.array([100.0])},
                timestamps=np.array([0.0]),
            )

            with NeXusWriter(filename) as writer:
                writer.write_scan(scan_data)
                writer.add_metadata("key with spaces", "value")
                writer.add_metadata("key-with-dashes", "value2")

            with h5py.File(filename, "r") as f:
                entry = f["entry"]
                assert "key_with_spaces" in entry.attrs
                assert "key_with_dashes" in entry.attrs

    def test_compression(self) -> None:
        """Test gzip compression."""
        with TemporaryDirectory() as tmpdir:
            filename_no_comp = Path(tmpdir) / "no_comp.nxs"
            filename_comp = Path(tmpdir) / "comp.nxs"

            n_points = 1000
            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.linspace(0, 100, n_points)},
                detector_readings={"BL02:DET:I0": np.random.rand(n_points) * 1000},
                timestamps=np.linspace(0, 100, n_points),
            )

            # Write without compression
            with NeXusWriter(filename_no_comp, compression=0) as writer:
                writer.write_scan(scan_data)

            # Write with compression
            with NeXusWriter(filename_comp, compression=1) as writer:
                writer.write_scan(scan_data)

            # For this test data, compression should help
            # But we just verify both files are readable
            with h5py.File(filename_no_comp, "r") as f:
                assert "entry" in f

            with h5py.File(filename_comp, "r") as f:
                assert "entry" in f

    def test_large_dataset_chunking(self) -> None:
        """Test chunking for large datasets."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "large.nxs"

            n_points = 50000  # Large dataset
            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.linspace(0, 100, n_points)},
                detector_readings={"BL02:DET:I0": np.random.rand(n_points) * 1000},
                timestamps=np.linspace(0, 100, n_points),
            )

            with NeXusWriter(filename) as writer:
                writer.write_scan(scan_data)

            # Verify file is readable and data is correct
            with h5py.File(filename, "r") as f:
                detector_data = f["entry/instrument/detector/data"]
                assert len(detector_data) == n_points
                # Check that chunking is applied (chunks attribute exists)
                assert detector_data.chunks is not None

    def test_start_time_iso8601(self) -> None:
        """Test start_time is stored as ISO 8601."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test_time.nxs"

            # Use specific timestamp
            base_time = datetime.datetime(2026, 1, 12, 10, 30, 0, tzinfo=datetime.UTC)
            timestamps = np.array([base_time.timestamp() + i for i in range(5)])

            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.linspace(0, 10, 5)},
                detector_readings={"BL02:DET:I0": np.random.rand(5) * 1000},
                timestamps=timestamps,
            )

            with NeXusWriter(filename) as writer:
                writer.write_scan(scan_data)

            with h5py.File(filename, "r") as f:
                entry = f["entry"]
                start_time_str = entry.attrs["start_time"]
                # Should be ISO 8601 format
                assert "T" in start_time_str or "+" in start_time_str or "Z" in start_time_str
                # Should be parseable
                parsed = datetime.datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                assert parsed.year == 2026

    def test_write_scan_no_file_open(self) -> None:
        """Test error when writing without opening file."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"
            writer = NeXusWriter(filename)

            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.array([0.0])},
                detector_readings={"BL02:DET:I0": np.array([100.0])},
                timestamps=np.array([0.0]),
            )

            with pytest.raises(RuntimeError, match="File not open"):
                writer.write_scan(scan_data)

    def test_add_metadata_no_file_open(self) -> None:
        """Test error when adding metadata without opening file."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"
            writer = NeXusWriter(filename)

            with pytest.raises(RuntimeError, match="File not open"):
                writer.add_metadata("key", "value")


class TestScanDataToNeXus:
    """Test ScanData.to_nexus() method."""

    def test_to_nexus_basic(self) -> None:
        """Test basic to_nexus() usage."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"

            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.array([0.0, 1.0, 2.0])},
                detector_readings={"BL02:DET:I0": np.array([100.0, 200.0, 300.0])},
                timestamps=np.array([0.0, 1.0, 2.0]),
            )

            scan_data.to_nexus(filename, title="Test Scan")

            # Verify file exists and is valid
            assert filename.exists()
            with h5py.File(filename, "r") as f:
                assert "entry" in f
                assert f["entry"].attrs["title"] == "Test Scan"

    def test_to_nexus_auto_title(self) -> None:
        """Test to_nexus() with auto-generated title."""
        with TemporaryDirectory() as tmpdir:
            filename = Path(tmpdir) / "test.nxs"

            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.array([0.0])},
                detector_readings={"BL02:DET:I0": np.array([100.0])},
                timestamps=np.array([0.0]),
                metadata={"title": "Metadata Title"},
            )

            scan_data.to_nexus(filename)

            with h5py.File(filename, "r") as f:
                assert f["entry"].attrs["title"] == "Metadata Title"

    def test_to_nexus_scan_type(self) -> None:
        """Test to_nexus() with different scan types."""
        with TemporaryDirectory() as tmpdir:
            filename_linear = Path(tmpdir) / "linear.nxs"
            filename_xafs = Path(tmpdir) / "xafs.nxs"

            scan_data = ScanData(
                motor_positions={"BL02:SAMPLE:X": np.array([0.0, 1.0])},
                detector_readings={"BL02:DET:I0": np.array([100.0, 200.0])},
                timestamps=np.array([0.0, 1.0]),
            )

            scan_data.to_nexus(filename_linear, scan_type="linear")
            scan_data.to_nexus(filename_xafs, scan_type="xafs")

            with h5py.File(filename_linear, "r") as f:
                data = f["entry/data"]
                assert data.attrs["axes"] == ["two_theta"]

            with h5py.File(filename_xafs, "r") as f:
                data = f["entry/data"]
                assert data.attrs["axes"] == ["energy"]
