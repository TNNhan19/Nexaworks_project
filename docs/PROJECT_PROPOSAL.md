# NexaWorks Decision Support System

## 4-Week Decision Support System

**Project Overview • Proposal • Architecture • Decision Pipeline**

Ứng dụng hỗ trợ ban quản lý lựa chọn công việc, phân bổ nguồn lực, đánh giá cơ hội kinh doanh và kiểm tra tính khả thi của kế hoạch trong 4 tuần.

> **Project status:** Kiến trúc, stack và hướng Decision Engine đã được chốt. Những điểm đề bài không định nghĩa rõ được quản lý dưới dạng explicit assumptions/policies để có thể giải thích, thay đổi theo scenario và tái tính toán.

---

## 1. Project Overview

### 1.1. Bối cảnh

NexaWorks cần lập kế hoạch hoạt động cho 4 tuần trong điều kiện:

- Nhân lực hữu hạn.
- Thời gian và deadline hữu hạn.
- Tiền mặt và minimum cash buffer hữu hạn.
- Shared resources có giới hạn và có thể exclusive.
- Có các công việc bắt buộc, công việc nội bộ, sự cố khách hàng và sales opportunities.
- Một số công việc có dependencies hoặc portfolio effects ảnh hưởng lẫn nhau.

Tổng workload lớn hơn capacity thực tế, nên hệ thống không thể đơn giản chọn “làm tất cả”.

### 1.2. Câu hỏi trung tâm

> **Trong 4 tuần tới, công ty nên làm gì, ai làm, làm khi nào, nên nhận cơ hội kinh doanh nào và kế hoạch đó có thật sự khả thi hay không?**

### 1.3. Tư duy sản phẩm

Đây là một **Decision Support System** cho manager, không phải chỉ là dashboard thống kê và cũng không phải hệ thống tự quyết định thay con người.

Mỗi recommendation phải:

- Có lý do rõ ràng.
- Có evidence/metrics đi kèm.
- Có warning nếu tồn tại rủi ro hoặc infeasibility.
- Có thể tái tính khi data hoặc assumption thay đổi.
- Cho phép so sánh giữa baseline và các scenario.

### 1.4. Canonical dataset summary

| Thông tin | Giá trị |
|---|---:|
| Planning horizon | 4 tuần (05/10/2026 - 01/11/2026) |
| People | 7 |
| Total capacity | 748 person-hours |
| Work items | 24 |
| Base workload | 1,277 hours |
| Mandatory work | 6 items / 433 hours |
| Commercial options | 18 |
| Shared resources | 2 exclusive resources |
| Portfolio effects | 5 |
| Starting cash | 12M JPY |
| Fixed cash outflow | 8M JPY |
| Desired minimum cash buffer | 5M JPY |

---

## 2. System Goals

Hệ thống phải giúp manager trả lời:

1. Work item nào nên **Do**, **Delay**, **Reject** hoặc **No-bid**.
2. Commercial option nào nên chọn cho từng sales opportunity.
3. Ai nên được phân công vào từng công việc.
4. Mỗi người nên được phân bổ bao nhiêu giờ.
5. Công việc nên được xếp vào ngày/tuần nào trong planning horizon.
6. Kế hoạch có vi phạm capacity, skill, language, dependency, deadline hay shared resource hay không.
7. Cash-flow có an toàn không, hay chỉ có revenue trên giấy nhưng thiếu tiền mặt thực tế.
8. Nếu thay đổi assumption hoặc input data thì plan mới thay đổi thế nào so với baseline.
9. Tại sao hệ thống đưa ra mỗi recommendation, warning hoặc rejection.

### 2.1. Những gì hệ thống không làm

