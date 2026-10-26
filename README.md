# Mechatronics Search Engine

A university project implementing an end-to-end, full-text web search engine focused on **mechatronics engineering** resources (robotics, PID control, sensors, actuators, embedded systems, PLCs, and automation).

The architecture consists of four strictly decoupled components:
1. **Polite Web Crawler**: Discovers, verifies (robots.txt), downloads, parses, and persists web pages into SQLite.
2. **Whoosh Indexing Engine**: Ingests crawled pages from SQLite into a persistent disk-backed inverted index.
3. **BM25F Search Engine**: Parses multi-word queries, scores title and content matches, and generates highlighted contextual snippets.
4. **Streamlit Web Interface (Stage 3)**: Presents the local search engine in a browser — desktop or phone — with ranked results, corpus statistics, and clear error states.

---

## Safety Model & Constraints

The system is safe by design:
1. **Strict domain allowlist** — Only approved domains (`docs.arduino.cc`, `eng.libretexts.org`) are ever requested.
2. **robots.txt compliance** — `PolitenessManager.can_fetch()` checks robots.txt rules before every request.
3. **Identification & Rate Limiting** — Transparent User-Agent (`MechatronicsUniversityBot/1.0`) with per-host crawl delays (default 2.0s or robots.txt `Crawl-delay`).
4. **Timeouts and size limits** — Requests time out at 5.0s; bodies exceeding 2 MB are aborted.
5. **Decoupled Architecture** — User queries never trigger live HTTP requests; search only operates on the local indexed collection.

---

## Project Layout

```text
app.py                    Streamlit Stage 3 web interface entry point
config/
  settings.py             Central paths, User-Agent, timeouts, rate limits, allowlist
src/
  crawler/
    url_safety.py         URL normalization, boundary validation, asset filtering
    politeness.py         robots.txt parsing and per-host delay enforcement
    fetcher.py            Safe HTTP requests, timeouts, redirects, size guard
    extractor.py          Clean text, title, canonical URL, and link extraction
    crawler.py            Breadth-first search orchestration & CLI
    __main__.py           Crawler CLI entrypoint
  storage/
    models.py             PageRecord and SearchResult dataclasses
    db.py                 SQLite schema and persistence operations
  indexer/
    schema.py             Whoosh schema with title boosting (2.5x) and StemmingAnalyzer
    indexer.py            Batch index builder from SQLite with deduplication & IndexReport
    __main__.py           Indexer CLI entrypoint
  search/
    searcher.py           SearchEngine class & search() function with BM25F scoring
    __main__.py           Search CLI entrypoint
tests/                    Offline test suite (mocked HTTP & temporary disk fixtures)
```

---

## Quickstart & Installation

Ensure you are using Python 3.10+ (tested with Python 3.14):

```powershell
# Activate your virtual environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Install dependencies (if not already installed)
pip install -r requirements.txt
```

---

## Command-Line Usage

### 1. Run the Crawler (Stage 1)
Crawl a small, controlled sample of mechatronics pages from an allowlisted seed:

```powershell
python -m src.crawler --seed https://docs.arduino.cc/learn/ --max-pages 10 --delay 2 --db data/pages.db
```

### 2. Build or Rebuild the Search Index (Stage 2)
Build the persistent Whoosh inverted index directly from the SQLite database:

```powershell
python -m src.indexer --db data/pages.db --index-dir data/whoosh_index
```

*Options:*
- `--db PATH`: Path to SQLite database (default: `data/pages.db`).
- `--index-dir PATH`: Directory for Whoosh index files (default: `data/whoosh_index`).
- `--no-clean`: Appends or updates documents instead of wiping and recreating the index directory.

### 3. Search the Index from the Terminal (Stage 2)
Execute a ranked query against the built index:

```powershell
python -m src.search "PID controller" --limit 5
```

Example queries to try:
- `python -m src.search "stepper motor microstepping"`
- `python -m src.search "rotary encoder position sensor"`
- `python -m src.search "PLC ladder logic automation"`
- `python -m src.search "ultrasonic distance sensor"`

### 4. Launch the Streamlit Web Interface (Stage 3)
Start the browser interface using the project virtual environment:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit prints a local URL, normally `http://localhost:8501`. Open that URL in your browser.

