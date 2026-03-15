/**
 * Static pre-generated experiment responses.
 *
 * Each scenario has:
 *   - baseline:   BaselineVariationRead  (single-agent proposal)
 *   - multiagent: DebateResult           (council debate + consensus)
 *
 * Persona values must match AgentPersona enum: "LEGACY_KEEPER" | "INNOVATOR" | "MEDIATOR"
 */

import type { BaselineVariationRead, DebateResult } from '../types';
import { ConsensusType } from '../types';

// ─── Scenario A: Payment Service Migration ────────────────────────────────────

const scenarioA_baseline: BaselineVariationRead = {
    id: 101,
    agent_persona: 'STANDARD',
    reasoning: null,
    confidence_score: 0.82,
    proposal_id: 1,
    generation_time_seconds: 4.1,
    structured_prd: `# Architectural Proposal: Payment Service Migration

## Executive Summary
Migrate payment processing out of the Rails monolith into a dedicated, independently scalable service within 6 months, while maintaining PCI-DSS Level 1 compliance and achieving zero data loss during transition.

## Recommended Architecture: Phased Microservice Extraction with Strangler Fig Pattern

### Phase 1 — Introduce a Payment Facade (Weeks 1–4)
Deploy a lightweight API gateway (e.g. Kong or AWS API Gateway) in front of the existing Rails payment code. All payment requests are routed through this facade without changing internal logic. This immediately decouples the payment interface from the monolith's routing layer and provides a stable contract for future consumers.

### Phase 2 — Extract the Payment Microservice (Weeks 5–14)
Build a new, dedicated payment service in a language suited to financial workloads (Node.js with TypeScript or Go). The service owns its own PostgreSQL schema — separated from the monolith database using schema-level isolation first, then migrated to a standalone RDS instance with Multi-AZ enabled. Implement dual-write during migration: all payment events are written to both the legacy monolith tables and the new service database, with a reconciliation job running nightly to detect drift. Once reconciliation shows zero discrepancy across two consecutive weeks, cut over fully.

### Phase 3 — PCI-DSS Hardening (Weeks 15–20)
- **Network segmentation**: Place the payment service in a dedicated VPC subnet with strict ingress/egress rules (no direct internet access; all external calls via the payment facade).
- **Tokenisation**: Integrate with Stripe, Adyen, or Braintree for card data tokenisation — no raw PANs ever touch application memory or logs.
- **Audit logging**: All payment events emitted to an append-only audit log (CloudWatch Logs or Datadog with tamper-evident hashing).
- **Encryption**: TLS 1.3 in transit; AES-256 at rest for all sensitive fields.
- **Penetration testing**: Schedule a third-party PCI pen test before go-live.

### Queue / Resilience Layer
Introduce RabbitMQ (or AWS SQS) between the facade and the new payment service to buffer bursts. This directly addresses the Black Friday scaling failures: the queue absorbs spikes and the payment service can scale horizontally (3–10 pods) independent of the Rails monolith.

## Trade-offs Considered
| Option | Pros | Cons |
|---|---|---|
| Microservice extraction (recommended) | Independent scaling, clean compliance boundary, long-term maintainability | Higher upfront effort, requires dual-write migration period |
| Queue/cache in front of existing code | Low risk, fast to ship | Does not solve underlying scalability; monolith still owns payment logic |
| Third-party orchestration (Stripe Billing, etc.) | Fastest compliance path | High vendor lock-in, expensive at scale, limited customisation |

## Risk Mitigation
- **Data loss prevention**: Dual-write + nightly reconciliation job before cutover.
- **Rollback plan**: Facade routes can revert traffic to monolith within 5 minutes by toggling a feature flag.
- **Compliance**: Engage a Qualified Security Assessor (QSA) at Phase 3 start to confirm scope reduction.
- **Team readiness**: Allocate one senior engineer full-time to the migration; monolith team retains ownership of business logic changes during transition.

## Timeline Summary
| Week | Milestone |
|---|---|
| 1–4 | Payment facade live; routing in place |
| 5–8 | New payment service built; dual-write active |
| 9–14 | Reconciliation period; load testing |
| 15–18 | PCI hardening; pen test |
| 19–20 | Cutover; monolith payment code deprecated |

## Success Metrics
- Zero payment-related incidents during Black Friday following migration.
- P99 payment latency ≤ 300 ms under 10× normal load.
- PCI-DSS Level 1 SAQ-D or AOC renewed within 3 months of go-live.
- Zero data loss confirmed by reconciliation tool.`,
};

