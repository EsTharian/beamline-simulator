"""High-level device abstractions for beamline control."""

from __future__ import annotations

import time
from enum import Enum

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from beamline.daq.client import DeviceClient
from beamline.daq.exceptions import TimeoutError


class MotorStatus(str, Enum):
    """Motor status enumeration."""

    IDLE = "IDLE"
    MOVING = "MOVING"


class Motor(BaseModel):
    """High-level motor abstraction.

    Provides convenient methods for motor control with automatic readback
    and status polling.
    """

    pv: str = Field(..., description="Motor setpoint PV (e.g., 'BL02:SAMPLE:X')")
    client: DeviceClient = Field(..., description="DeviceClient instance")

    model_config = ConfigDict(strict=True, arbitrary_types_allowed=True)

    @field_validator("pv")
    @classmethod
    def validate_pv(cls, v: str) -> str:
        """Validate PV name format."""
        if not v or ":" not in v:
            raise ValueError(f"Invalid PV name: {v}")
        return v

    def move_to(self, position: float, wait: bool = True, timeout: float = 60.0) -> None:
        """Move motor to target position.

        Args:
            position: Target position
            wait: If True, block until motor reaches target
            timeout: Maximum wait time in seconds (if wait=True)

        Raises:
            TimeoutError: If motor doesn't reach target within timeout
            ProtocolError: If motor movement fails
        """
        self.client.move(self.pv, position)

        if wait:
            self.wait_for_idle(timeout=timeout)

    def position(self) -> float:
        """Read current motor position (readback PV).

        Returns:
            Current position from .RBV PV

        Raises:
            ProtocolError: If readback fails
        """
        return self.client.get(self.readback_pv)

    def status(self) -> MotorStatus:
        """Get motor status.

        Returns:
            MotorStatus enum

        Raises:
            ProtocolError: If status check fails
        """
        status_str = self.client.status(self.pv)
        try:
            return MotorStatus(status_str)
        except ValueError:
            # Handle unexpected status values
            return MotorStatus.IDLE if status_str == "IDLE" else MotorStatus.MOVING

    def wait_for_idle(self, timeout: float = 60.0, poll_interval: float = 0.1) -> None:
        """Wait until motor is idle.

        Polls STATUS command until IDLE or timeout.

        Args:
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Raises:
            TimeoutError: If motor doesn't become idle within timeout
        """
        start_time = time.time()

        while True:
            current_status = self.status()
            if current_status == MotorStatus.IDLE:
                return

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Motor {self.pv} did not reach IDLE state within {timeout}s")

            time.sleep(poll_interval)

    @property
    def readback_pv(self) -> str:
        """Get readback PV name (.RBV suffix)."""
        return f"{self.pv}.RBV"


class Detector(BaseModel):
    """High-level detector abstraction."""

    pv: str = Field(..., description="Detector PV name")
    client: DeviceClient = Field(..., description="DeviceClient instance")

    model_config = ConfigDict(strict=True, arbitrary_types_allowed=True)

    def read(self) -> float:
        """Read detector value.

        Returns:
            Detector reading

        Raises:
            ProtocolError: If read fails
        """
        return self.client.get(self.pv)

    def read_multiple(self, n: int, dwell_time: float = 0.1) -> np.ndarray:
        """Read detector multiple times and return array of readings.

        Useful for noise reduction or averaging.

        Args:
            n: Number of readings
            dwell_time: Time between readings in seconds

        Returns:
            Array of readings

        Raises:
            ProtocolError: If any read fails
        """
        readings = []
        for _ in range(n):
            readings.append(self.read())
            if dwell_time > 0:
                time.sleep(dwell_time)
        return np.array(readings)


class Shutter(BaseModel):
    """Shutter control abstraction."""

    status_pv: str = Field(default="BL02:SHUTTER:STATUS", description="Status PV name")
    cmd_pv: str = Field(default="BL02:SHUTTER:CMD", description="Command PV name")
    client: DeviceClient = Field(..., description="DeviceClient instance")

    model_config = ConfigDict(strict=True, arbitrary_types_allowed=True)

    def open(self) -> None:
        """Open shutter.

        Raises:
            ProtocolError: If command fails
        """
        self.client.put(self.cmd_pv, 1.0)

    def close(self) -> None:
        """Close shutter.

        Raises:
            ProtocolError: If command fails
        """
        self.client.put(self.cmd_pv, 0.0)

    def is_open(self) -> bool:
        """Check if shutter is open.

        Returns:
            True if shutter is open, False otherwise

        Raises:
            ProtocolError: If status read fails
        """
        return self.client.get(self.status_pv) > 0.5
