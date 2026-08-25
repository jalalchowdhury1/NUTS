# AGENTS.md — NUTS Algo (Live Decision-Tree Visualizer)

> **This is the single source of truth for anyone (human or AI) touching this repo.**
> Read it fully before changing code, deploying, or "fixing" anything. The repo shipped
> with **no docs at all** (only `backend/requirements.txt`), so this file was written by
> reading the code. If something here is wrong, fix *this* file.
>
> **ACCURACY IS THE #1 PRIORITY.** This computes a real trading signal. The RSI unit test
> must pass before any live data is processed (`handle_evaluate` enforces this). Never
> change the RSI/MA math without re-deriving the unit test by hand.

---

## 1. What this is

NUTS Algo is a **live decision-tree visualizer** for a leveraged-ETF trading strategy
(a "Composer-style" symphony). It evaluates three hand-coded decision trees against live
market data and returns, for each, the full traversal (every node, active + inactive,
with live indicator values) so a React flowchart can render exactly which path "fired"
and which conditions were close calls.

Two parts, deployed separately:

- **backend/** — Python **AWS Lambda** (`nuts-visualizer`, `us-east-1`, runtime
  **python3.10**) behind an **API Gateway HTTP API** (`nuts-visualizer-api`). It also runs
  on two EventBridge crons. Source of truth for all data/state is **S3 bucket
  `nuts-algo-data`**.
- **frontend/** — a **Vite + React 18** SPA (`@xyflow/react` + dagre flowcharts), deployed
  on **Vercel** (`framework: vite`, output `dist`, SPA rewrite to `/index.html`). It polls
  the API's `/evaluate` endpoint every 60 min and renders the trees. It reads the API base
  from build-time env var **`VITE_API_URL`** (empty string = same-origin).

GitHub remote: `https://github.com/jalalchowdhury1/NUTS.git` (public, branch `main`).
There is **no CI** — no `.github/` workflows exist. Deploys are manual (see §4).

### The three trees (what each emits)

The strategy is two **selection branches** plus one always-on **portfolio branch**:

1. **Frontrunners** (`trees/frontrunners.py`) — a flat 10-node chain, first TRUE wins.
   Detects RSI extremes (overbought → buy vol hedge UVXY/VIXY; oversold → buy the 3x
   long SOXL/TECL/UPRO). If **no** node fires, it hands off (`result="→ FTLT"`,
   `fired=False`).
2. **FTLT** ("TQQQ For The Long Term", `trees/ftlt.py`) — a binary tree gated on
   `SPY price > SPY MA(200)` (bull/bear regime). **Always evaluated.** It is the *signal
   source* only when Frontrunners did not fire.
3. **BlackSwan** (`trees/blackswan.py`) — gated on `TQQQ RSI(10) > 79` → UVXY, else splits
   on `TQQQ 6d cumulative return < -13%`: huge-vol path (BS logic) vs normal-market path
   (two independent sub-trees **NMA** and **NMB** that vote; agree → that ticker, disagree
   → `"X/Y"` 50/50 split string). **Always evaluated**, `fired=True` always; it is a
   standing portfolio component whenever Frontrunners doesn't fire.

**Final signal logic** (`lambda_function.handle_evaluate`): if Frontrunners fired,
`final_result = frontrunners.result`, `final_source = "frontrunners"`, and FTLT's `fired`
is forced to `False` in the response. Otherwise `final_result = ftlt.result`,
`final_source = "ftlt"`. The frontend additionally shows `ftlt + blackswan` combined in
the header when Frontrunners didn't fire.

---

## 2. Architecture / data flow

```
                       EventBridge crons (us-east-1)
  nuts-compute        cron(5,35 13-20 ? * MON-FRI *)  →  {"action":"compute"}
  nuts-update-prices  cron(0 21   ? * MON-FRI *)      →  {"action":"update_prices"}
            │                                                     │
            ▼                                                     ▼
   ┌─────────────────────────── Lambda: nuts-visualizer ───────────────────────────┐
   │ lambda_handler(event):                                                         │
   │   action=="compute"        → handle_scheduled_compute → handle_evaluate(force) │
   │   action=="update_prices"  → handle_scheduled_update_prices                    │
   │   else (API Gateway HTTP)  → route by path:                                    │
   │      GET /test-rsi   → run_unit_test                                           │
   │      GET /evaluate   → handle_evaluate (cached ≤60min unless ?force=true)      │
   └───────────────────────────────────────────────────────────────────────────────┘
       │ read history                      ▲ read/write cache        ▲ live quote
       ▼                                   │                         │
  data_fetcher.download_all_tickers()  state_manager (S3)      Finnhub → Polygon
       │  (ThreadPool, 10 workers)     cache/latest_evaluation.json  (intraday inject)
       ▼
  data_manager.load_historical(ticker)
       └─ reads s3://nuts-algo-data/historical/{TICKER}_prices.csv
            (seeded once by bootstrap_historical.py; kept fresh by update_prices cron)

  Browser → Vercel SPA → fetch ${VITE_API_URL}/evaluate → API Gateway → Lambda
```

### Request → response shape (`GET /evaluate`)

Returns HTTP 200 with a JSON envelope (serialized with `_NumpyEncoder` so numpy scalars
become plain JSON). Top-level keys:
`cache_hit`, `frontrunners`, `ftlt`, `blackswan`, `final_result`, `final_source`,
`indicators` (a **list** — see §6 gotcha), `data_quality`, `download_errors`,
`unit_test`, plus `_cached_at_utc` and `evaluated_at` (stamped by `state_manager`).
Each tree object: `{fired, result, active_path:[node_ids], nodes:[...]}` (BlackSwan also
adds `sub_results:{bs,nma,nmb}`). Every node carries `id,label,ticker,indicator,window,
operator,threshold,live_value,distance,result,active,close_call,outcome` (leaves set
`is_leaf:true`; MA gates add `display_type:"ma_gate"`, `ma_value`, `price_value`).

### Caching

- `state_manager.write_state` stamps `_cached_at_utc` (UTC ISO) + `evaluated_at` (US/Eastern)
  and writes to **S3** in Lambda, or **`./nuts_cache_local.json`** locally
  (detected via `AWS_LAMBDA_FUNCTION_NAME`).
- `read_state` returns the cache only if younger than `CACHE_TTL_MINUTES = 60`; stale or
  missing → `None` → recompute. The `compute` cron and `?force=true` **bypass** the TTL.

---

## 3. Indicators / math (calculations.py)

- **RSI window for ALL NUTS conditions = 10.** RSI uses **Wilder's Smoothing** (matches
  TradingView/Barchart/ThinkorSwim). Seed = SMA of first `window` gains/losses; then
  `avg = (prev_avg*(window-1) + current)/window`. `avg_down == 0 → RSI = 100`.
- **Unit test is window=9 on a fixed 10-price series → 73.3333** (a seed-only case: 9 diffs
  with window 9 → no smoothing iterations). This is the canonical correctness gate; it does
  **not** mean the strategy uses window 9. `run_unit_test()` powers `/test-rsi` and the
  hard gate in `/evaluate`. The full hand-derivation is in the `run_unit_test` docstring —
  re-derive it if you ever touch `calculate_rsi_sma`.
- `moving_average_price`, `current_price`, `cumulative_return(prices, window_days)`
  (`None` if < window+1 rows), `max_drawdown(prices, window_days)` (`None` if < window
  rows; returns a positive % drawdown).
- `rsi_filter(dict, window)` returns the ticker with the **HIGHEST** RSI (`max`). NOTE the
  in-file section comment says "lowest RSI" and the docstring says "highest" — **the code
  picks the highest** (fixed in commit `e613cbb`). FTLT's B5 uses this to choose between
  SQQQ and TLT. (The "Stubs — implement in Phase 3" comment is also stale: those functions
  are fully implemented.)

### Tree thresholds (single source of truth = each tree's `THRESHOLDS` dict)

- **Frontrunners** RSI(10): SPY>80→UVXY; QQQ>79→VIXY; VTV>79→VIXY; **VOX>84**→VIXY (note
  84, not 79); XLK>79→VIXY; XLP>75→VIXY; XLF>80→VIXY; SOXX<30→SOXL; QQQ<30→TECL;
  SPY<30→UPRO. Else → FTLT.
- **FTLT**: gate SPY vs MA(200). Bull: TQQQ RSI>79→UVXY; else SPXL RSI>80→UVXY; else TQQQ.
  Bear: TQQQ RSI<31→TECL; else SPY RSI<30→UPRO; else TQQQ<MA(20)→rsi_filter(SQQQ,TLT);
  else SQQQ RSI<31→SQQQ; else TQQQ.
- **BlackSwan**: gate TQQQ RSI>79→UVXY. Huge-vol (TQQQ 6d cumret<-13): 1d>+6→UVXY; else
  RSI<32→TQQQ; else TMF maxdd(10)<7→TQQQ; else BIL. Normal market: NMA & NMB vote (full
  branch logic in the file; outcomes are TQQQ/BIL/UVXY/PSQ/URTY).
- `CLOSE_CALL_DISTANCE = 5` everywhere: a node is `close_call` if `abs(distance) <= 5`.

### Ticker universe (data_fetcher.ALL_TICKERS, 22 tickers)

`BIL, BND, IEF, QQQ, SH, SOXX, SOXL, SPY, SPXL, SQQQ, TECL, TLT, TMF, TQQQ, UPRO, UVXY,
VIXY, VOX, VTV, XLF, XLK, XLP`. `MIN_ROWS = 60` (a ticker with fewer usable rows raises and
lands in `download_errors`). **URTY, PSQ, FNGU are *outcome* tickers only** (emitted as
leaf signals / colored in the frontend) — they are **not** fetched or evaluated, so they
need no S3 CSV. (`bootstrap_historical.py` carries its own copy of the same 22-ticker list
— keep the two lists in sync if you add a tradable ticker.)

---

## 4. How to run / deploy / test

### Local dev — backend
Requires AWS creds with read access to `s3://nuts-algo-data` (it reads real history; cache
falls back to a local file). From `backend/`:
```bash
pip install -r requirements.txt
python lambda_function.py /evaluate --force   # runs a full eval, prints JSON
python lambda_function.py /test-rsi           # runs just the RSI unit test
python calculations.py                        # asserts the RSI unit test passes
python trees/blackswan.py                     # random-walk dry run of the BlackSwan tree
```

### Local dev — frontend
From `frontend/`:
```bash
npm install
VITE_API_URL="https://<api-id>.execute-api.us-east-1.amazonaws.com" npm run dev
npm run build       # production build into dist/ (also what Vercel runs)
npm run preview     # serve the built dist/
```

### Deploy — backend (`backend/deploy.sh`)
Manual, requires AWS CLI configured for `us-east-1`. The function name is
**`nuts-visualizer`**, runtime **python3.10**.
```bash
cd backend
./deploy.sh                  # zip + update-function-code (CODE ONLY — deps are in a Layer)
./deploy.sh --create-layer   # first build/publish the deps Layer (yfinance/pandas/numpy/
                             # pytz/requests, manylinux2014_x86_64, py3.10), then prints
                             # the update-function-configuration command to attach it
```
`deploy.sh` copies only the 5 top-level modules + the `trees/` package into the zip;
**dependencies live in a separate Lambda Layer** (`nuts-visualizer-deps`), not in the zip.
It then prints the API Gateway URL (`Name=='nuts-visualizer-api'`).

### Deploy — frontend
Vercel auto-builds from the repo (`vercel.json`: `npm run build` → `dist`, SPA rewrite).
Set **`VITE_API_URL`** in Vercel env vars to the API Gateway base URL.

### One-time infra (`backend/setup_infra.sh`)
Creates the S3 bucket (public access fully blocked), both EventBridge rules + targets +
Lambda invoke permissions, and writes `nuts_s3_policy.json` (S3 Get/Put/List on
`nuts-algo-data`). Run with `LAMBDA_ARN` exported. Then attach the IAM policy to the Lambda
execution role and run `bootstrap_historical.py` to seed the price CSVs.

### Tests
`backend/test_suite.py` is a 28-test pure-logic suite (`python test_suite.py`). **It is
currently stale and will not import cleanly** — its top import block does
`from state_manager import StateManager`, but `state_manager` exposes `read_state` /
`write_state` (there is no `StateManager` class), so `IMPORTS_OK=False` and the import-
dependent tests can't run. It also references FTLT label `TQQQ RSI(10) > 75` where the code
now uses `> 79`. Treat it as **documentation of intent, not a passing gate** until fixed.
The real correctness gate is `run_unit_test()` (RSI = 73.3333), wired into `/evaluate`.

---

## 5. Secrets, env vars, where things live

- **`VITE_API_URL`** (frontend, build-time) — API Gateway base URL. Empty = same-origin.
- **`AWS_LAMBDA_FUNCTION_NAME`** — set automatically in Lambda; `state_manager` uses its
  presence to choose S3 vs local-file caching.
- **`LAMBDA_ARN`, `AWS_REGION`** — only read by `setup_infra.sh`.
- AWS credentials — standard boto3 credential chain (Lambda execution role in prod, local
  profile in dev). The role needs the S3 policy in `nuts_s3_policy.json`.
- **S3 layout** (`nuts-algo-data`): `historical/{TICKER}_prices.csv` (CSV `date,close`),
  `cache/latest_evaluation.json` (the last `/evaluate` result).

### ⚠️ LEAKED API KEYS — OWNER ACTION REQUIRED
`backend/data_fetcher.py` **previously hardcoded** a Finnhub key and a Polygon key in
plaintext. The literals have been **removed** — the code now reads `FINNHUB_KEY` and
`POLYGON_KEY` from `os.environ` (a missing key degrades gracefully: the fetch raises and is
caught). **But the old keys are still in git history of this public repo, so they are
compromised.** Owner must:
1. **Rotate both keys** at Finnhub and Polygon (the old ones are burned).
2. **Set `FINNHUB_KEY` and `POLYGON_KEY` as environment variables on the `nuts-visualizer`
   Lambda** (and locally for dev) with the rotated values — until you do, live price fetches
   fail and signals fall back to the last S3 close.
3. (Optional) Purge the old literals from git history (`git filter-repo`) — rotation already
   neutralizes them, so this is hygiene, not strictly required.

---

## 6. Gotchas / hard rules (highest-value section)

1. **RSI unit test gates live data.** `/evaluate` runs `run_unit_test()` first and returns
   **500 "RSI unit test FAILED"** if it doesn't equal 73.3333. Never weaken or bypass this.
2. **`indicators` is a LIST, not a dict.** `_build_indicators` returns a sorted list of
   `{ticker, price, rsi_10, extras}`. The frontend `IndicatorSidebar` bails (`return null`)
   if it isn't an array — old cached dict-shaped payloads render nothing until recomputed.
   The `demo_output.py` mockup shows an *old* dict shape and uses a stale leaf id
   (`leaf_uvxy_bull`, which no longer exists — real ids are `leaf_uvxy_b1`/`leaf_uvxy_b2`).
   **`demo_output.py` is illustrative and out of date; do not treat it as the contract.**
3. **yfinance is NOT thread-safe — never call it inside `download_all_tickers`.** Live
   intraday prices are fetched via plain `urllib` REST: **Finnhub → Polygon** fallback
   (`_fetch_live_price`). `download_ticker` runs across a 10-worker ThreadPool, so any
   shared/lazy library there will corrupt results. yfinance is only used single-threaded
   in `bootstrap_historical.py` and `data_manager.update_daily`.
4. **Live-price injection window: weekdays 09:30–20:00 ET.** During that window
   `download_ticker` overwrites today's S3 close (or appends a new row) with the live quote.
   The window runs to **8 PM ET** on purpose: Finnhub's `c` field returns the *official*
   close after 4 PM, so EOD prices are correct before the 21:00 UTC `update_prices` cron
   writes them. Don't shrink this window.
5. **Two EventBridge schedules (verified in `setup_infra.sh`):**
   - `nuts-compute`: `cron(5,35 13-20 ? * MON-FRI *)` — :05 and :35 past the hour,
     13:00–20:00 UTC (≈09:00–16:00 ET), Mon–Fri → `{"action":"compute"}` → forces a fresh
     eval and rewrites the S3 cache.
   - `nuts-update-prices`: `cron(0 21 ? * MON-FRI *)` — 21:00 UTC (17:00 ET) Mon–Fri →
     `{"action":"update_prices"}` → appends today's close to every ticker's S3 CSV.
   EventBridge events are plain dicts with an `"action"` key and **no** `requestContext` —
   that's how `lambda_handler` distinguishes them from API Gateway requests.
6. **`update_daily` is idempotent** — re-running same-day is safe (it keeps only rows
   `>= last_known_date` and dedups keeping last). yfinance primary → **Stooq via urllib**
   fallback (`https://stooq.com/q/d/l/?s={ticker}.US&i=d`). Note Stooq's CSV endpoint may
   gate behind an apikey; if both fail it raises (the ticker is skipped, logged).
7. **Lambda packaging splits code vs deps.** `deploy.sh` zips **code only**; numpy/pandas/
   yfinance live in the **Layer**, built for **`manylinux2014_x86_64`, cp, python 3.10,
   `--only-binary=:all:`**. Never ship Mac-built native wheels — they crash on Lambda Linux
   with `Runtime.ImportModuleError`. Add a new backend dep in BOTH `requirements.txt` (local)
   and the `deploy.sh --create-layer` pip line, then re-publish the Layer.
8. **`_NumpyEncoder` everywhere.** All responses serialize numpy scalars/arrays via
   `_NumpyEncoder`. If you add a field holding a numpy type and bypass `_response`/
   `_NumpyEncoder`, `json.dumps` will throw.
9. **Frontend tree wiring is hand-maintained.** `DecisionTree.jsx` hardcodes the parent→
   child edge maps (`FTLT_EDGES_DEF`, `BS_EDGES_DEF`) and leaf-id sets
   (`LEAF_IDS`, `BS_LEAF_IDS`). **If you add/rename/remove a node id in a backend tree, you
   MUST update the matching edge map + leaf set**, or the node will be orphaned / mislaid in
   the flowchart. (History shows real bugs from exactly this: `cf5b82c` ghost node,
   `a8e1339` wrong BS edges.) Frontrunners is auto-chained from id order
   (`leaf_<parent_id>` convention + `fr_default`).
10. **`@xyflow/react` is pinned to an exact `12.11.3`, and `frontend/package-lock.json`
   is committed. Do not loosen either.** `12.11.4` is broken as published — it imports
   `handleAttributionWarning` from its own exactly-pinned `@xyflow/system@0.0.80`, which
   does not export it, so `vite build` dies with a rollup resolution error. There was no
   lockfile before 2026-08-25, so Vercel re-resolved on every deploy and the frontend
   silently became unbuildable while the last good deployment stayed live. If you ever
   bump it, run `rm -rf node_modules && npm ci && npm run build` locally first.
   (`npm install` may fail with EACCES on `~/.npm/_cacache` — root-owned entries from an
   old sudo install. Work around it per-run with `npm_config_cache=<a temp dir>`.)
11. **The frontend header links out to `nuts-radar.vercel.app`** (a read-only companion
   board: proximity to each threshold, what crossing would do, scheduled catalysts). That
   repo mirrors the tree **shape** in `assets/tree.js` and self-checks it against this
   API's own results on every page load. **If you add, rename or remove a node id, or
   change a tree's branching, that repo's self-check will start failing** — re-derive it
   from `backend/trees/`. It holds no thresholds and no indicator maths, by design.
12. **CORS is wide open** (`Access-Control-Allow-Origin: *`) and the API is unauthenticated
    read-only. Fine for a public read-only signal viewer; don't add write endpoints.
11. **Trees do `sys.path.insert` hacks** at import time so they can `from calculations import`
    when run both as a package (Lambda) and standalone (`python trees/blackswan.py`). Keep
    that if you reorganize.
12. **`backend/preview.html` / `preview_bull.html`** are static design mockups (no live
    data). `test_suite.py` greps `preview.html` for node labels — another reason its HTML
    tests drift from the real React app.

---

## 7. Known issues / open items

- **Rotate the leaked Finnhub + Polygon keys** and set `FINNHUB_KEY`/`POLYGON_KEY` env vars
  on the `nuts-visualizer` Lambda. The literals are already removed from `data_fetcher.py`
  (now `os.environ.get`), but the old keys remain in git history → compromised. Top priority
  (see §5).
- **`test_suite.py` is broken / stale** — fix the `StateManager` import (use `read_state`/
  `write_state`), update the FTLT `>75`→`>79` label expectation, and reconcile the HTML
  tests with the React frontend (or delete them). See §4.
- **Stale comments in `calculations.py`** — the `rsi_filter` section header ("lowest RSI")
  and the "Stubs — implement in Phase 3" header no longer match the code. Harmless but
  misleading; clean up when convenient. Code behavior is correct (highest RSI wins).
- **`demo_output.py` is outdated** (old indicators dict shape, dead `leaf_uvxy_bull` id).
  It's a demo script, not used in prod; update or remove.
- **No automated CI / no deployment of EventBridge from code on each change** — schedules,
  Layer version, and env config are managed by the one-time scripts + console. If you change
  a cron or the function config, update `setup_infra.sh`/`deploy.sh` to match reality.

---

## 8. File / module map

### backend/
- `lambda_function.py` — Lambda entry + API Gateway routing (`/test-rsi`, `/evaluate`),
  EventBridge action dispatch (`compute`, `update_prices`), final-signal logic,
  `_build_indicators` (the frontend table), local `__main__` runner.
- `calculations.py` — RSI (Wilder), MA, current price, cumulative return, max drawdown,
  `rsi_filter` (highest RSI wins), and the canonical `run_unit_test` (73.3333).
- `data_fetcher.py` — `ALL_TICKERS` (22), `download_ticker`/`download_all_tickers`
  (parallel S3 load + live intraday inject via Finnhub→Polygon), market-hours window logic.
  Reads `FINNHUB_KEY`/`POLYGON_KEY` from env (old hardcoded keys removed; rotate + set env).
- `data_manager.py` — all S3 historical-CSV I/O: `load_historical`, `update_daily`
  (yfinance→Stooq, idempotent), `get_prices`. Bucket `nuts-algo-data`, prefix `historical`.
- `state_manager.py` — `read_state`/`write_state` cache (S3 in Lambda, local file in dev),
  60-min TTL, `_NumpyEncoder`.
- `trees/frontrunners.py` — Branch 1 (10-node flat chain, first TRUE wins).
- `trees/ftlt.py` — Branch 2 (SPY MA(200)-gated bull/bear binary tree; always evaluated).
- `trees/blackswan.py` — Branch 3 (RSI gate → huge-vol BS path or NMA/NMB vote; always
  evaluated; has a `__main__` random-walk dry run).
- `bootstrap_historical.py` — one-off: download max yfinance history → upload CSVs to S3
  (`--dry-run`, `--tickers`).
- `deploy.sh` — package code-only zip + `update-function-code`; `--create-layer` builds/
  publishes the deps Layer.
- `setup_infra.sh` — create S3 bucket + EventBridge rules/targets/permissions; write IAM
  policy.
- `nuts_s3_policy.json` — S3 Get/Put/List policy for the Lambda role.
- `requirements.txt` — local Python deps (yfinance, pandas, numpy, pytz, requests, boto3).
- `test_suite.py` — 28-test pure-logic suite (currently stale — see §7).
- `demo_output.py` — static bull-scenario console demo (outdated — see §7).
- `preview.html`, `preview_bull.html` — static HTML design mockups (no live data).

### frontend/
- `index.html` — Vite entry; dark theme; mounts `#root`.
- `src/main.jsx` — React root render.
- `src/App.jsx` — top-level UI: fetches `/evaluate` (60-min auto-refresh + Force Refresh),
  tabs (Frontrunners / FTLT / BlackSwan), header signal, active/dimmed tab logic, banners.
  Reads `VITE_API_URL`.
- `src/components/DecisionTree.jsx` — builds the @xyflow/react + dagre flowchart per branch;
  **hardcoded `FTLT_EDGES_DEF` / `BS_EDGES_DEF` / leaf-id sets** + `getChainForNode`
  (click-to-explain chain extraction).
- `src/components/NodeBox.jsx` — custom node rendering, close-call styling, tooltips,
  `ASSET_DESCRIPTIONS`, `buildPlainQuestion`/`buildConditionDetail`/`buildConditionTooltip`.
- `src/components/IndicatorSidebar.jsx` — bottom table of per-ticker price/RSI/extras
  (requires `indicators` to be an array).
- `src/components/ChainPanel.jsx` (+ `.css`) — the slide-in "copy this chain" panel.
- `package.json` — React 18, `@xyflow/react`, `@dagrejs/dagre`, `react-tooltip`, Vite.
- `vite.config.js`, `vercel.json` — build config (note `define: {"process.env": {}}` shim).