const scenarioA_multiagent: DebateResult = {
    id: 'static-debate-A',
    proposal_id: 1,
    consensus_reached: true,
    consensus_type: ConsensusType.COMPROMISE,
    total_turns: 5,
    duration_seconds: 38,
    conflict_density: 0.42,
    legacy_keeper_consistency: 0.91,
    innovator_consistency: 0.88,
    mediator_consistency: 0.94,
    overall_persona_consistency: 0.91,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    final_consensus_proposal: `# Architectural Proposal: Payment Service Migration
## Council Consensus — Strangler Fig Extraction with Tokenisation-First

### Executive Summary
The council unanimously recommends a phased microservice extraction using the Strangler Fig pattern, with immediate PCI scope reduction via third-party tokenisation as the mandatory first step. A payment facade decouples routing from business logic, and dual-write with nightly reconciliation gates the final cutover. Delivery: 20 weeks.

### Recommended Architecture

#### Phase 1 — Tokenisation & Facade (Weeks 1–4)
Integrate Stripe or Adyen tokenisation directly into the existing Rails monolith before any extraction begins. Raw PANs are immediately delegated to the provider; our system stores only tokens. This collapses PCI scope from SAQ-D to SAQ-A regardless of what happens in subsequent phases — it is an unambiguous risk reduction that every council member agreed on.

Simultaneously, deploy a lightweight payment facade (Kong or AWS API Gateway) in front of the Rails payment code. All payment traffic routes through this facade. The business logic is untouched; only the routing layer changes. This creates the stable API contract that the new service will honour.

#### Phase 2 — Microservice Extraction (Weeks 5–18)
Build a dedicated payment microservice in Go on Kubernetes. Go was chosen over Node.js for its performance characteristics under financial workloads and its straightforward concurrency model for event handling.

The service owns its own PostgreSQL schema, initially schema-isolated from the monolith database, then migrated to a standalone RDS instance (Multi-AZ) during Phase 2.

**Traffic migration via feature flags:**
- Week 5: 5% of payment traffic routed to new service
- Week 8: 25% — monitor P99 latency and error rates
- Week 12: 75% — confirm stability under near-production load
- Week 16: 100% cutover — monolith payment path disabled

Automated rollback triggers revert all traffic to the monolith within 5 minutes if error rate exceeds 0.1% or P99 latency exceeds 2× baseline. This rollback SLA is tested under Black Friday-scale synthetic load in staging before any production traffic is shifted.

**Dual-write and reconciliation:**
During Weeks 9–18, all payment events are written to both the legacy monolith tables and the new service database. A nightly reconciliation job compares record counts, amounts, and checksums. Cutover to the new service as the system of record occurs only after two consecutive clean weeks of reconciliation.

#### Phase 3 — Hardening & Audit (Weeks 18–20)
- Network segmentation: payment service in a dedicated VPC subnet, no direct internet access
- Audit logging: append-only PostgreSQL audit tables (PCI-sufficient, auditor-friendly)
- Queue layer: SQS or RabbitMQ between facade and payment service to absorb burst traffic — directly addressing the Black Friday scaling failures
- PCI audit: QSA engagement in Week 18; scope is now SAQ-A due to tokenisation

### Trade-offs Considered
| Option | Verdict |
|---|---|
| Queue in front of existing code only | Rejected — solves burst scaling but creates operational dependency with no long-term payoff |
| Full event sourcing | Deferred — valuable but adds learning curve; append-only audit tables are PCI-sufficient for now |
| Third-party payment orchestration (Stripe Billing) | Partially adopted — tokenisation yes, full orchestration no (vendor lock-in, limited customisation) |

### Risk Mitigation
- **PCI exposure during migration**: Tokenisation in Week 1 ensures raw PANs never enter the new service at any point
- **Data loss**: Dual-write + nightly reconciliation; two clean weeks required before cutover
- **Rollback**: Feature-flag traffic routing reverts to monolith within 5 minutes; tested under load before production use
- **Scope creep**: Rails monolith retains all non-payment business logic throughout; migration scope is strictly bounded

### Delivery Timeline
| Weeks | Milestone |
|---|---|
| 1–3 | Stripe/Adyen tokenisation live in monolith |
| 1–4 | Payment facade deployed; all traffic routed through it |
| 5–18 | Go payment service built; progressive traffic ramp (5%→25%→75%→100%) |
| 9–18 | Dual-write active; nightly reconciliation running |
| 18–20 | PCI QSA audit; monolith payment code deprecated |`,
    debate_history: [
        {
            turn_number: 0,
            persona: 'LEGACY_KEEPER',
            timestamp: new Date().toISOString(),
            sentiment: 'disagree',
            response: `## My Position: Stabilise Before You Migrate

I want to be direct: rushing a full microservice extraction within 6 months on a live payment system that must maintain PCI-DSS Level 1 is the kind of decision that ends careers and companies.

Three Black Friday outages are a scaling problem, yes — but they are not evidence that the Rails monolith cannot be fixed incrementally. Before we contemplate a full extraction, I want to know: have we exhausted the following?

1. **Read replicas and connection pooling** (PgBouncer) to isolate payment queries from catalogue reads.
2. **Horizontal scaling of the monolith's payment workers** using Sidekiq or similar.
3. **A dedicated payment queue** (RabbitMQ or SQS) in front of the *existing* Rails payment code — not a new service.

A queue layer in front of the existing code can be delivered in 4–6 weeks and directly addresses the burst-scaling failure mode. That buys us 12–18 months to plan a *proper* extraction, write comprehensive test coverage, and do a QSA-reviewed scope reduction.

**My recommendation: queue-first, extraction later.** The migration risk — dual-write bugs, schema drift, PCI audit scope creep — is simply too high on a 6-month timeline.`,
            key_points: [
                'Queue layer in front of existing code solves burst-scaling in 4–6 weeks with minimal risk',
                'Full microservice extraction in 6 months on a PCI-DSS Level 1 system is dangerously aggressive',
                'Dual-write migration introduces data-consistency risk that is hard to fully test under load',
            ],
        },
        {
            turn_number: 1,
            persona: 'INNOVATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'disagree',
            response: `## My Position: Extract Now, Tokenise Immediately

Legacy Keeper's caution is understandable but it perpetuates exactly the problem we're trying to escape. A queue in front of the existing monolith is duct tape — it delays the inevitable and adds an extra operational component with no long-term architectural benefit.

Here's what I propose instead:

**Go straight to extraction, but reduce scope dramatically by delegating card data to Stripe or Adyen on day one.**

If we tokenise immediately, raw PANs never enter our system. Our PCI scope collapses from a full SAQ-D to SAQ-A. This is not a risk — it *eliminates* the biggest risk Legacy Keeper is worried about. We no longer own sensitive card data during the migration window.

The extraction itself:
- **New payment service in Go** — lightweight, fast, easy to containerise and scale on Kubernetes.
- **Event sourcing** for all payment state — gives us a complete audit log for free, satisfies PCI logging requirements, and makes rollback trivially safe (replay events).
- **Strangler Fig** pattern: route payment traffic progressively from monolith → new service over 8 weeks.
- **Feature flag per customer segment** — start with 1% of traffic, ramp to 100% over 4 weeks once P99 latency and error rates confirm stability.

This is deliverable in 16 weeks, not 20. And we come out with a genuinely modern, scalable payment platform — not a queue bolted onto a 6-year-old codebase.`,
            key_points: [
                'Tokenisation (Stripe/Adyen) immediately collapses PCI scope from SAQ-D to SAQ-A',
                'Event sourcing provides audit log and safe rollback without dual-write complexity',
                'Progressive traffic routing via feature flags makes cutover low-risk',
                'Go microservice on Kubernetes delivers independent scaling from day one',
            ],
        },
        {
            turn_number: 2,
            persona: 'MEDIATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'neutral',
            response: `## Finding the Middle Ground

Both positions have merit and both have blind spots. Let me try to synthesise.

**Legacy Keeper is right that:**
- 6 months is a tight window for a PCI-scope-changing migration on a production payment system.
- Dual-write bugs under load are a real and underappreciated risk.
- We need a rollback plan that ops can execute in minutes, not hours.

**Innovator is right that:**
- A queue in front of the monolith solves burst scaling but creates a new operational dependency with no long-term payoff.
- Tokenisation (Stripe/Adyen) is the single highest-leverage move we can make — it immediately shrinks our PCI attack surface regardless of which architecture we choose.
- Event sourcing is genuinely safer than dual-write for audit purposes.

**My proposed synthesis:**

1. **Adopt tokenisation immediately** (Week 1–3) — this is unambiguously good regardless of extraction timeline and makes both the Legacy Keeper and the auditors happier.
2. **Introduce a payment facade / API contract** (Week 1–4) — this is low-risk and gives us the ability to route traffic without changing business logic.
3. **Extract the payment service using the Strangler Fig pattern** (Week 5–18) — but use the facade's feature flags to route incrementally, starting at 5% of traffic, with automated rollback triggers on error rate thresholds.
4. **Abandon full event sourcing for now** — it's a good idea but adds learning curve. Use append-only audit tables in PostgreSQL instead; simpler, auditor-friendly, sufficient for PCI.

This gives us a credible 20-week delivery, genuine risk controls, and a path to independence — without betting the company on a single cutover event.`,
            key_points: [
                'Tokenise first — reduces PCI scope immediately, universally agreed benefit',
                'Payment facade decouples routing without touching business logic',
                'Strangler Fig with feature-flag traffic ramp is safer than a big-bang cutover',
                'Defer event sourcing — append-only audit tables are simpler and PCI-sufficient',
            ],
        },
        {
            turn_number: 3,
            persona: 'LEGACY_KEEPER',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Revised Position: Conditional Agreement

The Mediator's framing has shifted my thinking. Tokenisation first is the key insight I was missing — if raw PANs never enter the new service during the migration window, the PCI scope risk I was most concerned about is substantially neutralised.

I can support the Strangler Fig extraction on this basis, with three conditions:

1. **Dual-write is mandatory** during the overlap period — not optional. We run nightly reconciliation and we do not cut over until we have two clean weeks.
2. **The Rails monolith retains ownership of all non-payment business logic** throughout. No scope creep into order management or inventory during this migration.
3. **The feature flag rollback must be tested** in staging under Black Friday-scale load before we touch production. Rollback SLA: traffic back to monolith within 5 minutes.

If those three conditions are met, I withdraw my objection to the extraction timeline.`,
            key_points: [
                'Tokenisation first resolves the core PCI scope concern',
                'Dual-write + reconciliation is non-negotiable before cutover',
                'Rollback tested under production-scale load before any traffic shift',
            ],
        },
        {
            turn_number: 4,
            persona: 'MEDIATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Consensus Reached

The council has converged. All three conditions from Legacy Keeper are incorporated; Innovator's tokenisation-first and feature-flag ramp approach is adopted; the event sourcing deferral is accepted.

**Final Architecture:**
- **Weeks 1–3**: Stripe/Adyen tokenisation integrated into Rails monolith — PCI scope immediately reduced.
- **Weeks 1–4**: Payment facade (API gateway) deployed; all payment traffic routed through facade.
- **Weeks 5–18**: New payment microservice (Go on Kubernetes) built and progressively receives traffic (5% → 25% → 75% → 100%) via feature flags, with automated rollback on error rate > 0.1%.
- **Weeks 9–18**: Dual-write active; nightly reconciliation job; cutover only after 2 clean weeks.
- **Weeks 19–20**: PCI audit, monolith payment code deprecated.

This is the recommendation the council endorses.`,
            key_points: [
                'Tokenisation in Week 1–3 immediately shrinks PCI surface',
                'Strangler Fig with 5%→100% traffic ramp minimises cutover risk',
                'Dual-write reconciliation gates the final cutover decision',
                'Full delivery in 20 weeks with rollback available at every stage',
            ],
        },
    ],
};

// ─── Scenario B: Real-Time Analytics Pipeline ─────────────────────────────────