- Không dùng black-box AI score để quyết định mà không giải thích.
- Không biến `mandatory=true` thành “magic override”. Mandatory vẫn có thể infeasible.
- Không dùng probability để làm capacity committed nhỏ đi.
- Không hard-code W001, W006, 7 people, 24 work items hoặc bất kỳ ID cụ thể nào.
- Không thay thế quyết định cuối cùng của manager.

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React + Vite + TypeScript | Dashboard, editor, scenario compare, forms, visualization |
| Frontend state | Zustand | Quản lý UI/scenario state nhẹ và rõ ràng |
| Localization | react-i18next | JA / EN / VI |
| Charts | Recharts | Capacity, cash-flow, scenario comparison |
| Backend | Python FastAPI | Validation, CRUD, orchestration, scenario APIs |
| Decision Engine | Pure Python module | Deterministic decision logic, test độc lập với API/UI |
| Storage | SQLite | Baseline, scenarios, assumptions, runs, results |
| Deployment | Public frontend + public backend | Vercel/Cloudflare Pages + Railway/Render hoặc tương đương |

### 3.1. Core principle

Decision Engine phải độc lập với web framework và ngôn ngữ UI.

```text
Same dataset + same assumptions + same engine version = same result
```

---

## 4. High-Level Architecture

```text
                         ┌───────────────────────────┐
                         │       WEB FRONTEND        │
                         │ Dashboard / Editor        │
                         │ Scenario Compare / i18n   │
                         └─────────────┬─────────────┘
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │        BACKEND API        │
                         │ Validate / CRUD / Run     │
                         │ Scenario Management       │
                         └───────┬───────────┬───────┘
                                 │           │
                    ┌────────────┘           └────────────┐
                    ▼                                     ▼
          ┌───────────────────┐                ┌───────────────────────┐
          │ Scenario / Data   │                │    DECISION ENGINE    │
          │ Store             │                │                       │
          │                   │                │ Feasibility           │
          │ Baseline          │                │ Commercial Evaluation │
          │ Scenario A/B/...  │                │ Portfolio Effects     │
          │ Results           │                │ Cash-flow             │
          └───────────────────┘                │ Scoring               │
                                               │ Planner               │
                                               │ Explanation           │
                                               └──────────┬────────────┘
                                                          │
                                                          ▼
                                               ┌──────────────────────┐
                                               │   Decision Result    │
                                               │ Do / Delay / No-bid  │
                                               │ Option / Assignment  │
                                               │ Schedule / Cash      │
                                               │ Warnings / Reasons   │
                                               └──────────────────────┘
```

### 4.1. Architecture rules

- Backend quản lý dataset/scenario và gửi một snapshot cụ thể vào Decision Engine.
- Decision Engine không đọc trực tiếp UI state.
- Decision Engine không sinh hard-coded user-facing text.
- Engine trả về structured facts, metrics, warning codes và reason codes.
- Frontend chịu trách nhiệm dịch JA / EN / VI.

---

## 5. Business Rules & Explicit Assumptions

| Topic | Policy | Interpretation |
|---|---|---|
| Skill coverage | `TEAM_COVERAGE` | Các required skills có thể được cover bởi nhiều người khác nhau; level của cùng một skill không cộng dồn giữa người với người. |
| Work effort | `TOTAL_PERSON_HOURS` | `required_hours` là tổng person-hours của work item và có thể chia giữa nhiều người. |
| Language | `CUSTOMER_FACING_COVERAGE` | Language được cover ở cấp vai trò giao tiếp/điều phối khách hàng; không bắt buộc mọi technical member biết ngôn ngữ đó. |
| Sales capacity | `FULL_IF_COMMITTED` | Deal đã committed phải reserve đủ `delivery_hours`; pending pipeline được phân tích riêng bằng sensitivity. |
| Dependencies | `HARD` | Không được phá thứ tự dependency. |
| Contract/internal deadline | `SOFT_WITH_PENALTY` | Có thể trễ nhưng phải tính late days/penalty và flag at-risk. |
| Sales opportunity deadline | `HARD_OR_EXPIRY` | Được xem như thời hạn cơ hội; quá hạn có thể khiến opportunity/option không còn hợp lệ. |
| Mandatory | `REQUIRED_TARGET` | Planner phải cố đưa vào plan; nếu không thể thì báo infeasible/at-risk. |
| Direct cost timing | `PRORATED_OVER_EXECUTION` | Chi phí trực tiếp được phân bổ theo execution period khi dataset không cung cấp timing chính xác hơn. |
| Planning granularity | `DAY` | Lập lịch theo ngày. |
| Commercial options | `MUTUALLY_EXCLUSIVE` | Một opportunity chọn tối đa một option hoặc `NO_BID`. |
| Probabilistic effects | `EXPECTED_VALUE + DOWNSIDE` | Expected value dùng cho scoring; feasibility/risk phải có sensitivity success/failure hoặc downside. |

