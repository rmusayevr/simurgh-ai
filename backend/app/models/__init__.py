"""
Database models package.

Import order matters for SQLModel/SQLAlchemy relationship resolution.
Models are imported in dependency order (dependencies first).

Import Order:
    1. Link tables (no dependencies)
    2. Core models (User, Project)
    3. Feature models (Proposal, Debate, Stakeholder)
    4. Config models (Settings, Templates)
    5. Thesis models (Questionnaire, PersonaCoding)

Note:
    PersonaProfile and PersonaAnalysis are NOT database models.
    They have been moved to app.schemas.persona.

    Commented workflow models are preserved for future implementation.
"""

# ==================== 1. Link Tables ====================
# Must be imported first (no foreign key dependencies)

from app.models.links import ProjectStakeholderLink, ProjectRole  # noqa: F401

# ==================== 2. Core Models ====================
# Foundation models that others depend on

from app.models.token import RefreshToken  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401
from app.models.atlassian_credential import AtlassianCredential  # noqa: F401
from app.models.project import (  # noqa: F401
    Project,
    HistoricalDocument,
    DocumentStatus,
    ProjectVisibility,
)

# ==================== 3. Feature Models ====================

from app.models.proposal import (  # noqa: F401
    Proposal,
    ProposalVariation,
    ProposalStatus,
    ApprovalStatus,
    AgentPersona,
    TaskDocument,
)
from app.models.debate import (  # noqa: F401
    DebateSession,
    DebateTurn,
    ConsensusType,
)
from app.models.stakeholder import (  # noqa: F401
    Stakeholder,
    InfluenceLevel,
    InterestLevel,
    Sentiment,
)
from app.models.chunk import DocumentChunk  # noqa: F401

# ==================== 4. Config Models ====================

from app.models.settings import SystemSettings  # noqa: F401
from app.models.prompt import (  # noqa: F401
    PromptTemplate,
    TemplateCategory,
)

# ==================== 5. Thesis / Research Models ====================

from app.models.participant import (  # noqa: F401
    Participant,
    ExperienceLevel,
    ConditionOrder,
)

from app.models.questionnaire import (  # noqa: F401
    QuestionnaireResponse,
    ExperimentCondition,
    ScenarioID,
)
from app.models.persona_coding import (  # noqa: F401
    PersonaCoding,
    InCharacterRating,
    HallucinationRating,
)
from app.models.exit_survey import (  # noqa: F401
    ExitSurvey,
    PreferredSystem,
    FatigueLevel,
)

# ==================== Public API ====================

__all__ = [
    # --- Link Tables ---
    "ProjectStakeholderLink",
    "ProjectRole",
    # --- Core Models ---
    "RefreshToken",
    "User",
    "UserRole",
    "AtlassianCredential",
    # --- Project Models ---
    "Project",
    "ProjectVisibility",
    "HistoricalDocument",
    "DocumentStatus",
    # --- Proposal Models ---
    "Proposal",
    "ProposalVariation",
    "ProposalStatus",
    "ApprovalStatus",
    "AgentPersona",
    "TaskDocument",
    # --- Debate Models ---
    "DebateSession",
    "DebateTurn",
    "ConsensusType",
    # --- Stakeholder Models ---
    "Stakeholder",
    "InfluenceLevel",
    "InterestLevel",
    "Sentiment",
    # --- Document Models ---
    "DocumentChunk",
    # --- Config Models ---
    "SystemSettings",
    "PromptTemplate",
    "TemplateCategory",
    # --- Thesis Models ---
    "Participant",
    "ExperienceLevel",
    "ConditionOrder",
    "QuestionnaireResponse",
    "ExperimentCondition",
    "ScenarioID",
    "PersonaCoding",
    "InCharacterRating",
    "HallucinationRating",
    "ExitSurvey",
    "PreferredSystem",
    "FatigueLevel",
]