const scenarioB_baseline: BaselineVariationRead = {
    id: 102,
    agent_persona: 'STANDARD',
    reasoning: null,
    confidence_score: 0.85,
    proposal_id: 2,
    generation_time_seconds: 4.4,
    structured_prd: `# Architectural Proposal: Real-Time Analytics Pipeline

## Executive Summary
Replace direct PostgreSQL analytics queries with a dedicated real-time analytics pipeline capable of ingesting 8 million events/day (scalable to 80 million), serving dashboard metrics with sub-5-second latency, and supporting ad-hoc SQL — within a €15 k/month additional cloud budget.

## Recommended Architecture: Streaming Ingest → OLAP Store → Query Layer

### Component 1 — Event Ingest: Apache Kafka (or AWS Kinesis)
All application events (user actions, transactions, API calls) are published to Kafka topics. Kafka decouples the write path from analytics entirely — the production PostgreSQL database is no longer touched by analytics reads or writes. At 8 million events/day (~93 events/sec average, with peaks up to ~5× that), a 3-broker Kafka cluster comfortably handles the load. For managed simplicity within budget, consider **Confluent Cloud** (serverless tier) or **AWS Kinesis Data Streams**.

### Component 2 — Stream Processing: Apache Flink or AWS Kinesis Data Analytics
A stream processor consumes Kafka topics in real-time and:
- Aggregates metrics into pre-computed windows (5-min, 1-hour, 1-day).
- Writes aggregated results to the OLAP store.
- Handles late-arriving events with watermarking.

For teams without Flink expertise, **dbt + Airbyte** running on a short schedule (every 60 seconds) is a simpler alternative that sacrifices some latency for operational simplicity.

### Component 3 — OLAP Store: ClickHouse (self-managed) or Apache Pinot
**ClickHouse** is the primary recommendation:
- Columnar storage with vectorised query execution — ad-hoc SQL runs 10–100× faster than PostgreSQL on analytical workloads.
- Handles 80 million events/day on a 3-node cluster with ~€2,500/month in cloud compute (c5.2xlarge equivalent).
- Supports real-time inserts at >100k rows/sec.
- Native SQL interface — data team learns nothing new.
- **Materialized views** serve pre-aggregated dashboard metrics at <500 ms.

Alternative: **Snowflake** or **BigQuery** for fully managed options, but at the upper end of the budget.

### Component 4 — Query API: FastAPI or GraphQL Gateway
A thin query layer sits between the dashboard and ClickHouse. It:
- Enforces multi-tenant row-level security.
- Caches frequent dashboard queries in Redis (TTL 30 seconds) to reduce ClickHouse load.
- Provides a stable API contract so the dashboard does not query ClickHouse directly.

### PostgreSQL Relief
The production PostgreSQL read replica is immediately relieved of all analytics traffic once the pipeline is live. A one-time historical data backfill (pg_dump → ClickHouse) seeds the OLAP store with pre-pipeline history.

## Budget Estimate (Monthly)
| Component | Option | Est. Cost |
|---|---|---|
| Kafka / Kinesis | Confluent Cloud Essentials | €400 |
| ClickHouse cluster (3×c5.2xl) | AWS EC2 + EBS | €2,800 |
| Stream processor | Kinesis Data Analytics | €600 |
| Query API (ECS Fargate) | 2 tasks | €150 |
| Redis cache | AWS ElastiCache | €120 |
| Monitoring (Datadog / Grafana Cloud) | — | €300 |
| **Total** | | **~€4,370/month** |

Well within the €15 k/month ceiling, leaving headroom for 10× growth scaling.

## Latency Targets
| Query type | Target | Mechanism |
|---|---|---|
| Pre-aggregated dashboard tiles | < 500 ms | ClickHouse materialized views + Redis cache |
| Ad-hoc SQL (data team) | < 5 s (p95) | ClickHouse columnar scan |
| Event availability (recency) | < 10 s end-to-end | Kafka → Flink → ClickHouse pipeline latency |

## Migration Plan
1. **Week 1–2**: Provision Kafka and ClickHouse; instrument application to dual-publish events.
2. **Week 3–4**: Historical backfill; validate data parity with production PostgreSQL.
3. **Week 5–6**: Redirect dashboard queries to new pipeline; monitor error rates.
4. **Week 7**: Remove analytics queries from PostgreSQL read replica; confirm CPU normalises.

## Risk Mitigation
- **Data team disruption**: ClickHouse supports standard SQL; no retraining required.
- **Backfill consistency**: Run reconciliation queries comparing PostgreSQL aggregates to ClickHouse totals before cutover.
- **Vendor lock-in**: ClickHouse is open-source; self-managed deployment avoids cloud-vendor lock-in.`,
};

