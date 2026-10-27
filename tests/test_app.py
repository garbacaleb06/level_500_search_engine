"""Tests for the Stage 3 Streamlit interface and its integration with search."""

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
from config import settings
from src.indexer.indexer import SearchIndexer
from src.search.searcher import SearchEngine, search
from src.storage.db import DatabaseManager
from src.storage.models import PageRecord, SearchResult

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


def _ui_pages():
    """Returns an isolated Arduino collection for UI tests."""
    return [
        PageRecord(
            url="https://docs.arduino.cc/hardware/",
            domain="docs.arduino.cc",
            title="Arduino Hardware",
            content_text=(
                "Arduino hardware boards provide digital pins, sensors, and "
                "real-time control for electronics projects."
            ),
            http_status=200,
            content_length=1200,
        ),
        PageRecord(
            url="https://docs.arduino.cc/learn/",
            domain="docs.arduino.cc",
            title="Arduino Learn",
            content_text=(
                "Arduino tutorials cover sensors, servo motors, and control "
                "fundamentals for beginners."
            ),
            http_status=200,
            content_length=1100,
        ),
        PageRecord(
            url="https://eng.libretexts.org/mechanical-engineering",
            domain="eng.libretexts.org",
            title="Mechanical Engineering",
            content_text="Mechanical engineering covers dynamics and machine design.",
            http_status=200,
            content_length=900,
        ),
        PageRecord(
            url="https://eng.libretexts.org/electrical-engineering",
            domain="eng.libretexts.org",
            title="Electrical Engineering",
            content_text="Electrical engineering covers circuits, signals, and power.",
            http_status=200,
            content_length=950,
        ),
    ]


def _build_ui_index(index_dir: Path) -> Path:
    """Builds a small, isolated Arduino collection for UI tests."""
    SearchIndexer(index_dir=index_dir).build_from_pages(_ui_pages(), clean=True)
    return index_dir


@pytest.fixture
def ui_index(tmp_path):
    return _build_ui_index(tmp_path / "ui_index")


@pytest.fixture
def empty_index(tmp_path):
    index_dir = tmp_path / "empty_index"
    ix = SearchIndexer(index_dir=index_dir).open_or_create_index(clean=True)
    ix.close()
    return index_dir


def _run_app(monkeypatch, index_dir: Path, db_path: Path | None = None) -> AppTest:
    """Runs app.py against an isolated settings configuration."""
    database = db_path or index_dir.parent / "test_pages.db"
    database.write_text("")
    monkeypatch.setattr(app.settings, "INDEX_DIR", Path(index_dir))
    monkeypatch.setattr(app.settings, "DB_PATH", Path(database))

    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    return at


def test_app_imports_and_has_entry_point():
    assert app.APP_TITLE == "Mechatronics Search Engine"
    assert callable(app.main)
    assert app.SearchEngine is SearchEngine


def test_normalize_and_prepare_query():
    assert app.normalize_query("  Arduino hardware  ") == "Arduino hardware"
    assert app.normalize_query(None) == ""
    assert app.normalize_query(123) == ""
    assert app.prepare_query("   ") is None
    assert app.prepare_query("") is None
    assert app.prepare_query(None) is None
    assert app.prepare_query("  sensor ") == "sensor"


def test_limit_is_clamped_to_supported_range():
    assert app.clamp_limit(5) == 5
    assert app.clamp_limit(0) == 1
    assert app.clamp_limit(100) == app.MAX_LIMIT
    assert app.clamp_limit("nonsense") == app.DEFAULT_LIMIT


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://docs.arduino.cc/learn/", "https://docs.arduino.cc/learn/"),
        ("http://example.com/page", "http://example.com/page"),
        ("javascript:alert(1)", None),
        ("ftp://example.com/file", None),
        ("/relative/path", None),
        ("", None),
        (None, None),
    ],
)
def test_safe_http_url(url, expected):
    assert app.safe_http_url(url) == expected


def test_display_text_is_markdown_escaped():
    escaped = app.escape_markdown("<b>**stepper**</b>")
    assert "\\<b\\>" in escaped
    assert "\\*\\*stepper\\*\\*" in escaped


def test_inspect_index_reports_ready_missing_and_empty(ui_index, empty_index, tmp_path):
    ready = app.inspect_index(SearchEngine(index_dir=ui_index))
    assert ready.state == app.INDEX_READY
    assert ready.document_count == 4

    missing = app.inspect_index(SearchEngine(index_dir=tmp_path / "missing"))
    assert missing.state == app.INDEX_MISSING
    assert missing.document_count == 0

    empty = app.inspect_index(SearchEngine(index_dir=empty_index))
    assert empty.state == app.INDEX_EMPTY
    assert empty.document_count == 0


def test_inspect_index_reports_unreadable_index():
    class BrokenEngine:
        def is_index_ready(self):
            return True

        def document_count(self):
            raise RuntimeError("index is unreadable")

    status = app.inspect_index(BrokenEngine())
    assert status.state == app.INDEX_ERROR
    assert "index is unreadable" in status.detail


