# Fast FCS Sampler

Read a small, randomly selected set of raw cell events from a large FCS file.
The loader reads the FCS header and metadata, memory-maps the DATA segment,
and copies only requested rows into a NumPy array.

## Install

Requires Python 3.9+ and NumPy. Install directly from GitHub on any server:

```bash
python -m pip install "git+https://github.com/JaesikKim/fast-fcs-sampler.git@v0.1.0"
```

This command requires Git. The version tag pins the installed code. To install
the latest development version, replace `@v0.1.0` with `@main`.
This package is not currently published to PyPI.

For a server without Git, download a release wheel and install it with
`python -m pip install /path/to/fast_fcs_sampler-0.1.0-py3-none-any.whl`.
NumPy must also be available from your package index or local wheel directory.

## Usage

```python
from fast_fcs_sampler import FCSFile

fcs = FCSFile("sample.fcs")
indices, values = fcs.sample(1000, seed=42)
# values.shape == (1000, fcs.n_channels)
print(fcs.channels)  # FCS $PnN labels in column order
print(fcs.stains)    # FCS $PnS labels in column order

chunk = fcs.read_slice(start=100_000, count=1000)
chosen = fcs.read_indices([5, 20, 5])  # caller order and duplicates preserved
```

Paths are supplied by the caller; no data directory or server configuration is
required. `read_slice_pread` and `read_indices_pread` provide explicit file reads
when preferred over memory mapping. Select these methods explicitly; read errors
are raised to the caller.

`sample` selects events uniformly without replacement. The returned indices
can be stored to reproduce the exact selection. If the file has fewer events
than requested, the loader raises `ValueError`.

Values are the raw values recorded in FCS DATA. This package does not apply
compensation, transformation, gating, or marker filtering. It supports
fixed-width, byte-aligned `F`, `D`, and `I` DATA with equal channel widths and
common byte orders. It reads the first DATA segment. Unsupported layouts raise
an error. The minimal TEXT parser is intended for common FCS files and does
not fully handle escaped delimiters in arbitrary metadata fields.

The package contains no FCS data or project-specific paths. Performance depends
on filesystem caching, storage, file layout, and the number of selected events.

## Development

```bash
git clone https://github.com/JaesikKim/fast-fcs-sampler.git
cd fast-fcs-sampler
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests generate synthetic FCS files; no external datasets are needed. GitHub
Actions tests installed wheels on Linux across Python 3.9–3.14 and on macOS and
Windows with Python 3.12.

To build distribution files, run `python -m pip install build` followed by
`python -m build`. The resulting wheel and source archive are written to `dist/`.

Licensed under MIT. This package is not affiliated with the FCS standards body.
