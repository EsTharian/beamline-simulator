"""Scan data container and CSV export."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class ScanData:
    """Container for scan data with metadata.

    Stores motor positions, detector readings, timestamps, and metadata.
    """

    motor_positions: dict[str, np.ndarray] = field(default_factory=dict)
    detector_readings: dict[str, np.ndarray] = field(default_factory=dict)
    timestamps: np.ndarray = field(default_factory=lambda: np.array([]))
    metadata: dict[str, object] = field(default_factory=dict)

    def to_csv(self, path: Path | str, delimiter: str = ",") -> None:
        """Export scan data to CSV file.

        CSV format:
        - Header row: timestamp, motor1_pos, motor2_pos, det1, det2, ...
        - Data rows: one per scan point

        Args:
            path: Output file path
            delimiter: CSV delimiter (default: comma)

        Raises:
            ValueError: If data validation fails
        """
        self.validate()

        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Determine number of points from timestamps
        n_points = len(self.timestamps)
        if n_points == 0:
            raise ValueError("No timestamps in data")

        # Collect all column names
        columns = ["timestamp"]
        columns.extend(sorted(self.motor_positions.keys()))
        columns.extend(sorted(self.detector_readings.keys()))

        with path_obj.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=delimiter)

            # Write header
            writer.writerow(columns)

            # Write data rows
            for i in range(n_points):
                row = [self.timestamps[i]]
                # Add motor positions
                for motor_pv in sorted(self.motor_positions.keys()):
                    motor_data = self.motor_positions[motor_pv]
                    if i < len(motor_data):
                        row.append(motor_data[i])
                    else:
                        row.append(np.nan)
                # Add detector readings
                for det_pv in sorted(self.detector_readings.keys()):
                    det_data = self.detector_readings[det_pv]
                    if i < len(det_data):
                        row.append(det_data[i])
                    else:
                        row.append(np.nan)
                writer.writerow(row)

    def validate(self) -> None:
        """Validate data consistency.

        Checks:
        - All arrays have same length (or compatible lengths for mesh scans)
        - Timestamps are monotonically increasing
        - No NaN or Inf values in critical arrays

        Raises:
            ValueError: If validation fails
        """
        # Check timestamps
        if len(self.timestamps) == 0:
            raise ValueError("No timestamps in data")

        # Check for NaN/Inf in timestamps
        if np.any(np.isnan(self.timestamps)) or np.any(np.isinf(self.timestamps)):
            raise ValueError("Timestamps contain NaN or Inf values")

        # Check timestamp ordering (allow equal for simultaneous measurements)
        if len(self.timestamps) > 1:
            diffs = np.diff(self.timestamps)
            if np.any(diffs < 0):
                raise ValueError("Timestamps are not monotonically increasing")

        # Check motor positions
        expected_length = len(self.timestamps)
        for motor_pv, positions in self.motor_positions.items():
            if len(positions) != expected_length:
                raise ValueError(
                    f"Motor {motor_pv} has {len(positions)} points, expected {expected_length}"
                )
            if np.any(np.isnan(positions)) or np.any(np.isinf(positions)):
                raise ValueError(f"Motor {motor_pv} contains NaN or Inf values")

        # Check detector readings
        for det_pv, readings in self.detector_readings.items():
            if len(readings) != expected_length:
                raise ValueError(
                    f"Detector {det_pv} has {len(readings)} points, expected {expected_length}"
                )
            if np.any(np.isnan(readings)) or np.any(np.isinf(readings)):
                raise ValueError(f"Detector {det_pv} contains NaN or Inf values")