def test_build_indexer_command_uses_configured_paths(tmp_path):
    command = app.build_indexer_command(
        db_path=tmp_path / "pages.db", index_dir=tmp_path / "whoosh_index"
    )
    assert "-m src.indexer" in command
    assert str(tmp_path / "pages.db") in command
    assert str(tmp_path / "whoosh_index") in command


def test_inspect_database_reports_ready_missing_and_unusable(tmp_path):
    usable = tmp_path / "corpus.db"
    DatabaseManager(usable).save_page(
        PageRecord(
            url="https://docs.arduino.cc/learn/",
            domain="docs.arduino.cc",
            title="Learn",
            content_text="Arduino tutorials.",
            http_status=200,
            content_length=18,
        )
    )
    ready = app.inspect_database(usable)
    assert ready.state == app.DB_READY
    assert ready.page_count == 1

    missing = app.inspect_database(tmp_path / "absent.db")
    assert missing.state == app.DB_MISSING

    # The exact shape of the leftover data/pages.db in this project: a file that
    # exists but cannot rebuild an index.
    leftover = tmp_path / "pages.db"
    leftover.write_text("")
    unusable = app.inspect_database(leftover)
    assert unusable.state == app.DB_UNUSABLE
    assert "pages" in unusable.detail


@pytest.mark.skipif(
    not settings.INDEX_DIR.is_dir(),
    reason="the committed Whoosh index is not present in this checkout",
)
def test_repository_ships_a_searchable_index_and_database():
    """A fresh clone has no crawler run, so the committed index must answer queries."""
    engine = SearchEngine(index_dir=settings.INDEX_DIR)
    try:
        assert engine.document_count() == 4
        expected_counts = {
            "Arduino hardware": 2,
            "sensor": 1,
            "control": 2,
            "stepper motor": 1,
        }
        for query, count in expected_counts.items():
            assert len(engine.search(query_text=query, limit=5)) == count, query
        assert engine.search(query_text="   ", limit=5) == []
        assert engine.search(query_text="PID controller", limit=5) == []
    finally:
        engine.close()

    assert app.inspect_database(settings.DB_PATH).state == app.DB_READY


def test_build_indexer_command_uses_the_running_interpreter():
    command = app.build_indexer_command()
    assert sys.executable in command
    assert str(settings.DB_PATH) in command
    assert str(settings.INDEX_DIR) in command
    assert "-m src.indexer" in command


def test_streamlit_sidebar_explains_an_unusable_database(monkeypatch, ui_index):
    # _run_app points DB_PATH at a 0-byte file, the situation the app must report.
    at = _run_app(monkeypatch, ui_index)

    assert not at.exception
    assert any(
        "cannot rebuild the index" in info.value for info in at.sidebar.info
    )


def test_execute_search_matches_existing_engine_ranking(ui_index):
    expected = search("Arduino hardware", index_dir=ui_index)
    engine = app.create_search_engine(ui_index)
    try:
        snapshot = app.execute_search(engine, "Arduino hardware", 5)
        assert engine.document_count() == 4
    finally:
        engine.close()

    assert [r.url for r in snapshot.results] == [r.url for r in expected]
    assert [r.score for r in snapshot.results] == pytest.approx(
        [r.score for r in expected]
    )
    assert snapshot.results[0].title == "Arduino Hardware"
    assert snapshot.elapsed_ms >= 0.0


def test_execute_search_handles_zero_results(ui_index):
    engine = app.create_search_engine(ui_index)
    try:
        snapshot = app.execute_search(engine, "PID controller", 5)
    finally:
        engine.close()
    assert snapshot.results == ()


def test_streamlit_app_starts_and_connects_to_existing_index(monkeypatch, ui_index):
    at = _run_app(monkeypatch, ui_index)

    assert not at.exception
    assert any(title.value == app.APP_TITLE for title in at.title)
    assert any(
        metric.label == "Indexed documents" and metric.value == "4"
        for metric in at.metric
    )
    assert at.text_input(key="query_input").value == ""


def test_streamlit_search_matches_existing_ranking(monkeypatch, ui_index):
    at = _run_app(monkeypatch, ui_index)
    at.text_input(key="query_input").set_value("Arduino hardware").run()

    assert not at.exception
    assert at.text_input(key="query_input").value == "Arduino hardware"
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Matching results"] == "2"
    assert metrics["Indexed documents"] == "4"

    expected = search("Arduino hardware", index_dir=ui_index)
    headings = [
        markdown.value
        for markdown in at.markdown
        if markdown.value.startswith("#### ")
    ]
    assert headings == [
        f"#### {rank}. {result.title}"
        for rank, result in enumerate(expected, start=1)
    ]


