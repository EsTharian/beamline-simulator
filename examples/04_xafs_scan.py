"""Example: XAFS energy scan with variable step sizes."""

from beamline.daq import DeviceClient, ScanEngine, XAFSScanConfig


def main() -> None:
    """Run a XAFS scan example."""
    with DeviceClient("localhost", 5064) as client:
        # Configure XAFS scan
        # Regions: (start_offset, stop_offset, step_size) in eV relative to edge
        config = XAFSScanConfig(
            energy_pv="BL02:MONO:ENERGY",
            edge=7112.0,  # Fe K-edge
            regions=[
                (-200.0, -30.0, 5.0),  # Pre-edge: coarse steps
                (-30.0, 30.0, 0.5),  # Edge: fine steps
                (30.0, 200.0, 2.0),  # EXAFS: medium steps
                (200.0, 600.0, 5.0),  # EXAFS: coarse steps
            ],
            detectors=["BL02:DET:I0", "BL02:DET:IT"],
            dwell_time=0.2,
        )

        # Run scan
        print("Running XAFS scan...")
        print(f"Edge energy: {config.edge} eV")
        print(f"Number of regions: {len(config.regions)}")
        print(f"Total points: {len(config.generate_energies())}")

        engine = ScanEngine(client)
        data = engine.run_xafs(config)

        # Add metadata
        data.metadata.update(
            {
                "scan_type": "XAFS",
                "edge_energy": config.edge,
                "sample_name": "Fe foil",
            }
        )

        # Export to CSV and NeXus
        data.to_csv("example_outputs/xafs_scan_001.csv")
        data.to_nexus(
            "example_outputs/xafs_scan_001.nxs",
            title="Fe K-edge XAFS",
            scan_type="xafs",
        )

        print(f"\nScan complete: {len(data.timestamps)} points")
        print(
            f"Energy range: {data.motor_positions['BL02:MONO:ENERGY'].min():.1f} to "
            f"{data.motor_positions['BL02:MONO:ENERGY'].max():.1f} eV"
        )
        print("Data exported to:")
        print("  - example_outputs/xafs_scan_001.csv")
        print("  - example_outputs/xafs_scan_001.nxs")


if __name__ == "__main__":
    main()
