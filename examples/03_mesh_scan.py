"""Example: 2D mesh scan with dual motors."""

from beamline.daq import DeviceClient, MeshScanConfig, ScanEngine


def main() -> None:
    """Run a 2D mesh scan example."""
    with DeviceClient("localhost", 5064) as client:
        # Configure mesh scan
        config = MeshScanConfig(
            motor1=("BL02:SAMPLE:X", -500.0, 500.0, 20),
            motor2=("BL02:SAMPLE:Y", -200.0, 200.0, 15),
            detectors=["BL02:DET:I0", "BL02:DET:IT"],
            dwell_time=0.05,
        )

        # Run scan
        print("Running 2D mesh scan...")
        print(
            f"Motor X: {config.motor1[1]:.1f} to {config.motor1[2]:.1f} ({config.motor1[3]} steps)"
        )
        print(
            f"Motor Y: {config.motor2[1]:.1f} to {config.motor2[2]:.1f} ({config.motor2[3]} steps)"
        )
        print(f"Total points: {config.motor1[3] * config.motor2[3]}")

        engine = ScanEngine(client)
        data = engine.run_mesh(config)

        # Export
        data.to_csv("example_outputs/mesh_scan_001.csv")
        print(f"\nScan complete: {len(data.timestamps)} points")
        print("Data exported to example_outputs/mesh_scan_001.csv")


if __name__ == "__main__":
    main()
