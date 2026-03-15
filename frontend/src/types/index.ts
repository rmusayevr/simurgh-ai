// src/types/index.ts
// Aligned 1:1 with backend models and schemas.
// All enum values match the Python Enum .value strings exactly.

// ─── 1. ENUMS ────────────────────────────────────────────────────────────────

/** Matches backend UserRole enum */
export const UserRole = {
    ADMIN: 'ADMIN',
    MANAGER: 'MANAGER',
    USER: 'USER',
} as const;
export type UserRole = typeof UserRole[keyof typeof UserRole];

/** Matches backend InfluenceLevel enum */
export const InfluenceLevel = {
    HIGH: 'HIGH',
    MEDIUM: 'MEDIUM',
    LOW: 'LOW',
} as const;
export type InfluenceLevel = typeof InfluenceLevel[keyof typeof InfluenceLevel];

/** Matches backend InterestLevel enum */
export const InterestLevel = {
    HIGH: 'HIGH',
    MEDIUM: 'MEDIUM',
    LOW: 'LOW',
} as const;
export type InterestLevel = typeof InterestLevel[keyof typeof InterestLevel];

/** Matches backend Sentiment enum */
export const Sentiment = {
    CHAMPION: 'CHAMPION',
    SUPPORTIVE: 'SUPPORTIVE',
    NEUTRAL: 'NEUTRAL',
    CONCERNED: 'CONCERNED',
    RESISTANT: 'RESISTANT',
    BLOCKER: 'BLOCKER',
} as const;
export type Sentiment = typeof Sentiment[keyof typeof Sentiment];

/** Matches backend ProposalStatus enum */
export const ProposalStatus = {
    DRAFT: 'DRAFT',
    PROCESSING: 'PROCESSING',
    COMPLETED: 'COMPLETED',
    FAILED: 'FAILED',
} as const;
export type ProposalStatus = typeof ProposalStatus[keyof typeof ProposalStatus];

/** Matches backend ApprovalStatus enum */
export const ApprovalStatus = {
    DRAFT: 'DRAFT',
    PENDING_APPROVAL: 'PENDING_APPROVAL',
    IN_REVIEW: 'IN_REVIEW',
    APPROVED: 'APPROVED',
    REJECTED: 'REJECTED',
    REVISION_NEEDED: 'REVISION_NEEDED',
} as const;
export type ApprovalStatus = typeof ApprovalStatus[keyof typeof ApprovalStatus];

/** Matches backend AgentPersona enum */
export const AgentPersona = {
    LEGACY_KEEPER: 'LEGACY_KEEPER',
    INNOVATOR: 'INNOVATOR',
    MEDIATOR: 'MEDIATOR',
    BASELINE: 'BASELINE',
} as const;
export type AgentPersona = typeof AgentPersona[keyof typeof AgentPersona];

/** Matches backend DocumentStatus enum */
export const DocumentStatus = {
    PENDING: 'PENDING',
    PROCESSING: 'PROCESSING',
    COMPLETED: 'COMPLETED',
    FAILED: 'FAILED',
} as const;
export type DocumentStatus = typeof DocumentStatus[keyof typeof DocumentStatus];

/** Matches backend ProjectVisibility enum (lowercase values) */
export const ProjectVisibility = {
    PRIVATE: 'private',
    TEAM: 'team',
    PUBLIC: 'public',
} as const;
export type ProjectVisibility = typeof ProjectVisibility[keyof typeof ProjectVisibility];

/** Matches backend ProjectRole enum (links.py) */
export const ProjectRole = {
    OWNER: 'OWNER',
    ADMIN: 'ADMIN',
    EDITOR: 'EDITOR',
    VIEWER: 'VIEWER',
} as const;
export type ProjectRole = typeof ProjectRole[keyof typeof ProjectRole];

/** Matches backend ConsensusType enum */
export const ConsensusType = {
    UNANIMOUS: 'UNANIMOUS',
    MAJORITY: 'MAJORITY',
    COMPROMISE: 'COMPROMISE',
    TIMEOUT: 'TIMEOUT',
} as const;
export type ConsensusType = typeof ConsensusType[keyof typeof ConsensusType];