const scenarioB_multiagent: DebateResult = {
    id: 'static-debate-B',
    proposal_id: 2,
    consensus_reached: true,
    consensus_type: ConsensusType.COMPROMISE,
    total_turns: 5,
    duration_seconds: 41,
    conflict_density: 0.38,
    legacy_keeper_consistency: 0.89,
    innovator_consistency: 0.87,
    mediator_consistency: 0.93,
    overall_persona_consistency: 0.90,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    final_consensus_proposal: `# Architectural Proposal: Real-Time Analytics Pipeline
## Council Consensus — ClickHouse + Kafka with Redis Caching

### Executive Summary
The council recommends replacing direct PostgreSQL analytics queries with a dedicated ClickHouse OLAP database fed by a Kafka event stream. A Redis caching layer serves pre-aggregated dashboard metrics at sub-500ms latency. Ad-hoc SQL queries run directly against ClickHouse. Historical data is backfilled before cutover. Estimated monthly cost: ~€4,400 — well within the €15k budget and scalable to 10× event volume without architectural change.

### Recommended Architecture

#### Ingestion Layer — Kafka (Confluent Cloud managed)
All application events (~8 million/day, projected 80 million/day at 10× growth) are published to a Kafka topic via a lightweight producer library in the application. Confluent Cloud managed Kafka is used rather than self-hosted to keep operational overhead low for the current team — no Kafka cluster management, automatic scaling, and built-in schema registry.

The Kafka consumer writes events to ClickHouse using ClickHouse's native Kafka table engine, which handles batching, offset tracking, and exactly-once delivery semantics. No separate consumer process is required.

#### Storage Layer — ClickHouse
ClickHouse is an OLAP columnar database purpose-built for the query patterns this use case demands: aggregations over large time ranges, GROUP BY on high-cardinality dimensions, and concurrent dashboard queries without degrading write throughput.

Key configuration decisions:
- **Materialized views** pre-aggregate the 12 most common dashboard metrics (daily active users, revenue by segment, funnel conversion rates) at ingestion time. These queries return in <100ms regardless of data volume.
- **ReplicatedMergeTree** engine with 2-node replication for high availability
- **TTL policies** automatically tier data older than 90 days to S3-compatible object storage (Cloudflare R2), keeping ClickHouse storage costs flat as data grows
- **Ad-hoc SQL** queries from the data team run directly against ClickHouse without impacting the pre-aggregated dashboard paths

#### Caching Layer — Redis
A Redis cache sits between the dashboard API and ClickHouse for the pre-aggregated metrics. Cache TTL of 30 seconds — metrics are near-real-time, not live, which is acceptable for business dashboards. Cache hit rate is expected to exceed 90% during business hours, keeping ClickHouse query load minimal during peak times.

#### Migration Plan (No Downtime)
1. **Weeks 1–2**: Deploy Kafka (Confluent Cloud) and begin dual-writing all new events to both PostgreSQL (existing) and Kafka → ClickHouse
2. **Weeks 3–6**: Backfill historical PostgreSQL data into ClickHouse using a one-time migration script with chunked batches to avoid production DB impact. Run during off-peak hours.
3. **Weeks 7–8**: Switch dashboard API to read from Redis/ClickHouse. Validate query results against PostgreSQL for 1 week. PostgreSQL read replica relieved of all analytics queries.
4. **Week 9+**: Decommission analytics queries against PostgreSQL. Read replica CPU drops to normal operational levels.

### Cost Estimate (Monthly)
| Component | Cost |
|---|---|
| Confluent Cloud Kafka (8M events/day) | ~€800/month |
| ClickHouse Cloud (2 nodes, 500GB storage) | ~€2,200/month |
| Redis Cache (managed, 4GB) | ~€200/month |
| Cloudflare R2 (cold storage tier) | ~€150/month |
| Egress and monitoring | ~€150/month |
| **Total** | **~€3,500/month** |

Well within the €15k/month budget. At 10× event volume, Confluent Cloud and ClickHouse scale horizontally; estimated cost at 10× remains under €12k/month.

### Trade-offs Considered
| Option | Verdict |
|---|---|
| PostgreSQL read replica + aggressive indexing | Rejected — already at 95% CPU; this is a fundamental architecture mismatch for OLAP workloads |
| Apache Flink for stream processing | Deferred — powerful but significant operational complexity; ClickHouse materialized views are sufficient for current aggregation needs |
| Self-hosted Kafka | Rejected — managed Kafka cost premium is justified by eliminating cluster operations for the current team size |
| Snowflake / BigQuery | Rejected — egress costs and query pricing unpredictable at 10× scale; ClickHouse on fixed-cost infrastructure is preferable |

### Risk Mitigation
- **Query correctness**: Shadow mode — ClickHouse results validated against PostgreSQL for one week before cutover
- **Backfill risk**: Chunked batches during off-peak hours; PostgreSQL production traffic unaffected
- **Kafka consumer lag**: Confluent Cloud consumer lag monitoring with PagerDuty alerts; lag threshold of 5 minutes triggers on-call
- **ClickHouse availability**: ReplicatedMergeTree ensures no single point of failure; Confluent Cloud SLA is 99.95%`,
    debate_history: [
        {
            turn_number: 0,
            persona: 'LEGACY_KEEPER',
            timestamp: new Date().toISOString(),
            sentiment: 'neutral',
            response: `## My Position: Don't Introduce More Moving Parts Than Necessary

We have a 2 TB PostgreSQL database that works — it just can't handle analytics reads alongside transactional writes. Before we introduce Kafka, Flink, ClickHouse, and a stream processing layer, I want us to seriously consider two simpler interventions:

**Option A — Read-replica offloading with a time-series extension**
TimescaleDB can be deployed on a read replica *today*. It compresses time-series data aggressively, adds hypertable partitioning, and supports continuous aggregates that behave like ClickHouse materialized views. The data team keeps writing SQL they know. No new infrastructure category. Estimated cost: €600/month for a large RDS read replica.

**Option B — Scheduled materialisation with dbt**
Run dbt models every 60–120 seconds against a dedicated analytics replica. Results land in a summary schema queried by the dashboard. Latency: 60–120 s. For most dashboard use cases, this is indistinguishable from "real-time."

My concern with the full Kafka + ClickHouse stack is operational complexity. We're a product team — we don't have a data engineering team. Who manages Kafka broker failover at 2 AM? Who handles schema evolution when the application team adds a new event field?

If the data team truly needs ad-hoc sub-5-second SQL at 10× scale, ClickHouse is probably the right destination. But I'd want us to start with TimescaleDB and only migrate to ClickHouse when we hit a ceiling we can actually measure.`,
            key_points: [
                'TimescaleDB on a read replica solves the immediate problem with no new infrastructure category',
                'dbt scheduled materialisation can deliver "near-real-time" at 60–120 s latency at very low cost',
                'Kafka + Flink + ClickHouse requires data engineering expertise the team may not have',
            ],
        },
        {
            turn_number: 1,
            persona: 'INNOVATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'disagree',
            response: `## My Position: Build for 10× Now, Not for Today

Legacy Keeper's TimescaleDB suggestion solves today's problem and creates next year's crisis. We are approaching 500 customers with a projected 10× event growth in 12 months. TimescaleDB on a read replica will hit its ceiling before we finish celebrating the initial deployment.

Here's why TimescaleDB isn't enough at scale:
- PostgreSQL's row-oriented storage is fundamentally ill-suited for analytical aggregations over billions of rows. TimescaleDB adds compression and partitioning but doesn't change the execution model.
- At 80 million events/day, ad-hoc SQL on a PostgreSQL-based system will degrade again. We'll be back here in 12 months planning the same migration under more pressure.

**My recommendation: Kafka + ClickHouse, deployed as managed services to address the operational concern.**

Specifically:
- **Confluent Cloud** (serverless Kafka) — no broker management, autoscaling, €400/month at our volume. The 2 AM failover concern is Confluent's problem, not ours.
- **ClickHouse Cloud** (managed ClickHouse) — fully managed, autoscaling, no cluster administration. ~€1,500–2,500/month depending on query volume.
- **No Flink** — at 8M events/day, Kafka → ClickHouse direct ingest (using the Kafka table engine) is sufficient. Sub-10-second end-to-end latency without a stream processor.

The operational complexity argument evaporates when you use managed services. And we come out with an architecture that genuinely scales to 80M events/day and beyond.`,
            key_points: [
                'TimescaleDB will hit a ceiling at 80M events/day — build for 10× now',
                'Managed Confluent Cloud + ClickHouse Cloud eliminates the operational complexity concern',
                'Kafka → ClickHouse direct ingest (no Flink) is sufficient at our event volume',
            ],
        },
        {
            turn_number: 2,
            persona: 'MEDIATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'neutral',
            response: `## Synthesis: Managed ClickHouse, Skip the Intermediate Step

Both positions are internally consistent. The disagreement comes down to one question: is TimescaleDB a useful intermediate step, or does it just delay an inevitable migration to a columnar store?

Given the 10× growth projection and the €15 k/month budget headroom, I think the Innovator is right that we should go directly to ClickHouse. The budget clearly accommodates it, and a two-stage migration (PostgreSQL → TimescaleDB → ClickHouse) doubles the migration risk.

However, Legacy Keeper is right about operational complexity. The answer is to use **managed services**, not to regress to a simpler architecture.

**My proposed architecture:**
1. **Confluent Cloud** (serverless Kafka) — event ingest, ~€400/month. No broker management.
2. **ClickHouse Cloud** — OLAP store, ~€2,000/month. Fully managed, autoscaling.
3. **No stream processor** — Kafka native table engine in ClickHouse handles direct ingest at our volume.
4. **Redis (ElastiCache)** — cache pre-aggregated dashboard tiles, TTL 30s. ~€120/month.
5. **dbt** — for the data team's transformations, running against ClickHouse. Familiar tooling.
6. **Historical backfill** from PostgreSQL before cutover; reconciliation gates go-live.

This gives Legacy Keeper operational simplicity (managed services, no Kafka expertise required) and gives Innovator the scalable columnar architecture. Total cost: ~€4,400/month — well within budget.`,
            key_points: [
                'Skip TimescaleDB — go directly to ClickHouse given budget headroom and 10× growth target',
                'Managed Confluent Cloud + ClickHouse Cloud resolves operational complexity concerns',
                'Kafka→ClickHouse native table engine eliminates need for a stream processor at current volume',
                'dbt for data team transformations maintains familiar SQL workflow',
            ],
        },
        {
            turn_number: 3,
            persona: 'LEGACY_KEEPER',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Revised Position: Agreed with Conditions

The managed-services framing changes my calculus significantly. If Confluent Cloud handles Kafka operations and ClickHouse Cloud handles cluster management, then my operational complexity concern is substantially addressed.

I accept this architecture with two conditions:

1. **Backfill and reconciliation before cutover.** We run reconciliation queries comparing PostgreSQL aggregates to ClickHouse for a minimum of 1 week before redirecting dashboard traffic. This is non-negotiable.
2. **The PostgreSQL read replica stays running in read-only mode for 30 days post-cutover** as a fallback data source — not serving dashboard queries, but available for emergency analytical queries if ClickHouse has an incident.

With those two conditions, I support the proposed architecture.`,
            key_points: [
                'Managed services address the operational concern — agreement conditional on backfill/reconciliation',
                'PostgreSQL read replica retained for 30 days post-cutover as emergency fallback',
            ],
        },
        {
            turn_number: 4,
            persona: 'MEDIATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Consensus Reached

Both conditions from Legacy Keeper are incorporated — they are low-cost and prudent. The council unanimously endorses the following architecture:

**Final Recommendation:**
- **Confluent Cloud** (serverless Kafka) — event ingest from all application services.
- **ClickHouse Cloud** — primary OLAP store; Kafka native table engine for direct ingest; materialized views for dashboard metrics.
- **Redis (ElastiCache)** — dashboard tile cache, 30-second TTL.
- **dbt** — data team transformation layer on top of ClickHouse.
- **Historical backfill** from PostgreSQL + 1-week reconciliation gate before cutover.
- **PostgreSQL read replica** retained in standby for 30 days post-cutover.
- **Estimated cost**: ~€4,400/month — 70% below the €15 k/month ceiling, with clear headroom for 10× growth.`,
            key_points: [
                'Confluent Cloud + ClickHouse Cloud: fully managed, no specialist ops required',
                'Sub-5-second dashboard latency via materialized views + Redis cache',
                '1-week reconciliation gate before cutover; PostgreSQL replica retained 30 days',
                '~€4,400/month — well within budget, scalable to 80M+ events/day',
            ],
        },
    ],
};

// ─── Scenario C: Authentication Modernisation ─────────────────────────────────

const scenarioC_baseline: BaselineVariationRead = {
    id: 103,
    agent_persona: 'STANDARD',
    reasoning: null,
    confidence_score: 0.83,
    proposal_id: 3,
    generation_time_seconds: 4.2,
    structured_prd: `# Architectural Proposal: Authentication Modernisation

## Executive Summary
Modernise authentication and authorisation for 520,000 active users to support a native mobile app, a scoped developer API, and enterprise SSO — without forcing any existing user to re-authenticate, maintaining GDPR compliance, and delivered within 9 months by a team of 6 engineers.

## Recommended Architecture: Auth0 / Keycloak Identity Platform + Silent Migration

### Core Decision: Standards-Based Identity Platform
Replace the custom PHP session system with an industry-standard identity platform that natively supports:
- **OAuth 2.0 + OIDC** — mobile app and developer API token issuance.
- **SAML 2.0 / OIDC federation** — enterprise SSO for the 40 business accounts.
- **JWT access tokens + refresh tokens** — stateless, scalable session management.

**Recommended platform**: **Auth0** (managed) or **Keycloak** (self-hosted, open-source).

| | Auth0 | Keycloak |
|---|---|---|
| Operational burden | Low (fully managed) | High (self-hosted, tuning required) |
| Cost at 520k MAU | ~€2,000–3,500/month | ~€400/month (compute only) |
| SSO / SAML support | ✅ Native | ✅ Native |
| GDPR data residency | EU regions available | Full control |
| Mobile SDK | ✅ First-class | ✅ Community SDKs |

**Recommendation**: Auth0 for teams prioritising delivery speed; Keycloak if GDPR data-residency control or budget is paramount.

### Silent Migration Strategy (Zero Re-Authentication)
This is the most critical constraint. The approach:

1. **Deploy the new identity platform in parallel** alongside the PHP session system.
2. **Intercept login attempts**: when a user logs in via the PHP system, simultaneously validate their credentials and provision a new identity in the identity platform (first-time migration on login).
3. **Dual-session issuance**: the PHP system continues issuing its session cookies; the identity platform issues JWTs to new clients (mobile app, API consumers).
4. **Progressive sunset**: once >95% of active users have silently migrated (estimated 3–4 months based on monthly active user login frequency), retire PHP session creation. Users who haven't logged in in 4+ months are prompted to reset their password on next login — this is acceptable under GDPR as a security measure.

No user is ever forced to re-authenticate unexpectedly. The migration happens transparently on their next natural login event.

### Developer API: OAuth 2.0 Scoped Tokens
The identity platform issues OAuth 2.0 access tokens with fine-grained scopes (e.g. \`read:data\`, \`write:orders\`, \`admin:billing\`). Developers register applications in a self-service portal. Token introspection endpoint exposed at \`/oauth/introspect\` for resource servers. Refresh token rotation with short-lived access tokens (15-minute expiry).

### Enterprise SSO
For the 40 enterprise accounts:
- Support SAML 2.0 IdP federation (Okta, Azure AD, Google Workspace).
- Each enterprise tenant is a separate "Connection" in Auth0 / Realm in Keycloak.
- Just-In-Time (JIT) provisioning: enterprise users are auto-provisioned on first SSO login without manual admin intervention.
- Attribute mapping: map IdP claims (department, role) to application roles.

### GDPR Compliance
- **Data minimisation**: identity platform stores only authentication data (email, hashed credential, MFA factors). Application-level PII remains in the application database.
- **Right to erasure**: deleting a user in the identity platform cascades to revoke all active tokens; application-level data deletion handled separately.
- **Audit logs**: all authentication events (login, logout, token refresh, failed attempts) logged to an append-only audit store, retained for 12 months.
- **Consent**: existing users' consent obtained during the silent migration login flow via a lightweight consent banner (does not interrupt the login, displayed post-login).

## Delivery Timeline (9 months, 6 engineers)
| Phase | Duration | Work |
|---|---|---|
| Phase 1: Foundation | Weeks 1–6 | Identity platform provisioned; PHP login interceptor built; silent migration active for internal users |
| Phase 2: Mobile + API | Weeks 7–14 | Mobile app shipped with OIDC; developer API with OAuth 2.0 scopes launched |
| Phase 3: Enterprise SSO | Weeks 15–22 | SAML federation for 40 enterprise accounts; JIT provisioning |
| Phase 4: Sunset | Weeks 23–36 | PHP session system progressively retired as migration % climbs |

## Risk Mitigation
- **Silent migration failure**: if the identity platform is unavailable, the PHP system falls back to issuing sessions normally (degraded mode, no new-client functionality, but zero downtime for existing users).
- **SSO misconfiguration**: each enterprise SSO connection is tested in a staging tenant before production activation.
- **GDPR consent**: legal review of consent banner language before Phase 1 go-live.`,
};

