"""Whoosh schema definition for Mechatronics Search Engine."""

from whoosh.fields import Schema, ID, TEXT, STORED
from whoosh.analysis import StemmingAnalyzer


def create_search_schema() -> Schema:
    """
    Creates and returns the Whoosh schema for indexing mechatronics documents.
    
    Fields:
    - url: Unique document identifier, stored for display and deduplication.
    - domain: Host domain (e.g., 'docs.arduino.cc'), stored for filtering/display.
    - title: Document title, stemmed and boosted 2.5x over body content.
    - content: Full text body of the page, stemmed for morphological matching.
    - crawled_at: Timestamp of crawl, stored for metadata display.
    """
    analyzer = StemmingAnalyzer()
    return Schema(
        url=ID(stored=True, unique=True),
        domain=ID(stored=True),
        title=TEXT(stored=True, field_boost=2.5, analyzer=analyzer),
        content=TEXT(stored=True, analyzer=analyzer),
        crawled_at=STORED,
    )
