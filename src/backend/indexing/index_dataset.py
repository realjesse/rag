import argparse
from pathlib import Path

from sentence_transformers import SentenceTransformer

if __package__:
    from .chunking import build_records
    from .corpus import DATASET_ID, load_corpus
    from .embeddings import encode_records
    from .jsonl_writer import write_jsonl
else:
    from chunking import build_records
    from corpus import DATASET_ID, load_corpus
    from embeddings import encode_records
    from jsonl_writer import write_jsonl

MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Maximum corpus rows to process")
    parser.add_argument("--output", type=Path, default=Path("data/index_records.jsonl"))
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")

    corpus = load_corpus(limit=args.limit)

    # CPU keeps this example usable without GPU setup.
    model = SentenceTransformer(MODEL_ID, device="cpu")
    records = build_records(corpus, model, dataset_id=DATASET_ID, model_id=MODEL_ID)
    vectors = encode_records(records, model)
    write_jsonl(args.output, records, vectors)

    print(f"Processed {len(corpus)} corpus rows")
    print(f"Saved {len(records)} chunks with {vectors.shape[1]}-dimensional vectors")
    print(f"Output: {args.output.resolve()}")


if __name__ == "__main__":
    main()
