# MechaSearch — Mechatronics Knowledge Hub

A university project implementing an end-to-end, full-text web search engine for **mechatronics engineering** resources: robotics, control systems, electronics, mechanical engineering, sensors and embedded systems.

The architecture consists of four strictly decoupled components:
1. **Polite Web Crawler**: Discovers, verifies (robots.txt), downloads, parses, and persists web pages into SQLite.
2. **Whoosh Indexing Engine**: Ingests crawled pages from SQLite into a persistent disk-backed inverted index, and derives a topic label for each page.
3. **BM25F Search Engine**: Parses multi-word queries, scores title and content matches, generates highlighted contextual snippets, and supports topic filtering.
4. **MechaSearch Streamlit Interface**: Presents the local search engine in a browser — desktop or phone — with a topic filter, ranked result cards, corpus statistics and clear empty/loading/no-result/error states.

The app is live at <https://level500searchengine-u4q752dkog9e43lnwjjfmg.streamlit.app/>.

---

## Safety Model & Constraints

The system is safe by design:
1. **Strict domain allowlist** — Only the five approved domains in `config/settings.py` (`docs.arduino.cc`, `eng.libretexts.org`, `ocw.mit.edu`, `howtomechatronics.com`, `en.wikibooks.org`) are ever requested. Every one was checked against its own `robots.txt` before being added.
2. **robots.txt compliance** — `PolitenessManager.can_fetch()` checks robots.txt rules before every request.
3. **Identification & Rate Limiting** — Transparent User-Agent (`MechatronicsUniversityBot/1.0`) with per-host crawl delays (default 2.0s or robots.txt `Crawl-delay`).
4. **Timeouts and size limits** — Requests time out at 5.0s; bodies exceeding 2 MB are aborted.
5. **Decoupled Architecture** — User queries never trigger live HTTP requests; search only operates on the local indexed collection.

---

## Project Layout

```text
app.py                    MechaSearch Streamlit interface entry point
.streamlit/
  config.toml             Committed navy/white/teal theme (links, fonts, CORS/XSRF defaults)
config/
  settings.py             Central paths, User-Agent, timeouts, rate limits, allowlist, seeds
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
    schema.py             Whoosh schema with title boosting (2.5x), StemmingAnalyzer and topics
    topics.py             Deterministic topic classifier (rule table for the six topics)
    indexer.py            Batch index builder from SQLite with deduplication & IndexReport
    __main__.py           Indexer CLI entrypoint
  search/
    searcher.py           SearchEngine class & search() function with BM25F scoring + topic filter
    __main__.py           Search CLI entrypoint
data/
  seeds_check.db          Verified 65-page crawl (committed) - the indexer's source
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

Repeating no `--seed` argument crawls the curated multi-discipline list in `config/settings.py` (see *Sources, Crawl Policy and Topic Labels*). The exact commands that produced the committed corpus are in *Rebuilding the Corpus*.

Useful flags:

| Flag | Purpose |
|---|---|
| `--seed URL` | Seed page; repeat for several. Must be on an allowlisted domain. |
| `--max-pages N` | Ceiling on fetch **attempts** (not only successes). |
| `--max-depth D` | Link hops from a seed. `0` fetches exactly the seeds and follows nothing. |
| `--timeout S` | Per-request timeout. Raise it for large pages on a slow connection. |
| `--delay S` | Default seconds between requests to one host; robots.txt `Crawl-delay` wins if it declares one. |

Run one domain per invocation when you want per-domain failure reporting, because the crawler never mixes a host's delay budget with another's.

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

### 4. Launch the MechaSearch Web Interface
Start the browser interface using the project virtual environment:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit prints a local URL, normally `http://localhost:8501`. Open that URL in your browser.

The interface:

* **Identity and layout.** Titled **Mechatronics Knowledge Hub** under the **MechaSearch** name, with a navy, white and teal theme set by the committed `.streamlit/config.toml`.
* **Search controls.** A large touch-friendly search field, a primary **Search** button, a result-count selector, and a row of tappable suggested queries.
* **Topic filter.** A row of `st.pills` for Robotics, Control Systems, Electronics, Mechanical Engineering, Sensors and Embedded Systems. Each option shows how many indexed documents sit behind it, a topic with no documents is never offered, and selecting one restricts the Whoosh search for real — it must never be a decorative control.
* **Result cards.** Each result is a bordered card with its rank and title, an escaped `domain · Relevance score (BM25F)` line, topic badges, a snippet, and a full-width **Open original page** link that is validated as HTTP(S) before it becomes clickable.
* **Compact statistics.** The header shows documents, source sites and topics; the sidebar breaks the collection down by source and by topic.
* **States.** Distinct empty, loading (`st.spinner`), no-result, blank-query, missing-index, empty-index and search-error states. A no-result search explains that the topic may be outside the indexed collection and suggests clearing the topic filter.
* **Sidebar.** Short project description, collection statistics, **Refresh index connection** and **Clear search** buttons, plus collapsible **Setup details** and **Sources and licensing** sections, so it stays useful without dominating the page.
* **Behaviour.** It searches only the local Whoosh index, never calls an external search API, never crawls, and never rebuilds the index during a query. Ranking, snippets and title boosting are the same `SearchEngine.search()` used by the CLI.
* **Phone layout.** Touch targets of at least 44 px, long URLs/paths/commands that wrap instead of scrolling sideways, a wrapping suggested-query chip row, and `initial_sidebar_state="auto"` so the sidebar is expanded on a desktop but collapsed on a phone.

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

## Sources, Crawl Policy and Topic Labels

### The five indexed sources

| Source | robots.txt decision | Documents | Role in the collection |
|---|---|---|---|
| `docs.arduino.cc` | `Allow: /` | 10 | Embedded systems, hardware and kits |
| `eng.libretexts.org` | Allow, with `Crawl-delay: 5` | 12 | Control theory, robotics, electronics, mechanics textbooks |
| `ocw.mit.edu` | `Allow: /` | 12 | University courses: mechatronics, control, robotics, circuits |
| `howtomechatronics.com` | `Disallow:` (empty = allow all) | 15 | Applied motor control, sensors and actuator tutorials |
| `en.wikibooks.org` | Allow, except `/w/`, `/api/`, `/wiki/Special:*` | 16 | Open textbooks: control systems, robotics, embedded systems |

**MathWorks (`www.mathworks.com/help/`) was evaluated and is not included.** Its `/robots.txt` returns HTTP 403 and the help pages themselves return 403 to this User-Agent, so `PolitenessManager` fails closed and no MathWorks page can be fetched. The permitted alternatives used instead for control-systems material are **MIT OpenCourseWare** (`16.06 Principles of Automatic Control`, `16.30 Feedback Control Systems`), **LibreTexts** (`Introduction to Control Systems (Iqbal)`, `Book: Dynamic Systems and Control`), and **Wikibooks** (`Control Systems` book, including `Controllers and Compensators`, `Bode Plots`, `Root Locus`).

### How the crawl is kept small and intentional

* **Depth 0 with a curated seed list.** The committed corpus was produced with `--max-depth 0`, so the crawler fetches exactly the hand-verified seeds and follows no discovered links. No login pages, search-result pages or endless navigation chains can enter the collection that way.
* **Every seed was verified before being added.** A seed was only written into `config/settings.py` after it returned HTTP 200 *and* parsed to non-empty text.
* **Wikibooks `Print_version`, `All_Versions` and `All_pages` pages are deliberately excluded**, because each one duplicates an entire book as a single document.
* **A known crawl trap is documented rather than hidden.** `docs.arduino.cc` serves most of `/learn/` as a client-rendered shell: 15 of 19 tested `/learn/` subpages (including `stepper-motors`, `transistor-motor-control`, `spi`) return HTTP 200 but contain **no server-rendered text**, so `is_eligible_page()` would skip them. Only `/learn/`, `/hardware/` and the hardware product pages carry real text, so those are the Arduino seeds used.

### Topic labels

`src/indexer/topics.py` assigns each page up to three labels from a fixed vocabulary: **Robotics, Control Systems, Electronics, Mechanical Engineering, Sensors, Embedded Systems**. The rule is explicit and re-runnable:

```text
score = 2 × (distinct keywords found in the title)
      + 1 × (distinct keywords found in the body)
      + 2 × (matching URL path hints)
```

A topic is assigned only when its score reaches **3**, and the three highest-scoring topics are kept (ties broken by label). Counting *distinct* keywords rather than raw occurrences stops one long page from dominating a topic. Nothing is learned at runtime, so re-indexing the same pages always produces the same labels.

The labels are stored in a dedicated Whoosh `topics` field. That field is **not** in the query parser's field list, so a topic can never contribute to a BM25F score; filtering uses Whoosh's `filter=`, which removes non-matching documents without re-scoring the ones it keeps. An unrecognised topic slug returns no results instead of silently ignoring the filter.

