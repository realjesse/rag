from typing import Any

from numpy.typing import NDArray
from sentence_transformers import SentenceTransformer


def encode_records(
    records: list[dict[str, Any]], model: SentenceTransformer
) -> NDArray:
    return model.encode(
        [record["text"] for record in records],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
