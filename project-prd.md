# Beamline Device Simulator - Product Requirements Document

## Executive Summary

A synchrotron beamline control system demonstrating end-to-end capabilities: device simulation, data acquisition, scan orchestration, and scientific data analysis. The project emulates real-world patterns found at facilities like SESAME, bridging control systems engineering with materials science domain expertise.

---

## Problem Statement

Synchrotron beamlines require integrated software systems that span multiple layers:

1. **Device Control** - Real-time communication with hardware (motors, detectors, shutters)
2. **Data Acquisition** - Coordinated scans with metadata capture
3. **Scientific Analysis** - Domain-specific data processing (XRD, XAFS, etc.)
4. **Reliability** - Stable operation in 24/7 facility environments

This project addresses all four layers in a demonstrable package, showing both software engineering proficiency and materials science domain knowledge.

---

## Goals & Non-Goals

### Goals

- Production-quality TCP server implementation in C
- Multi-client connection management using I/O multiplexing
- EPICS-style process variable architecture
- Scan orchestration tools matching real beamline workflows
- Materials science analysis utilities (XRD, XAFS)
- NeXus/HDF5 data export (synchrotron standard format)
- Docker-based deployment

### Non-Goals

- Full EPICS IOC implementation (pattern demonstration only)
- GUI application (CLI/TUI sufficient)
- Production-grade security hardening
- Complete analysis suite (representative utilities only)

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Network                              │
│                                                                     │
│  ┌─────────────────┐    TCP:5064    ┌───────────────────────────┐  │
│  │  Device Server  │◄──────────────►│  Python Client Stack      │  │
│  │  (C)            │                │                           │  │
│  │                 │                │  ┌─────────────────────┐  │  │
│  │  - Sensors      │                │  │ DAQ Layer           │  │  │
│  │  - Motors       │                │  │ - Device Client     │  │  │
│  │  - Protocol     │                │  │ - Scan Engine       │  │  │
│  │  - Multi-client │                │  └─────────────────────┘  │  │
│  │                 │                │            │              │  │
│  │                 │                │            ▼              │  │
│  │                 │                │  ┌─────────────────────┐  │  │
│  │                 │                │  │ Analysis Layer      │  │  │
│  │                 │                │  │ - XRD Analysis      │  │  │
│  │                 │                │  │ - XAFS Processing   │  │  │
│  │                 │                │  │ - NeXus Export      │  │  │
│  │                 │                │  └─────────────────────┘  │  │
│  └─────────────────┘                └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. Device Server (C)

**Responsibilities:**

- TCP server on port 5064 (EPICS Channel Access default)
- Simulated sensors, motors, and shutters
- EPICS-style naming convention (FACILITY:SUBSYSTEM:DEVICE)
- Multi-client support via `select()` multiplexing

**Modules:**

| Module   | Files          | Responsibility                               |
| -------- | -------------- | -------------------------------------------- |
| Main     | `main.c`       | Entry point, initialization, signal handling |
| Server   | `server.c/h`   | TCP socket management, client tracking       |
| Protocol | `protocol.c/h` | Command parsing, response formatting         |
| Devices  | `devices.c/h`  | Sensor/motor/shutter simulation              |
| Utils    | `utils.c/h`    | Logging, error handling                      |

#### 2. DAQ Layer (Python)

**Responsibilities:**

- Device communication abstraction
- Scan orchestration (linear, mesh, XAFS-optimized)
- Metadata capture
- Data export to standard formats

**Modules:**

| Module      | Description                          |
| ----------- | ------------------------------------ |
| `client.py` | Low-level TCP client wrapper         |
| `device.py` | High-level device abstractions       |
| `scan.py`   | Scan engine with multiple strategies |
| `nexus.py`  | NeXus/HDF5 export utilities          |

#### 3. Analysis Layer (Python)

**Responsibilities:**

- Materials science data processing
- XRD pattern analysis (peak fitting, phase ID)
- XAFS data reduction (normalization, χ(k) extraction)
- Integration with NumPy/SciPy ecosystem

