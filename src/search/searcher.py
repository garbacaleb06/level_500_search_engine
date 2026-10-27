"""Search engine retrieval and BM25F ranking module using Whoosh."""

import gc
import html
import re
from pathlib import Path
from typing import List, Optional, Set, Union
from whoosh import index, scoring
from whoosh.index import Index
from whoosh.qparser import MultifieldParser, OrGroup, QueryParserError

from config import settings
from src.storage.models import SearchResult


# Whoosh's highlighter emits HTML (for example, <b class="match term0">) and
# extracted page text can contain stray entities. Terminal snippets should be
# plain text, so strip any tag/entity markup rather than a fixed tag list.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


class SearchEngine:
    """Provides full-text searching and BM25F ranking over the mechatronics index."""

    def __init__(self, index_dir: Optional[Union[str, Path]] = None):
        self.index_dir = Path(index_dir or settings.INDEX_DIR)
        self._index: Optional[Index] = None

    def is_index_ready(self) -> bool:
        """Checks if the Whoosh index directory exists and contains a valid index."""
        if not self.index_dir.exists():
            return False
        return index.exists_in(str(self.index_dir))

    def _get_index(self) -> Optional[Index]:
        """Opens and caches the index object."""
        if self._index is None:
            if not self.is_index_ready():
                return None
            self._index = index.open_dir(str(self.index_dir))
        return self._index

    def document_count(self) -> int:
        """Returns the number of indexed documents, or 0 if the index is unavailable.

        This is a read-only statistic for callers such as the Stage 3 UI. It does
        not change query parsing, matching, ranking, or the index contents.
        """
        ix = self._get_index()
        if ix is None:
            return 0
        return ix.doc_count()

    def close(self) -> None:
        """Closes any open index resources and triggers garbage collection for Windows."""
        if self._index is not None:
            try:
                self._index.close()
            except Exception:
                pass
            self._index = None
        gc.collect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _sanitize_query_text(self, text: str) -> str:
        """Removes unbalanced syntax characters that might disrupt Whoosh query parsing."""
        # Replace problematic boolean/syntax punctuation while preserving alphanumeric words
        cleaned = re.sub(r'[\(\)\[\]\{\}\^~:!]', ' ', text)
        return cleaned.strip()

    @staticmethod
    def _clean_snippet(text: str) -> str:
        """Converts highlighted HTML into readable, single-line terminal text."""
        if not text:
            return ""
        plain = _HTML_TAG_RE.sub("", text)
        plain = html.unescape(plain)
        plain = _CONTROL_CHAR_RE.sub("", plain)
        return _WHITESPACE_RE.sub(" ", plain).strip()

    @staticmethod
    def _query_term_texts(parsed_query) -> List[str]:
        """Returns the unique analyzed term texts that make up a query."""
        terms: List[str] = []
        seen: Set[str] = set()
        for _fieldname, text in sorted(parsed_query.all_terms()):
            if text and text not in seen:
                seen.add(text)
                terms.append(text)
        return terms

    @staticmethod
    def _term_exists_in_index(searcher, text: str) -> bool:
        """Checks whether an analyzed term occurs in either searchable field."""
        return any(
            searcher.doc_frequency(fieldname, text) > 0
            for fieldname in ("title", "content")
        )

    def search(self, query_text: str, limit: int = 10) -> List[SearchResult]:
        """
        Executes a ranked full-text search across titles and page contents.

        Requirements satisfied:
        - Returns empty list for blank queries or empty/missing index.
        - Uses BM25F ranking with title boosted 2.5x over body content.
        - Produces clean text excerpts (snippets) for terminal display.
        - Returns actual relevance scores computed by the engine.
        - Gracefully handles malformed queries.

        Partial-match policy:
        - The query is disjunctive: a document may match any of its analyzed
          terms, and BM25F ranks how strongly it matches.
        - If any analyzed query term is absent from the entire collection, the
          query returns no results. This prevents a query such as
          "PID controller" from looking like a PID match on a collection that
          has no PID material at all.
        - Each returned document must match at least half (rounded up) of the
          distinct query terms, so a document matching only one incidental term
          from a long query is not presented as a result.
        """
        if not query_text or not isinstance(query_text, str) or not query_text.strip():
            return []

        clean_query = query_text.strip()
        ix = self._get_index()
        if ix is None:
            return []

        searcher = ix.searcher(weighting=scoring.BM25F(B=0.75, K1=1.2))
        try:
            # Query across both title and content. fieldboosts give title matches
            # higher priority in BM25F scoring. The plain OrGroup is important:
            # OrGroup.factory(0.9) enables Whoosh's CoordMatcher, whose SQR
            # formula collapses every score to 0 when the index is missing some
            # query terms (the surviving matcher tree has only one term).
            qp = MultifieldParser(
                ["title", "content"],
                schema=ix.schema,
                fieldboosts={"title": 2.5, "content": 1.0},
                group=OrGroup,
            )

            try:
                parsed_query = qp.parse(clean_query)
            except QueryParserError:
                # Fallback to sanitized plain text query if user typed unclosed syntax
                fallback_text = self._sanitize_query_text(clean_query)
                if not fallback_text:
                    return []
                try:
                    parsed_query = qp.parse(fallback_text)
                except QueryParserError:
                    return []

            query_terms = self._query_term_texts(parsed_query)
            if not query_terms:
                return []

            # A query mentioning a term the collection does not contain has no
            # meaningful answer. Returning partial matches here would imply
            # relevance to material that was never indexed (for example, "PID"
            # on an Arduino-only collection).
            if any(
                not self._term_exists_in_index(searcher, term)
                for term in query_terms
            ):
                return []

            hits = searcher.search(parsed_query, limit=limit, terms=True)
            results: List[SearchResult] = []
            minimum_matches = (len(query_terms) + 1) // 2

            for hit in hits:
                matched_terms = {
                    text.decode("utf-8", "replace") if isinstance(text, bytes) else text
                    for _fieldname, text in hit.matched_terms()
                }
                if len(matched_terms) < minimum_matches:
                    continue

                url = hit["url"]
                domain = hit.get("domain", "")
                title = hit.get("title", "Untitled")
                score = float(hit.score)

                # Generate a highlighted snippet, then strip markup for terminal use
                snippet = hit.highlights("content")
                if not snippet:
                    raw_content = hit.get("content", "")
                    if len(raw_content) > 160:
                        snippet = raw_content[:160].rstrip() + "..."
                    else:
                        snippet = raw_content
                snippet = self._clean_snippet(snippet)

                results.append(
                    SearchResult(
                        url=url,
                        title=title,
                        snippet=snippet,
                        score=score,
                        domain=domain,
                    )
                )

            return results
        finally:
            searcher.close()


def search(
    query: str, limit: int = 10, index_dir: Optional[Union[str, Path]] = None
) -> List[SearchResult]:
    """
    Convenience function to search the mechatronics index.
    Opens, searches, and safely closes index resources in a single call.
    """
    with SearchEngine(index_dir=index_dir) as engine:
        return engine.search(query_text=query, limit=limit)