Coverage of the committed corpus, read from the index itself:

| Topic | Documents |
|---|---|
| Robotics | 12 |
| Control Systems | 18 |
| Electronics | 25 |
| Mechanical Engineering | 23 |
| Sensors | 9 |
| Embedded Systems | 25 |

63 of the 65 documents receive at least one label. The two that do not are LibreTexts *index* pages (`/Bookshelves/Electrical_Engineering` and `/Bookshelves/Electrical_Engineering/Signal_Processing_and_Modeling`) whose extracted text is almost entirely site navigation chrome, so the classifier abstains instead of guessing — the honest outcome, and it is reported in the sidebar rather than hidden.

---

## Rebuilding the Corpus

These are the exact commands that produced the committed database and index. Each domain is crawled separately at depth 0 with a conservative page ceiling; re-running one is harmless because `pages.url` is the primary key and existing rows are ignored.

```powershell
# 1. Crawl each allowlisted source (one invocation per domain)
.venv\Scripts\python.exe -m src.crawler --db data/seeds_check.db --max-depth 0 --timeout 25 --delay 2 --max-pages 15 `
  --seed https://docs.arduino.cc/learn/ `
  --seed https://docs.arduino.cc/hardware/ `
  --seed https://docs.arduino.cc/hardware/plc-starter-kit/ `
  --seed https://docs.arduino.cc/hardware/opta-lite/ `
  --seed https://docs.arduino.cc/hardware/sensor-kit/ `
  --seed https://docs.arduino.cc/hardware/automation-bot-bundle/

# ... repeat with the remaining seeds in config.settings.SEED_URLS.
# Crawling all of config.settings.SEED_URLS in one run also works:
.venv\Scripts\python.exe -m src.crawler --db data/seeds_check.db --max-depth 0 --timeout 45

# 2. Rebuild the index from the database
.venv\Scripts\python.exe -m src.indexer --db data/seeds_check.db --index-dir data/whoosh_index

# 3. Check the collection
.venv\Scripts\python.exe -m src.search "stepper motor" --limit 5
```

Expected crawler output per domain is a `Fetched` / `Saved` / `Errors` / `Blocked` summary. A `Blocked by robots.txt` count equal to the number of seeds means the robots.txt request itself failed for that run; the policy fails closed, so simply re-run that domain.

---

## Configuration

All project paths are centralized in `config/settings.py`:

- `INDEX_DIR` — default `data/whoosh_index`. The Streamlit app and the CLI search both read this index.
- `DB_PATH` — default `data/seeds_check.db`. It is used by the crawler and indexer, and by the UI only when displaying rebuild instructions. Searching an existing index does not require the database.

Both defaults are built from the project root, so they work even if you launch commands from another working directory.

`data/seeds_check.db` is the verified corpus (**65 pages** across the five allowlisted sources, all HTTP 200) and the database the shipped index was built from. It contains the original four-page collection plus 61 pages added for the multi-discipline corpus; nothing was deleted.

`data/pages.db` is a 0-byte leftover from an early crawl attempt: it has no `pages` table, so the indexer would fail with `no such table: pages` if it were treated as the corpus. It is still on disk but is no longer referenced by any default, is excluded from git, and the sidebar now warns when the configured database is present but unusable.

`ALLOWED_DOMAINS` and `SEED_URLS` live in the same file. Adding a domain requires verifying its `robots.txt` first, and adding a seed requires confirming it returns HTTP 200 *and* parses to real text.

To index a different collection, crawl into your own file and pass it explicitly:

```powershell
.venv\Scripts\python.exe -m src.crawler --seed https://docs.arduino.cc/learn/ --max-pages 10 --db data/my_crawl.db
.venv\Scripts\python.exe -m src.indexer --db data/my_crawl.db --index-dir data/whoosh_index
```

---

## Interface Troubleshooting

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
The collection holds 65 pages from five sources, so plenty of legitimate topics are still absent. The partial-match policy also returns nothing when any query term is missing from the whole collection. No results means the local index has no matching page; it does not mean the topic does not exist on the internet. Try broader terms, clear the topic filter, or check the sidebar for the topics and sources that are actually covered.

**A topic pill is missing.**
The filter only offers topics the index can answer. If *Sensors* is absent, no indexed document carries that label — that is the honest state, not a UI bug. Add sources that cover the topic and rebuild the index.

**The crawler reported `Blocked by robots.txt` for a whole domain.**
The robots.txt request itself failed (a network timeout or reset), and `PolitenessManager` deliberately fails closed, caching "disallow all" for that host for the rest of the run. Confirm the page still loads with `curl`, then re-run that domain. Do not disable the check.

---

## Deploying to Streamlit Community Cloud

The app is already deployed on Streamlit Community Cloud at <https://level500searchengine-u4q752dkog9e43lnwjjfmg.streamlit.app/>, from the `master` branch of `https://github.com/garbacaleb06/level_500_search_engine`. Community Cloud redeploys automatically on every push to that branch, so shipping a corpus or interface change is a matter of committing and pushing. Nothing on the host crawls or writes to the index.