/** Matches backend InCharacterRating enum */
export const InCharacterRating = {
    YES: 'yes',
    PARTIAL: 'partial',
    NO: 'no',
} as const;
export type InCharacterRating = typeof InCharacterRating[keyof typeof InCharacterRating];

/**
 * Matches backend HallucinationRating enum.
 * NOTE: NONE = "no" (not "none") — matches the Python Enum value exactly.
 */
export const HallucinationRating = {
    NONE: 'no',
    MINOR: 'minor',
    MAJOR: 'major',
} as const;
export type HallucinationRating = typeof HallucinationRating[keyof typeof HallucinationRating];

/** Matches backend ExperienceLevel enum */
export const ExperienceLevel = {
    MSC_STUDENT: 'msc_student',
    JUNIOR: 'junior',
    SENIOR: 'senior',
    ARCHITECT: 'architect',
} as const;
export type ExperienceLevel = typeof ExperienceLevel[keyof typeof ExperienceLevel];

export const ExperienceLevelLabels: Record<ExperienceLevel, string> = {
    msc_student: 'MSc Student',
    junior: 'Junior Developer (0-2 years)',
    senior: 'Senior Developer (3-7 years)',
    architect: 'Software Architect (8+ years)',
};

/** Matches backend ConditionOrder enum */
export const ConditionOrder = {
    BASELINE_FIRST: 'baseline_first',
    MULTIAGENT_FIRST: 'multiagent_first',
} as const;
export type ConditionOrder = typeof ConditionOrder[keyof typeof ConditionOrder];

/** Matches backend ExperimentCondition enum */
export const ExperimentCondition = {
    BASELINE: 'BASELINE',
    MULTIAGENT: 'MULTIAGENT',
} as const;
export type ExperimentCondition = typeof ExperimentCondition[keyof typeof ExperimentCondition];

/** Matches backend PreferredSystem enum */
export const PreferredSystem = {
    FIRST: 'first',
    SECOND: 'second',
    NO_PREFERENCE: 'no_preference',
    NOT_SURE: 'not_sure',
} as const;
export type PreferredSystem = typeof PreferredSystem[keyof typeof PreferredSystem];

/** Matches backend FatigueLevel enum */
export const FatigueLevel = {
    NONE: 'none',
    A_LITTLE: 'a_little',
    YES_SIGNIFICANTLY: 'yes_significantly',
} as const;
export type FatigueLevel = typeof FatigueLevel[keyof typeof FatigueLevel];

// ─── 2. AUTH & USERS ─────────────────────────────────────────────────────────

export interface JwtPayload {
    sub: string;
    exp: number;
    type: string;
}

/** Matches backend UserMinimalRead schema */
export interface UserMinimal {
    id: number;
    full_name: string | null;
    avatar_url?: string | null;
    role: UserRole;
}

interface BaseUser {
    id: number;
    email: string;
    full_name: string | null;
    job_title?: string | null;
    role: UserRole;
    is_active: boolean;
    is_superuser: boolean;
    email_verified: boolean;
    login_count: number;
    last_login?: string | null;
    created_at: string;
}

export type AdminUser = BaseUser;

export interface UserProfile extends BaseUser {
    avatar_url?: string | null;
    terms_accepted: boolean;
    updated_at: string;
    project_role?: ProjectRole;
}

export interface AuthContextType {
    isAuthenticated: boolean;
    user: UserProfile | null;
    loading: boolean;
    login: (username: string, password: string) => Promise<void>;
    logout: () => void;
    refreshProfile: () => Promise<void>;
}

// ─── 3. PROJECT ───────────────────────────────────────────────────────────────

export interface ProjectMemberLink {
    user_id: number;
    user: UserMinimal;
    role: ProjectRole;
    joined_at: string;
    last_active_at?: string | null;
}

