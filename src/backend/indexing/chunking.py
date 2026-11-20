from typing import Any

from datasets import Dataset
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

CHUNK_SIZE = 200  # Model tokenizer tokens, excluding special tokens.
CHUNK_OVERLAP = 30  # Target overlap in tokens.


def build_records(
    corpus: Dataset, model: SentenceTransformer, *, dataset_id: str, model_id: str
) -> list[dict[str, Any]]:
    tokenizer = model.tokenizer
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=lambda text: len(
            tokenizer.encode(text, add_special_tokens=False)
        ),
    )

    records = []
    for row in corpus:
        text = row["passage"]
        if not isinstance(text, str) or not text.strip():
            continue

        source_id = str(row["id"])
        for chunk_index, chunk in enumerate(splitter.split_text(text.strip())):
            # Fail visibly instead of silently embedding truncated text.
            if len(tokenizer.encode(chunk)) > model.max_seq_length:
                raise ValueError(
                    f"Chunk exceeds model limit: {source_id}:{chunk_index}"
                )
            records.append(
                {
                    "id": f"wiki:{source_id}:{chunk_index}",
                    "text": chunk,
                    "metadata": {
                        "dataset": dataset_id,
                        "source_id": source_id,
                        "chunk_index": chunk_index,
                        "embedding_model": model_id,
                    },
                }
            )

    if not records:
        raise ValueError("No nonempty chunks were produced")
    return records