def test_streamlit_refresh_reopens_rebuilt_index(monkeypatch, ui_index):
    at = _run_app(monkeypatch, ui_index)
    assert any(
        metric.label == "Indexed documents" and metric.value == "4"
        for metric in at.metric
    )

    extra_page = PageRecord(
        url="https://docs.arduino.cc/robotics/",
        domain="docs.arduino.cc",
        title="Arduino Robotics",
        content_text="Arduino robotics projects combine motors, sensors, and control.",
        http_status=200,
        content_length=1000,
    )
    SearchIndexer(index_dir=ui_index).build_from_pages(
        _ui_pages() + [extra_page], clean=True
    )

    at.button(key="refresh_index_button").click().run()

    assert not at.exception
    assert any(
        metric.label == "Indexed documents" and metric.value == "5"
        for metric in at.metric
    )


def test_streamlit_zero_result_query_is_clean(monkeypatch, ui_index):
    at = _run_app(monkeypatch, ui_index)
    at.text_input(key="query_input").set_value("PID controller").run()

    assert not at.exception
    assert any(
        metric.label == "Matching results" and metric.value == "0"
        for metric in at.metric
    )
    assert any("No documents matched" in warning.value for warning in at.warning)


def test_streamlit_blank_query_does_not_search(monkeypatch, ui_index):
    at = _run_app(monkeypatch, ui_index)
    at.text_input(key="query_input").set_value("   ").run()

    assert not at.exception
    assert any(
        "Please enter a search query" in warning.value for warning in at.warning
    )
    assert not any(metric.label == "Matching results" for metric in at.metric)


def test_streamlit_missing_index_has_actionable_message(monkeypatch, tmp_path):
    at = _run_app(monkeypatch, tmp_path / "missing_index")

    assert not at.exception
    assert any("missing" in error.value.lower() for error in at.error)
    assert any("src.indexer" in code.value for code in at.code)


def test_streamlit_empty_index_has_actionable_message(monkeypatch, empty_index):
    at = _run_app(monkeypatch, empty_index)

    assert not at.exception
    assert any("contains no documents" in warning.value for warning in at.warning)
    assert any("src.indexer" in code.value for code in at.code)


def test_streamlit_malformed_query_does_not_crash(monkeypatch, ui_index):
    at = _run_app(monkeypatch, ui_index)
    at.text_input(key="query_input").set_value("PID AND (").run()

    assert not at.exception
    assert any(
        "No documents matched" in warning.value for warning in at.warning
    )


def test_streamlit_search_exception_is_handled(monkeypatch, ui_index):
    def failing_search(self, *args, **kwargs):
        raise RuntimeError("simulated search failure")

    monkeypatch.setattr(SearchEngine, "search", failing_search)
    at = _run_app(monkeypatch, ui_index)
    at.text_input(key="query_input").set_value("control").run()

    assert not at.exception
    assert any("could not be completed" in error.value for error in at.error)


def test_format_result_meta_shows_domain_and_relevance_score():
    result = SearchResult(
        url="https://docs.arduino.cc/learn/",
        title="Arduino Learn",
        snippet="Snippet text.",
        score=1.23456,
        domain="docs.arduino.cc",
    )
    assert app.format_result_meta(result) == (
        "docs.arduino.cc · Relevance score (BM25F): 1.235"
    )


def test_format_result_meta_escapes_untrusted_domain():
    result = SearchResult(
        url="https://example.com/",
        title="Title",
        snippet="",
        score=2.0,
        domain="*<b>evil</b>",
    )
    meta = app.format_result_meta(result)
    assert r"\*\<b\>evil\</b\>" in meta
    assert "2.000" in meta


def test_streamlit_example_query_buttons_are_present_and_run_a_search(
    monkeypatch, ui_index
):
    at = _run_app(monkeypatch, ui_index)
    example_keys = [
        button.key for button in at.button if button.key.startswith("example_query_")
    ]
    assert example_keys == [
        f"example_query_{index}" for index in range(len(app.EXAMPLE_QUERIES))
    ]

    at.button(key="example_query_0").click().run()

    assert not at.exception
    assert app.EXAMPLE_QUERIES[0] == "Arduino hardware"
    assert at.text_input(key="query_input").value == "Arduino hardware"
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Matching results"] == "2"


def test_streamlit_results_render_tappable_http_links(monkeypatch, ui_index):
    at = _run_app(monkeypatch, ui_index)
    at.text_input(key="query_input").set_value("Arduino hardware").run()

    assert not at.exception
    expected = search("Arduino hardware", index_dir=ui_index)
    link_buttons = list(at.link_button)
    assert [button.value for button in link_buttons] == [
        "Open original page" for _ in expected
    ]
    assert [button.url for button in link_buttons] == [
        result.url for result in expected
    ]
    assert all(button.url.startswith("https://") for button in link_buttons)


def test_streamlit_sidebar_keeps_statistics_and_controls(monkeypatch, ui_index):
    at = _run_app(monkeypatch, ui_index)
    sidebar = at.sidebar

    assert not at.exception
    assert any(metric.label == "Indexed documents" for metric in sidebar.metric)
    assert sidebar.button(key="clear_search_button") is not None
    assert sidebar.button(key="refresh_index_button") is not None