export interface ProjectListItem {
    id: number;
    name: string;
    description: string | null;
    visibility: ProjectVisibility;
    is_archived: boolean;
    owner_id: number;
    owner: UserMinimal | null;
    tags: string | null;
    tech_stack: string | null;
    document_count: number;
    proposal_count: number;
    member_count: number;
    created_at: string;
    last_activity_at: string;
}

export interface Project {
    id: number;
    name: string;
    description: string | null;
    visibility: ProjectVisibility;
    is_archived: boolean;
    owner_id: number;
    owner: UserMinimal | null;
    tags: string | null;
    tech_stack: string | null;
    document_count: number;
    proposal_count: number;
    member_count: number;
    stakeholder_links: ProjectMemberLink[];
    historical_documents: HistoricalDocument[];
    analysis_stakeholders: Stakeholder[];
    created_at: string;
    updated_at: string;
    last_activity_at: string;
    archived_at?: string | null;
}

// ─── 4. DOCUMENTS ─────────────────────────────────────────────────────────────

export interface HistoricalDocument {
    id: number;
    filename: string;
    file_size_bytes: number | null;
    mime_type: string | null;
    status: DocumentStatus;
    chunk_count: number;
    character_count: number;
    upload_date: string;
    processed_at: string | null;
    uploaded_by_id: number | null;
    project_id: number;
}

export interface TaskDocument {
    id: number;
    filename: string;
    file_size_bytes: number | null;
    mime_type: string | null;
    uploaded_at: string;
    uploader: UserMinimal | null;
}

// ─── 5. STAKEHOLDERS ──────────────────────────────────────────────────────────

export interface Stakeholder {
    id: number;
    project_id: number;
    name: string;
    role: string;
    department?: string | null;
    email?: string | null;
    influence: InfluenceLevel;
    interest: InterestLevel;
    sentiment: Sentiment;
    notes?: string | null;
    strategic_plan?: string | null;
    concerns?: string | null;
    motivations?: string | null;
    approval_role?: string | null;
    notify_on_approval_needed: boolean;
    created_at: string;
    updated_at: string;
}

// ─── 6. PROPOSALS ─────────────────────────────────────────────────────────────

export interface ProposalVariation {
    id: number;
    agent_persona: AgentPersona;
    structured_prd: string;
    reasoning: string | null;
    trade_offs: string | null;
    confidence_score: number;
    chat_history: ChatMessage[];
    proposal_id: number;
    created_at: string;
}

export interface Proposal {
    id: number;
    project_id: number;
    task_description: string;
    structured_prd: string | null;
    status: ProposalStatus;
    approval_status: ApprovalStatus;
    error_message: string | null;
    selected_variation_id: number | null;
    created_by_id: number | null;
    approved_by_id: number | null;
    approved_at: string | null;
    variations: ProposalVariation[];
    task_documents: TaskDocument[];
    created_at: string;
    updated_at: string;
}

export interface ProposalListItem {
    id: number;
    project_id: number;
    task_description: string;
    status: ProposalStatus;
    approval_status: ApprovalStatus;
    selected_variation_id: number | null;
    created_by_id: number | null;
    variation_count: number;
    created_at: string;
    updated_at: string;
}

// ─── 7. CHAT ──────────────────────────────────────────────────────────────────

export interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp?: string | null;
}

// ─── 8. DEBATE ────────────────────────────────────────────────────────────────

export interface DebateTurn {
    turn_number: number;
    persona: string;
    response: string;
    timestamp: string;
    sentiment?: string | null;
    key_points: string[];
}

export interface DebateResult {
    id: string;
    proposal_id: number;
    debate_history: DebateTurn[];
    final_consensus_proposal: string | null;
    consensus_reached: boolean;
    consensus_type: ConsensusType | null;
    total_turns: number;
    duration_seconds: number;
    conflict_density: number;
    legacy_keeper_consistency: number;
    innovator_consistency: number;
    mediator_consistency: number;
    overall_persona_consistency: number;
    started_at: string;
    completed_at: string | null;
}

