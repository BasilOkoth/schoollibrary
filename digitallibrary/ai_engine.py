import os
import re
import time
import pickle
import threading
from pathlib import Path
from typing import List, Dict

import numpy as np
import fitz  # PyMuPDF
import faiss
from django.conf import settings

from .models import Resource

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # good + lightweight
INDEX_FILE = "faiss.index"
META_FILE = "meta.pkl"
LOCK_FILE = "build.lock"

# Prevent multiple builds at once
_build_lock = threading.Lock()


def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_pdf_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    chunks = []
    for page in doc:
        chunks.append(page.get_text("text"))
    return "\n".join(chunks)


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    text = _clean_text(text)
    if not text:
        return []
    chunks = []
    i = 0
    step = max(1, chunk_size - overlap)
    while i < len(text):
        chunks.append(text[i:i + chunk_size])
        i += step
    return chunks


def _paths():
    base = Path(settings.AI_INDEX_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base, base / INDEX_FILE, base / META_FILE, base / LOCK_FILE


def _load_embedder():
    # Lazy import so Django startup stays fast
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def build_index_from_db() -> Dict[str, int]:
    """
    Rebuild FAISS index from all PDF resources in DB.
    Returns stats dict.
    """
    base, index_path, meta_path, lock_path = _paths()

    # Build lock file (best effort)
    lock_path.write_text(str(time.time()), encoding="utf-8")

    pdf_resources = Resource.objects.filter(resource_type="PDF").exclude(file="")

    embedder = _load_embedder()

    all_vectors = []
    metadata = []  # each item: {resource_id, title, file_url, snippet}

    for r in pdf_resources:
        try:
            file_path = r.file.path  # local filesystem path
            if not os.path.exists(file_path):
                continue

            text = extract_pdf_text(file_path)
            chunks = chunk_text(text)

            if not chunks:
                continue

            # Embed in batches for stability
            vecs = embedder.encode(chunks, batch_size=32, show_progress_bar=False)
            vecs = np.array(vecs, dtype="float32")

            all_vectors.append(vecs)

            for c in chunks:
                metadata.append({
                    "resource_id": r.id,
                    "title": r.title,
                    "file_url": r.file.url,
                    "snippet": c[:900],
                })

        except Exception:
            # Skip bad PDFs; keep build robust
            continue

    if not all_vectors:
        # Create empty index
        dim = 384  # all-MiniLM-L6-v2 dimension
        index = faiss.IndexFlatL2(dim)
        faiss.write_index(index, str(index_path))
        with open(meta_path, "wb") as f:
            pickle.dump([], f)
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass
        return {"pdfs": pdf_resources.count(), "chunks": 0}

    vectors = np.vstack(all_vectors).astype("float32")
    dim = vectors.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(vectors)

    faiss.write_index(index, str(index_path))
    with open(meta_path, "wb") as f:
        pickle.dump(metadata, f)

    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass

    return {"pdfs": pdf_resources.count(), "chunks": len(metadata)}


def search_ai(query: str, k: int = 8) -> List[Dict]:
    """
    Returns list of result dicts with snippet + file link.
    """
    query = _clean_text(query or "")
    if not query:
        return []

    base, index_path, meta_path, _ = _paths()
    if not index_path.exists() or not meta_path.exists():
        return []

    index = faiss.read_index(str(index_path))
    with open(meta_path, "rb") as f:
        metadata = pickle.load(f)

    if not metadata or index.ntotal == 0:
        return []

    embedder = _load_embedder()
    qv = embedder.encode([query])
    qv = np.array(qv, dtype="float32")

    distances, ids = index.search(qv, k)
    out = []
    for rank, idx in enumerate(ids[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        item = metadata[idx]
        out.append({
            "rank": rank + 1,
            "title": item.get("title"),
            "file_url": item.get("file_url"),
            "snippet": item.get("snippet"),
        })
    return out


def trigger_rebuild_async():
    """
    Background rebuild. Safe to call multiple times; one build at a time.
    """
    if _build_lock.locked():
        return  # build already running

    def _job():
        with _build_lock:
            try:
                build_index_from_db()
            except Exception:
                pass

    t = threading.Thread(target=_job, daemon=True)
    t.start()