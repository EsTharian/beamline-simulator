"""Example: Linear scan with motor and detectors."""

from beamline.daq import DeviceClient, LinearScanConfig, ScanEngine


def main() -> None:
    """Run a linear scan example."""
    with DeviceClient("localhost", 5064) as client:
        # Configure scan
        config = LinearScanConfig(
            motor="BL02:SAMPLE:X",
            start=-1000.0,
            stop=1000.0,
            steps=100,
            detectors=["BL02:DET:I0", "BL02:DET:IT"],
            dwell_time=0.1,
        )

        # Run scan
        print("Running scan...")
        engine = ScanEngine(client)
        data = engine.run_linear(config)

        # Export
        data.to_csv("example_outputs/scan_001.csv")
        print(f"Scan complete: {len(data.timestamps)} points")
        print(f"Motor range: {data.motor_positions['BL02:SAMPLE:X'].min():.1f} to "
              f"{data.motor_positions['BL02:SAMPLE:X'].max():.1f}")
        print(f"Detector I0 range: {data.detector_readings['BL02:DET:I0'].min():.0f} to "
              f"{data.detector_readings['BL02:DET:I0'].max():.0f}")
        print(f"Data exported to example_outputs/scan_001.csv")


if __name__ == "__main__":
    main()
