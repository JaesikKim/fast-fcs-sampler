# Fast FCS Sampler

Read selected raw cell events from an FCS file into NumPy without loading its
entire DATA segment into a dense array. The reader parses the header and TEXT
metadata, memory-maps DATA, and copies only the requested rows.

- Uniform random sampling without replacement.
- Contiguous slices and arbitrary event indices, including duplicates.
- Channel names (`$PnN`), stain/marker labels (`$PnS`), and TEXT metadata.
- NumPy as the only runtime dependency; no dataset or server configuration required.

## Installation

Requires **Python 3.9+** and **NumPy 1.23+**. Pip installs a compatible NumPy version
automatically. The distribution name is `fast-fcs-sampler`; the Python import
name is `fast_fcs_sampler`. This package is currently distributed through GitHub,
not PyPI.

### Install a stable version from GitHub

Run these commands on the server where you will use the package. Git must be
installed for this method. In a shell on Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "git+https://github.com/JaesikKim/fast-fcs-sampler.git@v0.1.0"
python -c "from fast_fcs_sampler import FCSFile; print('Import successful')"
```

On Windows PowerShell, create the environment with `py -m venv .venv` and activate
it with `.venv\Scripts\Activate.ps1`, then run the same `python -m pip` command.
If you already have a project environment, activate it and run only the install
and import commands. Install separately in each server's environment.

### Install without Git

Install the wheel directly from the [v0.1.0 release](https://github.com/JaesikKim/fast-fcs-sampler/releases/tag/v0.1.0):

```bash
python -m pip install "https://github.com/JaesikKim/fast-fcs-sampler/releases/download/v0.1.0/fast_fcs_sampler-0.1.0-py3-none-any.whl"
```

You can also download that wheel, copy it to another server, and install it:

```bash
python -m pip install /path/to/fast_fcs_sampler-0.1.0-py3-none-any.whl
```

For a server without internet access, prepare the package and NumPy wheels on
an internet-connected machine with the **same OS, architecture, and Python
version** as the destination:

```bash
python -m pip download --only-binary=:all: --dest wheelhouse "https://github.com/JaesikKim/fast-fcs-sampler/releases/download/v0.1.0/fast_fcs_sampler-0.1.0-py3-none-any.whl"
```

Copy `wheelhouse/` to the destination server, activate its environment, and run:

```bash
python -m pip install --no-index --find-links=wheelhouse fast-fcs-sampler==0.1.0
```

### Install the latest development version

```bash
python -m pip install --upgrade "git+https://github.com/JaesikKim/fast-fcs-sampler.git@main"
```

Use the version tag for reproducible deployments. `main` may change between
installations. To reproduce sampled indices across environments, also pin NumPy
and retain the original FCS file and returned indices.

## Quick start

```python
from fast_fcs_sampler import FCSFile

fcs = FCSFile("sample.fcs")
print(fcs.n_events, fcs.n_channels)

# The file must contain at least 1,000 events.
indices, values = fcs.sample(count=1000, seed=42)
print(values.shape)  # (1000, fcs.n_channels)

# Labels are available separately and match the array's column order.
channel_names = fcs.channels
marker_names = fcs.stains
print(channel_names)
print(marker_names)

# Read the exact same events again, preserving their order.
selected = fcs.read_indices(indices)

# Read a contiguous range, provided the file contains these events.
chunk = fcs.read_slice(start=0, count=100)
```

`sample()` returns exactly **`(indices, values)`**. Labels are read during
`FCSFile(...)` construction and accessed through the same object's attributes;
they are not additional elements of the return tuple. Opening the file reads
metadata and checks DATA offsets; it does not load all event values.

## Channel names and marker labels

For every column `j` in a returned array:

| Attribute | FCS keyword | Meaning |
| --- | --- | --- |
| `fcs.channels[j]` | `$P{j+1}N` | Channel/parameter name, such as a detector or isotope label |
| `fcs.stains[j]` | `$P{j+1}S` | Stain/marker label, which may contain names such as `CD3` or `CD4` |

Both attributes are tuples of length `fcs.n_channels`, in the original file's
column order. The labels depend on how the instrument or exporting software
wrote the FCS file. Inspect both tuples before choosing column names. A missing
label is represented by `""`; labels may be duplicated. The reader does not
rename, deduplicate, or substitute labels.

An optional pandas DataFrame can retain both label sets as column levels:

```bash
python -m pip install pandas
```

```python
import pandas as pd
from fast_fcs_sampler import FCSFile

