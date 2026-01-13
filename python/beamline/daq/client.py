"""Low-level TCP client for beamline device server."""

from __future__ import annotations

import builtins
import contextlib
import socket
from types import TracebackType

from beamline.daq.exceptions import ConnectionError, ProtocolError, TimeoutError


class DeviceClient:
    """Low-level TCP client for beamline device server.

    Handles raw protocol communication: GET, PUT, MOVE, STATUS, LIST, MONITOR, STOP.
    Thread-safe for single connection (not thread-safe across multiple connections).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5064,
        timeout: float = 5.0,
    ) -> None:
        """Initialize client with connection parameters.

        Args:
            host: Server hostname or IP address
            port: TCP port (default: 5064, EPICS standard)
            timeout: Socket timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._connected = False

    def __enter__(self) -> DeviceClient:
        """Context manager entry: connect to server."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit: close connection."""
        self.disconnect()

    def connect(self) -> None:
        """Establish TCP connection to server.

        Raises:
            ConnectionError: If connection fails
        """
        if self._connected:
            return

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
            self._connected = True
        except OSError as e:
            self._connected = False
            if self._socket:
                with contextlib.suppress(Exception):
                    self._socket.close()
                self._socket = None
            raise ConnectionError(f"Failed to connect to {self.host}:{self.port}") from e

    def disconnect(self) -> None:
        """Close TCP connection."""
        if self._socket:
            with contextlib.suppress(Exception):
                self._socket.close()
            self._socket = None
        self._connected = False

    def get(self, pv: str) -> float:
        """Read process variable value.

        Args:
            pv: Process variable name (e.g., "BL02:RING:CURRENT")

        Returns:
            PV value as float

        Raises:
            ConnectionError: If not connected
            ProtocolError: If server returns error response
            ValueError: If response cannot be parsed as float
            TimeoutError: If operation times out
        """
        if not self._connected:
            raise ConnectionError("Not connected to server")

        response = self._send_command(f"GET:{pv}")
        status, data = self._parse_response(response)

        if status == "ERR":
            raise ProtocolError(data, f"Failed to get PV {pv}: {data}")

        try:
            return float(data)
        except ValueError as e:
            raise ValueError(f"Invalid float value in response: {data}") from e

    def put(self, pv: str, value: float) -> None:
        """Write process variable value.

        Args:
            pv: Process variable name
            value: Value to write

        Raises:
            ConnectionError: If not connected
            ProtocolError: If server returns error (e.g., ERR:INVALID_VALUE)
            TimeoutError: If operation times out
        """
        if not self._connected:
            raise ConnectionError("Not connected to server")

        response = self._send_command(f"PUT:{pv}:{value}")
        status, data = self._parse_response(response)

        if status == "ERR":
            raise ProtocolError(data, f"Failed to put PV {pv}={value}: {data}")

    def move(self, motor: str, position: float) -> None:
        """Move motor to position (asynchronous, non-blocking).

        Args:
            motor: Motor PV name (e.g., "BL02:SAMPLE:X")
            position: Target position

        Raises:
            ConnectionError: If not connected
            ProtocolError: If motor not found or invalid position
            TimeoutError: If operation times out
        """
        if not self._connected:
            raise ConnectionError("Not connected to server")

        response = self._send_command(f"MOVE:{motor}:{position}")
        status, data = self._parse_response(response)

        if status == "ERR":
            raise ProtocolError(data, f"Failed to move motor {motor} to {position}: {data}")

    def status(self, motor: str) -> str:
        """Get motor status.

        Args:
            motor: Motor PV name

        Returns:
            Motor status string ("IDLE" or "MOVING")

        Raises:
            ConnectionError: If not connected
            ProtocolError: If motor not found
            TimeoutError: If operation times out
        """
        if not self._connected:
            raise ConnectionError("Not connected to server")

        response = self._send_command(f"STATUS:{motor}")
        resp_status, data = self._parse_response(response)

        if resp_status == "ERR":
            raise ProtocolError(data, f"Failed to get status for motor {motor}: {data}")

        return data.strip().upper()

    def list_pvs(self, pattern: str | None = None) -> list[str]:
        """List process variables, optionally filtered by pattern.

        Args:
            pattern: Optional glob pattern (e.g., "BL02:DET:*")

        Returns:
            List of PV names

        Raises:
            ConnectionError: If not connected
            ProtocolError: If server returns error
            TimeoutError: If operation times out
        """
        if not self._connected:
            raise ConnectionError("Not connected to server")

        command = f"LIST:{pattern}" if pattern else "LIST"

        response = self._send_command(command)
        status, data = self._parse_response(response)

        if status == "ERR":
            raise ProtocolError(data, f"Failed to list PVs: {data}")

        if not data or data.strip() == "":
            return []

        return [pv.strip() for pv in data.split(",") if pv.strip()]

    def monitor_start(self, pv: str, interval_ms: int) -> None:
        """Start monitoring PV with periodic updates.

        Note: Monitoring implementation deferred to Phase 3.2 (async support).

        Args:
            pv: Process variable name
            interval_ms: Monitoring interval in milliseconds

        Raises:
            ConnectionError: If not connected
            ProtocolError: If server returns error
            TimeoutError: If operation times out
        """
        if not self._connected:
            raise ConnectionError("Not connected to server")

        response = self._send_command(f"MONITOR:{pv}:{interval_ms}")
        status, data = self._parse_response(response)

        if status == "ERR":
            raise ProtocolError(data, f"Failed to start monitoring {pv}: {data}")

    def monitor_stop(self) -> None:
        """Stop monitoring.

        Raises:
            ConnectionError: If not connected
            ProtocolError: If server returns error
            TimeoutError: If operation times out
        """
        if not self._connected:
            raise ConnectionError("Not connected to server")

        response = self._send_command("STOP")
        status, data = self._parse_response(response)

        if status == "ERR":
            raise ProtocolError(data, f"Failed to stop monitoring: {data}")

    def _send_command(self, command: str) -> str:
        """Send command and receive response.

        Internal method handling socket I/O and protocol parsing.

        Args:
            command: Command string (without newline)

        Returns:
            Response string (with newline stripped)

        Raises:
            ConnectionError: If socket error occurs
            TimeoutError: If operation times out
        """
        if not self._socket:
            raise ConnectionError("Socket not initialized")

        try:
            # Send command with newline
            self._socket.sendall(f"{command}\n".encode())

            # Receive response
            response_bytes = b""
            while True:
                chunk = self._socket.recv(4096)
                if not chunk:
                    raise ConnectionError("Connection closed by server")
                response_bytes += chunk
                if b"\n" in response_bytes:
                    break

            response = response_bytes.decode("utf-8").strip()
            return response

        except builtins.TimeoutError as e:
            raise TimeoutError(f"Operation timed out after {self.timeout}s") from e
        except OSError as e:
            self._connected = False
            raise ConnectionError(f"Socket error: {e}") from e

    def _parse_response(self, response: str) -> tuple[str, str]:
        """Parse response: "OK:data" or "ERR:code".

        Args:
            response: Response string from server

        Returns:
            (status, data) tuple where status is "OK" or "ERR"

        Raises:
            ProtocolError: If response format is invalid
        """
        if not response:
            raise ProtocolError("EMPTY", "Empty response from server")

        parts = response.split(":", 1)
        if len(parts) == 1:
            # Response without colon (e.g., "OK" or "ERR")
            status = parts[0].strip()
            data = ""
        else:
            status, data = parts
            status = status.strip()
            data = data.strip()

        if status not in ("OK", "ERR"):
            raise ProtocolError("INVALID", f"Invalid response format: {response}")

        return (status, data)
