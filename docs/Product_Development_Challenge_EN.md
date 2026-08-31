---
title: "Product Development Challenge"
subtitle: "NexaWorks Operations Decision Support Tool — Candidate Brief (English)"
author: "Internship Selection Assignment"
date: "Submission deadline will be communicated separately"
lang: en-US
---

# 1. Purpose of the assignment

In this assignment, you will build a decision-support tool for **NexaWorks**, a fictional AI and software company facing multiple simultaneous commitments, limited people, sales opportunities, deadlines, cash constraints and shared equipment.

NexaWorks does not have enough capacity to execute every item. Management must therefore answer questions such as:

- What should be prioritized, postponed, reduced or declined?
- Who should own each item, and when should it be performed?
- How should contracted delivery, incidents, new sales, product development and hiring be balanced?
- How should revenue, margin, payment timing, customer relationships, future value and technical risk be compared?
- How should the plan change when assumptions change?

> **There is no single correct answer.** Defining the objective, deciding what is a hard constraint and handling uncertainty are part of the assignment. Express your reasoning through the product you build.

# 2. Your mission

Using the provided dataset, design and implement an application that helps management decide what work to select, how to prioritize it, who should own it, when it should happen and what commercial terms to offer.

We are looking for more than a list, a fixed ranking or a visually polished static dashboard. When inputs or assumptions change, the application should recompute its output and help the user understand both the reasoning and the execution problems behind the plan.

You may choose the objective, scoring method, algorithm, architecture and user interface. You must be able to explain your choices.

# 3. Scenario

The planning horizon is four weeks. The dataset contains:

- Team members and their available capacity during the horizon
- Skills, languages, unavailable periods and hourly cost for each member
- Contracted delivery, existing-customer work, incidents, sales opportunities and internal work
- Required hours, deadlines, revenue, direct cost, payment terms, probabilities and skill requirements
- Shared resources with limited availability, such as a vision lab and an installation kit
- Dependencies and portfolio effects, including reduced future effort and unlocked commercial options
- Multiple price, scope, probability and effort options for sales opportunities
- Starting cash, fixed cash outflow and a minimum desired cash buffer

Probabilities and future values are estimates for decision-making, not guaranteed facts.

# 4. Mandatory requirements

## 4.1 Data import and editing

- The application must import `candidate_dataset.json`.
- You may transform the data internally, but the design must be able to import another dataset following the same structure.
- At minimum, the user must be able to add, edit and delete major fields for work items, people and company assumptions.
- The user must be able to restore the initial dataset or save a changed version as a separate scenario.
- Avoid hard-coding the number of records, IDs or specific work-item names.

`candidate_dataset_reference.xlsx` is provided for readability. The JSON file is the canonical dataset. A JSON Schema is also included.

## 4.2 Decision support

The tool must support the complete decision, not only one isolated part of it:

1. Decide what to execute and what to decline, delay or reduce
2. Assign selected work to people, or explicitly identify it as unassignable
3. Consider timing, deadlines and dependencies
4. Choose a commercial option for sales opportunities, or recommend no-bid / renegotiation
5. Recompute and compare the plan after assumptions change

A priority score alone is not enough. The output should help the manager take the next action.

## 4.3 Explainability

- The user must be able to understand the reason for recommendations, assignments, rejections and warnings.
- It must be possible to trace the role of revenue, margin, cash, deadlines, risk, customer value, effort and other factors you use.
- A single opaque AI-generated score is insufficient.
- If your model is uncertain, communicate uncertainty or sensitivity instead of presenting false certainty.

## 4.4 Feasibility and anomaly detection

The application must detect or clearly expose issues such as:

- Total workload exceeding people capacity
- No available person satisfying a required skill or language
- Missed deadlines or an infeasible plan
- Missing, contradictory or incomplete dependencies
- Shared-resource overload
- Cash shortfall, loss-making work or payment-timing risk
- Missing or invalid input values

Do not show an impossible plan as feasible without an explicit warning.

## 4.5 Sales and business decisions

- Compare the commercial options associated with sales opportunities.
- Distinguish price, estimated win probability, direct cost, effort, payment timing, warranty and future value.
- Account for the possibility that a high-revenue deal may be unprofitable or impossible to deliver.
- Allow the product to represent decisions such as no-bid, delay or renegotiate.

## 4.6 Three-language interface

The interface must switch between:

- Japanese
- English
- Vietnamese

Translate core actions, explanations, recommendation reasons, warnings and validation messages, not only navigation labels. Long Vietnamese text must not break the layout. It is preferable for the selected language to persist naturally across navigation and reloads.

Machine translation and generative AI are allowed, but the candidate remains responsible for terminology, meaning and layout.

## 4.7 Persistence and reproducibility

- The user must be able to save or restore changed data, assumptions, scenarios and plans.
- The same input should produce a reproducible result.
- If you use randomness, expose the assumptions, random seed or outcome range needed to understand and reproduce the result.

# 5. Implementation and delivery

## Preferred method

Publish the solution as a web application and submit the URL. The hosting provider and technology stack are your choice. Services such as Railway, Render, Vercel, Cloudflare or other platforms may be used.

