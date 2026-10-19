"""Politeness manager for robots.txt parsing and per-domain crawl delays."""

import time
import urllib.robotparser
from urllib.parse import urlparse
from typing import Dict, Optional


class PolitenessManager:
    """Handles robots.txt adherence and rate-limiting per host."""

    def __init__(self, user_agent: str, default_delay: float = 2.0, request_timeout: float = 5.0):
        self.user_agent = user_agent
        self.default_delay = default_delay
        self.request_timeout = request_timeout
        self._parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_request_times: Dict[str, float] = {}

    def _get_domain(self, url: str) -> str:
        """Extracts the lowercased network location (domain) from a URL."""
        return urlparse(url).netloc.lower()

    def get_robot_parser(self, url: str) -> urllib.robotparser.RobotFileParser:
        """Retrieves or loads the cached RobotFileParser for a domain."""
        domain = self._get_domain(url)
        if domain in self._parsers:
            return self._parsers[domain]

        scheme = urlparse(url).scheme or "https"
        robots_url = f"{scheme}://{domain}/robots.txt"

        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            # RobotFileParser.read() uses urllib.request internally
            parser.read()
        except Exception:
            # If robots.txt cannot be fetched (e.g. 404 or network timeout),
            # standard robot exclusion convention allows crawling
            pass

        self._parsers[domain] = parser
        return parser

    def can_fetch(self, url: str) -> bool:
        """Checks if the user-agent is permitted by robots.txt to crawl the URL."""
        try:
            parser = self.get_robot_parser(url)
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def get_crawl_delay(self, url: str) -> float:
        """Returns the domain's crawl delay from robots.txt, or the default delay."""
        try:
            parser = self.get_robot_parser(url)
            delay = parser.crawl_delay(self.user_agent)
            if delay is not None and delay > 0:
                return float(delay)
        except Exception:
            pass
        return self.default_delay

    def enforce_delay(self, url: str) -> float:
        """
        Calculates and pauses execution if needed to respect the domain's crawl delay.
        Returns the actual time slept in seconds.
        """
        domain = self._get_domain(url)
        delay = self.get_crawl_delay(url)
        now = time.time()

        slept = 0.0
        if domain in self._last_request_times:
            elapsed = now - self._last_request_times[domain]
            if elapsed < delay:
                slept = delay - elapsed
                time.sleep(slept)

        self._last_request_times[domain] = time.time()
        return slept
