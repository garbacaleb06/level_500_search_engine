"""Data models for stored pages and search results."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PageRecord:
    """Represents a crawled and parsed mechatronics web page stored in SQLite."""
    url: str
    domain: str
    title: str
    content_text: str
    http_status: int
    content_length: int
    crawled_at: Optional[str] = None


@dataclass
class SearchResult:
    """Represents a ranked document result returned to the user or UI."""
    url: str
    title: str
    snippet: str
    score: float
    domain: str
