"""Central settings and configuration for Mechatronics Search Engine."""

import os
from pathlib import Path

# Base Paths
#
# Paths are derived from this file's location, not the working directory, so the
# app behaves the same when started by Streamlit Community Cloud or by hand.
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# The verified corpus lives in data/seeds_check.db (4 crawled pages, all HTTP 200).
# data/pages.db is a 0-byte leftover from an early crawl attempt and contains no
# `pages` table, so using it as the default made the indexer fail with
# "no such table: pages". All code that resolves a default database goes through
# this value; pass --db explicitly to index a different database.
DB_PATH = DATA_DIR / "seeds_check.db"
INDEX_DIR = DATA_DIR / "whoosh_index"

# Crawler Identity & Safety
USER_AGENT = "MechatronicsUniversityBot/1.0 (+https://github.com/academic-search-project; student-project@university.edu)"
REQUEST_TIMEOUT = 5.0  # seconds
DEFAULT_CRAWL_DELAY = 2.0  # seconds (used if robots.txt does not specify a delay)
MAX_CRAWL_DEPTH = 3
MAX_PAGES_TO_CRAWL = 200
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB size ceiling to prevent memory issues

# Allowed Domains (strict allowlist)
ALLOWED_DOMAINS = [
    "docs.arduino.cc",
    "eng.libretexts.org",
]

# High-quality Mechatronics Seeds (all verified to return HTTP 200)
SEED_URLS = [
    "https://docs.arduino.cc/learn/",
    "https://docs.arduino.cc/hardware/",
    "https://eng.libretexts.org/Bookshelves/Mechanical_Engineering",
    "https://eng.libretexts.org/Bookshelves/Electrical_Engineering",
]

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