fcs = FCSFile("sample.fcs")
indices, values = fcs.sample(1000, seed=42)
columns = pd.MultiIndex.from_arrays(
    [fcs.channels, fcs.stains], names=["channel", "marker"]
)
df = pd.DataFrame(values, index=indices, columns=columns)
df.index.name = "event_index"
```

Pandas is optional and is not installed by this package. The DataFrame preserves
empty or duplicate labels as recorded in the file.

## API reference

### `FCSFile(path)`

Accepts a string or `pathlib.Path` pointing to a readable local FCS file. Keep the
file available and unchanged while using the reader; methods open it when reading
events. The reader is not a context manager and has no `close()` method to call.

| Attribute | Description |
| --- | --- |
| `path` | Input path as a `pathlib.Path` |
| `n_events` | Number of events from `$TOT` |
| `n_channels` | Number of parameters from `$PAR` |
| `channels` | Tuple of `$PnN` channel labels |
| `stains` | Tuple of `$PnS` stain/marker labels |
| `meta` | Parsed TEXT keyword/value dictionary; keys are uppercased, values are strings |
| `dtype` | NumPy dtype derived from `$DATATYPE`, channel width, and `$BYTEORD` |
| `data_start`, `data_end` | Resolved DATA byte offsets, inclusive; `data_end` may be zero when unspecified |

### Reading methods

All returned values are independent NumPy arrays with shape
`(number_of_selected_events, n_channels)`, in original column order. Event
indices are **zero-based**. Floating-point DATA retains its recorded precision;
integer DATA is returned as unsigned integers. No normalization is applied.

| Method | Returns and behavior |
| --- | --- |
| `sample(count=1000, seed=None)` | `(indices, values)`, sampled uniformly without replacement. `indices` is a one-dimensional NumPy integer array in sampling order, not sorted. An integer seed makes repeated calls reproducible for the same file and NumPy environment; `None` leaves the RNG unseeded. |
| `read_slice(start, count)` | Values for `[start, start + count)`, using a read-only memory map. |
| `read_indices(indices)` | Values for a one-dimensional integer sequence, preserving caller order and duplicates. An empty sequence returns shape `(0, n_channels)`. |
| `read_slice_pread(start, count)` | Same slice semantics, using explicit seek/read operations. |
| `read_indices_pread(indices)` | Same index semantics, using explicit seek/read operations and coalescing adjacent requested rows. |

Despite the `_pread` names, those methods use Python file `seek`/`read`, not the
OS `pread` syscall. Choose them explicitly when you want ordinary file reads.
`sample()` always uses `read_indices()` and its memory-map backend. To sample
with explicit reads, select indices yourself:

```python
import numpy as np

rng = np.random.default_rng(42)
indices = rng.choice(fcs.n_events, size=1000, replace=False)
values = fcs.read_indices_pread(indices)
```

### Errors

Failures propagate to the caller. The reader does not silently reduce a sample
size or switch read backends.

- `ValueError`: negative or excessive sample count; invalid header or metadata;
  unsupported DATA layout; detected truncated DATA segment.
- `IndexError`: negative or out-of-range event indices or slices.
- `TypeError`: nonempty indices that are not a one-dimensional integer sequence.
- `KeyError`: a required TEXT keyword is missing.
- `OSError` subclasses: file access failures, such as `FileNotFoundError` or
  `PermissionError`.

Pass integers for `start` and `count`. A request for more events than the file
contains raises an error; decide the desired sample size in your application.

## Supported layouts and limitations

- Fixed-width, equal-width channels: `F` (32-bit float), `D` (64-bit float), or
  `I` (unsigned 8-, 16-, 32-, or 64-bit integer).
- `$BYTEORD`: `1,2`, `1,2,3,4`, `2,1`, or `4,3,2,1`.
- Only the first DATA segment is read. Additional datasets and supplemental TEXT
  are not traversed.
- The minimal TEXT parser decodes bytes as Latin-1 and does not fully support
  escaped delimiters in arbitrary fields. Do not assume all FCS files are
  supported; malformed or unsupported metadata can raise errors or be misparsed.
- This is a raw event reader. It does not apply compensation, transformations,
  acquisition scaling, gating, marker filtering, or integer range-bit masking.
- Mixed channel widths, packed non-byte-aligned integers, ASCII DATA, and other
  unsupported DATA layouts are rejected. This is not a full FCS validator.

Memory mapping avoids materializing the entire DATA segment in a NumPy array.
The OS may cache mapped pages, and array selection can allocate intermediate
buffers. Performance and process memory depend on storage, caching, file layout,
and the number of selected events. No FCS datasets are distributed here.

## Development and validation

```bash
git clone https://github.com/JaesikKim/fast-fcs-sampler.git
cd fast-fcs-sampler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests generate synthetic FCS files; no external datasets are needed. GitHub
Actions builds and tests installed wheels on Linux with Python 3.9–3.14 and on
macOS and Windows with Python 3.12.

Build and check distribution files:

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

The wheel and source archive are written to `dist/`.
Report bugs with a minimal reproducer and relevant layout metadata through
[GitHub Issues](https://github.com/JaesikKim/fast-fcs-sampler/issues).

## License

[MIT](LICENSE). This project is not affiliated with the FCS standards body.
