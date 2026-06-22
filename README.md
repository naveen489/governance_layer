# IncuBrix Governance Layer

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Status](https://img.shields.io/badge/status-Internal_Alpha-orange)
![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen)
![React](https://img.shields.io/badge/react-18-61DAFB?logo=react&logoColor=black)
![License](https://img.shields.io/badge/license-Proprietary-red)

The **IncuBrix Governance Layer (Capability 3)** is a standalone policy and control system for video generation workflows. It evaluates policy, manages approvals, records immutable audit events, handles rights manifests, manages exceptions, and oversees retention policies — all fully independent of live provider integrations.

---

## 📑 Table of Contents
- [Features](#-features)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
  - [Backend Setup](#1-backend-setup)
  - [Frontend Setup](#2-frontend-setup)
- [Usage Guide](#-usage-guide)
  - [The Admin Dashboard](#the-admin-dashboard)
  - [Role-Based Access](#role-based-access)
- [Core Concepts](#-core-concepts)
  - [Governance States](#governance-states)
  - [Database Schema](#database-schema)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Seed Data Details](#-seed-data-details)

---

## ✨ Features

- **Policy Evaluator Engine**: Rule-based JSON evaluation against incoming requests and generation assets.
- **Approval State Machine**: Extended Finite State Machine (FSM) managing the lifecycle from draft to deletion, including `changes_requested` and `escalated` workflows.
- **Immutable Audit Trail (Tamper-Evident)**: Every state transition logs an immutable governance event, chained via SHA-256 event hashes and fully searchable via keyword query (`q`).
- **Automated Retention & Expiry**: Built-in APScheduler handles data expiry, and automatically reverts requests when temporary exceptions expire.
- **Provider Registry**: Manage risk classes, moderation styles, and verification status for downstream generative models.
- **Incidents & Legal Holds**: Fully integrated capability to flag specific items for targeted investigation or freeze them entirely for legal compliance.
- **Publish Gate**: Multi-factor downstream policy gate to dynamically verify provenance, rights manifests, and block unapproved assets from publishing.
- **Policy Simulation**: Run proposed JSON policy changes against historical or golden payloads before activating them in production.
- **Standalone MVP**: Operates independently with mock jobs, mock assets, and simulated provider events without needing the full IncuBrix stack.
- **Dark-Mode UI**: A premium Vite + React administrative dashboard to view queues, exceptions, policies, provider registries, incident alerts, and audit logs.

---

## 🏗 Architecture

The Governance Layer is divided into a decoupled backend and frontend:

```text
governance/
├── governance/          # Python package (FastAPI backend)
│   ├── engine/          # Core logic (Evaluator, FSM, Retention, Rights)
│   ├── models/          # SQLAlchemy ORM models
│   ├── routers/         # API endpoints (Requests, Assets, Reviews, etc.)
│   ├── schemas/         # Pydantic v2 validation schemas
│   ├── seed/            # Mock data bootstrapping
│   ├── database.py      # SQLite / Postgres configuration
│   ├── main.py          # FastAPI application entry
│   └── scheduler.py     # Background retention/expiry jobs
├── tests/               # Pytest suite (Unit & Integration)
└── ui/                  # Vite + React Admin UI
    └── src/
        ├── components/  # Reusable UI (Sidebar, Header, etc.)
        └── pages/       # Dashboard, Reviews, Assets, Policies, Exceptions, Audit
```

---

## 📋 Prerequisites

Ensure you have the following installed on your local machine:
- **Python 3.10+**
- **Node.js 18+** & **npm**
- Git

---

## 🚀 Quick Start

Follow these steps to get the full application running locally with seeded data.

### 1. Backend Setup

Open a terminal and navigate to the `governance` directory:

```bash
cd governance

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed the database with mock users, policies, assets, and events
python -m governance.seed.seed_data

# Start the FastAPI server
uvicorn governance.main:app --reload --port 8001
```
*The backend will be available at [http://localhost:8001](http://localhost:8001).*
*Interactive API Docs: [http://localhost:8001/docs](http://localhost:8001/docs).*

### 2. Frontend Setup

Open a **new** terminal window and navigate to the UI directory:

```bash
cd governance/ui

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```
*The admin UI will be available at [http://localhost:5174](http://localhost:5174).*

---

## 💻 Usage Guide

### The Admin Dashboard
Navigate to `http://localhost:5174` in your browser. The UI provides several key modules:
- **Dashboard**: High-level metrics, request state distributions, and recent audit activity.
- **Review Queue**: Action items that were flagged by the policy evaluator as `review_required`.
- **Assets**: Searchable registry of all generated videos and their Governance states.
- **Policies**: Interface to manage JSON rulesets for requests, assets, and retention.
- **Exceptions**: Workflows to request temporary business overrides on blocked requests.
- **Audit Log**: An immutable, filterable ledger of every action taken within the system.

### Workspace & Role-Based Access
For the Alpha MVP, the API relies on JSON Web Tokens (JWT) for authentication. When interacting with the API directly, you can obtain a mock Bearer token via the `/api/governance/auth/token` endpoint. 

By default, the UI connects using a mock token for `user_id: "admin_01"` within the `"default"` workspace, allowing seamless demonstration of the Strict Workspace Isolation feature.

---

## 🧠 Core Concepts

### Governance States
Every request and asset travels through a strict state machine:
```text
draft → policy_passed → approved_for_execution → executed → asset_registered
      → review_required → (approved_for_execution | rejected | exception_pending)
      → blocked → exception_pending → (exception_approved | rejected)
      → governance_passed → expired → deleted
```

### Database Schema
By default, the application uses an embedded SQLite database (`governance.db`). This can be overridden in production using the `DATABASE_URL` environment variable.

| Table | Description |
|-------|-------------|
| `governance_requests` | Generation requests paired with their policy decisions |
| `governance_assets` | Output assets with provenance and generated rights manifests |
| `governance_events` | Immutable audit trail capturing every state change |
| `governance_exceptions` | Exception override requests and approvals |
| `governance_policies` | Versioned JSON policy rule sets |
| `legal_holds` | Active and released legal and incident holds applied to system targets |
| `incidents` | Tracked security/compliance events with resolution statuses |
| `provider_policy_profiles` | Risk models, behaviors, and settings for supported Generative AI models |

---

## 🌐 API Reference

The backend exposes a comprehensive RESTful API. Below are the primary endpoints. *(See `/docs` for the full schema).*

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/governance/requests` | Create and automatically evaluate a new request |
| `GET`  | `/api/governance/requests/{id}` | Retrieve request details and current state |
| `POST` | `/api/governance/assets/evaluate`| Register a generated asset and evaluate against policy |
| `GET`  | `/api/governance/assets/{id}/manifest`| Download the Rights Manifest JSON |
| `POST` | `/api/governance/reviews/{id}/decision`| Submit a human decision (Approve/Reject) |
| `POST` | `/api/governance/exceptions` | Submit an exception request for a blocked item |
| `PATCH`| `/api/governance/exceptions/{id}`| Approve or reject an exception request |
| `POST` | `/api/governance/legal-holds` | Create a targeted legal or incident hold |
| `POST` | `/api/governance/incidents`  | Register a new security or compliance incident |
| `GET`  | `/api/governance/provider-profiles` | Retrieve the active provider intelligence registry |
| `POST` | `/api/governance/simulate/scenarios/run` | Simulate policy changes across seeded scenario payloads |
| `GET`  | `/api/governance/events` | Query the immutable audit log (supports keyword and correlation filtering) |
| `GET`  | `/api/governance/events/integrity-check` | Validate the SHA-256 chain integrity of the audit log |

---

## 🧪 Testing

The system includes a robust suite of unit and integration tests covering the state machine, policy evaluator, and all API endpoints.

To run the test suite:
```bash
cd governance
# Ensure the virtual environment is active
python -m pytest tests/ -v
```
*(Tests utilize an isolated in-memory SQLite database and do not interfere with local development data).*

---

## 🌱 Seed Data Details

When running the `seed_data.py` script, the database is populated with a rich set of realistic mock data to facilitate UI testing:
- **20 Requests**: (5 Safe, 5 Warned, 5 Review Required, 5 Blocked)
- **20 Assets**: Accompanied by provenance data and rights manifests
- **3 Retention Classes**: (Short = 7d, Standard = 30d, Extended = 90d)
- **3 Policy Versions**: Spanning request, asset, and retention scopes
- **9 Mock Users**: Spanning all RBAC roles
- **10 Exceptions**: Demonstrating Pending, Approved, Rejected, and Expired states
- **3 Provider Profiles**: Built-in configurations for OpenAI, Runway, and FAL AI
- **100+ Events**: A fully populated, hash-chained audit trail

---