**Modules:**

| Module     | Description                 |
| ---------- | --------------------------- |
| `xrd.py`   | Powder diffraction analysis |
| `xafs.py`  | XAFS/EXAFS processing       |
| `utils.py` | Common scientific utilities |

---

## Protocol Specification

### Message Format

```
REQUEST:  <COMMAND>:<TARGET>[:<VALUE>]\n
RESPONSE: <STATUS>:<DATA>\n
```

### Process Variable Naming Convention

Following EPICS standards:

```
BEAMLINE:SUBSYSTEM:DEVICE[:FIELD]

Examples:
  BL02:MONO:ENERGY          - Monochromator energy (eV)
  BL02:MONO:ENERGY.RBV      - Readback value
  BL02:SAMPLE:X             - Sample stage X position (μm)
  BL02:DET:COUNTS           - Detector counts
  BL02:SHUTTER:STATUS       - Photon shutter (0/1)
  BL02:VACUUM:PRESSURE      - Beamline vacuum (mbar)
```

### Commands

| Command | Format                       | Response                  | Description              |
| ------- | ---------------------------- | ------------------------- | ------------------------ |
| GET     | `GET:<pv>`                   | `OK:<value>`              | Read process variable    |
| PUT     | `PUT:<pv>:<value>`           | `OK:PUT`                  | Write process variable   |
| MOVE    | `MOVE:<motor>:<position>`    | `OK:MOVING`               | Move motor (async)       |
| STATUS  | `STATUS:<motor>`             | `OK:IDLE\|MOVING`         | Check motor status       |
| LIST    | `LIST[:<pattern>]`           | `OK:<pv1>,<pv2>,...`      | List PVs (optional glob) |
| MONITOR | `MONITOR:<pv>:<interval_ms>` | Continuous `DATA:<value>` | Subscribe to updates     |
| STOP    | `STOP`                       | `OK:STOPPED`              | Stop monitoring          |
| PING    | `PING`                       | `OK:PONG`                 | Connection check         |
| QUIT    | `QUIT`                       | `OK:BYE`                  | Close connection         |

### Error Responses

```
ERR:UNKNOWN_CMD       - Unrecognized command
ERR:UNKNOWN_PV        - Process variable not found
ERR:INVALID_VALUE     - Value out of range or wrong type
ERR:MOTOR_FAULT       - Motor error condition
ERR:INTERNAL          - Server internal error
```

### Simulated Devices

| PV                     | Type | Unit   | Range           | Description            |
| ---------------------- | ---- | ------ | --------------- | ---------------------- |
| `BL02:RING:CURRENT`    | AI   | mA     | 0-400           | Storage ring current   |
| `BL02:MONO:ENERGY`     | AO   | eV     | 4000-20000      | Monochromator energy   |
| `BL02:MONO:ENERGY.RBV` | AI   | eV     | -               | Energy readback        |
| `BL02:SAMPLE:X`        | AO   | μm     | -10000 to 10000 | Sample X position      |
| `BL02:SAMPLE:Y`        | AO   | μm     | -10000 to 10000 | Sample Y position      |
| `BL02:SAMPLE:Z`        | AO   | μm     | -5000 to 5000   | Sample Z position      |
| `BL02:SAMPLE:THETA`    | AO   | deg    | -180 to 180     | Sample rotation        |
| `BL02:DET:I0`          | AI   | counts | 0-1e6           | Incident intensity     |
| `BL02:DET:IT`          | AI   | counts | 0-1e6           | Transmitted intensity  |
| `BL02:DET:IF`          | AI   | counts | 0-1e5           | Fluorescence intensity |
| `BL02:VACUUM:PRESSURE` | AI   | mbar   | 1e-10 to 1e-8   | Beamline vacuum        |
| `BL02:HUTCH:TEMP`      | AI   | °C     | 20-26           | Hutch temperature      |
| `BL02:SHUTTER:STATUS`  | BI   | -      | 0/1             | Shutter state          |
| `BL02:SHUTTER:CMD`     | BO   | -      | 0/1             | Shutter command        |

