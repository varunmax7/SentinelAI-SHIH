"""Retrieval over `data/twin/corpus/`, for citing an SOP in a brief.

Keyword-scored, not embedding-based. `faiss-cpu` + `sentence-transformers`
would work too and are a natural upgrade path (the public interface,
`retrieve(query, top_k)`, would not need to change) - they were deliberately
not added here, because pulling in `torch` for a feature that is entirely
optional (an empty corpus is a fully supported steady state - see the
corpus's own README) is a large, slow, disk-heavy dependency to impose on
every install of this app for a nice-to-have. TF-IDF-style keyword overlap
over a few hundred short SOP documents is not meaningfully less accurate than
embeddings at this corpus size, and it is stdlib-only.

**Numeric queries are handled specially.** A query containing a measurement
("62 mm") is scored on *exact substring* presence, heavily weighted over
ordinary term overlap - a semantically-similar sentence about a different
number is exactly the wrong citation for "did the SOP say to act at 60mm or
80mm", and cosine similarity over embeddings is genuinely bad at this
(two numbers are close in embedding space for being both numbers, not for
being the same number).
"""

import glob
import math
import os
import re
from collections import Counter

from .. import config as twin_config

CORPUS_EXTENSIONS = ('.md', '.txt', '.json')
DEFAULT_TOP_K = 4
# Documents are split into paragraphs (blank-line-separated) - the natural
# citation unit for an SOP, and short enough that a citation points at one
# specific instruction rather than a whole multi-page document.
MIN_CHUNK_CHARS = 40

_WORD_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?", re.I)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

_CACHE = {'mtime': None, 'chunks': None}


def _corpus_dir():
    return twin_config.RAG_CORPUS_DIR


def _tokenize(text):
    return [w.lower() for w in _WORD_RE.findall(text or '')]


def _corpus_signature(directory):
    """Cheap change-detection: total size + latest mtime across corpus files.

    Re-scans the directory on every call (a few hundred files, at most,
    stat()-only) rather than watching for filesystem events - simple, and
    this runs at brief-draft time, not on a request path.
    """
    total = 0.0
    latest = 0.0
    for ext in CORPUS_EXTENSIONS:
        for path in glob.glob(os.path.join(directory, '**', '*' + ext), recursive=True):
            try:
                stat = os.stat(path)
            except OSError:
                continue
            total += stat.st_size
            latest = max(latest, stat.st_mtime)
    return (total, latest)


def _load_chunks(directory):
    chunks = []
    for ext in CORPUS_EXTENSIONS:
        for path in sorted(glob.glob(os.path.join(directory, '**', '*' + ext), recursive=True)):
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as fh:
                    text = fh.read()
            except OSError:
                continue
            for paragraph in re.split(r'\n\s*\n', text):
                paragraph = paragraph.strip()
                if len(paragraph) < MIN_CHUNK_CHARS:
                    continue
                chunks.append({
                    'text': paragraph,
                    'source': os.path.relpath(path, directory),
                    'tokens': Counter(_tokenize(paragraph)),
                    'numbers': set(_NUMBER_RE.findall(paragraph)),
                })
    return chunks


def _chunks():
    directory = _corpus_dir()
    if not os.path.isdir(directory):
        return []
    signature = _corpus_signature(directory)
    if _CACHE['mtime'] != signature:
        _CACHE['chunks'] = _load_chunks(directory)
        _CACHE['mtime'] = signature
    return _CACHE['chunks'] or []


def _idf(chunks):
    """Inverse document frequency per term, Counter-based - rarer terms in

    this specific corpus (a place name, a hazard type) discriminate between
    chunks far better than common ones ("the", "must") do, the same reasoning
    real TF-IDF is built on.
    """
    doc_count = Counter()
    for chunk in chunks:
        for term in chunk['tokens']:
            doc_count[term] += 1
    n = len(chunks) or 1
    return {term: math.log(1.0 + n / count) for term, count in doc_count.items()}


def _score(query_terms, query_numbers, chunk, idf):
    score = 0.0
    for term in query_terms:
        if term in chunk['tokens']:
            score += chunk['tokens'][term] * idf.get(term, 1.0)
    # A shared number is a near-certain match for "does the SOP mention this
    # measurement" - weighted far above ordinary term overlap.
    if query_numbers and (query_numbers & chunk['numbers']):
        score += 25.0 * len(query_numbers & chunk['numbers'])
    return score


def retrieve(query, top_k=None):
    """The `top_k` corpus chunks most relevant to `query`, highest first.

    Returns `[]` when the corpus is empty or missing - not an error, the
    fully-supported steady state until SOP files are placed there.
    """
    chunks = _chunks()
    if not chunks or not query:
        return []

    top_k = top_k or DEFAULT_TOP_K
    query_terms = _tokenize(query)
    query_numbers = set(_NUMBER_RE.findall(query))
    idf = _idf(chunks)

    scored = [
        (_score(query_terms, query_numbers, chunk, idf), chunk)
        for chunk in chunks
    ]
    scored = [(s, c) for s, c in scored if s > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [
        {'text': chunk['text'], 'source': chunk['source'], 'score': round(score, 2)}
        for score, chunk in scored[:top_k]
    ]


def corpus_size():
    """Chunk count, for the health/status surface - `0` is the honest,

    fully-supported default, not a degraded state.
    """
    return len(_chunks())