## When continuous hosting is difficult

You may instead submit one of the following:

- Source code that runs locally
- A Docker setup
- An executable or distributable package

In this case, the submitted package itself must be **under 100 MB**, and the README must provide instructions that allow evaluation to begin in approximately ten minutes on a standard environment. Dependencies may be downloaded through a package manager.

Do not require the evaluator to purchase an account, provide personal information or install an unusual proprietary development environment. If authentication is needed, provide evaluation-only credentials.

## Allowed technologies

There are no technology restrictions. You may use, for example:

- Any programming language, web framework or database
- Mathematical optimization, heuristics, simulation, rules or machine learning
- ERP, CMS, low-code tools and open-source software, including ERPNext
- External APIs
- Generative AI such as ChatGPT, Claude, Gemini, Cursor or GitHub Copilot

You do not need to build everything from scratch. However, you are expected to understand the licenses, dependencies, security implications and constraints of what you use, and to explain and modify the submitted result as your own work.

# 6. UI/UX and visual design

Aim for a level of quality that a real manager or operator could use for a decision, not merely a working demo.

Evaluation will consider:

- Whether the first information to inspect is separated from details that can be reviewed later
- Whether problems, constraints, recommendations, reasons and next actions are clearly distinguished
- Whether editing data and comparing results forms a natural workflow
- Whether color, spacing, typography, tables and charts carry meaning
- Whether empty, loading, error, infeasible and high-volume states have been designed
- Whether core operations survive smaller screens and long text
- Whether the information architecture reflects this specific problem and your own product judgment

A generic administration template made of interchangeable cards, gradients and decorative charts will not score highly. Using AI is not itself a penalty, but an AI-generated interface that has not been edited and validated for the problem will score poorly.

# 7. Use of AI and external tools

Use of AI is unrestricted. The amount of AI usage is not scored by itself.

Your README must state at least:

- AI tools, external services and major libraries used
- What each was used for
- How AI output was verified or modified
- Important design decisions that you made yourself rather than delegating to AI

You do not need to submit every AI conversation. However, you must be able to explain and modify the submitted code, model, design and constraints during the interview.

# 8. Submission items

The deadline will be communicated when the assignment is sent or separately. You may organize your working time and process freely.

Submit:

1. **A working application**
   - A public URL, or clear local execution instructions
2. **Source code**
   - A Git repository or ZIP archive
3. **README**
   - Your interpretation of the problem and target user
   - Objective function, decision logic and major assumptions
   - Technical architecture and setup instructions
   - AI, open-source software and external API usage
   - Known limitations and at least three cases in which the tool could make a poor decision
   - What you would improve with one additional day
4. **Visual evidence**
   - Three to six screenshots of the main screens
5. **Optional material**
   - A demo video of no more than five minutes, design diagrams, model explanation or test results

Keep the public URL accessible during the evaluation period. A local fallback is recommended in case the hosted application becomes unavailable.

# 9. Evaluation criteria

| Evaluation area | Points |
|---|---:|
| Problem understanding and mathematical model | 22 |
| Implementation and reliability | 20 |
| Business and sales judgment | 15 |
| UI/UX and visual design | 15 |
| Handling unseen data | 10 |
| Multilingual support and accessibility | 6 |
| Engineering quality | 7 |
| Documentation and transparency | 5 |
| **Total** | **100** |

The number of features is not the goal. A smaller set of carefully designed, correct and useful functions may score higher than a large but shallow product.

After submission, the interview will use the product, data and source code to examine design decisions, commercial reasoning, behavior under abnormal conditions, AI usage and possible improvements. We may change an assumption during the interview and ask you to explain how the plan should adapt.

# 10. Included files

| File | Purpose |
|---|---|
| `candidate_dataset.json` | Canonical assignment dataset |
| `candidate_dataset.schema.json` | JSON structure reference |
| `candidate_dataset_reference.xlsx` | Human-readable reference workbook |
| `SUBMISSION_README_TEMPLATE.md` | README template |
| `README_FIRST.md` | Suggested order for reviewing the package |

# 11. Final note

This is not a test of guessing a neat answer.

It is intended to reveal:

- How you define an ambiguous business problem
- How you organize competing values and constraints
- What you choose to build and not build
- Whether you can finish a usable product within a limited period
- Whether you recognize and explain the weaknesses of your own decisions

Submit a product that makes your reasoning visible.

# 12. Pre-submission self-check

Before submitting, test the product as if it were being opened by an evaluator on a fresh environment.

- A new evaluator can start it by following only the README
- It can import another JSON file following the same structure, not only the initial dataset
- Changing one input recomputes recommendations, assignments, warnings and metrics
- An infeasible input is not presented as a feasible plan
- Sales decisions do not confuse revenue, margin, cash timing, effort and win probability
- Core reasons and errors have been checked in Japanese, English and Vietnamese
- Long text, empty states, missing optional values and high record counts have been considered
- No private credentials or secrets remain in source code, logs or screens
- AI, open-source software, external APIs and known limitations are disclosed in the README
- You can explain the core logic, UI decisions and the AI output you substantially changed
