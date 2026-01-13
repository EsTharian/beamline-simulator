"""NeXus/HDF5 export for scan data following NXxas application definition."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Literal

import h5py
import numpy as np

from beamline.daq.data import ScanData


class NeXusWriter:
    """NeXus/HDF5 file writer following NXxas application definition.

    Creates HDF5 files compliant with NeXus standard for X-ray
    absorption spectroscopy (XAS) data storage.

    Example:
        >>> with NeXusWriter("scan.nxs") as writer:
        ...     writer.write_scan(scan_data, title="XRD Scan 001")
        ...     writer.add_metadata("sample_name", "Si powder")
    """

    def __init__(
        self,
        filename: str | Path,
        mode: Literal["w", "w-", "a"] = "w",
        compression: int = 1,
    ) -> None:
        """Initialize NeXus file.

        Args:
            filename: Output HDF5 file path
            mode: File mode ('w' overwrite, 'w-' fail if exists, 'a' append)
            compression: Gzip compression level (0-9, default 1)

        Raises:
            ValueError: If compression level is not in range 0-9
            OSError: If file cannot be opened
        """
        if not (0 <= compression <= 9):
            raise ValueError(f"Compression level must be 0-9, got {compression}")

        self.filename = Path(filename)
        self.mode = mode
        self.compression = compression
        self._file: h5py.File | None = None
        self._entry_group: h5py.Group | None = None

    def __enter__(self) -> NeXusWriter:
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.close()

    def open(self) -> None:
        """Open HDF5 file and create entry structure."""
        if self._file is not None:
            return

        self._file = h5py.File(self.filename, mode=self.mode)

        # Create entry group (NXentry)
        self._entry_group = self._file.create_group("entry")
        self._entry_group.attrs["NX_class"] = "NXentry"
        self._entry_group.attrs["definition"] = "NXxas"

    def close(self) -> None:
        """Close HDF5 file."""
        if self._file is not None:
            self._file.close()
            self._file = None
            self._entry_group = None

    def write_scan(
        self,
        scan_data: ScanData,
        title: str | None = None,
        scan_type: Literal["linear", "mesh", "xafs"] = "linear",
    ) -> None:
        """Write scan data to NeXus format.

        Creates NXxas-compliant structure:
        /entry (NXentry)
          /title
          /start_time (ISO 8601)
          /definition = "NXxas"
          /instrument (NXinstrument)
            /source (NXsource)
              /current (ring current from metadata)
            /monochromator (NXmonochromator)
              /energy (array, eV)
            /detector (NXdetector)
              /data (array)
          /sample (NXsample)
            /name
            /position_x, /position_y
          /data (NXdata)
            @signal = "intensity"
            @axes = ["energy"] or ["two_theta"]

        Args:
            scan_data: ScanData object to export
            title: Scan title (default: from metadata or auto-generated)
            scan_type: Scan type for proper axis labeling

        Raises:
            RuntimeError: If file is not open
            ValueError: If scan_data validation fails
        """
        if self._file is None or self._entry_group is None:
            raise RuntimeError("File not open. Use open() or context manager.")

        # Validate scan data
        scan_data.validate()

        # Set title
        if title is None:
            title_str: str | object = scan_data.metadata.get(
                "title", f"Scan {datetime.datetime.now().isoformat()}"
            )
            title = str(title_str) if not isinstance(title_str, str) else title_str
        self._entry_group.attrs["title"] = title

        # Set start time (ISO 8601)
        if len(scan_data.timestamps) > 0:
            start_time = datetime.datetime.fromtimestamp(scan_data.timestamps[0], tz=datetime.UTC)
            self._entry_group.attrs["start_time"] = start_time.isoformat()

        # Create instrument group
        instrument_group = self._entry_group.create_group("instrument")
        instrument_group.attrs["NX_class"] = "NXinstrument"

        # Source group
        source_group = instrument_group.create_group("source")
        source_group.attrs["NX_class"] = "NXsource"
        source_group.attrs["type"] = "Synchrotron X-ray Source"

        # Ring current from metadata
        ring_current = scan_data.metadata.get("ring_current", 0.0)
        source_group.create_dataset("current", data=ring_current, dtype=np.float64)

        # Monochromator group
        monochromator_group = instrument_group.create_group("monochromator")
        monochromator_group.attrs["NX_class"] = "NXmonochromator"

        # Energy axis: use motor position for XAFS, or two_theta for XRD
        n_points = len(scan_data.timestamps)
        if scan_type == "xafs" and scan_data.motor_positions:
            # Use first motor as energy (typically monochromator)
            energy_motor = next(iter(scan_data.motor_positions.values()))
            energy_data = energy_motor.astype(np.float64)
        elif scan_type in ("linear", "mesh") and scan_data.motor_positions:
            # Use first motor as two_theta or position
            energy_motor = next(iter(scan_data.motor_positions.values()))
            energy_data = energy_motor.astype(np.float64)
        else:
            # Fallback: use index
            energy_data = np.arange(n_points, dtype=np.float64)

        # Determine chunking for large datasets
        chunks = True if n_points > 10000 else None

        monochromator_group.create_dataset(
            "energy",
            data=energy_data,
            dtype=np.float64,
            compression="gzip" if self.compression > 0 else None,
            compression_opts=self.compression if self.compression > 0 else None,
            chunks=chunks,
        )

        # Detector group
        detector_group = instrument_group.create_group("detector")
        detector_group.attrs["NX_class"] = "NXdetector"

        # Write detector data (use first detector as default signal)
        if scan_data.detector_readings:
            default_detector = next(iter(scan_data.detector_readings.values()))
            detector_group.create_dataset(
                "data",
                data=default_detector.astype(np.float64),
                dtype=np.float64,
                compression="gzip" if self.compression > 0 else None,
                compression_opts=self.compression if self.compression > 0 else None,
                chunks=chunks,
            )

            # Write additional detectors as separate datasets
            for det_name, det_data in list(scan_data.detector_readings.items())[1:]:
                sanitized_name = det_name.replace(":", "_").replace("/", "_")
                detector_group.create_dataset(
                    sanitized_name,
                    data=det_data.astype(np.float64),
                    dtype=np.float64,
                    compression="gzip" if self.compression > 0 else None,
                    compression_opts=self.compression if self.compression > 0 else None,
                    chunks=chunks,
                )

        # Sample group
        sample_group = self._entry_group.create_group("sample")
        sample_group.attrs["NX_class"] = "NXsample"

        # Sample name from metadata
        sample_name = scan_data.metadata.get("sample_name", "unknown")
        sample_group.attrs["name"] = sample_name

        # Motor positions as sample positions
        motor_keys = sorted(scan_data.motor_positions.keys())
        if len(motor_keys) >= 1:
            sample_group.create_dataset(
                "position_x",
                data=scan_data.motor_positions[motor_keys[0]].astype(np.float64),
                dtype=np.float64,
                compression="gzip" if self.compression > 0 else None,
                compression_opts=self.compression if self.compression > 0 else None,
                chunks=chunks,
            )
        if len(motor_keys) >= 2:
            sample_group.create_dataset(
                "position_y",
                data=scan_data.motor_positions[motor_keys[1]].astype(np.float64),
                dtype=np.float64,
                compression="gzip" if self.compression > 0 else None,
                compression_opts=self.compression if self.compression > 0 else None,
                chunks=chunks,
            )

        # Data group (NXdata) - default plot
        data_group = self._entry_group.create_group("data")
        data_group.attrs["NX_class"] = "NXdata"

        # Set signal and axes
        if scan_data.detector_readings:
            data_group.attrs["signal"] = "intensity"
            data_group.attrs["axes"] = ["energy"] if scan_type == "xafs" else ["two_theta"]

            # Link to detector data
            data_group["intensity"] = detector_group["data"]
            data_group["energy"] = monochromator_group["energy"]

    def add_metadata(self, key: str, value: Any) -> None:
        """Add custom metadata to /entry group.

        Args:
            key: Metadata key (will be sanitized for HDF5)
            value: Metadata value (must be HDF5-serializable)

        Raises:
            RuntimeError: If file is not open
            TypeError: If value cannot be serialized to HDF5
        """
        if self._file is None or self._entry_group is None:
            raise RuntimeError("File not open. Use open() or context manager.")

        # Sanitize key (HDF5 attribute names should be valid identifiers)
        sanitized_key = key.replace(" ", "_").replace("-", "_")

        # Convert value to HDF5-compatible type
        if (
            isinstance(value, str | int | float | bool)
            or (
                isinstance(value, list | tuple)
                and all(isinstance(v, str | int | float | bool) for v in value)
            )
            or isinstance(value, np.ndarray)
        ):
            self._entry_group.attrs[sanitized_key] = value
        else:
            # Try to convert to string
            self._entry_group.attrs[sanitized_key] = str(value)
