# NexaWorks Decision Support System

A comprehensive enterprise decision support and operational planning system, combining an in-depth algorithmic analytics engine (Python) with an intuitive, multilingual user interface (React + TypeScript).

---

## 1. Problem Overview

The system addresses the challenge of operational management and resource optimization for an enterprise within a 4-week planning horizon (from **October 5, 2026** to **October 30, 2026**), under strict resource and financial constraints:

- **Work Demand Exceeding Capacity**: Total workload demand is 1,277 hours, while the total capacity of the 6-person team is only 748 hours (actual demand reaches 171% of available capacity).
- **Strict Skill and Language Constraints**: Each work item requires specific technical skill sets at minimum proficiency levels and client communication language standards (Japanese, English). Skill levels represent individual competency and cannot be mechanically aggregated across multiple team members.
- **Dependencies and Shared Resources**: Multiple work items require prerequisite tasks to be completed first. Additionally, certain exclusive equipment/resources can only be utilized by at most one work item per day.
- **Trade-offs Between Mandatory Commitments and Commercial Opportunities**: The system must balance fulfilling mandatory contract/safety commitments against pursuing commercial bids with win probabilities and potential revenue.
- **Cash Flow Timing Mismatch Risk**: Managing initial cash balance and daily fixed operational burn, while identifying short-term cash deficit risks during the 4-week horizon caused by major contract revenue inflows arriving at later dates.

---

## 2. What the System Does

NexaWorks serves as an intelligent assistant that empowers executive leadership to analyze, automatically optimize scheduling, and control operational risks:

- **Feasibility Assessment**: Automatically evaluates each work item against staff capacity, skill coverage, language proficiency, dependency chains, shared resources, and deadlines.
- **Portfolio Effects Analysis**: Assesses synergistic impacts between work items (e.g., completing an enablement task reduces hours required for subsequent tasks, unlocks new bid opportunities, or yields bonus cash flow).
- **Scoring and Prioritization**: Quantifies the contribution value of each action on an objective 0–100 scale using empirical distribution normalization.
- **Automated Operational Planning**: Generates day-by-day schedules for each employee, ensuring 100% completion of mandatory tasks, maximizing high-value work, and making automated `NO_BID` decisions on unviable opportunities.
- **Multi-Scenario Cash Flow Simulation**: Projects daily JPY cash ledgers across 3 scenarios (Expected, Pessimistic, Optimistic), pinpointing the exact days when cash reserves breach safety buffer thresholds.
- **Transparent Decision Explainability**: Explicitly details the reasoning and rationale behind every decision (why selected, why deferred, why no-bid) along with core risk warnings.
- **Scenario Management & Comparison**: Allows users to dynamically modify assumptions (capital, capacity, timeline, win probabilities) and visually compare trade-offs across different scenario runs.

---

## 3. Processing Pipeline

The data processing and decision-making pipeline is structured in a sequential, deterministic, and consistent workflow:

```
[ Input Dataset ] (Work Items, Employees, Resources, Opportunities, Cash Flow)
        │
        ▼
 1. Feasibility Check (Feasibility)
    └── Evaluates skills, languages, dependencies, capacity, and deadlines
        │
        ▼
 2. Portfolio Effects Evaluation (Portfolio Effects)
    └── Calculates effort reductions, unlocked bids, and bonus cash inflows
        │
        ▼
 3. Commercial Evaluation (Commercial Evaluation)
    └── Analyzes profit margins, win probabilities, and delivery hour reservations
        │
        ▼
 4. Priority Scoring (Scoring)
    └── Normalizes empirical distributions, computes value scores from 0 to 100
        │
        ▼
 5. Operational Planning (Planner)
    └── Day-by-day scheduling, prioritizes mandatory items, assigns staff, decides NO_BID
        │
        ▼
 6. Cash Flow Simulation (Cash Flow Simulator)
    └── Generates daily JPY ledger across 3 scenarios, flags safety buffer breaches
        │
        ▼
 7. Validation & Explainability (Validation & Explanations)
    └── Evaluates operational/financial status and assigns transparent reason codes
```

All business logic above is implemented in pure, decoupled Python, independent of UI frameworks or databases, guaranteeing determinism and high reliability.

---

## 4. Key Features

