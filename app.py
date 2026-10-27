"""MechaSearch — Streamlit interface for the Mechatronics Knowledge Hub.

The page is a presentation layer over the existing local Whoosh search engine.
It never crawls the web, calls an external search API, or rebuilds the index
while serving a query. The layout is responsive so the same page is usable in a
desktop browser and on a phone screen.

Visual design is driven by Streamlit's own theme (`.streamlit/config.toml`) plus a
small stylesheet for touch targets and narrow-screen wrapping. Components are
native Streamlit widgets: `st.pills` for the topic filter, bordered containers for
result cards, and `st.badge` for topic labels.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import streamlit as st

from config import settings
from src.indexer.topics import TOPIC_LABELS, topic_label
from src.search.searcher import SearchEngine
from src.storage.models import SearchResult

logger = logging.getLogger(__name__)

# Application identity
APP_NAME = "MechaSearch"
APP_TITLE = "MechaSearch"
APP_HEADING = "Mechatronics Knowledge Hub"
APP_TAGLINE = (
    "A focused search engine for mechatronics, robotics, control systems, "
    "electronics and mechanical engineering."
)

DEFAULT_LIMIT = 5
MAX_LIMIT = 20
LIMIT_OPTIONS = (5, 10, 20)
EXAMPLE_QUERIES = ("Arduino hardware", "PID controller", "stepper motor", "sensor")

# Topic filter. The order here is the order the pills are shown in, and the
# labels come from the shared rule table so the UI cannot drift from the labels
# the indexer actually wrote into the index.
TOPIC_ORDER: Tuple[str, ...] = (
    "robotics",
    "control_systems",
    "electronics",
    "mechanical_engineering",
    "sensors",
    "embedded_systems",
)
TOPIC_COLORS: Dict[str, str] = {
    "robotics": "violet",
    "control_systems": "blue",
    "electronics": "orange",
    "mechanical_engineering": "gray",
    "sensors": "green",
    "embedded_systems": "yellow",
}
ALL_TOPICS_LABEL = "All topics"

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


DB_READY = "ready"
DB_MISSING = "missing"
DB_UNUSABLE = "unusable"


@dataclass(frozen=True)
class DatabaseStatus:
    """The UI's view of the SQLite file that can rebuild the index."""

    state: str
    page_count: int = 0
    detail: str = ""


@dataclass(frozen=True)
class SearchSnapshot:
    """One completed search, retained only for the current browser session."""

    query: str
    results: Tuple[SearchResult, ...]
    elapsed_ms: float
    limit: int
    topic: Optional[str] = None


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


def execute_search(
    engine: SearchEngine,
    query: str,
    limit: int,
    topic: Optional[str] = None,
) -> SearchSnapshot:
    """Runs exactly one local BM25F search and records its wall-clock time."""
    effective_limit = clamp_limit(limit)
    started = time.perf_counter()
    results = engine.search(query_text=query, limit=effective_limit, topic=topic)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return SearchSnapshot(
        query=query,
        results=tuple(results),
        elapsed_ms=elapsed_ms,
        limit=effective_limit,
        topic=topic,
    )


def inspect_database(path: str | Path) -> DatabaseStatus:
    """Classifies the SQLite file that the indexer would read.

    A file existing is not proof that an index can be rebuilt: `data/pages.db`
    was a 0-byte file with no `pages` table, which the indexer rejects. The file
    is opened read-only because the app never writes to it.
    """
    database = Path(path)
    if not database.is_file():
        return DatabaseStatus(DB_MISSING)
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            has_pages = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pages'"
            ).fetchone()
            if has_pages is None:
                return DatabaseStatus(
                    DB_UNUSABLE, detail="the file has no 'pages' table"
                )
            row = connection.execute("SELECT COUNT(*) FROM pages").fetchone()
            return DatabaseStatus(DB_READY, page_count=int(row[0]) if row else 0)
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return DatabaseStatus(DB_UNUSABLE, detail=f"{type(exc).__name__}: {exc}")


def indexer_shell() -> str:
    """Names the shell whose quoting the rebuild command is written for."""
    return "powershell" if os.name == "nt" else "bash"