const scenarioC_multiagent: DebateResult = {
    id: 'static-debate-C',
    proposal_id: 3,
    consensus_reached: true,
    consensus_type: ConsensusType.COMPROMISE,
    total_turns: 5,
    duration_seconds: 36,
    conflict_density: 0.35,
    legacy_keeper_consistency: 0.90,
    innovator_consistency: 0.86,
    mediator_consistency: 0.92,
    overall_persona_consistency: 0.89,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    final_consensus_proposal: `# Architectural Proposal: Authentication Modernisation
## Council Consensus — Keycloak with Silent On-Login Migration

### Executive Summary
The council recommends deploying a self-hosted Keycloak identity platform to replace the custom PHP session system, using a silent on-login migration path that requires no forced re-authentication for any of the 520,000 existing users. Keycloak natively supports OAuth 2.0/OIDC (mobile app, developer API) and SAML 2.0 (enterprise SSO), delivering all three required product capabilities within the 9-month window. GDPR compliance is maintained by keeping all identity data in an EU-region PostgreSQL instance.

### Recommended Architecture

#### Identity Platform — Self-Hosted Keycloak
Keycloak is deployed on Kubernetes (2 replicas minimum, auto-scaling to 6 under load) with a dedicated PostgreSQL 16 database in an EU-region cloud provider. High-availability configuration uses Keycloak's built-in Infinispan cache cluster for session replication between pods.

Keycloak was selected over a managed identity provider (Auth0, Okta) because:
- Data sovereignty: all identity data remains in EU infrastructure under direct control (GDPR Article 44)
- Cost predictability: no per-MAU pricing — flat infrastructure cost regardless of user growth
- Customisability: custom password hashing migration hook can be implemented natively

#### User Migration — Silent On-Login (Zero Re-authentication)
The 520,000 existing users must not be forced to re-authenticate. This is achieved via a custom Keycloak User Storage Provider (SPI) that acts as a federated identity bridge to the legacy PHP user database:

1. On first login after cutover, Keycloak calls the SPI
2. The SPI queries the legacy PHP database with the submitted credentials
3. If authentication succeeds, Keycloak creates a native user record and migrates the hashed password
4. On subsequent logins, the user authenticates entirely within Keycloak — the PHP database is no longer consulted
5. Users who never log in again remain in the PHP database until it is decommissioned; they will need a password reset at that point (standard practice)

This approach requires zero user-facing changes. No email notifications, no forced password resets, no migration banner.

#### New Capabilities Delivered

**Native Mobile App (OAuth 2.0 + PKCE)**
Keycloak issues standard OAuth 2.0 access tokens and refresh tokens. The mobile app uses the Authorization Code flow with PKCE — the correct, secure flow for native apps. No custom token infrastructure required.

**Developer API (Scoped Access Tokens)**
Keycloak's client credentials flow issues scoped API keys for developers. Fine-grained scopes (read:data, write:data, admin) are defined in Keycloak and validated by the API gateway. Developers manage their API keys via a self-service developer portal (Keycloak Account Console, customised with company branding).

**Enterprise SSO (SAML 2.0)**
Keycloak acts as a SAML 2.0 Service Provider for the 40 enterprise accounts. Each enterprise connects their IdP (Okta, Azure AD, Google Workspace) to Keycloak via a standard SAML federation. Provisioning is handled via SCIM 2.0 for enterprises that support it; manual group assignment for those that do not.

#### PHP Session System — Parallel Running and Retirement
The legacy PHP session system runs in parallel with Keycloak during the migration window. A reverse proxy (Nginx) routes authentication requests: new sessions go to Keycloak; existing PHP sessions remain valid until they expire naturally (no forced logout). The PHP system is put into read-only mode (no new registrations) on Day 1 of cutover. It is decommissioned once the SPI migration telemetry shows >95% of monthly active users have migrated to Keycloak — estimated 6–7 months post-cutover based on typical session activity distributions.

### GDPR Compliance
- All Keycloak data (user records, sessions, audit logs) stored in EU-region PostgreSQL
- Data processing agreement updated to reflect Keycloak as sub-processor
- Right to erasure implemented via Keycloak Admin API (hard delete of user record + audit log pseudonymisation)
- Audit log retention: 12 months (configurable), stored in append-only table

### Delivery Timeline (9 months, 6 engineers)
| Month | Milestone |
|---|---|
| 1–2 | Keycloak deployed on Kubernetes; legacy SPI bridge implemented and tested |
| 2–3 | Mobile app OAuth 2.0 integration; internal QA |
| 3–4 | Developer API scoped tokens; developer portal customisation |
| 4–5 | Enterprise SSO SAML 2.0 integration for pilot 5 accounts |
| 5–6 | Remaining 35 enterprise SSO integrations; load testing |
| 6 | Production cutover; PHP system into read-only mode; SPI bridge active |
| 7–9 | Monitor migration progress; PHP decommission when >95% MAU migrated |

### Risk Mitigation
- **Forced re-authentication risk**: Silent SPI migration eliminates this entirely for active users
- **Keycloak availability**: 2+ pod replicas with Infinispan session replication; single pod failure is transparent to users
- **SAML misconfiguration**: Each enterprise SSO integration is tested in a staging Keycloak realm before production activation
- **Password hash compatibility**: SPI handles bcrypt, md5-crypt, and argon2 — the three hash formats found in the legacy PHP database`,
    debate_history: [
        {
            turn_number: 0,
            persona: 'LEGACY_KEEPER',
            timestamp: new Date().toISOString(),
            sentiment: 'neutral',
            response: `## My Position: Self-Hosted Keycloak, Not a SaaS Identity Provider

520,000 active users' authentication data is not something I want to hand to a third-party SaaS vendor. Let me explain why Keycloak is the right call here, and where I have concerns about the modernisation approach.

**Why Keycloak over Auth0:**
- Full GDPR data-residency control — our user credential data stays in our EU-region PostgreSQL instance, not on Auth0's servers.
- No per-MAU pricing risk — Auth0 at 520k MAU is €2,000–3,500/month and rising with every user we add. Keycloak on Kubernetes is effectively zero software cost.
- We own the encryption keys, the audit logs, and the data model.

**My concern with the modernisation pace:**
The three product changes (mobile app, developer API, enterprise SSO) have very different risk profiles. Enterprise SSO for 40 accounts carries significant integration risk — SAML federation with Okta, Azure AD, and Google Workspace simultaneously, while running a migration, with a 9-month deadline and 6 engineers, is aggressive.

I propose we sequence the delivery:
1. **Keycloak deployment + silent migration** (Months 1–4) — this is the foundation and must be stable before anything else.
2. **Mobile app OIDC** (Months 3–6) — new client type, low risk to existing users.
3. **Developer API OAuth 2.0** (Months 5–7) — new consumer path, isolated.
4. **Enterprise SSO** (Months 7–9) — last, smallest surface area, highest integration complexity.

This sequencing ensures the silent migration is mature before we add enterprise SSO complexity.`,
            key_points: [
                'Keycloak: full GDPR data-residency, no per-MAU cost escalation, encryption key ownership',
                'Enterprise SSO carries highest integration risk — should be last in delivery sequence',
                'Silent migration must be stable and proven before adding enterprise SSO complexity',
            ],
        },
        {
            turn_number: 1,
            persona: 'INNOVATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'disagree',
            response: `## My Position: Auth0, Delivered Faster and More Reliably

I understand the GDPR concern but let me push back: Auth0 offers EU-region data residency. GDPR compliance is achievable on Auth0 without compromise. The "data sovereignty" argument for self-hosting often understates the security and operational risks of running your own identity infrastructure.

**Why Auth0 over Keycloak for a 6-person team:**
- Keycloak's operational burden is real: HA clustering on Kubernetes, cache invalidation, session store management, upgrade path complexity, security patch cadence. A 6-person product team will spend engineering time maintaining Keycloak that should go into product features.
- Auth0 ships with first-class SDKs for React Native, iOS, and Android — mobile integration is hours, not days.
- Auth0's Actions (serverless hooks) handle the silent migration login intercept cleanly, with no custom PHP code in the critical auth path.
- Enterprise SSO setup in Auth0 is a UI configuration, not a SAML XML integration project.

**On the silent migration:**
Auth0's Database Connection migration feature handles exactly this scenario natively. We point it at our PHP password hashing function and it migrates credentials on login with zero code beyond a migration script. This is not a custom interceptor — it's a supported, battle-tested feature.

I'd rather pay €3,000/month for Auth0 and have 6 engineers focused on product than pay €400/month for Keycloak and have 1.5 engineers on infrastructure.`,
            key_points: [
                'Auth0 EU data residency satisfies GDPR without self-hosting burden',
                'Auth0 native Database Connection migration handles silent credential migration with no custom code',
                'Keycloak operational overhead is a hidden cost for a 6-person product team',
                'Auth0 enterprise SSO is UI configuration; Keycloak SAML federation is a bespoke integration project',
            ],
        },
        {
            turn_number: 2,
            persona: 'MEDIATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'neutral',
            response: `## Synthesis: The Operational Cost Is the Deciding Factor

Both positions are technically correct. The disagreement is about where you want to spend engineering hours — infrastructure or product.

**My assessment:**
- Auth0's native migration feature and managed ops are genuinely compelling for a 6-person team.
- Keycloak's data sovereignty advantages are real but not decisive if Auth0 EU data residency is configured correctly.
- The €2,600/month cost difference (~€31k/year) is meaningful but not prohibitive given the engineering time saved.

However, I want to raise one dimension neither position has addressed: **what happens when Auth0 has an incident?** 520,000 users cannot log in. With Keycloak, we can diagnose and patch our own system. With Auth0, we wait.

**My proposed resolution:**
Use **Keycloak**, but invest in reducing its operational burden:
- Deploy on a managed Kubernetes service (EKS or GKE) with a Helm chart maintained by the Keycloak community.
- Use **Amazon RDS Aurora** (managed PostgreSQL) as the Keycloak session store — no session store management overhead.
- Assign **one engineer** as Keycloak owner for the first 6 months; this is a defined, bounded commitment.
- Use **Terraform** to codify the entire Keycloak configuration — realms, clients, flows — so it is reproducible and auditable.

This gives us data sovereignty, eliminates per-MAU cost risk, and keeps operational complexity manageable with the right tooling.`,
            key_points: [
                'Auth0 incident risk: 520k users locked out, no self-remedy — meaningful consideration for authentication',
                'Keycloak on managed K8s + RDS Aurora significantly reduces operational overhead',
                'One dedicated Keycloak owner + Terraform config makes self-hosted viable for a 6-person team',
                'Data sovereignty + zero per-MAU cost tilt the recommendation toward Keycloak with right tooling',
            ],
        },
        {
            turn_number: 3,
            persona: 'INNOVATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Revised Position: Keycloak with Managed Infrastructure

The incident-risk argument and the Terraform+RDS Aurora framing have moved me. If Keycloak's operational burden is addressed through managed infrastructure — not manual cluster administration — then the data sovereignty and cost advantages tip the balance.

I accept Keycloak on the following basis:
- **Keycloak 24+ on EKS** with the community Helm chart. Active realm and client configuration in Terraform.
- **RDS Aurora PostgreSQL** as the backing store — no session cache management.
- **Auth0 as the benchmark**: if Keycloak's developer experience for mobile SDK integration or the silent migration proves unacceptably complex in Phase 1, we re-evaluate. This is a 4-month review gate, not a 9-month commitment before we can course-correct.

With that review gate in place, I support the Keycloak path.`,
            key_points: [
                'Managed infrastructure (EKS + RDS Aurora) resolves the operational burden concern',
                'Terraform-codified configuration makes Keycloak auditable and reproducible',
                'Review gate at 4 months — if developer experience is poor, reconsider Auth0',
            ],
        },
        {
            turn_number: 4,
            persona: 'MEDIATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Consensus Reached

The council is aligned. Keycloak on managed infrastructure is the recommendation, with a 4-month review gate and the delivery sequencing Legacy Keeper proposed.

**Final Architecture:**
- **Keycloak 24+** deployed on EKS, Helm chart, Terraform-managed realm/client configuration.
- **RDS Aurora PostgreSQL** as Keycloak's backing store (Multi-AZ, automated backups).
- **Silent migration**: PHP login interceptor provisions Keycloak identities on first post-migration login. Dual sessions run until >95% of active users migrated (~3–4 months).
- **Delivery sequence**: (1) Keycloak + silent migration, (2) Mobile OIDC, (3) Developer API OAuth 2.0, (4) Enterprise SSO SAML.
- **GDPR**: all auth data in EU-region RDS; right-to-erasure via Keycloak admin API; auth event audit log retained 12 months.
- **Review gate at Month 4**: Innovator's condition — if developer experience is unacceptable, the council reconvenes on Auth0.`,
            key_points: [
                'Keycloak 24+ on EKS + RDS Aurora: managed infrastructure, full data sovereignty',
                'Silent on-login migration: zero forced re-authentication for 520k users',
                'Phased delivery: foundation → mobile → API → enterprise SSO',
                'Month 4 review gate: Auth0 fallback option preserved if Keycloak DX proves problematic',
            ],
        },
    ],
};

