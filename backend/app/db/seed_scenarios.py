"""
Thesis Evaluation Scenario Seeder
==================================

Creates the 4 controlled scenarios required for the MSc user study.

Each scenario consists of:
  1. A shared "Thesis Study" Project  (created once, reused by all 4)
  2. A Proposal record with a rich task_description
  3. A HistoricalDocument with realistic architecture context
     → Celery vectorisation is dispatched immediately so it's COMPLETED
       by the time the first participant arrives.

Run once before recruiting any participants:

    docker compose exec backend python -m app.db.seed_scenarios

Idempotent: re-running is safe — existing records are skipped.
After running, copy the printed proposal IDs into ExperimentInterface.tsx.
"""

import asyncio

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import engine
from app.models.project import Project, HistoricalDocument, DocumentStatus
from app.models.proposal import Proposal, ProposalStatus
from app.models.user import User
from app.services.vector_service import VectorService


# ─── Scenario definitions ─────────────────────────────────────────────────────

SCENARIOS = [
    {
        "slug": "payment_migration",
        "proposal_task_description": (
            "Our e-commerce platform processes all payments inside a 6-year-old Ruby on Rails "
            "monolith. Last Black Friday we suffered three separate outages totalling 4.5 hours "
            "of downtime, costing an estimated €280 k in lost revenue. The current architecture "
            "cannot horizontally scale the payment flow independently of the rest of the application. "
            "We need an architecture decision for how to migrate payment processing out of the "
            "monolith within a 6-month deadline while maintaining PCI-DSS Level 1 compliance, "
            "zero data loss, and the ability to roll back at any stage. "
            "The engineering team has 8 backend engineers (3 senior), one DevOps engineer, "
            "and no dedicated DBA. Options under consideration include extracting a microservice, "
            "introducing a caching/queue layer in front of the existing code, or adopting a "
            "third-party payment orchestration platform."
        ),
        "doc_filename": "payment_migration_context.md",
        "doc_content": """\
# Payment Service — Architecture Context Document

## Company & Product
- **Company**: RetailCo (pseudonym) — mid-size B2C e-commerce, €40 M ARR
- **Traffic profile**: 15 k daily active users, peaks to 120 k on promotional days
- **Payment volume**: ~4 200 transactions/day, €1.8 M daily GMV at peak

## Current Architecture
- **Application**: Ruby on Rails 6.1 monolith, deployed on 4× EC2 c5.2xlarge behind an ALB
- **Database**: PostgreSQL 14 (RDS Multi-AZ, db.r6g.xlarge, 500 GB)
- **Payment flow**: Stripe SDK called synchronously inside a Rails controller action;
  order + payment state written in a single DB transaction
- **Session handling**: Rails sessions backed by Redis (ElastiCache)
- **Background jobs**: Sidekiq (6 workers) for email, PDF receipts, inventory sync

## Pain Points Observed in Production
| Incident | Date | Duration | Root cause |
|---|---|---|---|
| Checkout timeout storm | Nov 2023 | 2 h 10 min | Stripe webhook backlog starved Sidekiq |
| DB connection exhaustion | Nov 2023 | 1 h 05 min | Rails thread pool × 4 instances hit RDS max_connections |
| Deploy-time downtime | Nov 2023 | 1 h 20 min | Zero-downtime deploy failed; payments rolled back mid-flight |

## Compliance Requirements
- PCI-DSS Level 1 (SAQ-D): annual QSA audit, cardholder data must not touch application logs
- GDPR: customer PII retained max 7 years, right-to-erasure within 30 days
- SOC 2 Type II in progress

## Team
- 8 backend engineers (Rails, 3 with Go experience)
- 1 DevOps/SRE engineer (Terraform + AWS)
- No dedicated DBA — DB changes require peer review from 2 senior engineers
- Stripe integration maintained by 1 engineer who is the single point of knowledge

## Constraints
- 6-month hard deadline (next Black Friday)
- Budget: €120 k infrastructure headroom above current spend
- Cannot change payment provider (Stripe contract locked in for 18 months)
- Must support rollback at any stage with < 1 hour RTO

## Technology Already Available
- AWS EKS cluster (used for data pipeline, team has Kubernetes experience)
- Redis, SQS, SNS already provisioned
- Datadog APM + PagerDuty alerting in place
""",
    },
    {
        "slug": "analytics_pipeline",
        "proposal_task_description": (
            "Our SaaS product dashboard currently queries a 2 TB PostgreSQL OLTP database "
            "directly for all analytics. As we approach 500 business customers the dashboard "
            "query times have degraded from under 2 seconds to 18–45 seconds, and we see "
            "read replicas hitting 95 % CPU during business hours. "
            "We need an architecture recommendation for a real-time analytics pipeline that "
            "can ingest event data from our web and mobile clients, update dashboard metrics "
            "with under 5 seconds end-to-end latency, and support ad-hoc SQL queries from "
            "our data team without impacting product availability. "
            "Current daily ingest is ~8 million events; projected to reach 80 million within "
            "12 months. The team of 5 engineers has strong Python and SQL skills but limited "
            "streaming/Kafka experience. Budget is capped at €15 k/month additional cloud spend."
        ),
        "doc_filename": "analytics_pipeline_context.md",
        "doc_content": """\
# Analytics Pipeline — Architecture Context Document

## Company & Product
- **Company**: MetricFlow (pseudonym) — B2B SaaS, 480 business customers, €6 M ARR
- **Core product**: Operational dashboards for field-service teams (mobile + web)
- **Event types**: user_action, form_submitted, job_completed, location_update, sync_event

## Current Architecture
- **Application**: Django 4.2 monolith + DRF, deployed on Kubernetes (GKE)
- **Primary DB**: PostgreSQL 15 (Cloud SQL, db-custom-8-32768), 2.1 TB, ~400 tables
- **Read replica**: 1× replica; analytics queries routed here via PgBouncer
- **Event ingestion**: Events written synchronously to PostgreSQL from API handlers
- **Dashboard queries**: Complex JOINs across 8–12 tables; some run 20–60 s

## Performance Metrics (last 30 days)
| Metric | Value | Target |
|---|---|---|
| Dashboard P50 load time | 18 s | < 2 s |
| Dashboard P99 load time | 47 s | < 5 s |
| Read replica CPU (peak) | 94 % | < 60 % |
| Event ingest rate (peak) | 1 200 events/s | — |
| Daily event volume | 8.2 M | — |

## Data Team Requirements
- Ad-hoc SQL queries (Metabase connected to read replica — currently broken at peak)
- Backfill capability: re-process historical events after schema changes
- Data retention: 2 years hot, 5 years cold (currently all in PostgreSQL — expensive)

## Team
- 5 engineers (3 backend Python, 1 data engineer, 1 full-stack)
- Data engineer has used Spark; no one has production Kafka experience
- Infrastructure: GCP-only (Cloud SQL, GKE, Cloud Storage, Pub/Sub available)

## Constraints
- Budget cap: €15 k/month incremental cloud spend
- Must not increase dashboard latency during migration
- Dashboard SLA: 99.5 % uptime (currently at 98.9 %)
- Existing Metabase dashboards must continue to work (read-SQL compatible interface required)
- 18-month roadmap assumes 10× event volume growth

## Options Under Active Discussion
1. **Apache Kafka + ksqlDB** — streaming first, real-time aggregations, but team unfamiliar
2. **Materialised views + pg_cron** — low operational overhead, but write amplification risk
3. **Separate OLAP DB** — ClickHouse or BigQuery; proven at scale, higher migration effort
4. **Cloud Pub/Sub + Dataflow** — fully managed GCP-native, vendor lock-in concern
""",
    },
    {
        "slug": "auth_modernisation",
        "proposal_task_description": (
            "Our platform authenticates 520 000 active users with a custom session-based "
            "system built in 2018. The system uses server-side PHP sessions stored in Memcached "
            "and an in-house API key scheme for partner integrations. We are planning three "
            "major product changes that the current auth system cannot support: a native mobile "
            "app, a public developer API with fine-grained scopes, and single-sign-on (SSO) "
            "for our 40 enterprise accounts. "
            "We need an architectural recommendation for modernising authentication and "
            "authorisation while keeping all 520 000 existing users logged in (no forced "
            "re-authentication), maintaining GDPR compliance, and completing within 9 months "
            "with a team of 6 engineers. The system currently handles 2 400 logins/minute at peak."
        ),
        "doc_filename": "auth_modernisation_context.md",
        "doc_content": """\
# Authentication Modernisation — Architecture Context Document

## Company & Product
- **Company**: WorkflowHub (pseudonym) — B2B workflow automation SaaS, 520 k users
- **Customer segments**: SMB self-serve (480 k users) + Enterprise (40 accounts, 40 k users)
- **Client surfaces**: Web app (React), planned iOS/Android apps, partner API integrations

## Current Authentication Architecture
- **Session system**: PHP 8.1 + Laravel; sessions stored in Memcached (2× ElastiCache nodes)
- **Session lifetime**: 30-day sliding window; ~1.8 M active sessions at any time
- **API keys**: Custom HMAC-SHA256 scheme; keys stored hashed in MySQL; 12 k active keys
- **Password storage**: bcrypt cost 12
- **MFA**: TOTP only; 18 % of users enrolled
- **SSO**: Not implemented; enterprise accounts use shared team accounts (security concern)

## Security Incidents / Audit Findings
| Finding | Severity | Status |
|---|---|---|
| Session fixation possible on password reset | High | Patched Feb 2024 |
| API keys transmitted in query strings (logs) | High | Partially mitigated |
| No token revocation for API keys | Medium | Open |
| Memcached not TLS-encrypted (internal network only) | Low | Open |

## Planned Product Requirements That Require Auth Changes
1. **Mobile app**: Needs short-lived tokens + silent refresh (sessions don't work natively)
2. **Developer API v2**: Scoped access tokens (read/write/admin per resource), webhooks
3. **Enterprise SSO**: SAML 2.0 or OIDC federation with customer IdPs (Okta, Azure AD)

## Team
- 6 engineers (2 backend PHP, 2 backend Python, 1 security-focused engineer, 1 DevOps)
- Security engineer has implemented OAuth 2.0 before (at previous company)
- No experience with SAML; some familiarity with JWT

## Constraints
- MUST NOT force existing 520 k users to re-authenticate
- GDPR: session/token data subject to erasure requests within 72 hours
- PSD2 SCA compliance for payment-adjacent features (strong auth required)
- 9-month delivery window; enterprise SSO needed first (3-month milestone)
- Infrastructure: AWS (RDS MySQL, ElastiCache, EKS)

## Options Under Discussion
1. **OAuth 2.0 / OIDC with JWT** — industry standard, complex to implement correctly
2. **Sessions + new API-key scheme** — lowest migration risk, doesn't solve mobile/SSO
3. **Auth0 / Okta as IdP** — accelerates SSO, adds vendor dependency and €40 k/year cost
4. **AWS Cognito** — managed, AWS-native, but limited customisation for enterprise SSO
""",
    },
    {
        "slug": "media_storage_scaling",
        "proposal_task_description": (
            "Our platform hosts user-generated media — photos, videos, and documents — "
            "currently stored on a 48 TB NAS cluster in our co-location facility. "
            "Storage utilisation reached 87 % last month and we are adding approximately "
            "800 GB of new media per week. At the current growth rate we will exhaust "
            "capacity in under 4 months. All media is served via public URLs in the format "
            "https://media.ourplatform.com/{uuid}/{filename} — approximately 9 million such "
            "URLs exist in customer data and external integrations, and they must continue "
            "to resolve without redirection after any migration. "
            "We need an architecture recommendation for scaling media storage to accommodate "
            "10 TB+ of additional capacity annually, with a migration plan that preserves all "
            "existing URLs, stays within a €50 k first-year budget, and can be executed by "
            "a 3-person infrastructure team without service interruption."
        ),
        "doc_filename": "media_storage_context.md",
        "doc_content": """\
# Media Storage Scaling — Architecture Context Document

## Company & Product
- **Company**: CreatorBase (pseudonym) — creator economy platform, 280 k registered users
- **Media types**: Images (JPEG/PNG/WebP, avg 2.8 MB), Videos (MP4, avg 180 MB), Documents (PDF, avg 4 MB)
- **Access pattern**: 70 % of reads on media < 30 days old; long tail of historical content

## Current Infrastructure
- **Storage**: Dell PowerVault NAS, 48 TB usable (RAID-6), co-located in Amsterdam DC
- **CDN**: Cloudflare in front of NAS (cache hit rate 61 %, TTL 7 days for images)
- **Serving**: Nginx on 2× bare-metal servers proxying NAS via NFS mount
- **Upload pipeline**: Files uploaded to app servers → validated → moved to NAS via rsync
- **URL structure**: `https://media.ourplatform.com/{uuid}/{filename}` (9 M live URLs)
- **Backups**: Weekly rsync to a second NAS; last tested restore: 8 months ago

## Current Utilisation
| Metric | Value |
|---|---|
| Total capacity | 48 TB |
| Used | 41.7 TB (87 %) |
| Weekly growth | ~800 GB |
| Months to exhaustion | ~3.5 |
| CDN bandwidth (monthly) | 42 TB egress |

## Performance Characteristics
- Image delivery P95 latency: 110 ms (CDN hit), 680 ms (NAS miss)
- Video streaming: no adaptive bitrate; single MP4 served sequentially
- Concurrent upload limit: ~200 before NFS lock contention observed

## Team
- 3 infrastructure engineers (Linux, Nginx, basic AWS experience)
- No Kubernetes in production; Docker used for development
- Application team (separate): 4 engineers, Python/Django

## Constraints
- All 9 million existing URLs must continue to resolve **without HTTP redirects**
  (customers have embedded URLs in third-party integrations)
- First-year budget: €50 k (capex + opex combined)
- Zero planned downtime — migration must be live-switchover
- Data durability: 99.999 % (currently at risk with single-site NAS)
- Regulatory: media containing EU user data must remain in EU jurisdiction

## Options Under Discussion
1. **AWS S3 + CloudFront** — industry standard, €18–22 k/year at current volume
2. **NAS expansion** — add 24 TB shelf (€8 k hardware), same operational risk
3. **MinIO (self-hosted S3-compatible)** — lower egress cost, higher ops burden
4. **Cloudflare R2** — zero egress fees, S3-compatible API, newer product
""",
    },
]