export interface StartDebatePayload {
    document_ids?: number[];
    focus_areas?: string[];
    max_turns?: number;
    consensus_threshold?: number;
}

// ─── 9. ADMIN ─────────────────────────────────────────────────────────────────

export interface AdminProject {
    id: number;
    name: string;
    description: string | null;
    owner_email: string;
    created_at: string | null;
    proposal_count: number;
    document_count: number;
    member_count: number;
}

// ─── 10. PROMPTS ──────────────────────────────────────────────────────────────

export interface PromptTemplate {
    id: number;
    slug: string;
    name: string;
    system_prompt: string;
    is_active: boolean;
    updated_at: string;
}

// ─── 11. THESIS / EVALUATION ─────────────────────────────────────────────────

export interface ParticipantCreate {
    experience_level: ExperienceLevel;
    years_experience: number;
    familiarity_with_ai: number;
    consent_given: boolean;
}

export interface ParticipantRead {
    id: number;
    user_id: number;
    experience_level: ExperienceLevel;
    years_experience: number;
    familiarity_with_ai: number;
    consent_given: boolean;
    consent_timestamp: string | null;
    assigned_condition_order: ConditionOrder;
    created_at: string;
    completed_at: string | null;
}

export interface QuestionnaireCreate {
    participant_id: number;
    scenario_id: number;
    condition: ExperimentCondition;
    trust_overall: number;
    risk_awareness: number;
    technical_soundness: number;
    balance: number;
    actionability: number;
    completeness: number;
    strengths: string;
    concerns: string;
    trust_reasoning: string;
    persona_consistency?: string | null;
    debate_value?: string | null;
    most_convincing_persona?: string | null;
    time_to_complete_seconds?: number | null;
    order_in_session?: number | null;
    session_id?: string | null;
    condition_order?: ConditionOrder | null;
}

export interface QuestionnaireListRead {
    id: string;
    participant_id: number;
    scenario_id: number;
    condition: ExperimentCondition;
    trust_overall: number;
    risk_awareness: number;
    technical_soundness: number;
    balance: number;
    actionability: number;
    completeness: number;
    is_valid: boolean;
    session_id: string | null;
    order_in_session: number | null;
    time_to_complete_seconds: number | null;
    submitted_at: string;
}

export interface QuestionnaireRead extends QuestionnaireListRead {
    strengths: string;
    concerns: string;
    trust_reasoning: string;
    persona_consistency: string | null;
    debate_value: string | null;
    most_convincing_persona: string | null;
    quality_note: string | null;
}

export interface QuestionnaireExportRow {
    participant_id: number;
    scenario_id: number;
    condition: string;
    trust_overall: number;
    risk_awareness: number;
    technical_soundness: number;
    balance: number;
    actionability: number;
    completeness: number;
    mean_score: number;
    time_to_complete_seconds: number | null;
    order_in_session: number | null;
    session_id: string | null;
    is_valid: boolean;
    submitted_at: string;
}

export interface QuestionnaireExportSummary {
    total_responses: number;
    valid_responses: number;
    baseline_count: number;
    multiagent_count: number;
    baseline_mean_trust: number;
    multiagent_mean_trust: number;
    mean_difference: number;
    baseline_means: Record<string, number>;
    multiagent_means: Record<string, number>;
    invalid_count: number;
    straightlining_detected: number;
    rows: QuestionnaireExportRow[];
}

// ── Persona Coding (RQ2) ──────────────────────────────────────────────────────

export interface PersonaCodingCreate {
    debate_id: string;
    turn_index: number;
    persona: 'legacy_keeper' | 'innovator' | 'mediator';
    in_character: InCharacterRating;
    quality_attributes: string[];
    hallucination: HallucinationRating;
    bias_alignment: boolean;
    notes?: string | null;
    evidence_quote?: string | null;
    coder_id: number;
    coding_duration_seconds?: number | null;
}

export interface PersonaCoding extends PersonaCodingCreate {
    id: string;
    created_at: string;
    updated_at: string;
}

