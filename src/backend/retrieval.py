import json
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


class PassageIndex:
    def __init__(self, path: Path) -> None:
        self.records = []
        vectors = []
        model_ids = set()
        with path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                record = json.loads(line)
                vectors.append(record.pop("vector"))
                model_ids.add(record["metadata"]["embedding_model"])
                self.records.append(record)

        if len(model_ids) != 1:
            raise ValueError("The index must contain records from one embedding model.")

        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or not np.isfinite(matrix).all():
            raise ValueError("The index must contain finite, equally sized vectors.")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if (norms == 0).any():
            raise ValueError("Index vectors must have nonzero length.")
        self.vectors = matrix / norms

        self.model = SentenceTransformer(model_ids.pop(), device="cpu")
        if self.model.get_embedding_dimension() != matrix.shape[1]:
            raise ValueError(
                "Index vector dimensions do not match the embedding model."
            )

    def search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        query_vector = self.model.encode_query(query, normalize_embeddings=True)
        scores = np.clip(self.vectors @ query_vector, -1.0, 1.0)
        matches = np.argsort(-scores, kind="stable")[:top_k]
        return [{**self.records[i], "score": float(scores[i])} for i in matches]