# ─── Seeder ───────────────────────────────────────────────────────────────────


async def seed_scenarios() -> None:
    """
    Idempotently create the 4 thesis evaluation scenarios.

    Creates:
        - 1 shared "Thesis Evaluation Study" Project  (owner = first admin user)
        - 4 Proposal records
        - 4 HistoricalDocument records with vectorisation dispatched

    Prints the proposal IDs to paste into ExperimentInterface.tsx.
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # ── 1. Find or create the admin user to own the project ──────────────
        admin_result = await session.exec(select(User).where(User.is_superuser))
        admin = admin_result.first()
        if not admin:
            raise RuntimeError(
                "No superuser found. Run the main seed first or create an admin account."
            )

        # ── 2. Find or create the shared Thesis project ───────────────────────
        project_result = await session.exec(
            select(Project).where(Project.name == "Thesis Evaluation Study")
        )
        project = project_result.first()

        if not project:
            project = Project(
                name="Thesis Evaluation Study",
                description=(
                    "Controlled scenarios for the MSc thesis user study evaluating "
                    "multi-agent AI for software architecture decisions. "
                    "Do not modify these scenarios during the study period."
                ),
                owner_id=admin.id,
                visibility="private",
                tags="thesis,evaluation,research",
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)
            print(f"✓ Created project '{project.name}' (id={project.id})")
        else:
            print(f"  Project already exists (id={project.id})")

        # ── 3. Create Proposal + HistoricalDocument for each scenario ─────────
        vector_service = VectorService(session=session)
        created_proposals: list[tuple[str, int]] = []

        for s in SCENARIOS:
            # Check if proposal already exists for this slug (via task_description prefix)
            slug = s["slug"]
            existing_result = await session.exec(
                select(Proposal).where(
                    Proposal.project_id == project.id,
                    Proposal.task_description.startswith(
                        s["proposal_task_description"][:60]
                    ),
                )
            )
            existing = existing_result.first()

            if existing:
                print(f"  Proposal for '{slug}' already exists (id={existing.id})")
                created_proposals.append((slug, existing.id))
                continue

            # Create Proposal
            proposal = Proposal(
                task_description=s["proposal_task_description"],
                project_id=project.id,
                created_by_id=admin.id,
                status=ProposalStatus.DRAFT,
            )
            session.add(proposal)
            await session.commit()
            await session.refresh(proposal)
            print(f"✓ Created proposal '{slug}' (id={proposal.id})")

            # Create HistoricalDocument with context text
            content = s["doc_content"]
            doc = HistoricalDocument(
                filename=s["doc_filename"],
                content_text=content,
                file_size_bytes=len(content.encode("utf-8")),
                mime_type="text/markdown",
                project_id=project.id,
                uploaded_by_id=admin.id,
                status=DocumentStatus.PENDING,
                character_count=len(content),
            )
            session.add(doc)

            # Increment project document counter
            project.document_count += 1
            session.add(project)

            await session.commit()
            await session.refresh(doc)
            print(f"  Created document '{doc.filename}' (id={doc.id})")

            # Dispatch Celery vectorisation
            try:
                task_id = await vector_service.chunk_and_vectorize(
                    document_id=doc.id,
                    full_text=content,
                )
                print(f"  Vectorisation enqueued (celery task_id={task_id})")
            except Exception as e:
                print(f"  ⚠ Vectorisation dispatch failed: {e}")
                print(
                    "    → Document created but not vectorised. Re-run after fixing Celery."
                )

            created_proposals.append((slug, proposal.id))

        # ── 4. Print summary for developer ────────────────────────────────────
        print()
        print("=" * 60)
        print("SCENARIO SEED COMPLETE")
        print("=" * 60)
        print()
        print("Copy these IDs into ExperimentInterface.tsx SCENARIOS array:")
        print()
        for slug, pid in created_proposals:
            print(f"  {slug:<30}  proposalId: {pid}")
        print()
        print("Pre-study checklist:")
        print("  [ ] Documents show status COMPLETED in admin dashboard")
        print("  [ ] Test POST /experiments/baseline for each proposal ID")
        print("  [ ] Test debate endpoint for each proposal ID")
        print("  [ ] Time each scenario end-to-end (target: 10–15 min)")
        print()


if __name__ == "__main__":
    asyncio.run(seed_scenarios())
