# Beamline Device Simulator

A synchrotron beamline control system demonstrating device simulation, data acquisition, scan orchestration, and scientific data analysis.

## Features

- **C Device Server**: Multi-client TCP server with EPICS-style process variables
- **Python DAQ Layer**: High-level device abstractions and scan orchestration
- **Scientific Analysis**: XRD peak finding/fitting and XAFS data processing
- **NeXus Export**: HDF5 data export following NXxas application definition
- **Docker Deployment**: Containerized services with health checks

## Quick Start

### Docker (Recommended)

```bash
# Start device server and Python client
cd docker
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f device-server
```

### Local Development

#### Prerequisites

- GCC 13+ (C23 support)
- Meson & Ninja
- Python 3.12+ (3.14 recommended)
- uv (Python package manager)

#### Build Device Server

```bash
cd device
meson setup build
meson compile -C build
./build/beamline-sim
```

#### Install Python Package

```bash
cd python
uv sync --dev
uv run python -c "import beamline; print('OK')"
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                        │
│                                                          │
│  ┌──────────────┐    TCP:5064    ┌──────────────────┐   │
│  │ Device Server│◄──────────────►│ Python Client    │   │
│  │  (C, Alpine) │                 │  (Python, Slim)  │   │
│  └──────────────┘                 └──────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Python Client Stack                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │   │
│  │  │   DAQ    │  │ Analysis │  │ NeXus Export │   │   │
│  │  │  Layer   │  │  Module  │  │   (HDF5)    │   │   │
│  │  └──────────┘  └──────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
beamline-simulator/
├── device/              # C device server
│   ├── src/            # Source files
│   ├── include/        # Header files
│   └── tests/          # C unit tests
├── python/             # Python package
│   ├── beamline/
│   │   ├── daq/       # Data acquisition layer
│   │   └── analysis/  # Scientific analysis
│   └── tests/         # Python tests
├── docker/            # Docker configuration
│   ├── Dockerfile.device
│   ├── Dockerfile.python
│   └── docker-compose.yml
├── examples/          # Usage examples
│   ├── notebooks/     # Jupyter notebooks
│   └── *.py           # Python scripts
└── docs/              # Documentation
```

## API Overview

### Device Control

```python
from beamline.daq import DeviceClient, Motor, Detector

with DeviceClient("localhost", 5064) as client:
    motor = Motor(client, "BL02:SAMPLE:X")
    motor.move_to(100.0)
    motor.wait_for_idle()

    detector = Detector(client, "BL02:DET:I0")
    reading = detector.read()
```

### Scan Orchestration

```python
from beamline.daq import LinearScanConfig, ScanEngine

config = LinearScanConfig(
    motor="BL02:SAMPLE:X",
    start=-1000.0,
    stop=1000.0,
    steps=100,
    detectors=["BL02:DET:I0", "BL02:DET:IT"],
    dwell_time=0.1,
)

engine = ScanEngine(client)
data = engine.run_linear(config)
data.to_csv("scan.csv")
data.to_nexus("scan.nxs", scan_type="linear")
```

### Scientific Analysis

```python
from beamline.analysis import XRDAnalyzer, XAFSProcessor
import numpy as np

# XRD Analysis
analyzer = XRDAnalyzer()
peaks = analyzer.find_peaks(two_theta, intensity)
fit_result = analyzer.fit_peak(two_theta, intensity, center=20.0)
d_spacing = analyzer.calculate_d_spacing(20.0, wavelength=1.54)

# XAFS Processing
processor = XAFSProcessor()
e0 = processor.find_edge(energy, mu)
mu_norm = processor.normalize(energy, mu, e0)
k, chi_k = processor.extract_chi(energy, mu_norm, e0)
r, chi_r = processor.fourier_transform(k, chi_k)
```

## Examples

### Basic Scan

```bash
cd examples
python 02_linear_scan.py
```

### 2D Mesh Scan

```bash
python 03_mesh_scan.py
```

### XAFS Scan

```bash
python 04_xafs_scan.py
```

### NeXus Export

```bash
python 05_nexus_export.py
```

See `examples/` directory for more examples and Jupyter notebooks.

## Docker Services

### Device Server

- **Image**: `beamline-simulator/device-server:latest`
- **Port**: 5064
- **Health Check**: TCP connectivity on port 5064

### Python Client

- **Image**: `beamline-simulator/python-client:latest`
- **Depends on**: Device server
- **Volumes**: `/data` for output files

### Docker Compose

```bash
# Start all services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f
```

## Development

### Running Tests

```bash
# C tests
cd device
meson test -C build

# Python tests
cd python
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=beamline --cov-report=term-missing
```

### Code Quality

```bash
cd python

# Linting
uv run ruff check beamline/ tests/

# Type checking
uv run mypy beamline/

# Formatting
uv run ruff format beamline/ tests/
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Documentation

- [Architecture](docs/architecture.md) - System architecture details
- [NeXus Format](docs/nexus_format.md) - NeXus/HDF5 export format
- [API Reference](docs/api.md) - Python API documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT
