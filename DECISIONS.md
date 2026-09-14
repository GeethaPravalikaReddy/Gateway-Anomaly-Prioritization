# Architecture & Engineering Decisions (DECISIONS.md)

This document details five key architectural and technical decisions made during the engineering of **Gateway Anomaly Prioritization** for the **LPDG Innovation Hub Selection Challenge 2026 (Part 2: Software Development Specialization)**.

In accordance with the evaluation rubric, each decision explicitly articulates:
1. **The Decision**: What was chosen and implemented in code.
2. **Alternatives Considered**: Specific rejected alternatives (the counter-options).
3. **Why I Chose Mine**: Rigorous technical and operational rationale.
4. **What It Costs / Limitations**: Honest accounting of trade-offs, overhead, and constraints.

---

## Decision 1: Retaining the Statistical 3-Sigma Anomaly Baseline vs. Replacing with Machine Learning

* **Decision**: Kept and productionized the rolling 28-day / 7-day 3-sigma statistical anomaly ranking algorithm across key metrics (`offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`) rather than replacing it with an ML classifier or deep anomaly detector.
* **Alternatives Considered**:
  1. Training supervised gradient-boosted decision trees (XGBoost / LightGBM) or Random Forests on past technician dispatch records (`field_visits.csv`).
  2. Training an unsupervised deep autoencoder or Isolation Forest on multivariate telemetry embeddings.
* **Why I Chose Mine**:
  1. **Financial Asymmetry Alignment**: In this operational problem, a false negative (failing to dispatch to a broken gateway) costs **€600 per week**, while a false positive costs a one-time fee of **€380**. Supervised models trained on historical dispatches risk learning past human dispatch biases or missing rare, high-cost failure modes.
  2. **Auditability and Explanability**: Field dispatch technicians require clear, physical explanations for why a site visit is scheduled (e.g. *"43 hour(s) beyond 3 sigma of this gateway's own 28-day baseline; first breach on disconnection_cnt"*). 3-sigma provides deterministic thresholds ($\mu + 3\sigma$) and per-metric breach counts that translate directly into operational trust.
  3. **Data Efficiency & Zero Training Drift**: 3-sigma requires zero offline training phase, eliminates cold-start training pipeline failures, and dynamically adapts to each individual gateway's baseline operating characteristics.
* **What It Costs / Limitations**:
  * **Assumption of Baseline Stationarity**: 3-sigma assumes the trailing 28 days represent "normal" behavior. If a gateway was already degraded throughout the entire 28-day baseline, its baseline mean and standard deviation will be elevated, potentially masking persistent anomalies (variance masking).
  * **Linear Metric Isolation**: It evaluates metric breaches independently and sums flagged hours, ignoring non-linear cross-metric correlations (e.g. slight offline duration combined with high reboot frequency).

---

## Decision 2: Decoupled Strategy Pattern via `BaseRanker` Protocol vs. Hardcoded API Logic

* **Decision**: Decoupled the ranking algorithm from the web service layer using Python's `@runtime_checkable Protocol` (`BaseRanker` in `src/core/interfaces.py`), injecting it into `PredictionService`.
* **Alternatives Considered**:
  1. Direct hardcoded invocation of baseline scoring routines inside the FastAPI route handlers.
  2. Abstract base classes using `abc.ABC` with classical object-oriented inheritance.
* **Why I Chose Mine**:
  1. **Clean Code-Level Seam (Zero-Code-Change Swappability)**: The challenge explicitly asks for a swappable ranking engine. Using a structural subtyping `Protocol` allows any candidate algorithm (e.g. an ML model, an exponential smoothing ranker, or emergency business rules) to be plugged in via dependency injection (`PredictionService(ranker=NewRanker())`) without modifying a single line of API routing, controller, or Pydantic validation code.
  2. **Isolated Testability & Fast CI**: The ranking logic can be tested in isolation using lightweight synthetic fixtures without starting a web server or loading parquet partitions. Conversely, API endpoints can be tested with mock rankers in milliseconds.
* **What It Costs / Limitations**:
  * **Interface Overhead**: Requires defining and maintaining common domain models (`PredictionRecord`, `GatewayScoreDetail`) that any future ranking algorithm must conform to, slightly increasing upfront scaffolding compared to a monolithic script.

---

## Decision 3: On-Demand Dynamic Computation & Service Layer vs. Serving Static Pre-Generated Predictions

* **Decision**: Designed the API to compute rankings dynamically on demand through `PredictionService` and `TelemetryRepository`, supporting arbitrary query dates, variable top-$N$ limits (`?limit=15`), and single-gateway deep explanation drill-downs.
* **Alternatives Considered**:
  1. Pre-generating a static `predictions.csv` during deployment and having the API simply read and filter rows from the CSV file.
  2. Writing pre-calculated weekly scores into an SQLite/Postgres database and serving read-only database queries.