---

## Scan Engine Specification

### Scan Types

#### 1. Linear Scan

Standard 1D scan varying one motor while reading detectors.

```python
scan = LinearScan(
    motor="BL02:SAMPLE:X",
    start=-1000,
    stop=1000,
    steps=100,
    detectors=["BL02:DET:I0", "BL02:DET:IT"]
)
```

#### 2. Mesh Scan

2D mapping scan over two motors.

```python
scan = MeshScan(
    motor1=("BL02:SAMPLE:X", -500, 500, 50),
    motor2=("BL02:SAMPLE:Y", -500, 500, 50),
    detectors=["BL02:DET:IF"]
)
```

#### 3. XAFS Scan

Energy scan with variable step sizes optimized for X-ray absorption spectroscopy.

```python
scan = XAFSScan(
    energy_pv="BL02:MONO:ENERGY",
    edge=7112,  # Fe K-edge (eV)
    regions=[
        (-150, -20, 5.0),   # Pre-edge: 5 eV steps
        (-20, 30, 0.5),     # Edge: 0.5 eV steps
        (30, 500, 2.0),     # EXAFS: 2 eV steps
    ],
    detectors=["BL02:DET:I0", "BL02:DET:IT", "BL02:DET:IF"]
)
```

### Scan Output

All scans produce structured data with:

- Motor positions at each point
- Detector readings at each point
- Timestamps
- Metadata (scan parameters, user, beamline conditions)

Export formats:

- NumPy arrays (in-memory)
- CSV (simple interchange)
- NeXus/HDF5 (archival, facility standard)

---

## Analysis Module Specification

### XRD Analysis (`analysis/xrd.py`)

```python
class XRDAnalyzer:
    """Powder X-ray diffraction analysis utilities."""

    def find_peaks(self, two_theta: np.ndarray, intensity: np.ndarray,
                   prominence: float = 0.1) -> List[Peak]:
        """
        Identify diffraction peaks using scipy.signal.find_peaks.

        Returns list of Peak objects with position, intensity, FWHM.
        """

    def fit_peak(self, two_theta: np.ndarray, intensity: np.ndarray,
                 center: float, width: float = 1.0,
                 model: str = "gaussian") -> FitResult:
        """
        Fit peak profile (Gaussian, Lorentzian, or Pseudo-Voigt).

        Returns fitted parameters with uncertainties.
        """

    def calculate_d_spacing(self, two_theta: float,
                            wavelength: float = 1.5406) -> float:
        """
        Calculate d-spacing using Bragg's law: nλ = 2d sin(θ)

        Args:
            two_theta: Peak position in degrees
            wavelength: X-ray wavelength in Å (default: Cu Kα)
        """

    def estimate_crystallite_size(self, fwhm: float, two_theta: float,
                                   wavelength: float = 1.5406,
                                   K: float = 0.9) -> float:
        """
        Estimate crystallite size using Scherrer equation.

        D = Kλ / (β cos θ)

        Args:
            fwhm: Peak FWHM in degrees
            two_theta: Peak position in degrees
            wavelength: X-ray wavelength in Å
            K: Shape factor (default: 0.9)

        Returns:
            Crystallite size in nm
        """

    def calculate_lattice_parameter(self, d_spacings: List[float],
                                     hkl_indices: List[Tuple[int, int, int]],
                                     crystal_system: str = "cubic") -> float:
        """
        Calculate lattice parameter from indexed peaks.
        """
```

### XAFS Analysis (`analysis/xafs.py`)