### What was changed so the app can run on a host

| Blocker | Resolution |
|---|---|
| All of `data/` was gitignored, so a Git deploy shipped no index | `.gitignore` now ships `data/whoosh_index/` and `data/seeds_check.db` and still ignores scratch files, `.venv`, caches, secrets and Whoosh write locks |
| The search/indexer modules (`src/search/`, `src/indexer/`, parts of `src/crawler/`) were untracked | Every module `app.py` imports is now tracked |
| The default database was the empty `data/pages.db` | `DB_PATH` now points at the verified `data/seeds_check.db` |
| The rebuild command named a Windows-only `.venv\Scripts\python.exe` | It uses the interpreter running the app, so it is correct on Windows and in the container |
| A 0-byte database passed the "file exists" check | The sidebar classifies the database as ready / missing / unusable instead of trusting mere existence |

Paths are computed from `config/settings.py`'s own location, not the working directory, so `INDEX_DIR` resolves to `<repo>/data/whoosh_index` on the host exactly as it does on your laptop. No absolute paths, environment variables or secrets are required.

Sizes, measured after the corpus expansion: the Whoosh index is about **2.0 MB** (`MAIN_*.seg` 2.06 MB plus a 2.2 KB `_MAIN_1.toc`) and the database about **1.0 MB**. Both are far below GitHub's per-file warning threshold and any practical repository limit, so no Git LFS or other storage workaround is needed. The corpus is deliberately committed as data rather than rebuilt on the host, because the host has no crawler run available; the rebuild commands are in *Rebuilding the Corpus*.

### Step 1 — Push the changes (your action)

The `origin` remote already exists, so redeploying after a local change is:

```powershell
git add app.py README.md config src tests .streamlit data

git commit -m "Redesign the interface and expand the indexed corpus"

git push origin master
```

Streamlit Community Cloud picks up the push and rebuilds the app automatically; there is no separate deploy step. The first load after a redeploy can be slow while the new build installs.

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

After a redeploy, confirm on the live app:

- the header reports **65 indexed document(s) · 5 source site(s) · 6 topic(s)** and the sidebar reports **Indexed documents: 65**, so the committed index was found and opened;
- the topic pills read **Robotics (12)**, **Control Systems (18)**, **Electronics (25)**, **Mechanical Engineering (23)**, **Sensors (9)**, **Embedded Systems (25)**;
- each of the eight representative queries returns results: `Arduino hardware`, `PID controller`, `DC motor control`, `stepper motor`, `robotic arm`, `sensors and actuators`, `control systems`, `mechanical design`;
- filtering `stepper motor` to **Robotics** changes the result set, and filtering to a topic with no matching page returns the no-results state;
- a blank query shows the "Please enter a search query" warning and `quantum astrophysics supercollider` shows the no-results state.

If the page shows *"The search index is missing"*, the index was not committed or the working directory differs from the repository root; check `git ls-files data/` before redeploying.

### Updating the corpus later

The host's filesystem is ephemeral, so the index cannot be rebuilt inside the running app. Rebuild locally, commit, and push; Community Cloud redeploys the app automatically on each push:

```powershell
# Crawl (see "Rebuilding the Corpus" for the full per-domain commands)
.venv\Scripts\python.exe -m src.crawler --db data/seeds_check.db --max-depth 0 --timeout 45

# Rebuild the index, then commit the database *and* the whole index directory
.venv\Scripts\python.exe -m src.indexer --db data/seeds_check.db --index-dir data/whoosh_index
git add -A data
git commit -m "Refresh the indexed corpus"
git push origin master
```

`git add -A data` matters more than it looks: `--index-dir` is rebuilt with `clean=True`, so the previous generation's `MAIN_*.seg` files must be removed from git in the same commit, otherwise both generations would ship. `data/whoosh_index/MAIN_WRITELOCK` is ignored and must never be committed.

