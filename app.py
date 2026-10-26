"""Stage 3 Streamlit interface for the Mechatronics Search Engine.

The page is a thin presentation layer over the existing local Whoosh search
engine. It never crawls the web, calls an external search API, or rebuilds the
index while serving a query. The layout is responsive so the same page is
usable in a desktop browser and on a phone screen.
"""

from __future__ import annotations

import logging
import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import streamlit as st

from config import settings
from src.search.searcher import SearchEngine
from src.storage.models import SearchResult

logger = logging.getLogger(__name__)

APP_TITLE = "Mechatronics Search Engine"
DEFAULT_LIMIT = 5
MAX_LIMIT = 20
LIMIT_OPTIONS = (5, 10, 20)
EXAMPLE_QUERIES = ("Arduino hardware", "sensor", "control", "stepper motor")

INDEX_READY = "ready"
INDEX_MISSING = "missing"
INDEX_EMPTY = "empty"
INDEX_ERROR = "error"

_MARKDOWN_ESCAPE_RE = re.compile(r"([\\`*_{}\[\]<>#+!|])")


@dataclass(frozen=True)
class IndexStatus:
    """The UI's view of the local Whoosh index."""

    state: str
    document_count: int = 0
    detail: str = ""


@dataclass(frozen=True)
class SearchSnapshot:
    """One completed search, retained only for the current browser session."""

    query: str
    results: Tuple[SearchResult, ...]
    elapsed_ms: float
    limit: int


def normalize_query(value: object) -> str:
    """Returns a trimmed query string, or an empty string for non-text input."""
    if not isinstance(value, str):
        return ""
    return value.strip()


def prepare_query(value: object) -> Optional[str]:
    """Returns a non-empty trimmed query, or None when the user submitted blank input."""
    query = normalize_query(value)
    return query or None


def clamp_limit(value: object) -> int:
    """Keeps a result limit inside the range supported by the UI."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(parsed, MAX_LIMIT))


def safe_http_url(value: object) -> Optional[str]:
    """Returns an HTTP(S) URL suitable for a link button, or None if unsafe."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def escape_markdown(text: object) -> str:
    """Escapes crawled/display text so Streamlit cannot interpret it as markup."""
    if not isinstance(text, str):
        return ""
    return _MARKDOWN_ESCAPE_RE.sub(r"\\\1", text)


def create_search_engine(index_dir: str | Path) -> SearchEngine:
    """Creates the project's search engine for a specific index directory."""
    return SearchEngine(index_dir=index_dir)


def inspect_index(engine: SearchEngine) -> IndexStatus:
    """Classifies the index as missing, empty, ready, or unreadable."""
    try:
        if not engine.is_index_ready():
            return IndexStatus(INDEX_MISSING)
        count = engine.document_count()
        if count <= 0:
            return IndexStatus(INDEX_EMPTY)
        return IndexStatus(INDEX_READY, document_count=count)
    except Exception as exc:  # Corrupt or partially written index.
        logger.exception("Unable to inspect the search index")
        return IndexStatus(INDEX_ERROR, detail=f"{type(exc).__name__}: {exc}")


def execute_search(engine: SearchEngine, query: str, limit: int) -> SearchSnapshot:
    """Runs exactly one local BM25F search and records its wall-clock time."""
    effective_limit = clamp_limit(limit)
    started = time.perf_counter()
    results = engine.search(query_text=query, limit=effective_limit)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return SearchSnapshot(
        query=query,
        results=tuple(results),
        elapsed_ms=elapsed_ms,
        limit=effective_limit,
    )


def build_indexer_command(
    db_path: str | Path | None = None, index_dir: str | Path | None = None
) -> str:
    """Builds the documented PowerShell command for rebuilding the index."""
    database = Path(db_path or settings.DB_PATH)
    index = Path(index_dir or settings.INDEX_DIR)
    return (
        f'.venv\\Scripts\\python.exe -m src.indexer '
        f'--db "{database}" --index-dir "{index}"'
    )