```python
class XAFSProcessor:
    """XAFS/EXAFS data processing utilities."""

    def find_edge(self, energy: np.ndarray, mu: np.ndarray) -> float:
        """
        Determine absorption edge energy (E0).

        Uses maximum of first derivative method.
        """

    def normalize(self, energy: np.ndarray, mu: np.ndarray,
                  e0: float = None,
                  pre_edge: Tuple[float, float] = (-150, -30),
                  post_edge: Tuple[float, float] = (50, 300)) -> np.ndarray:
        """
        Perform edge-step normalization.

        1. Subtract pre-edge baseline (linear fit)
        2. Normalize to post-edge (linear or polynomial fit)
        """

    def extract_chi(self, energy: np.ndarray, mu: np.ndarray,
                    e0: float, rbkg: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract χ(k) from normalized μ(E).

        1. Convert E to k: k = √(2m(E-E0)/ℏ²)
        2. Subtract background spline
        3. Return k, χ(k)
        """

    def fourier_transform(self, k: np.ndarray, chi: np.ndarray,
                          kmin: float = 2.0, kmax: float = 12.0,
                          kweight: int = 2,
                          window: str = "hanning") -> Tuple[np.ndarray, np.ndarray]:
        """
        Fourier transform χ(k) to R-space.

        Args:
            k: Wavenumber array (Å⁻¹)
            chi: χ(k) array
            kmin, kmax: Transform range
            kweight: k-weighting (0, 1, 2, or 3)
            window: Apodization window

        Returns:
            R (Å), magnitude of χ(R)
        """
```

### NeXus Export (`daq/nexus.py`)

```python
class NeXusWriter:
    """NeXus/HDF5 file writer following NXxas application definition."""

    def __init__(self, filename: str):
        """Initialize HDF5 file with NeXus structure."""

    def write_scan(self, scan_data: ScanData):
        """
        Write scan data to NeXus format.

        Structure:
        /entry
          /title
          /start_time
          /instrument
            /source
              /current (ring current)
            /monochromator
              /energy
            /detector
              /data
          /sample
            /name
            /position_x
            /position_y
          /data (default NXdata group)
            @signal = "intensity"
            @axes = ["energy"]
        """

    def add_metadata(self, key: str, value: Any):
        """Add arbitrary metadata to file."""
```

---

## Implementation Phases

### Phase 1: Core Server

- TCP server with single client
- Basic command protocol (GET, PUT, PING, QUIT)
- Simulated sensors (read-only PVs)
- Signal handling for graceful shutdown

### Phase 2: Multi-Client & Motors

- `select()` based multiplexing
- Client connection tracking
- Motor simulation with MOVE/STATUS
- Asynchronous move completion

### Phase 3: Scan Engine

- Device client wrapper
- LinearScan implementation
- MeshScan implementation
- XAFSScan with variable step sizes
- CSV export

### Phase 4: Analysis Module

- XRD peak fitting
- Scherrer equation
- XAFS normalization
- χ(k) extraction
- Fourier transform

### Phase 5: Integration & Polish

- NeXus/HDF5 export
- Docker containerization
- Documentation
- Example notebooks

---

## File Structure

```
beamline-simulator/
├── README.md
├── LICENSE (MIT)
├── .gitignore
│
├── device/
│   ├── meson.build
│   ├── .clang-format
│   ├── .clang-tidy
│   ├── src/
│   │   ├── main.c
│   │   ├── server.c
│   │   ├── server.h
│   │   ├── protocol.c
│   │   ├── protocol.h
│   │   ├── devices.c
│   │   ├── devices.h
│   │   ├── utils.c
│   │   └── utils.h
│   ├── include/
│   │   └── config.h
│   └── tests/
│       └── test_*.c
│
├── python/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .python-version
│   ├── .pre-commit-config.yaml
│   ├── beamline/
│   │   ├── __init__.py
│   │   ├── daq/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── device.py
│   │   │   ├── scan.py
│   │   │   └── nexus.py
│   │   └── analysis/
│   │       ├── __init__.py
│   │       ├── xrd.py
│   │       ├── xafs.py
│   │       └── utils.py
│   └── tests/
│       ├── test_client.py
│       ├── test_scan.py
│       └── test_analysis.py
│
├── examples/
│   ├── 01_basic_usage.py
│   ├── 02_linear_scan.py
│   ├── 03_xafs_scan.py
│   ├── 04_xrd_analysis.ipynb
│   └── 05_xafs_analysis.ipynb
│
├── docker/
│   ├── Dockerfile.device
│   ├── Dockerfile.python
│   └── docker-compose.yml
│
└── docs/
    ├── PROTOCOL.md
    ├── ARCHITECTURE.md
    └── ANALYSIS.md
```