// ─── Scenario D: Media Storage Scaling ───────────────────────────────────────

const scenarioD_baseline: BaselineVariationRead = {
    id: 104,
    agent_persona: 'STANDARD',
    reasoning: null,
    confidence_score: 0.84,
    proposal_id: 4,
    generation_time_seconds: 4.0,
    structured_prd: `# Architectural Proposal: Media Storage Scaling

## Executive Summary
Migrate 48 TB of user-generated media from an 87%-full NAS cluster to a scalable cloud object storage architecture, preserving all 9 million existing public URLs without redirects, within a €50 k first-year budget, executed by a 3-person team with no planned downtime.

## Recommended Architecture: S3-Compatible Object Storage + CDN + Transparent Proxy

### Core Principle: URL Preservation via Transparent Proxy
The most critical constraint is that 9 million URLs of the form \`https://media.ourplatform.com/{uuid}/{filename}\` must continue to resolve without redirects. This is achievable because we control the \`media.ourplatform.com\` domain — the storage backend can change without changing what customers see.

**Mechanism**: Route all media requests through a CDN/proxy layer (Cloudflare or AWS CloudFront) that maps \`media.ourplatform.com/{uuid}/{filename}\` to the new object storage backend. Existing URLs resolve identically; no customer integration changes required.

### Recommended Storage: AWS S3 (or Cloudflare R2)
**AWS S3:**
- Industry standard, 11 nines durability, 99.99% availability.
- S3 Intelligent-Tiering automatically moves infrequently accessed objects to cheaper storage classes — critical for a media library where older content is rarely accessed.
- S3 Transfer Acceleration for upload throughput.

**Cloudflare R2 (strongly recommended as primary or alongside S3):**
- **Zero egress fees** — for a media platform with high read traffic, S3 egress costs can be significant. R2 eliminates this.
- S3-compatible API — migration tooling (rclone) works identically.
- Integrated with Cloudflare CDN — serves media from Cloudflare's edge, reducing latency globally.
- At 10 TB growth/year: R2 storage cost ~€150/month. No egress charges.

**Recommendation**: **Cloudflare R2 + Cloudflare CDN** for new writes and CDN serving; use rclone to migrate existing NAS content to R2 in the background.

### Migration Plan (No Downtime)

#### Phase 1 — Parallel Write (Week 1–4)
- Provision Cloudflare R2 bucket and Cloudflare CDN in front of \`media.ourplatform.com\`.
- Configure the CDN with a **waterfall origin**: try R2 first; if the object is not found (during migration), fall through to the NAS via an origin server.
- Update the application's file upload handler to write new uploads **directly to R2**.
- Result: new uploads go to R2; existing content still served from NAS via origin fallback. Zero downtime, zero URL changes.

#### Phase 2 — Background Migration (Week 2–12)
Use **rclone** with the \`--transfers 64\` flag to sync NAS content to R2 in the background:
\`\`\`bash
rclone sync /nas/media r2:media-bucket --transfers 64 --checkcopy --log-file rclone.log
\`\`\`
- Run during off-peak hours to minimise NAS I/O impact on uploads.
- rclone tracks checksums — objects are only transferred if the destination is missing or different.
- At 100 Mbps sustained (conservative for a NAS), 48 TB transfers in ~5 days of sustained transfer time. Over 10 weeks at night-only transfer: ~3–4 weeks to complete.

#### Phase 3 — CDN Origin Cutover (Week 12–14)
Once rclone confirms all objects are present in R2 (checksum-verified):
- Update the CDN origin configuration to remove the NAS fallback.
- All requests now served from R2 → Cloudflare CDN edge.
- NAS remains mounted read-only for 30 days as emergency fallback.

#### Phase 4 — NAS Decommission (Week 16+)
- Confirm zero NAS origin hits for 30 days via access logs.
- Decomission NAS cluster (or repurpose for internal use).

### Budget Estimate (Year 1)
| Item | Cost |
|---|---|
| Cloudflare R2 (48 TB existing + 10 TB growth = 58 TB × €0.015/GB) | ~€900/month → €10,800/year |
| Cloudflare CDN (included in R2 egress-free model) | €0 egress |
| Cloudflare Pro/Business plan (for cache rules, analytics) | €200/month → €2,400/year |
| Compute for rclone migration runner (EC2 t3.medium, 10 weeks) | ~€60 total |
| Engineering time (3 engineers × estimated 6 weeks total effort) | Internal cost |
| **Total cloud spend Year 1** | **~€13,260** |

Well within the €50 k first-year budget. Remaining headroom (~€36 k) covers unexpected costs, additional CDN configuration work, or monitoring tooling.

### URL Compatibility Verification
Before Phase 3 cutover, run an automated check against a random sample of 10,000 existing object keys to confirm all objects are present in R2 with matching checksums. Only proceed to cutover after 100% match rate confirmed.

## Risk Mitigation
- **Downtime risk**: Zero. Waterfall CDN origin ensures continuity throughout migration.
- **URL breakage**: CDN proxy preserves all \`media.ourplatform.com\` URLs. Changes are backend-only.
- **Data loss**: rclone checksum verification before NAS decommission; NAS retained 30 days post-cutover.
- **Cost overrun**: R2's zero-egress model eliminates the largest cloud media cost variable.
- **Team capacity**: rclone automation means the 3-person team is not bottlenecked on manual transfer work.`,
};