### 5.1. Skill coverage rule

Ví dụ work yêu cầu:

```text
AI >= 4
Project Management >= 4
```

Có thể được cover bởi hai người khác nhau.

Nhưng không được cộng level:

```text
AI=3 + AI=3 != AI=6
```

Mỗi required skill phải có ít nhất một assigned person đạt threshold tương ứng.

### 5.2. Language coverage rule

Language requirement không áp dụng bắt buộc cho mọi technical member.

Engine cần validate language ở cấp **customer-facing / coordination role** theo policy, không hard-code theo ID hay tên người.

### 5.3. Sales capacity rule

Nếu option đã được committed:

```text
delivery capacity required = full delivery_hours
```

Không dùng:

```text
delivery_hours × win_probability
```

cho committed capacity.

Pending deals được xem trong **pipeline sensitivity** riêng để cảnh báo overselling risk.

---

## 6. Decision Engine Modules

### 6.1. Schema Validation & Normalization

- Validate JSON Schema.
- Validate IDs/references.
- Validate data types.
- Normalize raw JSON thành domain models.

### 6.2. Portfolio Effects

Áp dụng hoặc đánh dấu:

- commercial option unlock,
- effort reduction,
- future effort reduction,
- cash effect,
- quality prerequisite risk.

### 6.3. Commercial Evaluation

Đánh giá từng commercial option dựa trên:

- price,
- win probability,
- expected margin,
- delivery hours,
- cash timing,
- follow-on value,
- deliverability.

### 6.4. Feasibility Engine

Kiểm tra:

- capacity,
- skill coverage,
- language coverage,
- dependencies,
- shared resources,
- timing,
- opportunity expiry,
- mandatory conflicts,
- option availability.

### 6.5. Value / Priority Scoring

Chỉ dùng **soft business objectives** để so sánh các lựa chọn đã có khả năng thực hiện.

Không dùng scoring để che giấu hard infeasibility.

### 6.6. Planner

V1 dùng heuristic/greedy có constraint để:

- chọn work,
- chọn commercial option,
- assign people,
- allocate person-hours,
- schedule theo ngày.

### 6.7. Cash-flow Simulator

Mô phỏng:

- starting cash,
- fixed outflow,
- direct costs theo timeline,
- cash-in timing,
- expected cash,
- downside cash,
- minimum cash buffer breach.

### 6.8. Final Feasibility Validation

Recheck toàn bộ plan sau assignment, schedule và cash simulation để tránh xuất ra plan giả khả thi.

### 6.9. Explanation Engine

Sinh:

- `reason_codes`,
- `warning_codes`,
- evidence,
- metrics,
- decision traces.

Không sinh trực tiếp câu tiếng Việt/Anh/Nhật trong core engine.

---

## 7. Portfolio Effects V1

| Effect | V1 Handling |
|---|---|
| E001 — `quality_prerequisite` | Qualitative risk flag + warning + configurable score penalty; không tự coi một % giảm probability bất kỳ là fact. |
| E002 — `hours_reduction` 25% | Áp dụng trực tiếp khi trigger condition thỏa. |
| E003 — `future_hours_reduction` 20%, p=0.75 | Expected benefit cho scoring; success/failure sensitivity cho planning. |
| E004 — `commercial_option_unlock` | Hard availability condition cho option bị khóa. |
| E005 — `cash_inflow` +3.8M JPY, p=0.85 | Expected value cho scoring; expected/downside cash scenarios cho risk/feasibility. |

### 7.1. Probability usage rule

Probability được dùng khác nhau tùy mục đích:

