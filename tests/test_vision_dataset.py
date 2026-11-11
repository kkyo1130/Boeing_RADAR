import csv
from vision.dataset import split_dataset

def test_split_preserves_sessions(tmp_path):
    source = tmp_path / "labels.csv"
    with source.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "altitude", "heading", "session_id"])
        writer.writeheader()
        for session in range(30):
            for frame in range(3):
                writer.writerow({"filename": f"{session}_{frame}.png", "altitude": 18000,
                                 "heading": 240, "session_id": str(session)})
    out = tmp_path / "splits"
    result = split_dataset(source, out)
    assert sum(result.values()) == 90
    groups = []
    for split in ("train", "val", "test"):
        with (out / f"{split}.csv").open() as f:
            groups.append({r["session_id"] for r in csv.DictReader(f)})
    assert all(not groups[i] & groups[j] for i in range(3) for j in range(i+1, 3))
