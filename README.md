# VoxBridge - Radio Network Anomaly Detection & Dispatch Prioritization

> **LPDG Innovation Hub Selection Challenge 2026** — *Part 2: Software Development Specialization*

VoxBridge is a production-grade Python web service and analytics engine designed to detect degraded radio network gateways and prioritize weekly technician site visits.

---

## 1. Overview & Business Problem

LPDG operates an IoT radio network comprising ~320 gateways across diverse site locations (rooftops, basements, switch cabinets). Each gateway relays telemetry for 40 to 900 utility meters.

* **The Challenge**: Gateway degradation often occurs silently without hard failure alarms, causing unread meter data, delayed customer billing, and costly manual reads.
* **Operational Constraint**: The field operations team has a hard capacity limit of **15 site visits per week**.
* **Financial Asymmetry**:
  * **False Positive (Unnecessary visit)**: €380 one-time cost.
  * **False Negative (Broken gateway ignored)**: €600 per week for every week the failure persists.

VoxBridge ingests hourly gateway telemetry, establishes per-gateway rolling baselines, detects multi-metric 3-sigma statistical anomalies, and generates prioritized, human-readable dispatch recommendations for field operations.

---

## 2. System Architecture

The project follows clean, decoupled architectural patterns:

```
                  ┌──────────────────────────────┐
                  │    Clients / Consumers       │
                  │  (CLI, Field Ops UI, cURL)   │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │      FastAPI Web Layer       │
                  │  (/predictions, /gateways)   │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │   Prediction Service Layer   │
                  │ (Orchestration & Validation) │
                  └──────┬────────────────┬──────┘
                         │                │
                         ▼                ▼
         ┌───────────────────────┐  ┌───────────────────────┐
         │ <<BaseRanker Protocol>>│  │ Repository / Data     │
         │  ThreeSigmaRanker     │  │ TelemetryRepository   │
         │  (Swappable Engine)   │  │ GatewayRepository     │
         └───────────────────────┘  └───────────────────────┘
```

### Core Design Principles
* **Decoupled Business Logic**: The ranking algorithm (`ThreeSigmaRanker`) is completely isolated from the API routing layer via the `BaseRanker` protocol. A new machine learning model or rule-based ranker can be plugged in without changing a single line of API code.
* **Memory-Efficient Data Ingestion**: Telemetry loading uses columnar projection (selecting only required metric and timestamp columns from parquet partitions), reducing memory footprint by >75%.
* **Robust Error Handling**: Pydantic v2 schemas and explicit HTTP exception handlers gracefully handle invalid dates, non-Mondays, unknown gateway IDs, and character encoding nuances.

---

## 3. Project Structure

```
├── .gitignore                  # Prevents accidental dataset/cache commits
├── README.md                   # System documentation & usage
├── DECISIONS.md                # 5 key engineering architecture decisions
├── AI-USAGE.md                 # AI assistance disclosure and bug log
├── requirements.txt            # Python dependencies
├── baseline_3sigma.py          # Original baseline reference script
├── validate_submission.py      # Official submission format checker
├── predictions.csv             # Generated 120-row predictions submission
│
├── src/
│   ├── __init__.py
│   ├── config.py               # Environment-driven configuration (DATA_DIR, SIGMA, etc.)
│   ├── cli.py                  # CLI runner (generate, serve, validate)
│   │
│   ├── core/                   # Pure business logic & ranking interfaces
│   │   ├── interfaces.py       # BaseRanker protocol
│   │   ├── models.py           # Domain dataclasses
│   │   └── ranker_3sigma.py    # 3-sigma anomaly ranking implementation
│   │
│   ├── data/                   # Data access and projection
│   │   ├── loader.py           # Multi-encoding CSV and Parquet loaders
│   │   └── repository.py       # TelemetryRepository & GatewayRepository
│   │
│   ├── services/               # Application service layer
│   │   └── prediction_service.py
│   │
│   └── api/                    # FastAPI web application
│       ├── app.py              # App factory & middleware
│       ├── dependencies.py     # Dependency injection providers
│       ├── schemas.py          # Pydantic v2 request/response schemas
│       └── routes/
│           ├── health.py       # GET /health
│           ├── predictions.py  # GET /predictions/{week_start} & drill-down
│           ├── pipeline.py     # POST /pipeline/run
│           └── gateways.py     # GET /gateways
│
└── tests/
    ├── conftest.py             # Shared fixtures & synthetic datasets
    ├── test_ranker.py          # Unit tests for ranking logic & ID normalization
    ├── test_repository.py      # Repository window filtering & NaN conversion tests
    ├── test_api.py             # API route integration, limit validation, & 503 missing data tests
    ├── test_edge_cases.py      # Bug regression tests (colon MAC, German 0xDF, NaN float, zero variance)
    ├── test_e2e.py             # Unmocked E2E pipeline execution against synthetic disk files & validator
    ├── test_live_reload.py     # Live evaluation test: dynamic data reload on /pipeline/run without server restart
    └── test_swappable_ranker.py # Verifies ranker swappability via BaseRanker protocol without API code changes
```

---

## 4. Installation & Quick Start

### Prerequisites
* Python 3.10+ (Tested on Python 3.13)
* Unzipped `data/` directory located at repository root (or pointed to via `--data` / `DATA_DIR`)

### 1. Setup Environment
```bash
python -m venv .venv
# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Generate Predictions (One-Command Run)
Generate the official 120-row `predictions.csv`:
```bash
python -m src.cli generate --data data --out predictions.csv
```

### 3. Validate Submission
Check output conformity against the challenge validator:
```bash
python validate_submission.py predictions.csv
```

---

## 5. Running the Web API

### Start the API Server
```bash
# Using the CLI entrypoint
python -m src.cli serve --host 127.0.0.1 --port 8080

# Or directly with Uvicorn
uvicorn src.api.app:app --host 127.0.0.1 --port 8080 --reload
```

Interactive OpenAPI documentation is available at:
* Swagger UI: **`http://127.0.0.1:8080/docs`**
* ReDoc: **`http://127.0.0.1:8080/redoc`**

---

## 6. API Endpoints & Examples

### 1. Health & Telemetry Status
`GET /health`
```bash
curl -X GET "http://127.0.0.1:8080/health"
```
**Response (200 OK):**
```json
{
  "status": "healthy",
  "telemetry_available": true,
  "telemetry_row_count": 1433387,
  "total_registered_gateways": 332,
  "ranker_algorithm": "ThreeSigmaRanker",
  "configured_metrics": [
    "offline_duration_sec",
    "disconnection_cnt",
    "reboot_cnt"
  ],
  "sigma_threshold": 3.0
}
```

### 2. Get Weekly Dispatch Recommendations
`GET /predictions/{week_start}?limit=15`
```bash
curl -X GET "http://127.0.0.1:8080/predictions/2026-02-02?limit=3"
```
**Response (200 OK):**
```json
{
  "week_start": "2026-02-02",
  "total_dispatches": 3,
  "recommendations": [
    {
      "week_start": "2026-02-02",
      "rank": 1,
      "gateway_id": "0A2778A31BE3",
      "score": 43.0,
      "reason": "43 hour(s) beyond 3 sigma of this gateway's own 28-day baseline in the last 7 days; first breach on disconnection_cnt"
    },
    {
      "week_start": "2026-02-02",
      "rank": 2,
      "gateway_id": "0E1B6F4DBA34",
      "score": 26.0,
      "reason": "26 hour(s) beyond 3 sigma of this gateway's own 28-day baseline in the last 7 days; first breach on offline_duration_sec"
    },
    {
      "week_start": "2026-02-02",
      "rank": 3,
      "gateway_id": "06F49BD8F572",
      "score": 26.0,
      "reason": "26 hour(s) beyond 3 sigma of this gateway's own 28-day baseline in the last 7 days; first breach on disconnection_cnt"
    }
  ]
}
```