- **Executive Dashboard**: Quickly monitors critical Key Performance Indicators (KPIs), team capacity utilization, cash buffer health, and system connectivity.
- **Data Ingestion & Planning Workflow**: Supports JSON schema validation, input dataset inspection, preliminary diagnostics, and end-to-end plan generation.
- **Work Items Management**: Detailed lookup of work items, technical skill requirements, mandatory flags, dependency chains, and linked commercial options.
- **Workforce Management (Employees)**: Displays personnel profiles, skill matrices, language proficiencies, hourly rates, absence schedules, and planned utilization.
- **Scenario Studio (Scenarios)**: Create, customize, and store simulation scenarios with parameter overrides (initial cash, daily fixed cost, safety buffer, employee capacity, win probabilities), with run history tracking.
- **Execution Plan Details (Plan)**: Comprehensive daily work allocation table, assigned personnel, deferred work items, and no-bid packages with explicit rationale.
- **Cash Flow Analytics**: Daily cash projection charts across 3 scenarios, highlighting periods dropping below safety buffers and summarizing post-period revenue inflows.
- **Scenario Comparison**: Side-by-side visual comparison between two scenario runs on workload output, revenue, resource utilization, and financial risks.
- **Decision Explainability Tree (Explanations)**: Transparent breakdown of the factors and reasoning behind every decision, highlighting strategic strengths and core risks.
- **Multilingual Support**: Seamlessly switch between **Vietnamese (Tiếng Việt)**, **English**, and **Japanese (日本語)**.

---

## 5. Project Structure

```
Nexaworks_Project/
├── backend/                      # Server source code and decision engine
│   ├── app/
│   │   ├── decision_engine/      # Core algorithms (feasibility, portfolio, scoring, planner, cash flow, validation)
│   │   ├── api/                  # FastAPI REST API endpoints
│   │   ├── domain/               # Data models and constraint validations (Pydantic)
│   │   ├── scenarios/            # Scenario management, parameter overrides, and SQLite storage
│   │   ├── services/             # Data loaders, JSON Schema validators
│   │   └── main.py               # FastAPI application entry point
│   ├── tests/                    # Comprehensive automated test suite
│   └── requirements.txt          # Python dependencies
├── frontend/                     # Web user interface
│   ├── src/
│   │   ├── pages/                # Page components (Dashboard, Scenarios, Plan, Cash Flow, etc.)
│   │   ├── components/           # Reusable UI components
│   │   ├── api/                  # Backend API client and integration
│   │   ├── workflow/             # Planning workflow state management
│   │   ├── i18n.ts               # Multilingual configuration (VI, EN, JA)
│   │   └── App.tsx               # Application shell and routing
│   ├── package.json              # Frontend scripts and dependencies
│   └── vite.config.ts            # Vite dev server and API proxy configuration
├── data/                         # Benchmark datasets
│   ├── candidate_dataset.json    # Standard 4-week benchmark dataset
│   └── candidate_dataset.schema.json # JSON Schema for dataset validation
└── docs/                         # Detailed business rules and specifications
```

---

## 6. Getting Started

### Prerequisites
- **Python**: Version 3.10 or higher
- **Node.js**: Version 18 or higher (with `npm`)

---

### Starting the Backend

1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # On Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # On macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Launch the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

The backend will be running at `http://127.0.0.1:8000`. Interactive API documentation (Swagger UI) is available at `http://127.0.0.1:8000/docs`.

---

### Starting the Frontend

1. Open a new terminal window and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to `http://localhost:5173`. The frontend automatically proxies API requests to the backend.

---

## 7. Testing & Notes

### Running Automated Tests

- **Backend Tests**:
  ```bash
  cd backend
  pytest -q
  ```
  *(Currently **365 test cases passed**, comprehensively verifying feasibility checks, scoring logic, scheduling algorithms, exact JPY cash flow projections, and robustness against anomalous data)*.

- **Frontend Tests**:
  ```bash
  cd frontend
  npm test
  ```
  *(Currently **76 unit/integration tests passed** across 18 test suites covering UI components and workflow logic)*.

---

### Important Business Notes

1. **Non-aggregative Skill Principle**: An employee's skill represents individual capability (two employees with Level 3 skill cannot substitute for a Level 4 requirement).
2. **Handling Blocked Dependencies (`BLOCKED`)**: A work item whose prerequisites are not yet completed is marked as `BLOCKED` (temporarily locked) rather than `INFEASIBLE`, allowing the planner to schedule prerequisites first and execute the dependent task within the same horizon.
3. **Commercial Capacity Preservation**: When a commercial option is selected, the committed delivery effort (`delivery_hours`) is fully reserved to guarantee real-world execution feasibility.
4. **Cash Timing Mismatch (`CASH_TIMING_MISMATCH`) in the Benchmark Scenario**:
   - In the benchmark scenario run, the system concludes with an overall status of **`PLAN_AT_RISK`**.
   - **Operationally**: Outstanding results with **100% of mandatory items completed (6/6 items)** and **98.5% team capacity utilization** (737/748 hours).
   - **Financially**: A temporary cash deficit occurs within the 4-week window due to daily operational fixed expenses, whereas substantial contract receivables (**27,600,000 JPY**) are disbursed only after the planning horizon concludes (in November 2026 and January 2027). The system faithfully highlights this real-world operational reality so management can arrange short-term bridge liquidity in a timely manner.
