import os
from functools import cache
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query

from .retrieval import PassageIndex

app = FastAPI()
DEFAULT_INDEX_PATH = Path(__file__).parent / "indexing" / "data" / "index_records.jsonl"
index_lock = Lock()


@cache
def load_index() -> PassageIndex:
    return PassageIndex(Path(os.getenv("RAG_INDEX_PATH", str(DEFAULT_INDEX_PATH))))


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/retrieve")
def retrieve(
    q: Annotated[str, Query(min_length=1)],
    top_k: Annotated[int, Query(ge=1, le=100)] = 5,
):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must contain text.")

    try:
        with index_lock:
            index = load_index()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503, detail="Retrieval index is unavailable."
        ) from exc
    return {"results": index.search(query, top_k)}
