import argparse
import json
from pathlib import Path

from datasets import load_dataset
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

DATASET_ID = "rag-datasets/rag-mini-wikipedia"
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 200  # Model tokenizer tokens, excluding special tokens.
CHUNK_OVERLAP = 30  # Target overlap in tokens.


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Maximum corpus rows to process")
    parser.add_argument("--output", type=Path, default=Path("data/index_records.jsonl"))
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")

    corpus = load_dataset(DATASET_ID, name="text-corpus", split="passages")
    if args.limit is not None:
        corpus = corpus.select(range(min(args.limit, len(corpus))))

    # CPU keeps this example usable without GPU setup.
    model = SentenceTransformer(MODEL_ID, device="cpu")
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
                        "dataset": DATASET_ID,
                        "source_id": source_id,
                        "chunk_index": chunk_index,
                        "embedding_model": MODEL_ID,
                    },
                }
            )

    if not records:
        raise ValueError("No nonempty chunks were produced")

    vectors = model.encode(
        [record["text"] for record in records],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for record, vector in zip(records, vectors, strict=True):
            record["vector"] = vector.tolist()
            output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")

    print(f"Processed {len(corpus)} corpus rows")
    print(f"Saved {len(records)} chunks with {vectors.shape[1]}-dimensional vectors")
    print(f"Output: {args.output.resolve()}")


if __name__ == "__main__":
    main()