The interface:
- Searches only the existing local Whoosh index; it does not call an external search API.
- Uses the same `SearchEngine.search()` method, BM25F ranking, title boost, and snippets as the CLI.
- Shows matching-result count, search time, and total indexed-document count.
- Handles blank queries, zero results, missing indexes, empty indexes, malformed queries, and search errors.
- Provides a **Refresh index connection** button for use after rebuilding the index while the app is running.
- Never crawls websites or rebuilds the index during a search.
- Lays out for narrow phone screens: touch targets of at least 44 px, long URLs/paths/commands that wrap instead of scrolling sideways, a wrapping example-query chip row, and each result in its own card with a full-width **Open original page** link.
- Starts with the sidebar expanded on a desktop but collapsed on a phone (`initial_sidebar_state="auto"`), so the search form is visible first while statistics and the index controls stay one tap away.
- Keeps the desktop wide layout and all existing functionality.

`streamlit` is already listed in `requirements.txt`; no additional dependency is required for this stage.

---

### 5. Open the App on a Phone over the Same Wi-Fi

Streamlit can serve the page to any device on your own network, so no public hosting or extra code is needed. This section covers local Wi-Fi access only; nothing here exposes the app to the internet.

**Step 1 — Start the app so it listens on the network** (PowerShell, from the project directory):

```powershell
.venv\Scripts\python.exe -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

- `--server.address 0.0.0.0` binds to every network interface instead of `localhost` only. Without it the phone cannot reach the app.
- `--server.headless true` skips auto-opening a browser on the laptop. Drop it if you also want the local browser window.

**Step 2 — Find the laptop's local IPv4 address:**

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike "127.*" } |
  Select-Object InterfaceAlias, IPAddress
```

Read the address next to the Wi-Fi adapter, normally `192.168.x.x` or `10.x.x.x`. The classic `ipconfig` command works too — use the `IPv4 Address` line of the active adapter. Streamlit also prints it at startup as `Network URL`.

**Step 3 — Open the URL on the phone:**

```text
http://<laptop-ipv4>:8501
```

If Streamlit printed `Network URL: http://192.168.1.25:8501`, open exactly that address in the phone browser. Use `http://` (not `https://`) and keep the port.

**Requirements and troubleshooting**

- Both devices must be on the same Wi-Fi network. A guest network, a hotspot you are not sharing, or Wi-Fi "client isolation" / AP isolation will block the connection.
- A corporate VPN on the laptop can also block inbound LAN traffic; disconnect it while testing.
- The laptop must stay awake, and the PowerShell window must stay open while you search.
- **Windows Firewall:** the first launch usually shows a *Windows Defender Firewall has blocked some features* prompt for Python — allow it for **Private** networks. If the phone still cannot connect, the inbound rule is missing. Creating it needs an administrator PowerShell window and changes a system-wide setting, so decide first:

  ```powershell
  # Administrator PowerShell — inbound TCP 8501 on private networks only
  New-NetFirewallRule -DisplayName "Streamlit 8501 (private)" -Direction Inbound `
      -Protocol TCP -LocalPort 8501 -Action Allow -Profile Private
  ```

- Port already in use: start with `--server.port 8502` and use that port in the phone URL.
- Test on the laptop first with `http://localhost:8501`. If that works but the phone cannot connect, the problem is the network or the firewall, not the app.

---

## Configuration

All project paths are centralized in `config/settings.py`:

- `INDEX_DIR` — default `data/whoosh_index`. The Streamlit app and the CLI search both read this index.
- `DB_PATH` — default `data/pages.db`. It is used by the crawler and indexer, and by the UI only when displaying rebuild instructions. Searching an existing index does not require the database.

Both defaults are built from the project root, so they work even if you launch commands from another working directory.

For the verified four-page collection in this project, the index was built from `data/seeds_check.db`. Build or rebuild it with:

```powershell
.venv\Scripts\python.exe -m src.indexer --db data/seeds_check.db --index-dir data/whoosh_index
```

If you crawled your own pages into `data/pages.db`, use that database instead:

```powershell
.venv\Scripts\python.exe -m src.indexer --db data/pages.db --index-dir data/whoosh_index
```

---

## Stage 3 Troubleshooting

**The app says the index is missing.**
The UI reads the index directory from `config/settings.py`. Build it using the indexer command above, then refresh the browser. The missing-index panel also shows the configured paths and an exact indexer command.

**The app says the index is empty.**
The index exists but contains no eligible pages. Make sure the SQLite database has crawled pages with HTTP 200 status and non-empty content, then rebuild the index.

**The app shows a database notice.**
The database is only needed to rebuild the index. Searching an existing index still works. If you want to rebuild, point `--db` at the database you actually crawled.

**The corpus changed but search results did not.**
Rebuild the index, then use the sidebar's **Refresh index connection** button. This closes the cached Whoosh handle so the next request opens the rebuilt index.

