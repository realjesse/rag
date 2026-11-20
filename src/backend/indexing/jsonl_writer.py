import json
from pathlib import Path
from typing import Any

from numpy.typing import NDArray


def write_jsonl(path: Path, records: list[dict[str, Any]], vectors: NDArray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record, vector in zip(records, vectors, strict=True):
            record["vector"] = vector.tolist()
            output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