@st.cache_resource(show_spinner=False)
def get_search_engine(index_dir: str) -> SearchEngine:
    """Caches the engine, which in turn caches the opened Whoosh index."""
    return create_search_engine(index_dir)


def _queue_search() -> None:
    """Callback for Enter and the Search button; performs no search itself."""
    st.session_state["pending_query"] = normalize_query(
        st.session_state.get("query_input", "")
    )


def _use_example(example: str) -> None:
    """Callback for an example chip."""
    st.session_state["query_input"] = example
    st.session_state["pending_query"] = example


def _clear_search() -> None:
    """Callback that clears the query and any retained search state."""
    st.session_state["query_input"] = ""
    st.session_state.pop("pending_query", None)
    st.session_state.pop("last_snapshot", None)
    st.session_state.pop("last_search_error", None)
    st.session_state["empty_submitted"] = False


def _refresh_index() -> None:
    """Closes the cached engine so a rebuilt index is opened on the next run."""
    try:
        get_search_engine(str(settings.INDEX_DIR)).close()
    except Exception:
        logger.exception("Unable to close the cached search engine")
    finally:
        get_search_engine.clear()
        st.session_state.pop("last_snapshot", None)
        st.session_state.pop("last_search_error", None)


MOBILE_CSS = """
<style>
/* Reading column: keeps content inside the viewport at every screen size. */
.block-container {
    max-width: 1080px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}
div[data-testid="stMetric"] {
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 0.6rem;
    padding: 0.7rem 0.9rem;
}
/* Long target URLs, index paths and shell commands must wrap instead of
   forcing horizontal scrolling on a narrow phone screen. */
.stMarkdown p,
div[data-testid="stCaptionContainer"],
div[data-testid="stCaptionContainer"] p {
    overflow-wrap: anywhere;
    word-break: break-word;
}
div[data-testid="stCode"] pre,
div[data-testid="stCodeBlock"] pre {
    white-space: pre-wrap;
    word-break: break-word;
}
/* Touch targets of at least 44px, and 1rem inputs so mobile browsers do not
   zoom the page when a field receives focus. */
div[data-testid="stButton"] button,
div[data-testid="stLinkButton"] a,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    min-height: 2.75rem;
}
div[data-testid="stTextInput"] input {
    min-height: 2.75rem;
    font-size: 1rem;
}
/* Phone layout: tighter padding and smaller headings/metrics so the search
   form, statistics and results stay scannable on a narrow screen. */
@media (max-width: 640px) {
    .block-container {
        padding-top: 1.1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    h1 {
        font-size: 1.6rem;
        line-height: 1.25;
    }
    h4 {
        font-size: 1.05rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.8rem;
    }
}
</style>
"""


def _apply_styles() -> None:
    """A small amount of static CSS; no user-controlled HTML is injected."""
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)


def _render_index_help(status: IndexStatus) -> None:
    """Shows actionable setup instructions for missing, empty, or broken indexes."""
    if status.state == INDEX_MISSING:
        st.error("The search index is missing or has not been initialized.")
        st.write("The app expects the Whoosh index at:")
        st.code(str(settings.INDEX_DIR), language=None)
        st.write(
            "Build it from your crawled SQLite database, for example with "
            "`data/seeds_check.db` if that is the database you created:"
        )
        st.code(build_indexer_command(), language="powershell")
        st.info(
            "Use the database you actually crawled if it differs from the configured "
            "path. This app never crawls the web or creates an index automatically."
        )
    elif status.state == INDEX_EMPTY:
        st.warning("The search index exists but contains no documents.")
        st.write("Rebuild it from a populated SQLite database with:")
        st.code(build_indexer_command(), language="powershell")
        st.caption(
            "Searching cannot return results until the index contains indexed pages."
        )
    else:
        st.error("The search index could not be opened.")
        st.write(
            "Check that the index directory is readable, or rebuild it from the "
            "SQLite database."
        )
        if status.detail:
            with st.expander("Technical details"):
                st.code(status.detail, language="text")