```text
Scoring
→ expected value = probability × impact

Operational feasibility
→ không giả định expected value là guaranteed outcome

Risk / sensitivity
→ evaluate success case + downside/failure case
```

---

## 8. End-to-End Decision Pipeline

```text
1. Dataset / Scenario
        ↓
2. Schema Validation
        ↓
3. Normalize Inputs
        ↓
4. Apply Assumptions
        ↓
5. Apply Portfolio Effects
        ↓
6. Evaluate Commercial Options
        ↓
7. Base Feasibility Analysis
        ↓
8. Value / Priority Scoring
        ↓
9. Planner
   ├─ Select work
   ├─ Select commercial option
   ├─ Assign people
   └─ Schedule by day
        ↓
10. Cash-flow Simulation
        ↓
11. Final Feasibility Validation
        ↓
12. Explanation
        ↓
13. Decision Result
        ↓
14. Dashboard / Edit / Scenario Compare
```

---

## 9. Hard Constraints vs Soft Objectives

### 9.1. Hard / Operational Constraints

- Dependency order.
- Commercial option unlock/exclusivity.
- Required skill threshold.
- Language coverage policy.
- Capacity của từng person.
- Exclusive shared resources.
- Opportunity expiry.
- Invalid/missing references.

### 9.2. Soft / Business Objectives

- Expected margin.
- Cash timing.
- Minimum cash buffer impact.
- Strategic/customer value.
- Urgency.
- Follow-on value.
- Risk.
- Late penalty.
- Capacity efficiency.

### 9.3. Important rule

Một hard constraint bị vi phạm **không được biến thành score penalty**.

Ví dụ:

```text
Required AI >= 4
No eligible employee
```

Kết quả đúng:

```text
INFEASIBLE
Reason: MISSING_SKILL_COVERAGE
```

Không phải:

```text
priority_score -= 30
```

---

## 10. Decision Result

Một decision run cần có khả năng trả về:

```text
Recommended work
Deferred work
Rejected / No-bid work
Selected commercial options
Employee assignments
Daily schedule
Capacity usage
Resource usage
Cash-flow
Expected/downside scenarios
Warnings
Reason codes
Metrics / evidence
```

### 10.1. Expected main screens

| Screen | Purpose |
|---|---|
| Executive Dashboard | Tổng quan cash, capacity, mandatory work, selected work, risk |
| Recommended Plan | Do / Delay / Reject / No-bid + reasons |
| Commercial Decision | Option recommendation hoặc no-bid |
| Assignment | Ai làm việc nào, bao nhiêu giờ |
| Schedule | Timeline theo ngày/tuần |
| Capacity | Used / remaining / overload theo person và resource |
| Cash-flow | Expected/downside cash và buffer breach |
| Work/People Editor | CRUD input data |
| Scenario Compare | Baseline vs Scenario A/B |

---

## 11. Scenario & Data Model

Baseline dataset không bị mutate trực tiếp.

```text
BASELINE DATASET
Canonical input / original state
        ↓
SCENARIO A / B / ...
Overrides + assumptions + user edits
        ↓
DECISION RUN
Input snapshot + engine version + result
        ↓
COMPARE / RESTORE
Compare with baseline / restore original data
```

### 11.1. Minimal SQLite entities

```text
datasets
scenarios
scenario_changes or scenario_json
decision_runs
decision_results
```

Mục tiêu:

- save scenario,
- restore baseline,
- compare scenarios,
- reproduce result,
- track engine version + assumptions used.

---

## 12. Explainability & i18n

Core engine chỉ trả structured information.

Ví dụ:

```json
{
  "code": "MISSING_SKILL_COVERAGE",
  "severity": "ERROR",
  "work_item_id": "W002",
  "details": {
    "skill": "quality",
    "required_level": 4,
    "best_available_level": 3
  }
}
```

Frontend dùng `react-i18next` để render:

- Japanese,
- English,
- Vietnamese.

Không hard-code câu user-facing vào Decision Engine.

---

## 13. Reliability Principles

