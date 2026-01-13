"""Scan engine for beamline data acquisition."""

from __future__ import annotations

import time
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from beamline.daq.client import DeviceClient
from beamline.daq.data import ScanData
from beamline.daq.device import Motor


class ScanConfig(BaseModel):
    """Base scan configuration."""

    detectors: list[str] = Field(..., min_length=1, description="List of detector PVs")
    dwell_time: float = Field(default=0.1, gt=0, description="Dwell time per point (seconds)")

    model_config = ConfigDict(strict=True)


class LinearScanConfig(ScanConfig):
    """Linear 1D scan configuration."""

    scan_type: Literal["linear"] = "linear"
    motor: str = Field(..., description="Motor PV name")
    start: float = Field(..., description="Start position")
    stop: float = Field(..., description="Stop position")
    steps: int = Field(..., gt=0, description="Number of steps")

    @field_validator("stop")
    @classmethod
    def validate_range(cls, v: float, info) -> float:
        """Validate start < stop."""
        if "start" in info.data and v <= info.data["start"]:
            raise ValueError("stop must be greater than start")
        return v

    @property
    def positions(self) -> np.ndarray:
        """Generate motor positions array."""
        return np.linspace(self.start, self.stop, self.steps)


class MeshScanConfig(ScanConfig):
    """2D mesh scan configuration."""

    scan_type: Literal["mesh"] = "mesh"
    motor1: tuple[str, float, float, int] = Field(
        ...,
        description="(PV, start, stop, steps) for first motor",
    )
    motor2: tuple[str, float, float, int] = Field(
        ...,
        description="(PV, start, stop, steps) for second motor",
    )

    @field_validator("motor1", "motor2")
    @classmethod
    def validate_motor_range(
        cls, v: tuple[str, float, float, int]
    ) -> tuple[str, float, float, int]:
        """Validate motor range."""
        pv, start, stop, steps = v
        if steps <= 0:
            raise ValueError(f"Motor {pv}: steps must be > 0")
        if stop <= start:
            raise ValueError(f"Motor {pv}: stop must be > start")
        return v

    @property
    def positions1(self) -> np.ndarray:
        """Generate motor1 positions."""
        pv, start, stop, steps = self.motor1
        return np.linspace(start, stop, steps)

    @property
    def positions2(self) -> np.ndarray:
        """Generate motor2 positions."""
        pv, start, stop, steps = self.motor2
        return np.linspace(start, stop, steps)


class XAFSScanConfig(ScanConfig):
    """XAFS energy scan configuration with variable step sizes."""

    scan_type: Literal["xafs"] = "xafs"
    energy_pv: str = Field(default="BL02:MONO:ENERGY", description="Energy PV name")
    edge: float = Field(..., gt=0, description="Absorption edge energy (eV)")
    regions: list[tuple[float, float, float]] = Field(
        ...,
        description="List of (start_offset, stop_offset, step_size) tuples in eV",
    )

    @field_validator("regions")
    @classmethod
    def validate_regions(
        cls, v: list[tuple[float, float, float]]
    ) -> list[tuple[float, float, float]]:
        """Validate regions are non-overlapping and ordered."""
        if not v:
            raise ValueError("At least one region required")

        for i, (start_offset, stop_offset, step_size) in enumerate(v):
            if step_size <= 0:
                raise ValueError(f"Region {i}: step_size must be > 0")
            if stop_offset <= start_offset:
                raise ValueError(f"Region {i}: stop_offset must be > start_offset")

        # Check ordering (regions should be in order)
        for i in range(len(v) - 1):
            current_stop = v[i][1]
            next_start = v[i + 1][0]
            if next_start < current_stop:
                raise ValueError(f"Region {i + 1} overlaps with region {i}")

        return v

    def generate_energies(self) -> np.ndarray:
        """Generate energy array from regions.

        Returns:
            Array of energy values in eV
        """
        energies: list[float] = []
        for start_offset, stop_offset, step_size in self.regions:
            start = self.edge + start_offset
            stop = self.edge + stop_offset
            n_steps = int((stop - start) / step_size) + 1
            region_energies = np.linspace(start, stop, n_steps)
            energies.extend(region_energies)
        return np.array(energies)