def _render_sidebar(status: IndexStatus) -> None:
    """Renders project context, corpus statistics, and connection controls."""
    db_exists = Path(settings.DB_PATH).exists()

    with st.sidebar:
        st.header("About this project")
        st.write(
            "A university mechatronics project that crawls a small, allowlisted "
            "set of engineering pages, stores them in SQLite, indexes them with "
            "Whoosh, and ranks local results with BM25F."
        )

        st.divider()
        st.subheader("Current collection")
        if status.state == INDEX_READY:
            st.metric("Indexed documents", status.document_count)
        elif status.state == INDEX_EMPTY:
            st.metric("Indexed documents", 0)
            st.caption("The index exists but is empty.")
        else:
            st.metric("Indexed documents", "Unavailable")

        st.caption("Whoosh index directory")
        st.code(str(settings.INDEX_DIR), language=None)
        st.caption("SQLite database (used only to rebuild the index)")
        st.code(str(settings.DB_PATH), language=None)
        if not db_exists:
            st.info(
                "The configured database file is not present. Searching the "
                "existing index still works; rebuilding it requires a valid database."
            )

        st.divider()
        st.button(
            "Refresh index connection",
            key="refresh_index_button",
            on_click=_refresh_index,
            width="stretch",
        )
        st.caption("Use this after rebuilding the index while the app is running.")
        st.button(
            "Clear search",
            key="clear_search_button",
            on_click=_clear_search,
            width="stretch",
        )

        st.divider()
        st.caption(
            "Local search only: no external search API, web crawl, or index "
            "rebuild happens when you submit a query."
        )


def format_result_meta(result: SearchResult) -> str:
    """Builds the one-line domain and relevance score shown under a title."""
    domain = escape_markdown(result.domain or "unknown domain")
    return f"{domain} · Relevance score (BM25F): {result.score:.3f}"


def _render_result(result: SearchResult, rank: int) -> None:
    """Renders one result as a framed, touch-friendly card."""
    title = escape_markdown(result.title or "Untitled")
    snippet = escape_markdown(
        result.snippet or "No snippet is available for this document."
    )

    # A bordered container separates results without extra dividers, which
    # would add vertical scrolling on a phone.
    with st.container(border=True):
        st.markdown(f"#### {rank}. {title}")
        st.caption(format_result_meta(result))
        st.markdown(snippet)

        url = safe_http_url(result.url)
        if url:
            # Full-width link keeps the tap target large on a touchscreen.
            st.link_button("Open original page", url, width="stretch")
            st.caption(escape_markdown(url))
        else:
            st.warning("This result has an invalid URL and cannot be opened.")


def _render_search_state(status: IndexStatus) -> None:
    """Shows the current search result, empty state, or search error."""
    if status.state != INDEX_READY:
        _render_index_help(status)
        return

    if st.session_state.get("empty_submitted"):
        st.warning(
            "Please enter a search query before searching. "
            "Try a topic such as `Arduino hardware`, `sensor`, or `control`."
        )
        return

    search_error = st.session_state.get("last_search_error")
    if search_error:
        st.error(
            "The search could not be completed. The index connection may need "
            "refreshing, or the index may have been moved while the app was open."
        )
        with st.expander("Technical details"):
            st.code(search_error, language="text")
        return

    snapshot: Optional[SearchSnapshot] = st.session_state.get("last_snapshot")
    if snapshot is None:
        st.info(
            "Enter a query above to search the local mechatronics collection. "
            "Example queries are suggestions only; results depend on what is indexed."
        )
        return

    metric_columns = st.columns(3)
    metric_columns[0].metric("Matching results", len(snapshot.results))
    metric_columns[1].metric("Search time", f"{snapshot.elapsed_ms:.1f} ms")
    metric_columns[2].metric("Indexed documents", status.document_count)

    if not snapshot.results:
        st.warning(
            f'No documents matched "{escape_markdown(snapshot.query)}". '
            "The local index may not contain this topic."
        )
        st.write(
            "This does not mean the topic is absent from the internet; it only "
            "means the currently indexed collection has no matching pages. Try "
            "broader or alternative terms, such as `motor`, `sensor`, `control`, "
            "or `Arduino hardware`."
        )
        st.caption(
            f"Showing up to {snapshot.limit} results. The ranking, partial-match "
            "policy, and snippets come from the existing BM25F search engine."
        )
        return

    st.caption(
        f'Showing up to {snapshot.limit} results for "{escape_markdown(snapshot.query)}". '
        "Order and scores come directly from the existing BM25F engine."
    )
    for rank, result in enumerate(snapshot.results, start=1):
        _render_result(result, rank)


