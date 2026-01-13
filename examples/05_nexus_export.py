"""Example: Export scan data to NeXus/HDF5 format."""

from beamline.daq import DeviceClient, LinearScanConfig, NeXusWriter, ScanEngine


def main() -> None:
    """Run a scan and export to NeXus format."""
    with DeviceClient("localhost", 5064) as client:
        # Configure scan
        config = LinearScanConfig(
            motor="BL02:SAMPLE:X",
            start=-1000.0,
            stop=1000.0,
            steps=50,
            detectors=["BL02:DET:I0", "BL02:DET:IT"],
            dwell_time=0.1,
        )

        # Run scan
        print("Running scan...")
        engine = ScanEngine(client)
        data = engine.run_linear(config)

        # Add metadata
        data.metadata.update(
            {
                "experiment_id": "EXP001",
                "beamline": "BL02",
                "sample_name": "Si powder",
                "operator": "John Doe",
                "ring_current": 350.5,
            }
        )

        # Export to NeXus using NeXusWriter directly
        print("\nExporting to NeXus format...")
        with NeXusWriter("example_outputs/scan_nexus_001.nxs", compression=1) as writer:
            writer.write_scan(data, title="XRD Scan 001", scan_type="linear")
            writer.add_metadata("experiment_id", "EXP001")
            writer.add_metadata("beamline", "BL02")
            writer.add_metadata("sample_name", "Si powder")

        # Also export using ScanData.to_nexus() convenience method
        data.to_nexus(
            "example_outputs/scan_nexus_002.nxs",
            title="XRD Scan 002",
            scan_type="linear",
        )

        print(f"Scan complete: {len(data.timestamps)} points")
        print("NeXus files exported:")
        print("  - example_outputs/scan_nexus_001.nxs")
        print("  - example_outputs/scan_nexus_002.nxs")
        print("\nYou can open these files with h5py or NeXpy for inspection.")


if __name__ == "__main__":
    main()