Crawling never happens on the host: the app only reads the index that was committed.

After a corpus change, update `SHIPPED_DOCUMENT_COUNT` and `SHIPPED_DOMAIN_COUNTS` in `tests/test_app.py` from the indexer's real output — the test is what stops a stale index from being deployed silently.

### Remaining considerations before you make it public

1. **There is no authentication.** Anyone with the link can search, and the sidebar shows the container's absolute index and database paths. That exposes no secret, but if you need access control, add `st.login()` (OIDC) or put the app behind a proxy that authenticates.
2. **The app sleeps when idle.** Community Cloud suspends inactive apps and wakes them on the next visit, so the first load after a pause is slow. This is normal and needs no code change.
3. **The corpus is fixed at deploy time.** With 65 pages many topics still return no results until more pages are crawled and indexed locally, committed and pushed.
4. **Whoosh is pure Python and single-node.** That suits a 65-document demonstrator; it is not a design for a large, concurrently written corpus. Nothing here writes to the index at runtime, so the platform's read-only usage of the committed files is fine.
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

Current test suite status: **134 passing tests** covering:

- Safe URL normalization, redirect checks, and asset extension filtering.
- robots.txt disallow policies, timeout handling, and crawl delay enforcement.
- HTML content extraction, visible text cleaning, and canonical URL handling.
- SQLite persistence, deduplication, and crawl logging.
- Whoosh schema validation, batch building, duplicate prevention, and rebuilds.
- Title vs. body BM25F ranking, positive scores, partial-match policy, absent technical terms, HTML-free snippets, empty/malformed queries, and Windows resource cleanup.
- **Topic classification** (`tests/test_topics.py`): a representative page per topic, determinism across repeated calls, the documented 3-point threshold, the URL-evidence weight (including a case where it decides a close call), the three-topic ceiling, the ordering rule, the six-label vocabulary, and the guarantee that the `topics` field exists while ranking still only sees `title` and `content`.
- **Topic filtering** (`tests/test_searcher.py`): labels travelling from the index into each `SearchResult`, a filter narrowing results, identical BM25F scores for the documents it keeps, an unknown topic slug returning nothing instead of being ignored, and topic/domain counts matching the index.
- **Topic storage** (`tests/test_indexer.py`): labels written into the Whoosh document, and a page with no clear evidence being counted as unclassified rather than given a wrong label.
- MechaSearch interface: startup and identity, the six documented topic pills, pills offering only topics with indexed documents and only in the documented order, the compact statistics line, a filter changing the visible result set (including down to zero), badges rendering the same vocabulary the indexer wrote, ranking parity with the CLI, zero-result, blank-query, missing-index, empty-index, malformed-query and handled-exception states, and refreshing a rebuilt index connection.
- Mobile layout wiring: the escaped domain/relevance-score line, the wrapping suggested-query buttons triggering a search, results exposing HTTP(S) tap targets, and the sidebar statistics and controls staying reachable.
- **Deployment readiness**: the committed index reports 65 documents over the five expected domains, every one of the six topics has real documents behind it, all eight representative queries return positive-scored results, the shipped index answers a topic-filtered query, and the rebuild command names the running interpreter and configured paths.

---

## Module Reference

### `src/indexer/schema.py`
Defines the document structure in Whoosh:
- `url`: Unique document identifier (`ID(stored=True, unique=True)`).
- `domain`: Host domain (`ID(stored=True)`).
- `title`: Page title, indexed with `StemmingAnalyzer` and given a `field_boost=2.5`.
- `content`: Page body text, indexed with `StemmingAnalyzer` for morphological root matching (e.g. matching "controllers" to "control").
- `crawled_at`: Timestamp metadata (`STORED`).
- `topics`: Comma-separated topic slugs (`KEYWORD(stored=True, commas=True, lowercase=True)`), used only for display and exact filtering and never for scoring.

### `src/indexer/topics.py`
- `TOPIC_LABELS`: the six slugs and their display names, shared by the indexer, the searcher and the UI so the vocabularies cannot drift apart.
- `classify_topics(title, content_text, url)`: returns the topic slugs a page genuinely belongs to, strongest first, or `()` when the page carries no clear evidence.
- `TOPIC_KEYWORDS` / `TOPIC_URL_HINTS`: the auditable rule table; `describe_rules()` prints it.