### 3. Gateway Anomaly Drill-Down & Explanation
`GET /predictions/{week_start}/gateway/{gateway_id}`
```bash
curl -X GET "http://127.0.0.1:8080/predictions/2026-02-02/gateway/0A2778A31BE3"
```
**Response (200 OK):**
```json
{
  "gateway_id": "0A2778A31BE3",
  "week_start": "2026-02-02",
  "rank": 1,
  "score": 43.0,
  "total_flagged_hours": 43,
  "first_breach_metric": "offline_duration_sec",
  "reason": "43 hour(s) beyond 3 sigma of this gateway's own 28-day baseline in the last 7 days; first breach on disconnection_cnt",
  "recent_total_hours_observed": 143,
  "baseline_total_hours_observed": 625,
  "metric_breakdown": [
    {
      "metric_name": "offline_duration_sec",
      "mean": 908.8496,
      "std": 6132.4947,
      "threshold_3sigma": 19306.3336,
      "recent_breaches_count": 7
    },
    {
      "metric_name": "disconnection_cnt",
      "mean": 0.0848,
      "std": 0.2955,
      "threshold_3sigma": 0.9714,
      "recent_breaches_count": 36
    },
    {
      "metric_name": "reboot_cnt",
      "mean": 0.0,
      "std": 0.0,
      "threshold_3sigma": 0.0,
      "recent_breaches_count": 0
    }
  ]
}
```

### 4. Trigger Batch Pipeline
`POST /pipeline/run`
```bash
curl -X POST "http://127.0.0.1:8080/pipeline/run" \
     -H "Content-Type: application/json" \
     -d '{"output_path": "predictions.csv"}'
```

---

## 7. Deterministic Ranking & Live Pipeline Execution

### Deterministic Tie-Breaking Rule
If two gateways have the same flagged-hour count, normalized gateway ID is used as a deterministic secondary key (`flagged_hours` descending, `normalized_id` ascending).
* **Primary criterion**: `flagged_hours` descending (higher anomaly score ranked first).
* **Secondary tie-breaker**: Normalized 12-character hexadecimal `gateway_id` ascending (`"0A..."` before `"0B..."`).
* This prevents the ranking result from depending on the order in which gateways happen to be returned by DataFrame grouping operations.

### Live `/pipeline/run` Reloading & Atomic Writing
* **Dynamic Data Ingestion**: When `POST /pipeline/run` is called, `PredictionService` forces an un-cached re-scan of the storage directory (`data/telemetry/`). Reviewers can add new monthly telemetry partitions while the API server remains running, and subsequent `/pipeline/run` requests immediately incorporate the new data.
* **Atomic File Replacement**: Predictions are generated into a temporary file (`.predictions.csv.tmp`) and atomically replaced via `replace()` under a `threading.Lock()`. If execution is interrupted, the existing `predictions.csv` is never corrupted or left half-written.

---

## 8. Automated Testing Suite

The project includes **33 automated tests** across 7 distinct test modules covering unit logic, error contracts, bug regressions, swappable interfaces, live data reloading, and unmocked end-to-end pipeline validation.

Run the test suite with:
```bash
python -m pytest -v
```

