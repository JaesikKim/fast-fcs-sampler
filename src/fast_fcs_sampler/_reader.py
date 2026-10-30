"""Read selected raw FCS events without loading the entire DATA segment."""

from pathlib import Path
import numpy as np


def _text_fields(raw):
    raw = raw.rstrip(b"\x00")
    if not raw:
        raise ValueError("empty TEXT segment")
    sep = raw[:1]
    parts = raw[1:].split(sep)
    if parts and parts[-1] == b"":
        parts.pop()
    if len(parts) % 2:
        raise ValueError("odd number of TEXT fields")
    # This small reader targets common fixed-width FCS files. Metadata fields
    # containing escaped delimiters need a full FCS TEXT parser.
    return {parts[i].decode("latin-1").upper(): parts[i + 1].decode("latin-1")
            for i in range(0, len(parts), 2)}


class FCSFile:
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open("rb") as fh:
            h = fh.read(58)
            if len(h) != 58 or not h.startswith(b"FCS"):
                raise ValueError("invalid FCS header")
            offsets = [int(h[i:i + 8].strip() or b"0") for i in (10, 18, 26, 34)]
            ts, te, ds, de = offsets
            if ts < 58 or te < ts or te - ts > 20_000_000:
                raise ValueError("invalid TEXT offsets")
            fh.seek(ts)
            meta = _text_fields(fh.read(te - ts + 1))
        self.meta = meta
        self.n_events = int(meta["$TOT"])
        self.n_channels = int(meta["$PAR"])
        if self.n_events < 0 or not 1 <= self.n_channels <= 1000:
            raise ValueError("invalid $TOT or $PAR")
        self.channels = tuple(meta.get(f"$P{i}N", "") for i in range(1, self.n_channels + 1))
        self.stains = tuple(meta.get(f"$P{i}S", "") for i in range(1, self.n_channels + 1))
        byteord = meta.get("$BYTEORD")
        endian = {"1,2,3,4": "<", "1,2": "<", "4,3,2,1": ">", "2,1": ">"}.get(byteord)
        if endian is None:
            raise ValueError(f"unsupported $BYTEORD: {byteord}")
        kind = meta.get("$DATATYPE", "").upper()
        bits = [int(meta[f"$P{i}B"]) for i in range(1, self.n_channels + 1)]
        if len(set(bits)) != 1 or bits[0] not in (8, 16, 32, 64):
            raise ValueError("requires uniform byte-aligned channel widths")
        width = bits[0] // 8
        if kind == "F" and width == 4 or kind == "D" and width == 8:
            code = "f"
        elif kind == "I":
            code = "u"
        else:
            raise ValueError(f"unsupported $DATATYPE / width: {kind}/{bits[0]}")
        self.dtype = np.dtype(f"{endian}{code}{width}")
        self.data_start = ds or int(meta.get("$BEGINDATA", "0"))
        self.data_end = de or int(meta.get("$ENDDATA", "0"))
        need_end = self.data_start + self.n_events * self.n_channels * width - 1
        if self.data_start <= 0 or self.path.stat().st_size <= need_end:
            raise ValueError("truncated DATA segment")
        if self.data_end and self.data_end < need_end:
            raise ValueError("DATA segment shorter than $TOT")

    def read_slice(self, start, count):
        if start < 0 or count < 0 or start + count > self.n_events:
            raise IndexError("event slice out of bounds")
        full = np.memmap(self.path, dtype=self.dtype, mode="r", offset=self.data_start,
                         shape=(self.n_events, self.n_channels))
        return np.asarray(full[start:start + count]).copy()

    def read_slice_pread(self, start, count):
        """Alternative contiguous explicit read backend."""
        if start < 0 or count < 0 or start + count > self.n_events:
            raise IndexError("event slice out of bounds")
        with self.path.open("rb") as fh:
            fh.seek(self.data_start + start * self.n_channels * self.dtype.itemsize)
            data = fh.read(count * self.n_channels * self.dtype.itemsize)
        if len(data) != count * self.n_channels * self.dtype.itemsize:
            raise ValueError("truncated DATA segment")
        return np.frombuffer(data, dtype=self.dtype).reshape(count, self.n_channels).copy()

    def read_indices(self, indices):
        """Copy selected events in caller order using a read-only memory map."""
        indices = self._validate_indices(indices)
        if not len(indices):
            return np.empty((0, self.n_channels), dtype=self.dtype)
        full = np.memmap(self.path, dtype=self.dtype, mode="r", offset=self.data_start,
                         shape=(self.n_events, self.n_channels))
        return np.asarray(full[indices]).copy()

    def read_indices_pread(self, indices):
        """Alternative explicit seek/read backend for filesystems where mmap is slow."""
        indices = self._validate_indices(indices)
        out = np.empty((len(indices), self.n_channels), dtype=self.dtype)
        if not len(indices):
            return out
        order = np.argsort(indices, kind="stable")
        sorted_indices = indices[order]
        row_bytes = self.n_channels * self.dtype.itemsize
        with self.path.open("rb", buffering=0) as fh:
            # Coalesce adjacent requested rows into one read, retaining input order.
            pos = 0
            while pos < len(order):
                stop = pos + 1
                while stop < len(order) and sorted_indices[stop] <= sorted_indices[stop - 1] + 1:
                    stop += 1
                first = int(sorted_indices[pos])
                last = int(sorted_indices[stop - 1])
                fh.seek(self.data_start + first * row_bytes)
                block = fh.read((last - first + 1) * row_bytes)
                if len(block) != (last - first + 1) * row_bytes:
                    raise ValueError("truncated DATA segment")
                rows = np.frombuffer(block, dtype=self.dtype).reshape(-1, self.n_channels)
                out[order[pos:stop]] = rows[sorted_indices[pos:stop] - first]
                pos = stop
        return out

    def _validate_indices(self, indices):
        values = np.asarray(indices)
        if values.ndim == 1 and values.size == 0:
            return np.empty(0, dtype=np.int64)
        if values.ndim != 1 or values.dtype.kind not in "iu":
            raise TypeError("indices must be a one-dimensional integer sequence")
        values = np.asarray(values, dtype=np.int64)
        if np.any(values < 0) or np.any(values >= self.n_events):
            raise IndexError("event index out of bounds")
        return values

    def sample(self, count=1000, seed=None):
        if count < 0 or count > self.n_events:
            raise ValueError("sample count out of bounds")
        indices = np.random.default_rng(seed).choice(self.n_events, size=count, replace=False)
        return indices, self.read_indices(indices)