### `src/indexer/indexer.py`
- `SearchIndexer.build_from_database(db_manager, clean=True)`: Loads records via `get_all_pages()`, filters out error pages or empty text, computes each page's topic labels, writes documents to Whoosh, and returns an `IndexReport(indexed, skipped, failed, total_pages, unclassified)`.
- Supports atomic rebuilds: deleting the index directory and running the rebuild reconstructs the exact same index without needing network access.

### `src/search/searcher.py`
- `SearchEngine(index_dir)`: Opens index with `BM25F(B=0.75, K1=1.2)` weighting.
- `search(query_text, limit=10, topic=None)`: Parses user query using `MultifieldParser(["title", "content"])`, boosts title matches, applies the partial-match policy above, converts `hit.highlights()` output into plain terminal text, attaches the page's topic labels, and safely closes searchers and index handles. `topic` restricts results with a Whoosh filter that excludes documents without re-scoring the ones it keeps.
- `document_count()`, `topic_counts()` and `domain_counts()`: read-only statistics read from the index lexicon; a topic with no documents is omitted rather than reported as zero.
- Gracefully returns `[]` on blank queries, queries with terms absent from the whole collection, non-matching terms, unknown topic slugs, or empty indexes.

### `app.py`
- Thin Streamlit presentation layer over the existing `SearchEngine`; it contains no second ranking algorithm and no crawler/indexer calls.
- Caches one `SearchEngine` resource per configured index path and exposes a refresh action for rebuilt indexes.
- Native components first: `st.pills` for the topic filter, `st.badge` for topic labels, bordered `st.container`s for result cards, `st.link_button` for the result link, `st.spinner` while searching. The committed `.streamlit/config.toml` supplies the colour theme; `MOBILE_CSS` only adds what a theme cannot express (touch-target sizes, wrapping, a tighter phone layout).
- `topic_options(topic_counts)` builds the filter from the index's real counts, so a pill that would return nothing is never rendered.
- Changing the topic filter or the result limit re-runs the retained query, so the visible results always match the controls that are set.
- Renders results through plain-text-safe Streamlit components and validates links as HTTP(S) before making them clickable.
- `format_result_meta(result)` builds the escaped `domain · Relevance score (BM25F)` line, so the displayed metadata is unit-testable without a browser.

---

## Known Limitations

- **Unauthenticated**: the interface has no login. On a local network that is fine; a public deployment means anyone with the link can search, so add authentication first if the collection should be private (see the deployment section above).
- **MathWorks could not be indexed**: `www.mathworks.com` returns HTTP 403 for both `robots.txt` and its help pages, and the crawler fails closed. Control-systems material comes from MIT OpenCourseWare, LibreTexts and Wikibooks instead. Do not work around this by disabling the robots.txt check.
- **Part of the Arduino documentation is unreachable**: most `docs.arduino.cc/learn/` subpages return HTTP 200 but contain no server-rendered text, so they cannot be indexed from the crawler as it stands. Only `/learn/`, `/hardware/` and the hardware product pages contribute text.
- **LibreTexts landing pages carry navigation chrome**: the extracted text of bookshelf and book index pages includes the site's menus and toolbars, which can add incidental term matches. Chapter pages are cleaner. A more selective extractor would improve this.
- **Two documents have no topic label**: the two LibreTexts index pages whose text is almost entirely chrome are reported as unclassified rather than guessed at, so they appear under *All topics* but under no specific topic.
- **Topic labels are rule-based, not learned**: the classifier matches a hand-written keyword table with a fixed 3-point threshold. A page that discusses a topic without using its vocabulary will not be labelled, and the labels will need review if the corpus changes substantially.
- **A single robots.txt failure blocks a whole domain for that run**: the policy fails closed and caches the decision, which is the safe behaviour but means a transient network error costs a domain until the crawl is re-run.
- **The corpus is still small**: 65 documents from five sources, so many legitimate topics return no results. Closing the gap means crawling and indexing more pages.
- **Mobile Styling Tied to Streamlit Internals**: the narrow-screen rules target Streamlit DOM test IDs such as `stButton`, `stLinkButton` and `stTextInput`. A future Streamlit upgrade could rename them, in which case the app still works but loses the touch-target and wrapping polish.
- **No Live Crawling on Search**: Searching only queries the local disk index; new pages must be crawled and indexed separately.
- **No Semantic/Vector Search**: Search is lexical and morphological (BM25F + stemming); synonyms not explicitly present in text require user query reformulation.
- **Cached Index Handle**: If the index is rebuilt while Streamlit is running, use the sidebar refresh action so the next search opens the new index generation.
