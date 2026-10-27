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
data/
  seeds_check.db          Verified four-page crawl (committed) - the indexer's source
  whoosh_index/           Prebuilt Whoosh index (committed) - what the app searches
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
python -m src.crawler --seed https://docs.arduino.cc/learn/ --max-pages 10 --delay 2 --db data/seeds_check.db
```

### 2. Build or Rebuild the Search Index (Stage 2)
Build the persistent Whoosh inverted index directly from the SQLite database:

```powershell
python -m src.indexer --db data/seeds_check.db --index-dir data/whoosh_index
```

*Options:*
- `--db PATH`: Path to SQLite database (default: `data/seeds_check.db`).
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
- `DB_PATH` — default `data/seeds_check.db`. It is used by the crawler and indexer, and by the UI only when displaying rebuild instructions. Searching an existing index does not require the database.

Both defaults are built from the project root, so they work even if you launch commands from another working directory.

`data/seeds_check.db` is the verified corpus (four pages, all HTTP 200) and the database the shipped index was built from. `data/pages.db` is a 0-byte leftover from an early crawl attempt: it has no `pages` table, so the indexer would fail with `no such table: pages` if it were treated as the corpus. It is still on disk but is no longer referenced by any default, is excluded from git, and the sidebar now warns when the configured database is present but unusable.

To index a different collection, crawl into your own file and pass it explicitly:

```powershell
.venv\Scripts\python.exe -m src.crawler --seed https://docs.arduino.cc/learn/ --max-pages 10 --db data/my_crawl.db
.venv\Scripts\python.exe -m src.indexer --db data/my_crawl.db --index-dir data/whoosh_index
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

## Deploying to Streamlit Community Cloud

This repository is prepared for Streamlit Community Cloud but **has not been deployed or published**. Nothing below has been carried out: the repository is not on GitHub, its visibility has not been changed, and no app exists yet. The steps are for you to run when you decide to publish.

### What was changed so the app can run on a host

| Blocker | Resolution |
|---|---|
| All of `data/` was gitignored, so a Git deploy shipped no index | `.gitignore` now ships `data/whoosh_index/` and `data/seeds_check.db` and still ignores scratch files, `.venv`, caches, secrets and Whoosh write locks |
| The search/indexer modules (`src/search/`, `src/indexer/`, parts of `src/crawler/`) were untracked | Every module `app.py` imports is now tracked |
| The default database was the empty `data/pages.db` | `DB_PATH` now points at the verified `data/seeds_check.db` |
| The rebuild command named a Windows-only `.venv\Scripts\python.exe` | It uses the interpreter running the app, so it is correct on Windows and in the container |
| A 0-byte database passed the "file exists" check | The sidebar classifies the database as ready / missing / unusable instead of trusting mere existence |

Paths are computed from `config/settings.py`'s own location, not the working directory, so `INDEX_DIR` resolves to `<repo>/data/whoosh_index` on the host exactly as it does on your laptop. No absolute paths, environment variables or secrets are required.

Sizes: the index is about 170 KB and the database about 56 KB, far below GitHub's per-file warning threshold and any practical repository limit.

### Step 1 — Put the repository on GitHub (your action)

Community Cloud deploys from a GitHub repository. Create an empty repository on GitHub, then from the project directory:

```powershell
git remote add origin https://github.com/<your-account>/<repository>.git
git push -u origin master
```

For the free Community Cloud tier the repository normally has to be **public**. That is a visibility decision, so it is yours to make; this project contains only four publicly crawled pages and no credentials.

### Step 2 — Create the app

1. Sign in at <https://share.streamlit.io> with the same GitHub account (authorise Streamlit for that repository if asked).
2. Choose **Create app** / **New app** → *Deploy a public app from GitHub*. Button labels differ slightly between releases.
3. Fill in:
   - **Repository:** `<your-account>/<repository>`
   - **Branch:** `master`
   - **Main file path:** `app.py`
4. Open **Advanced settings** and choose a Python version that satisfies the pins in `requirements.txt` (`pandas`, `numpy`, `pyarrow` need a recent interpreter — 3.12 or 3.13 is a safe choice). There are no secrets to add, and no `.streamlit/secrets.toml` is needed.
5. Press **Deploy**. The first build installs `requirements.txt` and takes a few minutes.

