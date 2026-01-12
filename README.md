# Beamline Device Simulator

A synchrotron beamline control system demonstrating device simulation, data acquisition, scan orchestration, and scientific data analysis.

## Quick Start

### Prerequisites

- GCC 13+ (C23 support)
- Meson & Ninja
- Python 3.14+
- uv (Python package manager)

### Build Device Server

    cd device
    meson setup build
    meson compile -C build
    ./build/beamline-sim

### Install Python Package

    cd python
    uv sync --dev
    uv run python -c "import beamline; print(beamline.__version__)"

## Project Structure

- `device/` - C device server (TCP, EPICS-style PVs)
- `python/beamline/` - Python client and analysis tools
- `docker/` - Container deployment
- `examples/` - Usage examples
- `docs/` - Documentation

## License

MIT
