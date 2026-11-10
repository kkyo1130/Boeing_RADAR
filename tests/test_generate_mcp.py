import csv
from PIL import Image
from vision.generate_mcp import SEGMENTS, generate

def test_segments():
    assert SEGMENTS["0"] == "abcdef"
    assert SEGMENTS["8"] == "abcdefg"
    assert SEGMENTS["1"] == "bc"

def test_generator_labels_and_no_pair_leakage(tmp_path):
    output = tmp_path / "mcp"
    generate(output, count=80, seed=11)
    with (output / "labels.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 80
    assert all(len(r["altitude"]) == 5 and len(r["heading"]) == 3 for r in rows)
    assert all(0 <= int(r["heading"]) < 360 for r in rows)
    assert all(0 <= int(r["altitude"]) <= 50000 for r in rows)
    with Image.open(output / rows[0]["filename"]) as img:
        assert img.size == (850, 190)
    splits = []
    for split in ("train", "val", "test"):
        with (output / f"{split}.csv").open(newline="") as f:
            splits.append(list(csv.DictReader(f)))
    assert sum(map(len, splits)) == 80
    groups = [{r["original_id"] for r in split} for split in splits]
    assert not groups[0] & groups[1]
    assert not groups[0] & groups[2]
    assert not groups[1] & groups[2]
