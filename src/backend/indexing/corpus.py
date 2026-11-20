from datasets import Dataset, load_dataset

DATASET_ID = "rag-datasets/rag-mini-wikipedia"


def load_corpus(limit: int | None = None) -> Dataset:
    corpus = load_dataset(DATASET_ID, name="text-corpus", split="passages")
    if limit is not None:
        corpus = corpus.select(range(min(limit, len(corpus))))
    return corpus
