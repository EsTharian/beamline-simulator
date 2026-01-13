"""Example: Basic device operations and simple scan."""

from beamline.daq import DeviceClient, Detector, Motor


def main() -> None:
    """Run basic device operations example."""
    with DeviceClient("localhost", 5064) as client:
        print("Connected to device server")

        # Read a sensor
        print("\nReading sensors...")
        ring_current = client.get("BL02:RING:CURRENT")
        print(f"Ring current: {ring_current} mA")

        vacuum = client.get("BL02:VACUUM:PRESSURE")
        print(f"Vacuum pressure: {vacuum:.2e} mbar")

        # Motor operations
        print("\nMotor operations...")
        motor = Motor(client=client, pv="BL02:SAMPLE:X")
        current_pos = motor.position()
        print(f"Current position: {current_pos:.2f} mm")

        # Move motor
        print("Moving to 100.0 mm...")
        motor.move_to(100.0)
        motor.wait_for_idle()
        new_pos = motor.position()
        print(f"New position: {new_pos:.2f} mm")

        # Detector operations
        print("\nDetector operations...")
        detector = Detector(client=client, pv="BL02:DET:I0")
        reading = detector.read()
        print(f"Detector I0 reading: {reading:.2f} counts")

        # Read multiple detectors
        print("\nReading multiple detectors...")
        readings = detector.read_multiple(n=3, dwell_time=0.1)
        print(f"Detector I0 readings: {readings.mean():.2f} counts")

        print("\nBasic operations complete!")


if __name__ == "__main__":
    main()