class ScanEngine:
    """Scan execution engine."""

    def __init__(self, client: DeviceClient) -> None:
        """Initialize scan engine with device client.

        Args:
            client: DeviceClient instance
        """
        self.client = client

    def run_linear(self, config: LinearScanConfig) -> ScanData:
        """Execute linear scan.

        Algorithm:
        1. Generate motor positions
        2. For each position:
           a. Move motor to position (wait for completion)
           b. Sleep dwell_time
           c. Read all detectors
           d. Record timestamp
        3. Return ScanData

        Args:
            config: Linear scan configuration

        Returns:
            ScanData with motor positions, detector readings, and timestamps
        """
        motor = Motor(pv=config.motor, client=self.client)
        positions = config.positions
        n_points = len(positions)

        # Pre-allocate arrays
        timestamps = np.zeros(n_points)
        detector_data: dict[str, list[float]] = {det: [] for det in config.detectors}

        # Execute scan
        for i, pos in enumerate(positions):
            # Move motor
            motor.move_to(pos, wait=True, timeout=60.0)

            # Dwell time
            time.sleep(config.dwell_time)

            # Read detectors
            timestamp = time.time()
            timestamps[i] = timestamp

            for det_pv in config.detectors:
                value = self.client.get(det_pv)
                detector_data[det_pv].append(value)

        # Convert lists to numpy arrays
        detector_readings = {det_pv: np.array(values) for det_pv, values in detector_data.items()}

        return ScanData(
            motor_positions={config.motor: positions},
            detector_readings=detector_readings,
            timestamps=timestamps,
            metadata={
                "scan_type": "linear",
                "motor": config.motor,
                "start": config.start,
                "stop": config.stop,
                "steps": config.steps,
                "dwell_time": config.dwell_time,
            },
        )

    def run_mesh(self, config: MeshScanConfig) -> ScanData:
        """Execute 2D mesh scan.

        Algorithm:
        1. Generate motor1 and motor2 position grids
        2. For each (pos1, pos2) combination:
           a. Move both motors
           b. Wait for both to be idle
           c. Sleep dwell_time
           d. Read all detectors
        3. Return ScanData with 2D arrays flattened

        Args:
            config: Mesh scan configuration

        Returns:
            ScanData with motor positions, detector readings, and timestamps
        """
        motor1_pv, motor1_start, motor1_stop, motor1_steps = config.motor1
        motor2_pv, motor2_start, motor2_stop, motor2_steps = config.motor2

        motor1 = Motor(pv=motor1_pv, client=self.client)
        motor2 = Motor(pv=motor2_pv, client=self.client)

        positions1 = config.positions1
        positions2 = config.positions2

        n_points = len(positions1) * len(positions2)

        # Pre-allocate arrays
        timestamps = np.zeros(n_points)
        motor1_positions = np.zeros(n_points)
        motor2_positions = np.zeros(n_points)
        detector_data: dict[str, list[float]] = {det: [] for det in config.detectors}

        # Execute scan
        point_idx = 0
        for pos1 in positions1:
            for pos2 in positions2:
                # Move both motors
                motor1.move_to(pos1, wait=True, timeout=60.0)
                motor2.move_to(pos2, wait=True, timeout=60.0)

                # Dwell time
                time.sleep(config.dwell_time)

                # Read detectors
                timestamp = time.time()
                timestamps[point_idx] = timestamp
                motor1_positions[point_idx] = pos1
                motor2_positions[point_idx] = pos2

                for det_pv in config.detectors:
                    value = self.client.get(det_pv)
                    detector_data[det_pv].append(value)

                point_idx += 1

        # Convert lists to numpy arrays
        detector_readings = {det_pv: np.array(values) for det_pv, values in detector_data.items()}

        return ScanData(
            motor_positions={
                motor1_pv: motor1_positions,
                motor2_pv: motor2_positions,
            },
            detector_readings=detector_readings,
            timestamps=timestamps,
            metadata={
                "scan_type": "mesh",
                "motor1": motor1_pv,
                "motor2": motor2_pv,
                "dwell_time": config.dwell_time,
            },
        )

    def run_xafs(self, config: XAFSScanConfig) -> ScanData:
        """Execute XAFS energy scan.

        Algorithm:
        1. Generate energy array from regions
        2. For each energy:
           a. Move monochromator to energy
           b. Wait for completion
           c. Sleep dwell_time
           d. Read all detectors (I0, IT, IF)
        3. Return ScanData

        Args:
            config: XAFS scan configuration

        Returns:
            ScanData with energy positions, detector readings, and timestamps
        """
        motor = Motor(pv=config.energy_pv, client=self.client)
        energies = config.generate_energies()
        n_points = len(energies)

        # Pre-allocate arrays
        timestamps = np.zeros(n_points)
        detector_data: dict[str, list[float]] = {det: [] for det in config.detectors}

        # Execute scan
        for i, energy in enumerate(energies):
            # Move monochromator
            motor.move_to(energy, wait=True, timeout=60.0)

            # Dwell time
            time.sleep(config.dwell_time)

            # Read detectors
            timestamp = time.time()
            timestamps[i] = timestamp

            for det_pv in config.detectors:
                value = self.client.get(det_pv)
                detector_data[det_pv].append(value)

        # Convert lists to numpy arrays
        detector_readings = {det_pv: np.array(values) for det_pv, values in detector_data.items()}

        return ScanData(
            motor_positions={config.energy_pv: energies},
            detector_readings=detector_readings,
            timestamps=timestamps,
            metadata={
                "scan_type": "xafs",
                "energy_pv": config.energy_pv,
                "edge": config.edge,
                "regions": config.regions,
                "dwell_time": config.dwell_time,
            },
        )

    def run(
        self,
        config: LinearScanConfig | MeshScanConfig | XAFSScanConfig,
    ) -> ScanData:
        """Run scan based on config type.

        Dispatches to appropriate run_* method.

        Args:
            config: Scan configuration

        Returns:
            ScanData with scan results
        """
        if isinstance(config, LinearScanConfig):
            return self.run_linear(config)
        elif isinstance(config, MeshScanConfig):
            return self.run_mesh(config)
        elif isinstance(config, XAFSScanConfig):
            return self.run_xafs(config)
        else:
            raise ValueError(f"Unknown scan config type: {type(config)}")
