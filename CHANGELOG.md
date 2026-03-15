# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_Changes staged for the next release go here._

---

## [0.1.0] — 2026-03-04

### Added

#### Core Platform
- Multi-agent Council of Three AI Agents (Legacy Keeper, Innovator, Mediator) with structured multi-turn debate before proposal generation
- RAG pipeline using pgvector + FastEmbed (BAAI/bge-small-en-v1.5, runs locally) for grounding proposals in uploaded project documents
- Stakeholder profiling with Mendelow Power/Interest Matrix, sentiment tracking (Champion → Blocker), and AI-generated communication plans
- Persistent persona chat — users can debate proposals directly with the AI persona that wrote them
- Proposal approval workflow (Draft → Pending Approval → In Review → Approved / Rejected / Revision Needed)
- Jira and Confluence integration for exporting approved proposals
- Async document indexing via Celery + Redis so uploads never block the UI
- Fernet encryption for sensitive stakeholder data at rest
- JWT authentication with access and refresh tokens, role-based access control (ADMIN / MANAGER / USER), and project-level roles (OWNER / ADMIN / EDITOR / VIEWER)
- Maintenance mode middleware with admin bypass
- Token usage tracking and cost calculation per API call, persisted to database

#### Research & Evaluation Module
- Controlled A/B experiment framework: Condition A (single-agent baseline) vs Condition B (multi-agent Council)
- Counterbalanced condition order assignment per participant (BASELINE_FIRST / MULTIAGENT_FIRST)
- 4 seeded experiment scenarios: Payment Service Migration, Real-Time Analytics Pipeline, Authentication Modernisation, Media Storage Scaling
- 7-item trust questionnaire (RQ1: trust, risk awareness, technical soundness, balance, actionability, completeness)
- Persona consistency coding tool for researcher (RQ2: bias alignment, hallucination rating, in-character rating)
- Debate metrics: conflict density, consensus confidence, rounds-to-consensus, per-persona consistency scores (RQ3)
- Exit survey with system preference, fatigue, and free-text feedback
- Thesis analytics dashboard with SPSS/R data export (debates.csv, questionnaires.csv, persona_codings.csv)
- Thematic analysis panel for exit survey free-text responses

#### Infrastructure
- Docker Compose setup for development (hot-reload) and production (Nginx + pre-built static bundle)
- Alembic database migrations with 5 versioned migration files
- Comprehensive health check endpoint reporting database, encryption, and maintenance mode status
- Structured logging with structlog + JSON format
- Exponential backoff retry (tenacity) for all Anthropic API calls
- Prompt caching support (up to 90% cost reduction on repeated system prompts)
- Extended thinking support (10,000 token budget) for complex reasoning tasks
- Rate limiting middleware with sliding-window algorithm (Redis sorted sets), three tiers: authenticated users, auth endpoints, anonymous IP traffic

#### Admin Console
- User management (create, activate/deactivate, role assignment)
- Project oversight across all users
- Prompt template CRUD (edit persona system prompts without redeploying)
- System settings (maintenance mode toggle, AI model selection, RAG toggle)
- Experiment data export panel
- Persona deviation coding interface for researcher
- Token usage analytics and recent activity feed

### Fixed
- RAG retrieval scoped to the current project only, preventing cross-project document leakage in multi-tenant deployments
- JSONB debate history mutation now calls `flag_modified()` to ensure SQLAlchemy flushes in-place list changes to the database
- `ProposalVariation.add_chat_message()` reassigns to a new list instead of mutating in-place, ensuring JSONB changes are tracked by the ORM

### Security
- Sensitive stakeholder fields encrypted at rest using Fernet symmetric encryption
- Prompt injection detection on all user inputs before sending to Claude API
- JWT secret and encryption key validated on application startup — hard failure if missing
- API docs (`/docs`, `/redoc`) disabled automatically in production environment

---

## How to Update This File

When you make a change, add an entry under `[Unreleased]` using these categories:

- **Added** — new features
- **Changed** — changes to existing behaviour
- **Deprecated** — features that will be removed in a future release
- **Removed** — features removed in this release
- **Fixed** — bug fixes
- **Security** — security fixes or improvements

When cutting a release, rename `[Unreleased]` to `[x.y.z] — YYYY-MM-DD` and add a new empty `[Unreleased]` section above it.

[Unreleased]: https://github.com/rmusayevr/simurgh-ai/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rmusayevr/simurgh-ai/releases/tag/v0.1.0