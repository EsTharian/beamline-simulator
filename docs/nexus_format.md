# NeXus/HDF5 Export Format

This document describes the NeXus/HDF5 export format used by the beamline simulator, following the NXxas application definition for X-ray Absorption Spectroscopy (XAS) data.

## Overview

The NeXus format is a standard for storing neutron, X-ray, and muon data in HDF5 files. Our implementation follows the **NXxas** application definition, which standardizes the storage of X-ray Absorption Spectroscopy data.

## File Structure

```
/entry (NXentry)
  /title                    # Scan title (string)
  /start_time              # ISO 8601 timestamp (string)
  /definition = "NXxas"    # Application definition (string)

  /instrument (NXinstrument)
    /source (NXsource)
      /current             # Ring current (float, mA)
      /type = "Synchrotron X-ray Source"

    /monochromator (NXmonochromator)
      /energy              # Energy array (float array, eV)

    /detector (NXdetector)
      /data                # Detector data (float array)
      /BL02_DET_IT         # Additional detectors (float array)

  /sample (NXsample)
    /name                  # Sample name (string)
    /position_x            # X position (float array)
    /position_y            # Y position (float array, optional)

  /data (NXdata)
    @signal = "intensity"  # Default signal dataset
    @axes = ["energy"]      # or ["two_theta"] for XRD
    /intensity             # Link to detector/data
    /energy                # Link to monochromator/energy
```

## Usage

### Basic Export

```python
from beamline.daq import ScanData, NeXusWriter

# Create scan data
data = ScanData(...)

# Export using convenience method
data.to_nexus("scan.nxs", title="My Scan", scan_type="linear")
```

### Advanced Export

```python
from beamline.daq import NeXusWriter

with NeXusWriter("scan.nxs", compression=1) as writer:
    writer.write_scan(data, title="XRD Scan 001", scan_type="linear")
    writer.add_metadata("experiment_id", "EXP001")
    writer.add_metadata("sample_name", "Si powder")
    writer.add_metadata("beamline", "BL02")
```

## Scan Types

### Linear Scan

- **Axis**: `two_theta` (for XRD) or motor position
- **Signal**: First detector in `detector_readings`
- **Energy**: Motor position (if XAFS motor) or two_theta

### XAFS Scan

- **Axis**: `energy` (eV)
- **Signal**: Detector intensity
- **Energy**: Monochromator energy from motor positions

### Mesh Scan

- **Axis**: `two_theta` or motor position
- **Signal**: Detector intensity
- **Positions**: X and Y motor positions stored in `/sample/position_x` and `/sample/position_y`

## Metadata

Custom metadata can be added to the `/entry` group:

```python
writer.add_metadata("experiment_id", "EXP001")
writer.add_metadata("operator", "John Doe")
writer.add_metadata("beamline", "BL02")
```

Metadata keys are automatically sanitized (spaces and dashes converted to underscores) for HDF5 compatibility.

## Compression

Gzip compression is applied to datasets by default (level 1). This provides a good balance between file size and read/write performance.

```python
# No compression
writer = NeXusWriter("scan.nxs", compression=0)

# High compression
writer = NeXusWriter("scan.nxs", compression=9)
```

## Chunking

For large datasets (>10,000 points), chunked storage is automatically enabled to improve read performance and enable partial I/O.

## Reading NeXus Files

### Using h5py

```python
import h5py
import numpy as np

with h5py.File("scan.nxs", "r") as f:
    entry = f["entry"]
    title = entry.attrs["title"]
    start_time = entry.attrs["start_time"]

    energy = f["entry/instrument/monochromator/energy"][:]
    intensity = f["entry/instrument/detector/data"][:]

    print(f"Title: {title}")
    print(f"Points: {len(energy)}")
```

### Using NeXpy

```python
import nexpy.api.nexus as nx

file = nx.load("scan.nxs")
entry = file["entry"]
energy = entry.instrument.monochromator.energy
intensity = entry.instrument.detector.data
```

## Validation

NeXus files can be validated using tools like:

- **pynxtools**: Python framework for NeXus validation
- **NeXpy**: GUI tool with validation features
- **h5dump**: HDF5 command-line tool

## References

- [NeXus Manual](https://manual.nexusformat.org/)
- [NXxas Application Definition](https://manual.nexusformat.org/classes/applications/NXxas.html)
- [h5py Documentation](https://docs.h5py.org/)