- Deterministic core.
- No hidden mutable global state.
- No hard-coded canonical IDs.
- No unexplained magic numbers.
- Explicit assumptions.
- Unit tests cho từng business rule.
- Regression tests trên canonical dataset.
- Unseen-data tests với dataset cùng schema.
- Final feasibility recheck trước khi trả plan.

---

## 14. Implementation Plan

### Phase 1 — Domain Model & Rules

- Map schema thành Python domain models.
- Assumption Registry.
- Schema/reference validation.
- Canonical parsing tests.

### Phase 2 — Core Decision Engine

Tách nhỏ để triển khai an toàn:

```text
Phase 2A — Feasibility Engine
Phase 2B — Portfolio Effects
Phase 2C — Commercial Evaluation
Phase 2D — Value / Priority Scoring
Phase 2E — Heuristic Planner
Phase 2F — Cash-flow Simulator
Phase 2G — Final Validation + Explanation
```

### Phase 3 — Automated Tests

- Unit tests.
- Regression tests.
- Edge cases.
- Unseen dataset tests.

### Phase 4 — FastAPI

- CRUD.
- Dataset validation APIs.
- Scenario lifecycle.
- Run endpoint.
- Compare endpoint.
- Error handling.

### Phase 5 — React UI

- Executive dashboard.
- Recommended plan.
- Schedule/resource view.
- Editor.
- Scenario compare.
- JA / EN / VI localization.

### Phase 6 — Reliability & Polish

- Restore baseline.
- Accessibility.
- Multilingual layout.
- Screenshots.
- Submission README.
- Deployment.

### Optional — Advanced Optimizer

Sau khi V1 stable mới cân nhắc OR-Tools CP-SAT/ILP.

Optimizer không được trở thành single point of failure.

---

## 15. Definition of Done — V1

V1 được coi là hoàn thành khi:

- [ ] Import và validate được canonical dataset.
- [ ] Import được unseen dataset cùng schema.
- [ ] Edit/save/restore scenario và recalculate được.
- [ ] Trả được Do / Delay / Reject / No-bid.
- [ ] Recommend commercial option.
- [ ] Assign people và person-hours.
- [ ] Schedule theo ngày.
- [ ] Detect capacity violation.
- [ ] Detect skill/language shortage.
- [ ] Enforce dependencies.
- [ ] Check exclusive shared resources.
- [ ] Apply deadline policies.
- [ ] Model đầy đủ 5 portfolio effects ở mức V1 đã chốt.
- [ ] Simulate cash-flow và minimum cash buffer.
- [ ] Có expected/downside view cho probabilistic effects.
- [ ] Mỗi quyết định quan trọng có reason codes + evidence.
- [ ] JA / EN / VI hoạt động và không phá layout.
- [ ] Scenario compare hoạt động.
- [ ] Baseline restore hoạt động.
- [ ] Core engine deterministic.
- [ ] Automated tests pass.

---

## 16. Repository Guidance

Recommended project structure:

```text
Nexaworks_Project/
├── backend/
├── frontend/
├── data/
│   ├── candidate_dataset.json
│   ├── candidate_dataset.schema.json
│   └── candidate_dataset_reference.xlsx
├── docs/
│   ├── Product_Development_Challenge_EN.md
│   ├── Product_Development_Challenge_JA.md
│   ├── README_FIRST.md
│   ├── SUBMISSION_README_TEMPLATE.md
│   ├── PROJECT_PROPOSAL.md
│   ├── BUSINESS_RULES.md
│   └── FEASIBILITY_ENGINE.md
├── README.md
└── .gitignore
```

---

## 17. Current Next Step

Current implementation order:

```text
Domain Model + Business Rules
        ↓
Phase 2A — Feasibility Engine
        ↓
Portfolio Effects
        ↓
Commercial Evaluation
        ↓
Scoring
        ↓
Planner
        ↓
Cash-flow
        ↓
Final Validation + Explanation
        ↓
FastAPI
        ↓
React UI
```

**Do not skip directly to frontend or optimizer before the core Decision Engine is validated.**