def build_indexer_command(
    db_path: str | Path | None = None, index_dir: str | Path | None = None
) -> str:
    """Builds a copy-pasteable command for rebuilding the index.

    The interpreter is the one running this app, so the command stays correct in
    a local virtual environment and in a hosted deployment instead of naming a
    Windows-only `.venv\\Scripts` path.
    """
    database = Path(db_path or settings.DB_PATH)
    index = Path(index_dir or settings.INDEX_DIR)
    interpreter = sys.executable or "python"
    return (
        f'"{interpreter}" -m src.indexer '
        f'--db "{database}" --index-dir "{index}"'
    )


def topic_options(topic_counts: Dict[str, int]) -> List[Tuple[str, Optional[str]]]:
    """Returns the topic filter choices the index can actually answer.

    Only topics with at least one indexed document are offered. A pill that
    filtered to nothing would be decorative, and the brief for this stage was
    explicit that filters must operate on real indexed metadata.
    """
    options: List[Tuple[str, Optional[str]]] = [(ALL_TOPICS_LABEL, None)]
    for slug in TOPIC_ORDER:
        if topic_counts.get(slug, 0) > 0:
            options.append((f"{topic_label(slug)} ({topic_counts[slug]})", slug))
    return options


def collection_summary(
    document_count: int,
    domain_counts: Dict[str, int],
    topic_counts: Dict[str, int],
) -> str:
    """Builds the compact one-line statistics caption."""
    sources = len(domain_counts)
    topics = len(topic_counts)
    return (
        f"{document_count} indexed document(s) · {sources} source site(s) · "
        f"{topics} topic(s) with matches"
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


# Streamlit's theme (navy / white / teal) is set in .streamlit/config.toml. This
# stylesheet only adds what a theme cannot express: touch-target sizes, wrapping
# of long URLs and paths, and a tighter phone layout.
MOBILE_CSS = """
<style>
.block-container {
    max-width: 1080px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
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
            "Build it from the SQLite database that holds the crawled pages "
            "(the configured path is shown in the sidebar):"
        )
        st.code(build_indexer_command(), language=indexer_shell())
        st.info(
            "Pass `--db` if the pages live in another database. The shipped index "
            "was built from `data/seeds_check.db`. This app never crawls the web "
            "or creates an index automatically."
        )
    elif status.state == INDEX_EMPTY:
        st.warning("The search index exists but contains no documents.")
        st.write("Rebuild it from a populated SQLite database with:")
        st.code(build_indexer_command(), language=indexer_shell())
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


def _render_collection_statistics(
    status: IndexStatus, domain_counts: Dict[str, int], topic_counts: Dict[str, int]
) -> None:
    """Renders compact source and topic statistics inside the sidebar."""
    st.subheader("Collection")
    if status.state == INDEX_READY:
        st.metric("Indexed documents", status.document_count)
    elif status.state == INDEX_EMPTY:
        st.metric("Indexed documents", 0)
        st.caption("The index exists but is empty.")
    else:
        st.metric("Indexed documents", "Unavailable")

    if domain_counts:
        st.caption("Sources")
        for domain, count in sorted(
            domain_counts.items(), key=lambda item: (-item[1], item[0])
        ):
            st.markdown(f"- {escape_markdown(domain)} — {count}")

    if topic_counts:
        st.caption("Topics")
        for slug in TOPIC_ORDER:
            count = topic_counts.get(slug, 0)
            if count:
                st.markdown(f"- {escape_markdown(topic_label(slug))} — {count}")


def _render_sidebar(status: IndexStatus) -> None:
    """Renders project context, corpus statistics, and connection controls."""
    db_status = inspect_database(settings.DB_PATH)
    domain_counts = st.session_state.get("domain_counts", {})
    topic_counts = st.session_state.get("topic_counts", {})

    with st.sidebar:
        st.subheader(f"About {APP_NAME}")
        st.caption(APP_TAGLINE)
        st.caption(
            "Crawls a small allowlisted set of engineering pages, stores them in "
            "SQLite, indexes them with Whoosh and ranks local results with BM25F."
        )

        st.divider()
        _render_collection_statistics(status, domain_counts, topic_counts)

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

        with st.expander("Setup details"):
            st.caption("Whoosh index directory")
            st.code(str(settings.INDEX_DIR), language=None)
            st.caption("SQLite database (used only to rebuild the index)")
            st.code(str(settings.DB_PATH), language=None)
            if db_status.state == DB_READY:
                st.caption(
                    f"{db_status.page_count} stored page record(s) available to "
                    "rebuild the index."
                )
            elif db_status.state == DB_MISSING:
                st.info(
                    "The configured database file is not present. Searching the "
                    "existing index still works; rebuilding it needs a valid database."
                )
            else:
                st.info(
                    "The configured database file cannot rebuild the index "
                    f"({db_status.detail or 'it is not a populated crawl database'}). "
                    "Searching the existing index still works."
                )

        with st.expander("Sources and licensing"):
            st.caption(
                "Every source is crawled only after its robots.txt permits this "
                "User-Agent and with the per-domain delay it declares. Page content "
                "belongs to the original authors and is linked, not reproduced."
            )

        st.caption(
            "Local search only: no external search API, web crawl, or index "
            "rebuild happens when you submit a query."
        )


def format_result_meta(result: SearchResult) -> str:
    """Builds the one-line domain and relevance score shown under a title."""
    domain = escape_markdown(result.domain or "unknown domain")
    return f"{domain} · Relevance score (BM25F): {result.score:.3f}"


def _render_result_topics(result: SearchResult) -> None:
    """Shows the topic labels the indexer assigned to this document."""
    if not result.topics:
        return
    # A wrapping row of badges stays on one line on a phone and never scrolls
    # sideways. Labels are a fixed vocabulary, not crawled text.
    with st.container(horizontal=True, wrap=True, gap="small"):
        for slug in result.topics:
            st.badge(
                topic_label(slug),
                color=TOPIC_COLORS.get(slug, "blue"),
            )


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
        _render_result_topics(result)
        st.markdown(snippet)

        url = safe_http_url(result.url)
        if url:
            # Full-width link keeps the tap target large on a touchscreen.
            st.link_button("Open original page", url, width="stretch")
            st.caption(escape_markdown(url))
        else:
            st.warning("This result has an invalid URL and cannot be opened.")


def _active_topic_label(topic: Optional[str]) -> str:
    """Returns the display name of the active topic filter."""
    return topic_label(topic) if topic else ALL_TOPICS_LABEL


def _render_search_state(status: IndexStatus) -> None:
    """Shows the current search result, empty state, or search error."""
    if status.state != INDEX_READY:
        _render_index_help(status)
        return

    if st.session_state.get("empty_submitted"):
        st.warning(
            "Please enter a search query before searching. "
            "Try a topic such as `Arduino hardware`, `PID controller`, or `sensor`."
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
            "Start typing above, or tap one of the suggested queries. Results come "
            "only from the pages indexed in this project, so a topic the collection "
            "does not cover will return nothing."
        )
        st.caption(
            "Every result is ranked by the project's own Whoosh BM25F engine, and "
            "each one links back to the original page."
        )
        return

    metric_columns = st.columns(3)
    metric_columns[0].metric("Matching results", len(snapshot.results))
    metric_columns[1].metric("Search time", f"{snapshot.elapsed_ms:.1f} ms")
    metric_columns[2].metric("Indexed documents", status.document_count)

    topic_note = (
        f" Filtered to **{_active_topic_label(snapshot.topic)}**."
        if snapshot.topic
        else ""
    )

    if not snapshot.results:
        st.warning(
            f'No documents matched "{escape_markdown(snapshot.query)}".'
            f"{topic_note}"
        )
        st.write(
            "This does not mean the topic is absent from the internet; it only "
            "means the currently indexed collection has no matching pages. Things "
            "worth trying:"
        )
        st.markdown(
            "- Use broader or alternative terms, such as `motor`, `sensor`, `control` "
            "or `robotics`.\n"
            "- Clear the topic filter to search the whole collection.\n"
            "- Check the sidebar for the topics and sources the index actually covers."
        )
        st.caption(
            f"Searched {status.document_count} indexed document(s) with up to "
            f"{snapshot.limit} results requested."
        )
        return

    st.caption(
        f'Showing up to {snapshot.limit} results for '
        f'"{escape_markdown(snapshot.query)}".{topic_note} '
        "Order and scores come directly from the existing BM25F engine."
    )
    for rank, result in enumerate(snapshot.results, start=1):
        _render_result(result, rank)


def _render_header(status: IndexStatus) -> None:
    """Renders the application identity and the compact statistics line."""
    st.title(APP_HEADING)
    st.write(f"**{APP_NAME}** · {APP_TAGLINE}")
    if status.state == INDEX_READY:
        st.caption(
            collection_summary(
                status.document_count,
                st.session_state.get("domain_counts", {}),
                st.session_state.get("topic_counts", {}),
            )
        )
    st.caption(
        "Local demonstrator · no external search API · no crawling or index "
        "rebuilding during searches"
    )


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

    # Statistics are read once per run and reused for the sidebar and header.
    if status.state == INDEX_READY:
        try:
            st.session_state["topic_counts"] = engine.topic_counts()
            st.session_state["domain_counts"] = engine.domain_counts()
        except Exception:
            logger.exception("Unable to read collection statistics")
            st.session_state["topic_counts"] = {}
            st.session_state["domain_counts"] = {}
    else:
        st.session_state["topic_counts"] = {}
        st.session_state["domain_counts"] = {}

    _render_header(status)

    topic_choices = topic_options(st.session_state.get("topic_counts", {}))

    st.text_input(
        "Search the indexed collection",
        placeholder="Search topics, components, techniques — e.g. Arduino hardware, PID controller",
        key="query_input",
        on_change=_queue_search,
        help=(
            "Press Enter or use the Search button. Leading and trailing "
            "whitespace is trimmed."
        ),
    )

    # On a phone these two columns stack into full-width taps; on a desktop
    # they stay side by side, so both layouts remain usable.
    search_column, limit_column = st.columns([2, 1])
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
                f"Choose between 1 and {MAX_LIMIT} results. Changing this re-runs "
                "the current search. The default is 5."
            ),
        )

    # The topic filter is a real filter: each option carries the number of indexed
    # documents behind it, and selecting one restricts the Whoosh search to pages
    # the indexer labelled with that topic.
    selected_label = st.pills(
        "Topic filter",
        options=[label for label, _slug in topic_choices],
        selection_mode="single",
        default=ALL_TOPICS_LABEL,
        key="topic_filter",
        help=(
            "Restricts results to documents labelled with that topic at index "
            "time. Topics are assigned from each page's own title, text and URL."
        ),
    )
    selected_topic = dict(
        (label, slug) for label, slug in topic_choices
    ).get(selected_label)

    st.caption("Suggested queries (tap one to search):")
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
            with st.spinner("Searching the local index…"):
                try:
                    st.session_state["last_snapshot"] = execute_search(
                        engine, query, result_limit, selected_topic
                    )
                except Exception:
                    logger.exception("Search failed for query %r", query)
                    st.session_state["last_search_error"] = traceback.format_exc()
                    st.session_state.pop("last_snapshot", None)

    # Changing the topic filter or the result limit re-runs the retained query so
    # the visible results always correspond to the controls that are set.
    snapshot: Optional[SearchSnapshot] = st.session_state.get("last_snapshot")
    if (
        snapshot is not None
        and initialization_error is None
        and status.state == INDEX_READY
    ):
        tightened_limit = clamp_limit(result_limit)
        if snapshot.topic != selected_topic or snapshot.limit != tightened_limit:
            with st.spinner("Applying filters…"):
                try:
                    st.session_state["last_snapshot"] = execute_search(
                        engine, snapshot.query, tightened_limit, selected_topic
                    )
                except Exception:
                    logger.exception("Search failed for query %r", snapshot.query)
                    st.session_state["last_search_error"] = traceback.format_exc()
                    st.session_state.pop("last_snapshot", None)

    _render_sidebar(status)

    st.divider()
    _render_search_state(status)


if __name__ == "__main__":
    main()
