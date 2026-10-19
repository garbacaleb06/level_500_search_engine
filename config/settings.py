"""Central settings and configuration for Mechatronics Search Engine."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "pages.db"
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

# High-quality Mechatronics Seeds
SEED_URLS = [
    "https://docs.arduino.cc/learn/electronics/",
    "https://docs.arduino.cc/hardware/",
    "https://eng.libretexts.org/Bookshelves/Control_Systems_Engineering",
    "https://eng.libretexts.org/Bookshelves/Mechanical_Engineering",
]

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
