"""Unit tests for ScanData and CSV export."""

import csv
import tempfile
from pathlib import Path

import numpy as np
import pytest

from beamline.daq.data import ScanData


class TestScanData:
    """Test ScanData container."""

    def test_init(self) -> None:
        """Test ScanData initialization."""
        data = ScanData()
        assert len(data.motor_positions) == 0
        assert len(data.detector_readings) == 0
        assert len(data.timestamps) == 0
        assert len(data.metadata) == 0

    def test_validate_success(self) -> None:
        """Test successful validation."""
        data = ScanData(
            motor_positions={"BL02:SAMPLE:X": np.array([1.0, 2.0, 3.0])},
            detector_readings={"BL02:DET:I0": np.array([100.0, 101.0, 102.0])},
            timestamps=np.array([1000.0, 1001.0, 1002.0]),
        )
        data.validate()  # Should not raise

    def test_validate_empty_timestamps(self) -> None:
        """Test validation with empty timestamps."""
        data = ScanData()
        with pytest.raises(ValueError, match="No timestamps"):
            data.validate()

    def test_validate_length_mismatch(self) -> None:
        """Test validation with length mismatch."""
        data = ScanData(
            motor_positions={"BL02:SAMPLE:X": np.array([1.0, 2.0])},  # 2 points
            detector_readings={"BL02:DET:I0": np.array([100.0, 101.0, 102.0])},  # 3 points
            timestamps=np.array([1000.0, 1001.0, 1002.0]),  # 3 points
        )
        with pytest.raises(ValueError, match="has 2 points, expected 3"):
            data.validate()

    def test_validate_nan_values(self) -> None:
        """Test validation with NaN values."""
        data = ScanData(
            motor_positions={"BL02:SAMPLE:X": np.array([1.0, np.nan, 3.0])},
            detector_readings={"BL02:DET:I0": np.array([100.0, 101.0, 102.0])},
            timestamps=np.array([1000.0, 1001.0, 1002.0]),
        )
        with pytest.raises(ValueError, match="contains NaN"):
            data.validate()

    def test_validate_timestamp_ordering(self) -> None:
        """Test validation with non-monotonic timestamps."""
        data = ScanData(
            motor_positions={"BL02:SAMPLE:X": np.array([1.0, 2.0, 3.0])},
            detector_readings={"BL02:DET:I0": np.array([100.0, 101.0, 102.0])},
            timestamps=np.array([1000.0, 999.0, 1002.0]),  # Decreasing
        )
        with pytest.raises(ValueError, match="not monotonically increasing"):
            data.validate()

    def test_to_csv_success(self) -> None:
        """Test successful CSV export."""
        data = ScanData(
            motor_positions={"BL02:SAMPLE:X": np.array([-100.0, 0.0, 100.0])},
            detector_readings={
                "BL02:DET:I0": np.array([500000.0, 501000.0, 502000.0]),
                "BL02:DET:IT": np.array([450000.0, 451000.0, 452000.0]),
            },
            timestamps=np.array([1000.0, 1001.0, 1002.0]),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_scan.csv"
            data.to_csv(csv_path)

            # Verify file exists
            assert csv_path.exists()

            # Read and verify content
            with csv_path.open("r") as f:
                reader = csv.reader(f)
                rows = list(reader)

            # Check header
            assert "timestamp" in rows[0]
            assert "BL02:SAMPLE:X" in rows[0]
            assert "BL02:DET:I0" in rows[0]
            assert "BL02:DET:IT" in rows[0]

            # Check data rows (skip header)
            assert len(rows) == 4  # 1 header + 3 data rows
            assert float(rows[1][0]) == 1000.0  # timestamp
            assert float(rows[1][rows[0].index("BL02:SAMPLE:X")]) == -100.0

    def test_to_csv_empty_data(self) -> None:
        """Test CSV export with empty data."""
        data = ScanData()
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_scan.csv"
            with pytest.raises(ValueError, match="No timestamps"):
                data.to_csv(csv_path)