---

## Success Criteria

### Functional Requirements

- Server handles 10+ concurrent clients without degradation
- All protocol commands function correctly
- Motor simulation includes realistic acceleration/deceleration
- Linear, Mesh, and XAFS scans complete successfully
- XRD peak fitting matches scipy.optimize accuracy
- XAFS χ(k) extraction produces physically reasonable results
- NeXus files validate against NXxas schema
- Docker Compose deployment works on fresh system

### Quality Requirements

- No memory leaks (valgrind clean)
- No compiler warnings (`-Wall -Wextra -Wpedantic -Werror`)
- Python code passes `ruff` and `mypy` (strict mode)
- C code passes `clang-tidy` and `cppcheck`
- All code formatted with `clang-format` (C) and `ruff format` (Python)
- Test coverage > 80% for Python modules
- All public APIs documented with docstrings
- README enables setup in under 10 minutes

---

## Tech Stack (2026 Best Practices)

### Python Stack

**Package Management:**

- **uv** - Modern Python package manager (replaces pip, pipenv, poetry)
- **Python 3.14** - Latest stable version
- **pyproject.toml** - PEP 621 standard configuration

**Type Safety & Code Quality:**

- **mypy** - Static type checking (strict mode recommended)
- **ruff** - Fast Rust-based linter/formatter (replaces black, isort, flake8)
- **pydantic** - Runtime type validation for scan parameters and config
- **typing-extensions** - Backport for older Python versions if needed

**Testing:**

- **pytest** - Test framework
- **pytest-cov** - Code coverage reporting
- **pytest-asyncio** - Async test support
- **hypothesis** - Property-based testing for scientific data validation

**Scientific Computing:**

- **numpy>=1.26** - Array operations
- **scipy>=1.11** - Scientific algorithms
- **h5py>=3.10** - HDF5/NeXus file I/O
- **pandas** - Tabular data handling (optional, for scan results)
- **xarray** - Labeled multi-dimensional arrays (optional, for complex scan data)

**Development Tools:**

- **jupyter** - Interactive development and notebooks
- **matplotlib** - Plotting and visualization
- **pre-commit** - Git hooks for automated quality checks

### C Stack

**Build System:**

- **Meson** - Modern, fast build system (replaces Makefile)
- **pkg-config** - Dependency management

**Code Quality:**

- **clang-format** - Code formatting
- **clang-tidy** - Static analysis
- **cppcheck** - Additional static analysis
- **AddressSanitizer (ASan)** - Runtime memory error detection
- **Valgrind** - Memory leak detection

**Compiler:**

- **GCC 13+** - Modern C standard support
- **C23** - Latest C standard
- **-Wall -Wextra -Wpedantic -Werror** - Strict compiler warnings

**Testing:**

- **CMocka** - Unit testing framework
- **gcov/lcov** - Code coverage reporting

### DevOps & Infrastructure

**Containerization:**

- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Multi-stage builds** - Optimized image sizes
- **alpine** - Minimal base images for security

**CI/CD:**

- **GitHub Actions** - CI/CD pipeline
- **pre-commit.ci** - Automated pre-commit runs
- **Dependabot** - Automated dependency updates

**Monitoring & Logging:**

- **structlog** (Python) - Structured logging
- **syslog** (C) - System logging

### Code Standards

**Python:**

- PEP 8 compliance (enforced via ruff)
- Type hints required for all public APIs
- Google/NumPy style docstrings
- Conventional Commits for git messages

**C:**

- MISRA-C subset patterns (safety-critical coding practices)
- Consistent error handling patterns
- Memory safety best practices