* **Why I Chose Mine**:
  1. **Operational Drill-Downs (`GET /predictions/{week}/gateway/{id}`)**: Operations engineers don't just need the top 15 list; when investigating a contested site visit, they query specific gateways to see the exact baseline $\mu$, $\sigma$, threshold values, and recent breach counts across all metrics.
  2. **Live Telemetry Adaptability**: When new telemetry arrives, static files or pre-computed tables become obsolete. An on-demand service layer computes fresh dispatches directly from current telemetry state.
* **What It Costs / Limitations**:
  * **Computational Latency**: Serving a dynamically computed week takes ~100–150ms of CPU aggregation time across all gateways, whereas reading a static pre-computed CSV row takes < 2ms. This is mitigated by columnar projection parquet loading and vectorized Pandas operations.

---

## Decision 4: Full Deterministic Re-reading on `/pipeline/run` with Atomic Writes vs. Startup-Only In-Memory Caching or Incremental Updates

* **Decision**: `/pipeline/run` triggers a full re-scan of the storage partitions (`TelemetryRepository.get_telemetry(force_reload=True)` and `GatewayRepository.get_master(force_reload=True)`) and atomically writes `predictions.csv` via a temporary file swap (`tmp.replace(out_path)`) under a thread lock.
* **Alternatives Considered**:
  1. Loading the dataset into memory once at application startup and caching it indefinitely in a singleton.
  2. Implementing incremental cache updates that only scan and append newly timestamped parquet partitions.
  3. Writing directly to destination CSV files in-place during streaming loops.
* **Why I Chose Mine**:
  1. **Satisfying the Live Reviewer Requirement**: The challenge specification explicitly highlights that during live review, the reviewer will keep the API running, drop a new month into `data/telemetry/`, and trigger `/pipeline/run`. Systems that load data only at startup fail this test.
  2. **Determinism & Cache Invalidation Avoidance**: Incremental state maintenance introduces severe edge cases (out-of-order data arrival, amended historical records, partition re-indexing bugs). Full regeneration over the challenge dataset takes ~1.5 seconds with column pruning, making full re-reads both deterministic and lightning fast.
  3. **Atomic File Safety**: Writing directly to `predictions.csv` risks leaving a corrupted, half-written file if the server encounters an unhandled exception or process termination halfway. Generating to a `.tmp` file and executing an atomic OS rename guarantees `predictions.csv` is either 100% complete or untouched.
  4. **Concurrency Safety**: A `threading.Lock()` serializes concurrent executions of `/pipeline/run`, preventing race conditions on disk I/O.
* **What It Costs / Limitations**:
  * **Memory & I/O Burst**: Calling `/pipeline/run` triggers a burst of parquet disk I/O and temporary DataFrame memory allocation (~180 MB). While negligible for ~330 gateways on local hardware, scaling to 100,000 gateways would eventually necessitate an external task queue (Celery/Temporal) and distributed query engine (DuckDB/ClickHouse).

---

## Decision 5: Resilient Data Ingestion & Strict Fail-Safe Error Handling vs. Permissive In-Place Overwriting

* **Decision**: Handled real-world data nuances (German Latin-1 character encodings, colon-formatted MAC addresses, Pandas float `NaN` vs. Pydantic `None`) inside data access adapters, returning structured HTTP error responses (400, 404, 422, 503) without Python stack traces.
* **Alternatives Considered**:
  1. Overwriting or pre-sanitizing raw files in `data/` before launching the application.
  2. Letting unhandled Python exceptions bubble up as generic 500 Internal Server Errors with stack traces.
  3. Coercing invalid dates (e.g. Sundays or mid-week days) to the nearest Monday automatically.
* **Why I Chose Mine**:
  1. **Immutability of Source Data**: Modifying or cleaning source data on disk breaks reproducibility and would fail in read-only production container environments. Implementing multi-encoding fallback (`utf-8` with fallback to `latin1`) in `load_gateway_master` allows the app to run on any host OS without touching raw data.
  2. **Deliberate Business Contracts**: Silently coercing non-Monday dates or missing dates conceals client errors. The API strictly validates that requested prediction dates are valid Mondays (returning HTTP 400 Bad Request if a Sunday is queried), enforces integer bounds on `limit` (1..50 via HTTP 422), and cleanly reports missing data files as HTTP 503 Service Unavailable.
  3. **Zero Python Traceback Leaks**: Custom FastAPI exception handlers format errors as clean JSON contracts (`detail` and `error_type`), shielding underlying server internals from API consumers.
* **What It Costs / Limitations**:
  * **Slight Parsing Overhead**: Attempting UTF-8 first before catching `UnicodeDecodeError` adds a one-time catch block on initial cold start when reading Latin-1 files. Strict parameter validation requires clients to adhere precisely to ISO 8601 formatting.