def main() -> None:
    """Entry point used by Streamlit and by the AppTest integration tests."""
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="⚙️",
        layout="wide",
        # "auto" keeps the sidebar expanded on a desktop, but collapsed on a
        # phone where an open sidebar would hide the search controls.
        initial_sidebar_state="auto",
    )
    _apply_styles()

    engine: Optional[SearchEngine] = None
    initialization_error: Optional[str] = None
    try:
        engine = get_search_engine(str(settings.INDEX_DIR))
        status = inspect_index(engine)
    except Exception:
        initialization_error = traceback.format_exc()
        logger.exception("Unable to initialize the search engine")
        status = IndexStatus(INDEX_ERROR, detail=initialization_error)

    st.title(APP_TITLE)
    st.write(
        "Search a **locally indexed collection** of mechatronics, electronics, "
        "mechanical engineering, robotics, automation, and embedded-systems "
        "resources. Results are ranked by the project's existing Whoosh BM25F "
        "search engine."
    )
    st.caption(
        "Local demonstrator only · no external search API · no crawling or "
        "index rebuilding during searches"
    )
    st.caption(
        "On a phone, open the sidebar with the `»` arrow (top left) for setup "
        "details and collection statistics."
    )

    st.text_input(
        "Search the indexed collection",
        placeholder="e.g. Arduino hardware, sensor, stepper motor",
        key="query_input",
        on_change=_queue_search,
        help="Press Enter or use the Search button. Leading and trailing whitespace is trimmed.",
    )

    # On a phone these two columns stack into full-width taps; on a desktop
    # they stay side by side, so both layouts remain usable.
    search_column, limit_column = st.columns([1, 1])
    with search_column:
        st.button(
            "Search",
            key="search_button",
            type="primary",
            on_click=_queue_search,
            width="stretch",
        )
    with limit_column:
        result_limit = st.selectbox(
            "Results to show",
            options=LIMIT_OPTIONS,
            index=0,
            key="result_limit",
            help=(
                f"Choose between 1 and {MAX_LIMIT} results. The selected limit "
                "applies to your next search. The default is 5."
            ),
        )

    st.caption("Example queries (tap one to search; suggestions only, corpus is small):")
    # A wrapping chip row stays compact on a phone instead of stacking four
    # full-width buttons above the results.
    with st.container(horizontal=True, wrap=True):
        for index, example in enumerate(EXAMPLE_QUERIES):
            st.button(
                example,
                key=f"example_query_{index}",
                on_click=_use_example,
                args=(example,),
            )

    # A query is executed only on an explicit submit (Enter/Search/example).
    # The pending value is consumed so unrelated reruns do not repeat the search.
    pending = st.session_state.pop("pending_query", None)
    if pending is not None:
        query = prepare_query(pending)
        st.session_state["empty_submitted"] = query is None
        st.session_state.pop("last_search_error", None)

        if query is None:
            st.session_state.pop("last_snapshot", None)
        elif initialization_error is not None:
            st.session_state["last_search_error"] = initialization_error
            st.session_state.pop("last_snapshot", None)
        elif status.state != INDEX_READY:
            st.session_state.pop("last_snapshot", None)
        else:
            try:
                st.session_state["last_snapshot"] = execute_search(
                    engine, query, result_limit
                )
            except Exception:
                logger.exception("Search failed for query %r", query)
                st.session_state["last_search_error"] = traceback.format_exc()
                st.session_state.pop("last_snapshot", None)

    _render_sidebar(status)

    st.divider()
    _render_search_state(status)


if __name__ == "__main__":
    main()