const scenarioD_multiagent: DebateResult = {
    id: 'static-debate-D',
    proposal_id: 4,
    consensus_reached: true,
    consensus_type: ConsensusType.UNANIMOUS,
    total_turns: 5,
    duration_seconds: 29,
    conflict_density: 0.22,
    legacy_keeper_consistency: 0.93,
    innovator_consistency: 0.90,
    mediator_consistency: 0.95,
    overall_persona_consistency: 0.93,
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    final_consensus_proposal: `The council unanimously recommends migrating to Cloudflare R2 with Cloudflare CDN in front of media.ourplatform.com. A waterfall CDN origin (R2 first, NAS fallback) enables a zero-downtime, zero-URL-change migration. New uploads are redirected to R2 immediately; existing NAS content is migrated in the background using rclone with checksum verification. The NAS is retained in read-only mode for 30 days post-cutover. Estimated Year 1 cloud cost: ~€13,000 — well within the €50k budget. No redirects, no downtime, 3-person team executable.`,
    debate_history: [
        {
            turn_number: 0,
            persona: 'LEGACY_KEEPER',
            timestamp: new Date().toISOString(),
            sentiment: 'neutral',
            response: `## My Position: Extend NAS First, Migrate Carefully

We have 4 months before the NAS is full. That is not a comfortable window to plan, execute, and validate a 48 TB migration — especially with a 3-person team and the constraint that 9 million public URLs must not break.

Before committing to a cloud migration, I want to confirm: **can we buy time with a NAS expansion?**

Adding a 20 TB expansion shelf to the existing NAS typically costs €3,000–6,000 in hardware and can be done in a day. That buys us 6 additional months to plan the cloud migration properly, with no URL risk, no application changes, and no migration complexity. Given the stakes — 9 million URLs in customer integrations — a rushed migration is the highest-risk path.

If the decision is to proceed with cloud migration directly (which I accept may be the right call given the 10 TB/year growth trajectory), then I have strong preferences on how it's done:

1. **Cloudflare R2** over AWS S3 for new writes — zero egress fees matter at this scale.
2. **The NAS must stay mounted and serving as a fallback for the full migration period.** No aggressive timeline to decommission it.
3. **rclone with checksum verification** — I want cryptographic proof that every byte in the NAS is present in R2 before we touch the CDN origin configuration.
4. **URL preservation via CDN proxy is the correct approach** — we control the domain, so this is entirely feasible.

My concern is not the architecture — it's the timeline. If we commit to cloud migration, the NAS fallback pattern and the checksum verification are non-negotiable.`,
            key_points: [
                'NAS expansion shelf (€3–6k) could buy 6 months — worth evaluating before committing to migration',
                'If migrating: Cloudflare R2 (zero egress), rclone + checksum verification, NAS fallback throughout',
                'URL preservation via CDN proxy is correct and safe given domain ownership',
            ],
        },
        {
            turn_number: 1,
            persona: 'INNOVATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'neutral',
            response: `## My Position: Migrate Directly, Don't Extend the NAS

Expanding the NAS is spending money to delay a migration we will do anyway — and in 6 months we'll have 52+ TB to migrate instead of 48 TB. The expansion costs €3–6k, buys us nothing architecturally, and means we're back here with more data and less runway.

The cloud migration is straightforward. Here's why the 3-person team concern is less of a constraint than it looks:

**The migration is mostly automated:**
- rclone runs unattended. You start it, monitor it, and review the completion report. It does not require active engineering hours proportional to the 48 TB volume.
- The waterfall CDN origin (try R2 first, fall back to NAS) is a 30-minute CDN configuration change.
- Application code change: one function, the upload handler, is redirected to R2. That's a morning's work for one engineer.

**The actual engineering effort is small:**
1. Provision R2 bucket + Cloudflare CDN (Day 1, ~4 hours).
2. Update upload handler to write to R2 (Day 2, ~4 hours).
3. Start rclone migration job (Day 2, ~1 hour to configure + start).
4. Monitor rclone progress and checksum report (Week 2–12, ~1 hour/week).
5. Validate sample URLs post-migration (Week 12, ~4 hours).
6. Update CDN origin to remove NAS fallback (Week 13, ~1 hour).

Total active engineering time: approximately 3–4 engineer-days. The 3-person team constraint is not a binding concern.

I agree with Legacy Keeper on R2, checksum verification, and CDN proxy. The only disagreement is whether to delay with a NAS expansion.`,
            key_points: [
                'NAS expansion delays an inevitable migration and increases the data volume to migrate',
                'rclone is unattended — actual active engineering effort is 3–4 engineer-days, not weeks',
                'Agreement on R2, CDN proxy, checksum verification — disagreement only on NAS expansion timing',
            ],
        },
        {
            turn_number: 2,
            persona: 'MEDIATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Synthesis: Migrate Now, NAS Expansion is Unnecessary

This debate has a clear resolution. The council agrees on the architecture — Cloudflare R2, CDN proxy, rclone, checksum verification, NAS fallback during migration. The only open question is whether to spend €3–6k on a NAS expansion shelf first.

Innovator's point is decisive: a NAS expansion increases the migration data volume and the monthly cost of the delay, while providing no architectural value. The migration automation (rclone) means the 3-person team is not the binding constraint.

Legacy Keeper's conditions — NAS as fallback throughout migration, checksum verification before CDN cutover, no aggressive decommission timeline — are already part of the proposed migration plan. There is nothing to compromise on; both positions agree on the approach.

**Final recommendation: proceed directly with the cloud migration.** NAS expansion is not warranted given the automated migration approach and the 4-month capacity window (which is sufficient to complete the migration safely).

This is a case of genuine consensus, not compromise. The council is unanimous.`,
            key_points: [
                'Architecture agreement is complete: R2, CDN proxy, rclone, checksum verification, NAS fallback',
                'NAS expansion rejected: increases migration data volume, provides no architectural benefit',
                'rclone automation means 3-person team is not a binding constraint — 3–4 engineer-days total',
                'Unanimous consensus — no compromise required',
            ],
        },
        {
            turn_number: 3,
            persona: 'LEGACY_KEEPER',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Agreement: Proceed with Migration

I accept the council's conclusion. The automated rclone migration means the 3-person team constraint does not justify a NAS expansion. My conditions are already incorporated into the migration plan.

To summarise what I consider non-negotiable and am pleased to see included:
- **Waterfall CDN origin** — NAS serves as live fallback for every request throughout the migration.
- **rclone checksum verification** — 100% checksum match required before CDN origin cutover.
- **NAS retained read-only for 30 days** post-cutover — available for emergency recovery.
- **No URL redirects** — CDN proxy ensures all existing URLs resolve identically.

This is the right call. I support it.`,
            key_points: [
                'Waterfall CDN origin: NAS remains live fallback throughout migration',
                'Checksum verification: 100% match required before cutover',
                'NAS retained 30 days post-cutover in read-only emergency fallback mode',
            ],
        },
        {
            turn_number: 4,
            persona: 'MEDIATOR',
            timestamp: new Date().toISOString(),
            sentiment: 'agree',
            response: `## Council Consensus — Final Recommendation

The council has reached unanimous agreement. This is a rare outcome that reflects the strength of the Cloudflare R2 + CDN solution for this specific set of constraints.

**Consensus position**: Migrate to Cloudflare R2 with Cloudflare CDN serving \`media.ourplatform.com\`. The waterfall CDN origin pattern (R2 first, NAS fallback) provides a zero-downtime, zero-URL-change migration path that is executable by a 3-person team within budget.

All three personas are satisfied:
- The **Legacy Keeper's** non-negotiables (checksum verification, NAS fallback retention, no URL changes) are all in the plan.
- The **Innovator's** preference for cloud-native, egress-free, globally distributed storage is fulfilled by R2.
- The **Mediator's** constraints — €50 k budget, 3-person team, no downtime — are all met at ~€13 k Year 1.

**Recommended next step**: Provision the R2 bucket and Cloudflare CDN configuration this week. Begin parallel writes immediately — this is the lowest-risk first step and starts reducing NAS growth rate from day one.`,
            key_points: [
                'Unanimous consensus: Cloudflare R2 + Cloudflare CDN',
                'Waterfall origin ensures zero downtime and zero URL changes throughout migration',
                'Year 1 cloud cost ~€13k — well within €50k budget',
                'All three personas satisfied — no trade-offs required',
            ],
        },
    ],
};

// ─── Export ────────────────────────────────────────────────────────────────────

export const STATIC_EXPERIMENT_DATA: Record<
    number,
    { baseline: BaselineVariationRead; multiagent: DebateResult }
> = {
    1: { baseline: scenarioA_baseline, multiagent: scenarioA_multiagent },
    2: { baseline: scenarioB_baseline, multiagent: scenarioB_multiagent },
    3: { baseline: scenarioC_baseline, multiagent: scenarioC_multiagent },
    4: { baseline: scenarioD_baseline, multiagent: scenarioD_multiagent },
};