### Test Suite Matrix:
| Category | Test Module | Description |
| :--- | :--- | :--- |
| **Unit Tests** | `tests/test_ranker.py` | Validates 3-sigma mathematical formulas ($\mu + 3\sigma$), ID normalization, empty frames, and explanation generators. |
| **Data Access** | `tests/test_repository.py` | Validates time-window filtering, UTC conversion safety, and metadata search. |
| **API Endpoints** | `tests/test_api.py` | Tests response schemas, `/health`, `/gateways`, query limits (1..50), and invalid date parsing. |
| **Error Handling** | `tests/test_api.py` | Validates deliberate error responses: 422 for malformed dates, 400 for non-Mondays, 404 for unknown gateways or dates with no telemetry, and 503 for missing telemetry files. |
| **Bug Regressions** | `tests/test_edge_cases.py` | Minimal reproducing tests for real caught bugs: colon MAC disappearance, Latin-1 `0xDF` character decode, Pandas `NaN` float Pydantic serialization, and division-by-zero on zero-variance flatlines. |
| **Deterministic Ordering** | `tests/test_edge_cases.py` | Verifies gateways with identical anomaly scores break ties strictly by normalized gateway ID ascending. |
| **Ranker Swappability** | `tests/test_swappable_ranker.py` | Proves an alternative custom ranker implementing `BaseRanker` can be injected and served via the API without modifying API routes. |
| **Live Reloading** | `tests/test_live_reload.py` | Simulates the reviewer's workflow: Start API → `/run` → Add new telemetry month partition → `/run` again without restarting server → Asserts output updates immediately. |
| **End-to-End (E2E)** | `tests/test_e2e.py` | Exercises the real unmocked path from synthetic disk files (Parquet + CSV) → Loader → Repository → Ranker → Service → `/pipeline/run` → `predictions.csv` → `validate_submission.py` (0 validation errors). |

---

## 9. Known Limitations & Architectural Trade-offs

A transparent accounting of system boundaries, statistical assumptions, and engineering trade-offs:

1. **Stationarity Assumption of 3-Sigma Rolling Baselines**:
   * *Mechanism*: The algorithm establishes thresholds based on each gateway's trailing 28-day operating window.
   * *Limitation*: It assumes the 28-day baseline represents "healthy" operation. If a gateway suffered severe degradation or continuous disconnections across the entire month, its baseline mean ($\mu$) and standard deviation ($\sigma$) inflate, causing the anomaly threshold ($\mu + 3\sigma$) to skyrocket (variance masking). Such a chronically failing gateway might flag zero hours in the recent week.
   * *Mitigation in Production*: Establish fixed population-level sanity caps (e.g. any gateway offline > 12 hours/week is flagged regardless of its historical baseline).

2. **Statistical Anomaly vs. Physical Hardware Causality**:
   * *Mechanism*: Flags statistical spikes in `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt`.
   * *Limitation*: Telemetry breaches do not diagnose physical root cause. A gateway experiencing 15 reboots in an hour might have a degraded internal power capacitor, or it might be located in a neighborhood undergoing electrical utility grid switching. Dispatching a technician to a healthy gateway during local grid maintenance incurs a €380 false-positive visit cost.

3. **Completely Dead / Silent Gateways (Missing Telemetry Ambiguity)**:
   * *Mechanism*: Evaluates hours where telemetry values exceed $\mu + 3\sigma$.
   * *Limitation*: If a gateway suffers catastrophic power loss or lightning damage, it transmits zero bytes. Because no rows are emitted into `data/telemetry/`, there are no data points to flag as exceeding 3-sigma. A gateway that is 100% dead for 7 days would produce 0 flagged hours in standard anomaly loops unless complemented by explicit silence detection.

4. **Fixed Operational Capacity vs. Failure Severity**:
   * *Mechanism*: The system caps dispatches at strictly 15 site visits per week matching field operations capacity.
   * *Limitation*: If a regional storm or firmware bug causes 30 gateways to fail simultaneously in a single week, the system can only prioritize the top 15. The remaining 15 broken gateways must wait at least an additional week, accruing €600/week in uncollected meter data penalties.

5. **Full Batch In-Memory Regeneration vs. Distributed Stream Processing**:
   * *Mechanism*: `/pipeline/run` re-scans parquet partitions and computes rankings in ~1.5 seconds.
   * *Limitation*: While optimal for the current fleet (~330 gateways, 1.4M rows), scaling to nationwide deployments (100,000+ gateways and billions of telemetry rows) would exceed single-machine memory and CPU limits.
   * *Future Scale Architecture*: Migrate storage to an analytical columnar store (ClickHouse / DuckDB), stream hourly telemetry through Apache Kafka, and schedule rolling dispatch updates via Celery or Temporal workers.
