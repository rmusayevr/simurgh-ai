"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-15 00:00:00.000000

Squashed from 7 migrations:
  856c2910c631 — initial schema
  e823a5d068d5 — add token_usage_records (later dropped)
  79f8bd0da366 — drop token_usage_records; add debate_sessions.consensus_confidence
  01cf076eac9d — add questionnaire_responses.condition_order
  7eaf5615d438 — add exit_surveys.preferred_system_actual
  b3e26d351cb4 — fix questionnaire_responses.participant_id FK target
  472b065a56f7 — add proposals.rejection_reason + revision_feedback
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel
import pgvector

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── 1. Base tables (no foreign keys) ─────────────────────────────────────

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column(
            "hashed_password", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "full_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column(
            "job_title", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column(
            "avatar_url", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column(
            "role", sa.Enum("ADMIN", "MANAGER", "USER", name="userrole"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column(
            "verification_token",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=True,
        ),
        sa.Column("terms_accepted", sa.Boolean(), nullable=False),
        sa.Column("terms_accepted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "reset_token", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True
        ),
        sa.Column("reset_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("login_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_user_created_at", "users", ["created_at"], unique=False)
    op.create_index(
        "idx_user_email_verified", "users", ["email", "email_verified"], unique=False
    )
    op.create_index(
        "idx_user_role_active", "users", ["role", "is_active"], unique=False
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(
        op.f("ix_users_reset_token"), "users", ["reset_token"], unique=False
    )
    op.create_index(
        op.f("ix_users_verification_token"),
        "users",
        ["verification_token"],
        unique=False,
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "DEBATE",
                "PROPOSAL",
                "STAKEHOLDER",
                "COMMUNICATION",
                "SYSTEM",
                name="templatecategory",
            ),
            nullable=False,
        ),
        sa.Column(
            "description", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=True),
        sa.Column(
            "model_override",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=True,
        ),
        sa.Column("temperature_override", sa.Float(), nullable=True),
        sa.Column("max_tokens_override", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_prompt_template_category_active",
        "prompt_templates",
        ["category", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_prompt_template_slug_active",
        "prompt_templates",
        ["slug", "is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prompt_templates_category"),
        "prompt_templates",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prompt_templates_is_active"),
        "prompt_templates",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prompt_templates_slug"), "prompt_templates", ["slug"], unique=True
    )

    op.create_table(
        "token_usage_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cache_creation_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "cache_read_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_token_usage_user", "token_usage_records", ["user_id", "created_at"]
    )
    op.create_index(
        "idx_token_usage_operation", "token_usage_records", ["operation", "created_at"]
    )

    # ── 2. Level 1 tables (depend on users) ──────────────────────────────────

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "visibility",
            sa.Enum("PRIVATE", "TEAM", "PUBLIC", name="projectvisibility"),
            nullable=False,
        ),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("tags", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column(
            "tech_stack", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("proposal_count", sa.Integer(), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_project_archived_activity",
        "projects",
        ["is_archived", "last_activity_at"],
        unique=False,
    )
    op.create_index(
        "idx_project_owner_created",
        "projects",
        ["owner_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_project_visibility",
        "projects",
        ["visibility", "is_archived"],
        unique=False,
    )
    op.create_index(
        op.f("ix_projects_created_at"), "projects", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_projects_last_activity_at"),
        "projects",
        ["last_activity_at"],
        unique=False,
    )
    op.create_index(op.f("ix_projects_name"), "projects", ["name"], unique=False)
    op.create_index(
        op.f("ix_projects_owner_id"), "projects", ["owner_id"], unique=False
    )

    op.create_table(
        "participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "experience_level",
            sa.Enum(
                "MSC_STUDENT", "JUNIOR", "SENIOR", "ARCHITECT", name="experiencelevel"
            ),
            nullable=False,
        ),
        sa.Column("years_experience", sa.Integer(), nullable=False),
        sa.Column("familiarity_with_ai", sa.Integer(), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False),
        sa.Column("consent_timestamp", sa.DateTime(), nullable=True),
        sa.Column(
            "assigned_condition_order",
            sa.Enum("BASELINE_FIRST", "MULTIAGENT_FIRST", name="conditionorder"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_participant_condition_order",
        "participants",
        ["assigned_condition_order"],
        unique=False,
    )
    op.create_index(
        "idx_participant_created", "participants", ["created_at"], unique=False
    )
    op.create_index("idx_participant_user", "participants", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_participants_created_at"), "participants", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_participants_user_id"), "participants", ["user_id"], unique=True
    )

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("maintenance_mode", sa.Boolean(), nullable=False),
        sa.Column(
            "maintenance_message",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
        sa.Column("allow_registrations", sa.Boolean(), nullable=False),
        sa.Column("ai_model", sa.String(length=100), nullable=False),
        sa.Column("ai_temperature", sa.Float(), nullable=False),
        sa.Column("ai_max_tokens", sa.Integer(), nullable=False),
        sa.Column("max_debate_turns", sa.Integer(), nullable=False),
        sa.Column("debate_consensus_threshold", sa.Float(), nullable=False),
        sa.Column("rag_enabled", sa.Boolean(), nullable=False),
        sa.Column("debate_feature_enabled", sa.Boolean(), nullable=False),
        sa.Column("thesis_mode_enabled", sa.Boolean(), nullable=False),
        sa.Column("rate_limit_enabled", sa.Boolean(), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False),
        sa.Column("max_upload_size_mb", sa.Integer(), nullable=False),
        sa.Column(
            "allowed_file_types",
            sqlmodel.sql.sqltypes.AutoString(length=200),
            nullable=False,
        ),
        sa.Column("email_notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "revocation_reason",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=True,
        ),
        sa.Column(
            "user_agent", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column(
            "ip_address", sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True
        ),
        sa.Column(
            "device_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("is_remember_me", sa.Boolean(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_refresh_token_created",
        "refresh_tokens",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_refresh_token_expires",
        "refresh_tokens",
        ["expires_at", "revoked_at"],
        unique=False,
    )
    op.create_index(
        "idx_refresh_token_user_active",
        "refresh_tokens",
        ["user_id", "revoked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_created_at"),
        "refresh_tokens",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_expires_at"),
        "refresh_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_token"), "refresh_tokens", ["token"], unique=True
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False
    )

    # questionnaire_responses — FK points to participants.id (fixed in b3e26d351cb4)
    op.create_table(
        "questionnaire_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column(
            "condition",
            sa.Enum("BASELINE", "MULTIAGENT", name="experimentcondition"),
            nullable=False,
        ),
        sa.Column("trust_overall", sa.Integer(), nullable=False),
        sa.Column("risk_awareness", sa.Integer(), nullable=False),
        sa.Column("technical_soundness", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.Column("actionability", sa.Integer(), nullable=False),
        sa.Column("completeness", sa.Integer(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=False),
        sa.Column("concerns", sa.Text(), nullable=False),
        sa.Column("trust_reasoning", sa.Text(), nullable=False),
        sa.Column("persona_consistency", sa.Text(), nullable=True),
        sa.Column("debate_value", sa.Text(), nullable=True),
        sa.Column(
            "most_convincing_persona",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=True,
        ),
        sa.Column("time_to_complete_seconds", sa.Integer(), nullable=True),
        sa.Column("order_in_session", sa.Integer(), nullable=True),
        sa.Column(
            "session_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        # condition_order added in 01cf076eac9d
        sa.Column(
            "condition_order",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=True,
        ),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column(
            "quality_note", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_response_participant_condition",
        "questionnaire_responses",
        ["participant_id", "condition"],
        unique=False,
    )
    op.create_index(
        "idx_response_scenario_condition",
        "questionnaire_responses",
        ["scenario_id", "condition"],
        unique=False,
    )
    op.create_index(
        "idx_response_session", "questionnaire_responses", ["session_id"], unique=False
    )
    op.create_index(
        "idx_response_submitted",
        "questionnaire_responses",
        ["submitted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_questionnaire_responses_condition"),
        "questionnaire_responses",
        ["condition"],
        unique=False,
    )
    op.create_index(
        op.f("ix_questionnaire_responses_participant_id"),
        "questionnaire_responses",
        ["participant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_questionnaire_responses_scenario_id"),
        "questionnaire_responses",
        ["scenario_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_questionnaire_responses_session_id"),
        "questionnaire_responses",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_questionnaire_responses_submitted_at"),
        "questionnaire_responses",
        ["submitted_at"],
        unique=False,
    )

    # ── 3. Tables depending on projects or participants ───────────────────────

    op.create_table(
        "historical_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "mime_type", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="documentstatus"
            ),
            nullable=False,
        ),
        sa.Column("indexing_progress", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("upload_date", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_document_project_status",
        "historical_documents",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_document_status_processed",
        "historical_documents",
        ["status", "processed_at"],
        unique=False,
    )
    op.create_index(
        "idx_document_upload_date",
        "historical_documents",
        ["upload_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_historical_documents_project_id"),
        "historical_documents",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_historical_documents_status"),
        "historical_documents",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_historical_documents_upload_date"),
        "historical_documents",
        ["upload_date"],
        unique=False,
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_length", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column(
            "section_title", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True
        ),
        sa.Column("start_char", sa.Integer(), nullable=True),
        sa.Column("end_char", sa.Integer(), nullable=True),
        sa.Column(
            "embedding", pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True
        ),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["historical_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_chunk_document_index",
        "document_chunks",
        ["document_id", "chunk_index"],
        unique=False,
    )
    op.create_index(
        "idx_chunk_document_page",
        "document_chunks",
        ["document_id", "page_number"],
        unique=False,
    )
    op.create_index(
        "idx_chunk_embedding",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "idx_chunk_search_vector",
        "document_chunks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"),
        "document_chunks",
        ["document_id"],
        unique=False,
    )

    op.create_table(
        "project_stakeholder_links",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("OWNER", "ADMIN", "EDITOR", "VIEWER", name="projectrole"),
            nullable=False,
        ),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
    )
    op.create_index(
        "idx_link_project_role",
        "project_stakeholder_links",
        ["project_id", "role"],
        unique=False,
    )
    op.create_index(
        "idx_link_user_projects",
        "project_stakeholder_links",
        ["user_id", "joined_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_stakeholder_links_role"),
        "project_stakeholder_links",
        ["role"],
        unique=False,
    )

    op.create_table(
        "stakeholders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=False),
        sa.Column(
            "department", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True
        ),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column(
            "influence",
            sa.Enum("HIGH", "MEDIUM", "LOW", name="influencelevel"),
            nullable=False,
        ),
        sa.Column(
            "interest",
            sa.Enum("HIGH", "MEDIUM", "LOW", name="interestlevel"),
            nullable=False,
        ),
        sa.Column(
            "sentiment",
            sa.Enum(
                "CHAMPION",
                "SUPPORTIVE",
                "NEUTRAL",
                "CONCERNED",
                "RESISTANT",
                "BLOCKER",
                name="sentiment",
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("strategic_plan", sa.Text(), nullable=True),
        sa.Column("concerns", sa.Text(), nullable=True),
        sa.Column("motivations", sa.Text(), nullable=True),
        sa.Column(
            "approval_role", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("notify_on_approval_needed", sa.Boolean(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_stakeholder_approval_role",
        "stakeholders",
        ["approval_role", "project_id"],
        unique=False,
    )
    op.create_index(
        "idx_stakeholder_project_influence",
        "stakeholders",
        ["project_id", "influence"],
        unique=False,
    )
    op.create_index(
        "idx_stakeholder_project_sentiment",
        "stakeholders",
        ["project_id", "sentiment"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stakeholders_approval_role"),
        "stakeholders",
        ["approval_role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stakeholders_email"), "stakeholders", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_stakeholders_influence"), "stakeholders", ["influence"], unique=False
    )
    op.create_index(
        op.f("ix_stakeholders_interest"), "stakeholders", ["interest"], unique=False
    )
    op.create_index(
        op.f("ix_stakeholders_project_id"), "stakeholders", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_stakeholders_sentiment"), "stakeholders", ["sentiment"], unique=False
    )

    # exit_surveys — preferred_system_actual added in 7eaf5615d438
    op.create_table(
        "exit_surveys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column(
            "preferred_system",
            sa.Enum(
                "FIRST", "SECOND", "NO_PREFERENCE", "NOT_SURE", name="preferredsystem"
            ),
            nullable=False,
        ),
        sa.Column(
            "preferred_system_actual",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=True,
        ),
        sa.Column("preference_reasoning", sa.Text(), nullable=False),
        sa.Column("interface_rating", sa.Integer(), nullable=False),
        sa.Column(
            "experienced_fatigue",
            sa.Enum("NONE", "A_LITTLE", "YES_SIGNIFICANTLY", name="fatiguelevel"),
            nullable=False,
        ),
        sa.Column("technical_issues", sa.Text(), nullable=True),
        sa.Column("additional_feedback", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_exit_survey_participant", "exit_surveys", ["participant_id"], unique=False
    )
    op.create_index(
        "idx_exit_survey_preferred_system",
        "exit_surveys",
        ["preferred_system"],
        unique=False,
    )
    op.create_index(
        "idx_exit_survey_submitted", "exit_surveys", ["submitted_at"], unique=False
    )
    op.create_index(
        op.f("ix_exit_surveys_participant_id"),
        "exit_surveys",
        ["participant_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_exit_surveys_submitted_at"),
        "exit_surveys",
        ["submitted_at"],
        unique=False,
    )

    # ── 4. proposals + variations (circular dependency) ───────────────────────

    # proposals — rejection_reason + revision_feedback added in 472b065a56f7
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("structured_prd", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "PROCESSING", "COMPLETED", "FAILED", name="proposalstatus"
            ),
            nullable=False,
        ),
        sa.Column(
            "approval_status",
            sa.Enum(
                "DRAFT",
                "PENDING_APPROVAL",
                "IN_REVIEW",
                "APPROVED",
                "REJECTED",
                "REVISION_NEEDED",
                name="approvalstatus",
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("revision_feedback", sa.Text(), nullable=True),
        sa.Column("selected_variation_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        # selected_variation_id FK added below after proposal_variations is created
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_proposal_approval",
        "proposals",
        ["approval_status", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_proposal_created_by",
        "proposals",
        ["created_by_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_proposal_project_status",
        "proposals",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposals_approval_status"),
        "proposals",
        ["approval_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposals_created_at"), "proposals", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_proposals_created_by_id"), "proposals", ["created_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_proposals_project_id"), "proposals", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_proposals_status"), "proposals", ["status"], unique=False)

    op.create_table(
        "proposal_variations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "agent_persona",
            sa.Enum(
                "LEGACY_KEEPER",
                "INNOVATOR",
                "MEDIATOR",
                "BASELINE",
                name="agentpersona",
            ),
            nullable=True,
        ),
        sa.Column("structured_prd", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("trade_offs", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("generation_seconds", sa.Float(), nullable=True),
        sa.Column(
            "chat_history", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("proposal_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_proposal_variations_proposal_id"),
        "proposal_variations",
        ["proposal_id"],
        unique=False,
    )

    # Close the circular FK
    op.create_foreign_key(
        "fk_proposals_selected_variation_id",
        "proposals",
        "proposal_variations",
        ["selected_variation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── 5. Tables depending on proposals ─────────────────────────────────────

    # debate_sessions — consensus_confidence added in 79f8bd0da366
    op.create_table(
        "debate_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Integer(), nullable=False),
        sa.Column("debate_history", sa.JSON(), nullable=True),
        sa.Column(
            "final_consensus_proposal",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
        sa.Column("consensus_reached", sa.Boolean(), nullable=False),
        sa.Column(
            "consensus_type",
            sa.Enum(
                "UNANIMOUS", "MAJORITY", "COMPROMISE", "TIMEOUT", name="consensustype"
            ),
            nullable=True,
        ),
        sa.Column("consensus_confidence", sa.Float(), nullable=True),
        sa.Column("total_turns", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("conflict_density", sa.Float(), nullable=False),
        sa.Column("legacy_keeper_consistency", sa.Float(), nullable=False),
        sa.Column("innovator_consistency", sa.Float(), nullable=False),
        sa.Column("mediator_consistency", sa.Float(), nullable=False),
        sa.Column("overall_persona_consistency", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_debate_consensus",
        "debate_sessions",
        ["consensus_reached", "completed_at"],
        unique=False,
    )
    op.create_index(
        "idx_debate_proposal", "debate_sessions", ["proposal_id"], unique=False
    )
    op.create_index(
        "idx_debate_started", "debate_sessions", ["started_at"], unique=False
    )
    op.create_index(
        op.f("ix_debate_sessions_proposal_id"),
        "debate_sessions",
        ["proposal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_debate_sessions_started_at"),
        "debate_sessions",
        ["started_at"],
        unique=False,
    )

    op.create_table(
        "persona_codings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("debate_id", sa.Uuid(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column(
            "persona", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False
        ),
        sa.Column(
            "in_character",
            sa.Enum("YES", "PARTIAL", "NO", name="incharacterrating"),
            nullable=False,
        ),
        sa.Column("quality_attributes", sa.JSON(), nullable=True),
        sa.Column(
            "hallucination",
            sa.Enum("NONE", "MINOR", "MAJOR", name="hallucinationrating"),
            nullable=False,
        ),
        sa.Column("bias_alignment", sa.Boolean(), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("evidence_quote", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("coder_id", sa.Integer(), nullable=False),
        sa.Column("coding_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["coder_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_coding_coder", "persona_codings", ["coder_id", "created_at"], unique=False
    )
    op.create_index(
        "idx_coding_debate_turn",
        "persona_codings",
        ["debate_id", "turn_index"],
        unique=False,
    )
    op.create_index(
        "idx_coding_persona",
        "persona_codings",
        ["persona", "in_character"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persona_codings_coder_id"),
        "persona_codings",
        ["coder_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persona_codings_created_at"),
        "persona_codings",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_persona_codings_debate_id"),
        "persona_codings",
        ["debate_id"],
        unique=False,
    )

    op.create_table(
        "task_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "mime_type", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("proposal_id", sa.Integer(), nullable=False),
        sa.Column("uploader_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.id"]),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_task_documents_proposal_id"),
        "task_documents",
        ["proposal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_documents_uploader_id"),
        "task_documents",
        ["uploader_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_task_documents_uploader_id"), table_name="task_documents")
    op.drop_index(op.f("ix_task_documents_proposal_id"), table_name="task_documents")
    op.drop_table("task_documents")

    op.drop_index(op.f("ix_persona_codings_debate_id"), table_name="persona_codings")
    op.drop_index(op.f("ix_persona_codings_created_at"), table_name="persona_codings")
    op.drop_index(op.f("ix_persona_codings_coder_id"), table_name="persona_codings")
    op.drop_index("idx_coding_persona", table_name="persona_codings")
    op.drop_index("idx_coding_debate_turn", table_name="persona_codings")
    op.drop_index("idx_coding_coder", table_name="persona_codings")
    op.drop_table("persona_codings")

    op.drop_index(op.f("ix_debate_sessions_started_at"), table_name="debate_sessions")
    op.drop_index(op.f("ix_debate_sessions_proposal_id"), table_name="debate_sessions")
    op.drop_index("idx_debate_started", table_name="debate_sessions")
    op.drop_index("idx_debate_proposal", table_name="debate_sessions")
    op.drop_index("idx_debate_consensus", table_name="debate_sessions")
    op.drop_table("debate_sessions")

    op.drop_constraint(
        "fk_proposals_selected_variation_id", "proposals", type_="foreignkey"
    )

    op.drop_index(
        op.f("ix_proposal_variations_proposal_id"), table_name="proposal_variations"
    )
    op.drop_table("proposal_variations")

    op.drop_index(op.f("ix_proposals_status"), table_name="proposals")
    op.drop_index(op.f("ix_proposals_project_id"), table_name="proposals")
    op.drop_index(op.f("ix_proposals_created_by_id"), table_name="proposals")
    op.drop_index(op.f("ix_proposals_created_at"), table_name="proposals")
    op.drop_index(op.f("ix_proposals_approval_status"), table_name="proposals")
    op.drop_index("idx_proposal_project_status", table_name="proposals")
    op.drop_index("idx_proposal_created_by", table_name="proposals")
    op.drop_index("idx_proposal_approval", table_name="proposals")
    op.drop_table("proposals")

    op.drop_index(op.f("ix_exit_surveys_submitted_at"), table_name="exit_surveys")
    op.drop_index(op.f("ix_exit_surveys_participant_id"), table_name="exit_surveys")
    op.drop_index("idx_exit_survey_submitted", table_name="exit_surveys")
    op.drop_index("idx_exit_survey_preferred_system", table_name="exit_surveys")
    op.drop_index("idx_exit_survey_participant", table_name="exit_surveys")
    op.drop_table("exit_surveys")

    op.drop_index(op.f("ix_stakeholders_sentiment"), table_name="stakeholders")
    op.drop_index(op.f("ix_stakeholders_project_id"), table_name="stakeholders")
    op.drop_index(op.f("ix_stakeholders_interest"), table_name="stakeholders")
    op.drop_index(op.f("ix_stakeholders_influence"), table_name="stakeholders")
    op.drop_index(op.f("ix_stakeholders_email"), table_name="stakeholders")
    op.drop_index(op.f("ix_stakeholders_approval_role"), table_name="stakeholders")
    op.drop_index("idx_stakeholder_project_sentiment", table_name="stakeholders")
    op.drop_index("idx_stakeholder_project_influence", table_name="stakeholders")
    op.drop_index("idx_stakeholder_approval_role", table_name="stakeholders")
    op.drop_table("stakeholders")

    op.drop_index(
        op.f("ix_project_stakeholder_links_role"),
        table_name="project_stakeholder_links",
    )
    op.drop_index("idx_link_user_projects", table_name="project_stakeholder_links")
    op.drop_index("idx_link_project_role", table_name="project_stakeholder_links")
    op.drop_table("project_stakeholder_links")

    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_index(
        "idx_chunk_search_vector", table_name="document_chunks", postgresql_using="gin"
    )
    op.drop_index(
        "idx_chunk_embedding",
        table_name="document_chunks",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_index("idx_chunk_document_page", table_name="document_chunks")
    op.drop_index("idx_chunk_document_index", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index(
        op.f("ix_historical_documents_upload_date"), table_name="historical_documents"
    )
    op.drop_index(
        op.f("ix_historical_documents_status"), table_name="historical_documents"
    )
    op.drop_index(
        op.f("ix_historical_documents_project_id"), table_name="historical_documents"
    )
    op.drop_index("idx_document_upload_date", table_name="historical_documents")
    op.drop_index("idx_document_status_processed", table_name="historical_documents")
    op.drop_index("idx_document_project_status", table_name="historical_documents")
    op.drop_table("historical_documents")

    op.drop_index(
        op.f("ix_questionnaire_responses_submitted_at"),
        table_name="questionnaire_responses",
    )
    op.drop_index(
        op.f("ix_questionnaire_responses_session_id"),
        table_name="questionnaire_responses",
    )
    op.drop_index(
        op.f("ix_questionnaire_responses_scenario_id"),
        table_name="questionnaire_responses",
    )
    op.drop_index(
        op.f("ix_questionnaire_responses_participant_id"),
        table_name="questionnaire_responses",
    )
    op.drop_index(
        op.f("ix_questionnaire_responses_condition"),
        table_name="questionnaire_responses",
    )
    op.drop_index("idx_response_submitted", table_name="questionnaire_responses")
    op.drop_index("idx_response_session", table_name="questionnaire_responses")
    op.drop_index(
        "idx_response_scenario_condition", table_name="questionnaire_responses"
    )
    op.drop_index(
        "idx_response_participant_condition", table_name="questionnaire_responses"
    )
    op.drop_table("questionnaire_responses")

    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_token"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_expires_at"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_created_at"), table_name="refresh_tokens")
    op.drop_index("idx_refresh_token_user_active", table_name="refresh_tokens")
    op.drop_index("idx_refresh_token_expires", table_name="refresh_tokens")
    op.drop_index("idx_refresh_token_created", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_table("system_settings")

    op.drop_index(op.f("ix_participants_user_id"), table_name="participants")
    op.drop_index(op.f("ix_participants_created_at"), table_name="participants")
    op.drop_index("idx_participant_user", table_name="participants")
    op.drop_index("idx_participant_created", table_name="participants")
    op.drop_index("idx_participant_condition_order", table_name="participants")
    op.drop_table("participants")

    op.drop_index(op.f("ix_projects_owner_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_name"), table_name="projects")
    op.drop_index(op.f("ix_projects_last_activity_at"), table_name="projects")
    op.drop_index(op.f("ix_projects_created_at"), table_name="projects")
    op.drop_index("idx_project_visibility", table_name="projects")
    op.drop_index("idx_project_owner_created", table_name="projects")
    op.drop_index("idx_project_archived_activity", table_name="projects")
    op.drop_table("projects")

    op.drop_index("idx_token_usage_operation", table_name="token_usage_records")
    op.drop_index("idx_token_usage_user", table_name="token_usage_records")
    op.drop_table("token_usage_records")

    op.drop_index(op.f("ix_users_verification_token"), table_name="users")
    op.drop_index(op.f("ix_users_reset_token"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index("idx_user_role_active", table_name="users")
    op.drop_index("idx_user_email_verified", table_name="users")
    op.drop_index("idx_user_created_at", table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_prompt_templates_slug"), table_name="prompt_templates")
    op.drop_index(op.f("ix_prompt_templates_is_active"), table_name="prompt_templates")
    op.drop_index(op.f("ix_prompt_templates_category"), table_name="prompt_templates")
    op.drop_index("idx_prompt_template_slug_active", table_name="prompt_templates")
    op.drop_index("idx_prompt_template_category_active", table_name="prompt_templates")
    op.drop_table("prompt_templates")

    # Drop all PostgreSQL enum types created by this migration.
    # Without this, a subsequent upgrade will fail with
    # "type X already exists" since enums outlive their tables.
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS templatecategory")
    op.execute("DROP TYPE IF EXISTS projectvisibility")
    op.execute("DROP TYPE IF EXISTS projectrole")
    op.execute("DROP TYPE IF EXISTS experiencelevel")
    op.execute("DROP TYPE IF EXISTS conditionorder")
    op.execute("DROP TYPE IF EXISTS experimentcondition")
    op.execute("DROP TYPE IF EXISTS documentstatus")
    op.execute("DROP TYPE IF EXISTS influencelevel")
    op.execute("DROP TYPE IF EXISTS interestlevel")
    op.execute("DROP TYPE IF EXISTS sentiment")
    op.execute("DROP TYPE IF EXISTS preferredsystem")
    op.execute("DROP TYPE IF EXISTS fatiguelevel")
    op.execute("DROP TYPE IF EXISTS proposalstatus")
    op.execute("DROP TYPE IF EXISTS approvalstatus")
    op.execute("DROP TYPE IF EXISTS agentpersona")
    op.execute("DROP TYPE IF EXISTS consensustype")
    op.execute("DROP TYPE IF EXISTS incharacterrating")
    op.execute("DROP TYPE IF EXISTS hallucinationrating")