### Step 3 — Check it

The app is served at `https://<app-name>.streamlit.app` and works on a phone with no extra configuration. After the first load, confirm:

- the sidebar reports **Indexed documents: 4**, so the committed index was found and opened;
- `Arduino hardware` returns 2 results, `sensor` 1, `control` 2, `stepper motor` 1;
- a blank query shows the "Please enter a search query" warning and `PID controller` shows the no-results message.

If the page shows *"The search index is missing"*, the index was not committed or the working directory differs from the repository root; check `git ls-files data/` before redeploying.

### Updating the corpus later

The host's filesystem is ephemeral, so the index cannot be rebuilt inside the running app. Rebuild locally, commit, and push; Community Cloud redeploys the app automatically on each push:

```powershell
.venv\Scripts\python.exe -m src.crawler --seed https://docs.arduino.cc/learn/ --max-pages 10 --db data/seeds_check.db
.venv\Scripts\python.exe -m src.indexer --db data/seeds_check.db --index-dir data/whoosh_index
git add data/seeds_check.db data/whoosh_index
git commit -m "Refresh the indexed corpus"
git push
```

Crawling never happens on the host: the app only reads the index that was committed.

### Remaining considerations before you make it public

1. **There is no authentication.** Anyone with the link can search, and the sidebar shows the container's absolute index and database paths. That exposes no secret, but if you need access control, add `st.login()` (OIDC) or put the app behind a proxy that authenticates.
2. **The app sleeps when idle.** Community Cloud suspends inactive apps and wakes them on the next visit, so the first load after a pause is slow. This is normal and needs no code change.
3. **The corpus is fixed at deploy time.** With four pages, most topics return no results until you crawl and index more pages.
4. **Whoosh is pure Python and single-node.** That suits a four-document demonstrator; it is not a design for a large, concurrently written corpus. Nothing here writes to the index at runtime, so the platform's read-only usage of the committed files is fine.
5. **Keep the Streamlit defaults.** XSRF/CORS protection and WebSocket handling are provided by the platform; do not disable them without a specific reason.

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

Current test suite status: **92 passing tests** covering:
- Safe URL normalization, redirect checks, and asset extension filtering.
- robots.txt disallow policies, timeout handling, and crawl delay enforcement.
- HTML content extraction, visible text cleaning, and canonical URL handling.
- SQLite persistence, deduplication, and crawl logging.
- Whoosh schema validation, batch building, duplicate prevention, and rebuilds.
- Title vs. body BM25F ranking, positive scores, partial-match policy, absent technical terms, HTML-free snippets, empty/malformed queries, and Windows resource cleanup.
- Streamlit startup, connection to the existing index, ranking parity with the CLI, zero-result and blank-query states, missing/empty indexes, malformed queries, handled search exceptions, and refreshing a rebuilt index connection.
- Mobile layout wiring: the domain/relevance-score line for each result (including escaping of untrusted titles and domains), the wrapping example-query buttons still triggering a search, results exposing HTTP(S) tap targets, and the sidebar statistics and controls staying reachable.
- Deployment readiness: the committed index and database answer the four example queries exactly as expected, the rebuild command names the running interpreter and configured paths, and the sidebar distinguishes a usable database from a missing one and from a file that cannot rebuild the index.

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

- **Unauthenticated**: the interface has no login. On a local network that is fine; a public deployment means anyone with the link can search, so add authentication first if the collection should be private (see the deployment section above).
- **Mobile Styling Tied to Streamlit Internals**: the narrow-screen rules target Streamlit DOM test IDs such as `stButton`, `stLinkButton` and `stTextInput`. A future Streamlit upgrade could rename them, in which case the app still works but loses the touch-target and wrapping polish.
- **No Live Crawling on Search**: Searching only queries the local disk index; new pages must be crawled and indexed separately.
- **No Semantic/Vector Search**: Search is lexical and morphological (BM25F + stemming); synonyms not explicitly present in text require user query reformulation.
- **Small Local Corpus**: The verified index currently contains four pages, so many legitimate topics return no results. Additional coverage requires crawling and indexing more pages in a later stage.
- **Cached Index Handle**: If the index is rebuilt while Streamlit is running, use the sidebar refresh action so the next search opens the new index generation.