**A search raises an error or the index was moved while the app was open.**
Refresh the index connection. If that does not help, stop the app, rebuild the index, and restart Streamlit.

**Port 8501 is already in use.**
Choose another local port:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

**Streamlit is not installed in the virtual environment.**
Install the existing dependency file with the venv interpreter:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**A query returns no results.**
The current collection contains only four pages, so many valid topics are absent. No results means the local index has no matching page; it does not mean the topic does not exist on the internet. Try broader terms or crawl/index more pages in a later stage.

---

## Deploying to Public Hosting (Not Performed)

The app is a local demonstrator and has **not** been deployed or exposed publicly. Publishing it would require deliberate decisions and changes beyond this UI work:

1. **The host must run a long-lived server process with WebSockets.** Streamlit streams its UI over a WebSocket, so the fit is a container or a platform that supports persistent web services (Streamlit Community Cloud, Render/Railway/Fly.io, or your own VM). Serverless functions that scale to zero and cap request duration do not fit.
2. **The start command must bind to the platform's interface and port**, for example `--server.address 0.0.0.0 --server.port $env:PORT --server.headless true`. `requirements.txt` already pins everything the app imports.
3. **The Whoosh index has to exist on the host.** `data/` is gitignored, so a Git-based deploy ships no index and would show the "index is missing" panel. Options: commit a prebuilt index (adjust `.gitignore`), build it during deploy from a committed SQLite database, or mount a volume containing it. Whoosh opens the index directory for reading but writes a `MAIN_WRITELOCK` file there, so the directory must be writable — a read-only image needs a copied working directory or an attached volume.
4. **Keep crawling off the host.** Rebuilding the index should stay an explicit offline step; the app itself never crawls or indexes.
5. **TLS and proxying.** Terminate HTTPS at a reverse proxy (Caddy, nginx, or the platform's TLS) or pass `--server.sslCertFile` / `--server.sslKeyFile`. Keep Streamlit's XSRF/CORS defaults unless a reverse proxy gives you a specific reason to change them.
6. **There is no authentication.** A public URL means anyone can search the collection, and the sidebar displays absolute local paths. Authentication (`st.login`/OIDC, or a proxy's auth) or a private network would be required before exposing it.
7. **No secrets are needed today.** Paths come from `config/settings.py` and the `data/` directory; there are no API keys, so no secret store is required unless authentication is added.
8. **Corpus updates are manual.** The index currently holds four documents; a small instance is enough, but the index must be rebuilt and re-uploaded whenever the crawl changes.

---

## Inverted Index and BM25F Scoring Explained

### What is an Inverted Index?
In a standard database, you look up a document by its ID and read its content (Forward Index).

An **Inverted Index** flips this mapping backwards: for every distinct word, it maintains a list of all documents where that word occurs, along with term frequency and position:
```text
"pid":        [Doc 1 (title, pos 0), Doc 2 (body, pos 14)]
"controller": [Doc 1 (title, pos 1), Doc 5 (body, pos 3)]
"stepper":    [Doc 3 (title, pos 0), Doc 3 (body, pos 2)]
```
When a user searches for `"PID controller"`, the engine looks up `"pid"` and `"controller"` directly in memory and intersects the matching document sets in milliseconds, without having to scan through gigabytes of raw text.

### How BM25F Ranks Results
BM25F (**Best Matching 25 with Field Weighting**) evaluates document relevance based on three fundamental principles:
1. **Term Frequency (TF) with Saturation**: The more times a search term appears in a document, the more relevant it is. Unlike simple term counting, BM25 uses an asymptotic curve: mentioning `"PID"` 5 times increases relevance significantly, but mentioning it 500 times does not make it 100 times more relevant.
2. **Inverse Document Frequency (IDF)**: Rare terms across the collection carry more weight than common terms. In a mechatronics collection, the word `"circuit"` might appear everywhere, whereas `"quadrature"` appears only in encoder documents. Matches on `"quadrature"` therefore score higher.
3. **Document Length Normalization**: Matches in concise documents are scored higher than matches in massive documents to avoid unfairly favoring verbose pages.
4. **Field Weighting (The 'F' in BM25F)**: A match in a document's `<title>` is weighted **2.5x** more heavily than the same match buried in body text.

### Partial-Match Policy

Queries are parsed with the same `StemmingAnalyzer` used at indexing time, then interpreted disjunctively: a document may match any of the analyzed query terms, and BM25F decides how strongly it matches. Two guards keep that flexibility from producing misleading results:

1. **Unknown terms invalidate the query.** If any analyzed query term does not occur anywhere in the indexed collection, search returns an empty list. A query such as `PID controller` therefore does not return Arduino pages that merely contain "controller" when the collection has no PID material at all.
2. **Half-term floor per result.** Each returned document must match at least half (rounded up) of the distinct query terms. A document matching only one incidental word from a long query is not shown.

When no result survives these guards, the CLI prints a clear "No matching mechatronics documents found" message instead of unrelated pages.

---

## Running the Automated Tests

All tests are completely offline and use temporary directories, mocked HTTP sessions, and Streamlit's `AppTest` harness. Run them with the project virtual-environment interpreter:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Current test suite status: **88 passing tests** covering:
- Safe URL normalization, redirect checks, and asset extension filtering.
- robots.txt disallow policies, timeout handling, and crawl delay enforcement.
- HTML content extraction, visible text cleaning, and canonical URL handling.
- SQLite persistence, deduplication, and crawl logging.
- Whoosh schema validation, batch building, duplicate prevention, and rebuilds.
- Title vs. body BM25F ranking, positive scores, partial-match policy, absent technical terms, HTML-free snippets, empty/malformed queries, and Windows resource cleanup.
- Streamlit startup, connection to the existing index, ranking parity with the CLI, zero-result and blank-query states, missing/empty indexes, malformed queries, handled search exceptions, and refreshing a rebuilt index connection.
- Mobile layout wiring: the domain/relevance-score line for each result (including escaping of untrusted titles and domains), the wrapping example-query buttons still triggering a search, results exposing HTTP(S) tap targets, and the sidebar statistics and controls staying reachable.

---

## Module Reference

### `src/indexer/schema.py`
Defines the document structure in Whoosh:
- `url`: Unique document identifier (`ID(stored=True, unique=True)`).
- `domain`: Host domain (`ID(stored=True)`).
- `title`: Page title, indexed with `StemmingAnalyzer` and given a `field_boost=2.5`.
- `content`: Page body text, indexed with `StemmingAnalyzer` for morphological root matching (e.g. matching "controllers" to "control").
- `crawled_at`: Timestamp metadata (`STORED`).

### `src/indexer/indexer.py`
- `SearchIndexer.build_from_database(db_manager, clean=True)`: Loads records via `get_all_pages()`, filters out error pages or empty text, writes documents to Whoosh, and returns an `IndexReport(indexed, skipped, failed)`.
- Supports atomic rebuilds: deleting the index directory and running the rebuild reconstructs the exact same index without needing network access.

### `src/search/searcher.py`
- `SearchEngine(index_dir)`: Opens index with `BM25F(B=0.75, K1=1.2)` weighting.
- `search(query_text, limit=10)`: Parses user query using `MultifieldParser(["title", "content"])`, boosts title matches, applies the partial-match policy above, converts `hit.highlights()` output into plain terminal text, and safely closes searchers and index handles.
- `document_count()`: Read-only count of indexed documents used by the Stage 3 statistics panel.
- Gracefully returns `[]` on blank queries, queries with terms absent from the whole collection, non-matching terms, or empty indexes.

### `app.py`
- Thin Streamlit presentation layer over the existing `SearchEngine`; it contains no second ranking algorithm and no crawler/indexer calls.
- Caches one `SearchEngine` resource per configured index path and exposes a refresh action for rebuilt indexes.
- Renders results through plain-text-safe Streamlit components and validates links as HTTP(S) before making them clickable.
- Responsive by construction: `MOBILE_CSS` holds the phone styles, the example queries sit in a wrapping chip row, and each result is a card whose link button stretches to full width on a touchscreen.
- `format_result_meta(result)` builds the escaped `domain · Relevance score (BM25F)` line, so the displayed metadata is unit-testable without a browser.

---

## Known Limitations

- **Local and Unauthenticated**: the interface has no login and is meant for a trusted local network; do not expose it publicly (see the deployment notes above).
- **Mobile Styling Tied to Streamlit Internals**: the narrow-screen rules target Streamlit DOM test IDs such as `stButton`, `stLinkButton` and `stTextInput`. A future Streamlit upgrade could rename them, in which case the app still works but loses the touch-target and wrapping polish.
- **No Live Crawling on Search**: Searching only queries the local disk index; new pages must be crawled and indexed separately.
- **No Semantic/Vector Search**: Search is lexical and morphological (BM25F + stemming); synonyms not explicitly present in text require user query reformulation.
- **Small Local Corpus**: The verified index currently contains four pages, so many legitimate topics return no results. Additional coverage requires crawling and indexing more pages in a later stage.
- **Cached Index Handle**: If the index is rebuilt while Streamlit is running, use the sidebar refresh action so the next search opens the new index generation.