---

## Technical Decisions

### Why `select()` over `epoll()`?

- POSIX portability (RHEL, Scientific Linux compatibility)
- Backwards compatibility with older systems
- Sufficient for expected client count
- Simpler debugging

### Why Meson over Makefile?

- Modern, fast, and user-friendly build system
- Better dependency management
- Cross-platform support
- Integrated testing and coverage support
- Easier to maintain than Makefiles

### Why NeXus/HDF5?

- International standard for synchrotron data
- Used by SESAME, ESRF, Diamond, APS, etc.
- Self-describing, includes metadata
- Efficient for large datasets

### Why separate analysis module?

- Demonstrates domain expertise beyond pure software engineering
- Shows understanding of what scientists measure
- Directly applicable to SESAME beamlines (XAFS/XRF, MS/XPD)

### Why uv over pip?

- 10-100x faster than pip
- Modern dependency resolution
- Built-in virtual environment management
- Better lock file support
- Single tool for all Python package management needs

---

## Future Possible Enhancements

1. **EPICS Channel Access** - Native CA protocol instead of custom TCP
2. **Bluesky Integration** - RunEngine compatibility
3. **Live Plotting** - Matplotlib/PyQtGraph real-time display
4. **Phase Identification** - COD/ICSD database matching
5. **EXAFS Fitting** - Coordination number extraction
6. **Web Dashboard** - Flask/FastAPI monitoring interface

---

## References

- [EPICS Documentation](https://epics-controls.org/)
- [NeXus Format](https://www.nexusformat.org/)
- [NXxas Application Definition](https://manual.nexusformat.org/classes/applications/NXxas.html)
- [Beej's Guide to Network Programming](https://beej.us/guide/bgnet/)
- [SESAME Control Systems](https://www.sesame.org.jo/accelerators/technology/control-pss)
- [Larch XAFS Analysis](https://xraypy.github.io/xraylern/)
- [CrystFEL](https://www.desy.de/~twhite/crystfel/)

---

## Author

Software developer with ~18 years of experience and a background in Materials Science and Engineering. Previous experience includes powder XRD analysis during undergraduate research. More recent experience includes serial crystallography data processing using CrystFEL/Cheetah from SACLA and SLAC beamlines.

This project demonstrates control systems patterns and scientific computing capabilities relevant to synchrotron facilities.

---

## Appendix A: Quick Start

```bash
# Clone repository
git clone https://github.com/EsTharian/beamline-simulator
cd beamline-simulator

# Docker deployment (recommended)
docker-compose up --build

# Manual build
cd device
meson setup build
meson compile -C build
./build/beamline-sim &

cd ../python
uv sync --dev
uv run python examples/01_basic_usage.py
```

## Appendix B: Example Session

```python
from beamline.daq import DeviceClient, XAFSScan
from beamline.analysis import XAFSProcessor

# Connect to device server
client = DeviceClient("localhost", 5064)

# Check beam status
current = client.get("BL02:RING:CURRENT")
print(f"Ring current: {current} mA")

# Run XAFS scan at Fe K-edge
scan = XAFSScan(
    client,
    energy_pv="BL02:MONO:ENERGY",
    edge=7112,
    regions=[
        (-150, -20, 5.0),
        (-20, 30, 0.5),
        (30, 500, 2.0),
    ],
    detectors=["BL02:DET:I0", "BL02:DET:IT", "BL02:DET:IF"]
)
data = scan.run()

# Process data
proc = XAFSProcessor()
energy = data["BL02:MONO:ENERGY"]
mu = np.log(data["BL02:DET:I0"] / data["BL02:DET:IT"])

e0 = proc.find_edge(energy, mu)
mu_norm = proc.normalize(energy, mu, e0)
k, chi = proc.extract_chi(energy, mu_norm, e0)
r, chi_r = proc.fourier_transform(k, chi, kweight=2)

# Export to NeXus
scan.to_nexus("fe_xafs_001.nxs")
```