export interface PersonaConsistencyBreakdown {
    persona: string;
    total_turns_coded: number;
    fully_consistent: number;
    partially_consistent: number;
    inconsistent: number;
    mean_consistency_score: number;
    hallucination_count: number;
    major_hallucination_count: number;
    bias_aligned_count: number;
    top_quality_attributes: string[];
}

export interface PersonaCodingSummary {
    debate_id: string;
    total_turns_in_debate: number;
    turns_coded: number;
    coding_coverage: number;
    legacy_keeper: PersonaConsistencyBreakdown;
    innovator: PersonaConsistencyBreakdown;
    mediator: PersonaConsistencyBreakdown;
    overall_consistency_rate: number;
    overall_hallucination_rate: number;
    overall_bias_alignment_rate: number;
    coder_ids: number[];
    total_coding_time_seconds: number | null;
}

// ── Experiments ───────────────────────────────────────────────────────────────

export interface BaselineProposalRequest {
    proposal_id: number;
}

export interface BaselineVariationRead {
    id: number;
    agent_persona: string;
    structured_prd: string | null;
    reasoning: string | null;
    confidence_score: number;
    proposal_id: number;
    generation_time_seconds?: number | null;
}

export interface ExperimentComparison {
    proposal_id: number;
    baseline: {
        variation_id: number;
        word_count: number;
        confidence_score: number;
        generation_time_seconds: number | null;
    };
    multiagent: {
        variation_ids: number[];
        avg_word_count: number;
        avg_confidence_score: number;
    };
}

export interface ExperimentConditions {
    condition_a: {
        name: string;
        description: string;
        persona: string;
        generation_method: string;
    };
    condition_b: {
        name: string;
        description: string;
        personas: string[];
        generation_method: string;
    };
    evaluation: {
        questionnaire: string;
        rq1: string;
        rq3: string;
    };
}

// ── Exit Survey ───────────────────────────────────────────────────────────────

export interface ExitSurveyCreate {
    participant_id: number;
    preferred_system: PreferredSystem;
    /** Resolved at submission time: 'baseline' | 'multiagent' | 'no_preference' | 'not_sure' */
    preferred_system_actual?: string | null;
    preference_reasoning: string;
    interface_rating: number;
    experienced_fatigue: FatigueLevel;
    technical_issues?: string | null;
    additional_feedback?: string | null;
}

export interface ExitSurveyRead {
    id: string;
    participant_id: number;
    preferred_system: PreferredSystem;
    /** Resolved value — use this for statistical analysis, not preferred_system */
    preferred_system_actual?: string | null;
    preference_reasoning: string;
    interface_rating: number;
    experienced_fatigue: FatigueLevel;
    technical_issues?: string | null;
    additional_feedback?: string | null;
    submitted_at: string;
}

// ── Thesis analytics ──────────────────────────────────────────────────────────

export interface Transcript {
    debate_id: string;
    turn_index: number;
    persona: string;
    response: string;
    timestamp: string;
}

export interface ThematicTheme {
    name: string;
    description: string;
    example_quotes: string[];
    frequency: number;
    sentiment: 'positive' | 'negative' | 'neutral';
}

// ─── 12. RAG VERIFICATION ────────────────────────────────────────────────────

export interface DocumentVerification {
    filename: string;
    status: string;
    chunk_count: number;
    created_at: string;
}

export interface VerificationData {
    total_chunks: number;
    total_documents: number;
    documents: DocumentVerification[];
}

// ─── 13. COMPONENT PROPS ─────────────────────────────────────────────────────

export interface GeneratorTabProps {
    projectId: string;
    onHistoryUpdate?: (history: Proposal[]) => void;
    onVariationSelect?: (variation: ProposalVariation | null) => void;
}

export interface DocumentsTabProps {
    projectId: string;
}

// ─── 14. MISC ─────────────────────────────────────────────────────────────────

export interface RecentActivity {
    id: number;
    email: string;
    task: string;
    status: string;
    time: string;
}