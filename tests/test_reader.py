import tempfile
import unittest
from pathlib import Path

import numpy as np

from fast_fcs_sampler import FCSFile


def write_fcs(path, values, *, byteord="1,2,3,4"):
    n, p = values.shape
    fields = ["$TOT", str(n), "$PAR", str(p), "$DATATYPE", "F", "$BYTEORD", byteord]
    for i in range(1, p + 1):
        fields += [f"$P{i}B", "32", f"$P{i}N", f"Marker{i}", f"$P{i}S", f"Stain{i}"]
    text = ("/" + "/".join(fields) + "/").encode("latin-1")
    data = values.astype("<f4" if byteord == "1,2,3,4" else ">f4").tobytes()
    text_start = 58
    text_end = text_start + len(text) - 1
    data_start = text_end + 1
    data_end = data_start + len(data) - 1
    header = bytearray(b" " * 58)
    header[:6] = b"FCS3.1"
    for position, value in ((10, text_start), (18, text_end), (26, data_start), (34, data_end)):
        header[position:position + 8] = f"{value:>8d}".encode("ascii")
    path.write_bytes(bytes(header) + text + data)


class TestFCSFile(unittest.TestCase):
    def setUp(self):
        test_output = Path.cwd() / ".test-output"
        test_output.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_output)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.fcs"
        self.values = np.arange(600, dtype=np.float32).reshape(200, 3)
        write_fcs(self.path, self.values)

    def test_random_and_selected_rows(self):
        fcs = FCSFile(self.path)
        self.assertEqual(fcs.channels, ("Marker1", "Marker2", "Marker3"))
        self.assertEqual(fcs.stains, ("Stain1", "Stain2", "Stain3"))
        indices, values = fcs.sample(30, seed=42)
        np.testing.assert_array_equal(values, self.values[indices])
        self.assertEqual(len(set(indices)), 30)
        np.testing.assert_array_equal(fcs.sample(30, seed=42)[0], indices)
        np.testing.assert_array_equal(fcs.read_indices([4, 1, 4]), self.values[[4, 1, 4]])
        self.assertEqual(fcs.read_indices([]).shape, (0, 3))
        np.testing.assert_array_equal(fcs.read_slice(27, 10), self.values[27:37])

    def test_explicit_reads_match_mmap(self):
        fcs = FCSFile(self.path)
        indices = [199, 4, 1, 4, 2, 3, 0]
        np.testing.assert_array_equal(fcs.read_indices_pread(indices), self.values[indices])
        np.testing.assert_array_equal(fcs.read_slice_pread(27, 10), self.values[27:37])
        self.assertEqual(fcs.read_indices_pread([]).shape, (0, 3))
        self.assertEqual(fcs.read_slice_pread(200, 0).shape, (0, 3))

    def test_big_endian(self):
        write_fcs(self.path, self.values, byteord="4,3,2,1")
        np.testing.assert_array_equal(FCSFile(self.path).read_indices([199, 0, 17]),
                                      self.values[[199, 0, 17]])

    def test_fail_visibly(self):
        fcs = FCSFile(self.path)
        with self.assertRaises(ValueError):
            fcs.sample(201, seed=42)
        with self.assertRaises(IndexError):
            fcs.read_indices([200])
        with self.assertRaises(TypeError):
            fcs.read_indices([1.5])
        with self.assertRaises(IndexError):
            fcs.read_slice(199, 2)
        self.path.write_bytes(self.path.read_bytes()[:-4])
        with self.assertRaises(ValueError):
            FCSFile(self.path)


if __name__ == "__main__":
    unittest.main()
