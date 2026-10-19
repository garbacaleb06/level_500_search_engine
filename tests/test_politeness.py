"""Unit tests for PolitenessManager and robots.txt handling."""

import time
import urllib.robotparser
from src.crawler.politeness import PolitenessManager


def test_politeness_custom_robot_parser():
    manager = PolitenessManager(user_agent="MechatronicsBot/1.0", default_delay=1.0)

    # Inject a simulated robot parser
    mock_parser = urllib.robotparser.RobotFileParser()
    mock_parser.parse([
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /private/",
        "Crawl-delay: 3",
        "Allow: /learn/"
    ])
    manager._parsers["docs.arduino.cc"] = mock_parser

    assert manager.can_fetch("https://docs.arduino.cc/learn/sensors") is True
    assert manager.can_fetch("https://docs.arduino.cc/admin/dashboard") is False
    assert manager.get_crawl_delay("https://docs.arduino.cc/learn/sensors") == 3.0


def test_politeness_enforce_delay():
    manager = PolitenessManager(user_agent="MechatronicsBot/1.0", default_delay=0.1)

    url = "https://docs.arduino.cc/test"
    # First call should not sleep
    slept1 = manager.enforce_delay(url)
    assert slept1 == 0.0

    # Immediate second call should sleep roughly 0.1s
    start = time.time()
    slept2 = manager.enforce_delay(url)
    elapsed = time.time() - start

    assert slept2 > 0.0
    assert elapsed >= 0.08  # Tolerant threshold for test execution
