import { useEffect, useState, useCallback } from 'react';
import {
    Users, BarChart3, MessageSquare, ClipboardCheck, RefreshCw,
    ChevronDown, ChevronUp, AlertTriangle, Trash2, XCircle,
    CheckCircle2, TrendingUp, TrendingDown, Minus, Eye,
    ShieldOff, FlaskConical, Clock, Target, Zap, Award
} from 'lucide-react';
import { experimentDataApi } from '../../api/client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Overview {
    // Matches GET /experiment-data/overview response shape
    participants: {
        total: number;
        completed: number;
        completion_rate_pct: number;
        condition_balance: { baseline_first: number; multiagent_first: number };
    };
    questionnaires: {
        total: number;
        valid: number;
        validity_rate_pct: number;
        mean_trust_score: { baseline: number | null; multiagent: number | null };
    };
    debates: { total: number; consensus_reached: number; consensus_rate_pct: number };
    exit_surveys: {
        total: number; preferred_baseline: number;
        preferred_multiagent: number; no_preference_or_unsure: number;
    };
    rq2_persona_codings: { total_codings: number };
}

interface ParticipantListItem {
    participant_id: number;
    user: { id: number; email: string | null; full_name: string | null };
    demographics: { experience_level: string; years_experience: number; familiarity_with_ai: number };
    experiment: {
        assigned_condition_order: string; consent_given: boolean;
        registered_at: string; completed_at: string | null; duration_minutes: number | null;
    };
    progress: {
        questionnaire_baseline_done: boolean; questionnaire_multiagent_done: boolean;
        exit_survey_done: boolean; steps_completed: number; steps_total: number;
        is_fully_complete: boolean;
    };
    questionnaire_summary: {
        baseline: { submitted: boolean; mean_score: number | null; trust_overall: number | null; is_valid: boolean | null };
        multiagent: { submitted: boolean; mean_score: number | null; trust_overall: number | null; is_valid: boolean | null };
        condition_difference: number | null;
    };
    exit_survey: {
        submitted: boolean; preferred_system_raw: string | null;
        preferred_system_actual: string | null; interface_rating: number | null;
        experienced_fatigue: string | null;
    };
}

interface ParticipantDetail {
    participant_id: number;
    user: { id: number; email: string | null; full_name: string | null };
    demographics: { experience_level: string; experience_level_display: string; years_experience: number; familiarity_with_ai: number };
    consent: { consent_given: boolean; consent_timestamp: string | null };
    experiment: { assigned_condition_order: string; registered_at: string; completed_at: string | null; duration_minutes: number | null };
    progress: { steps_completed: number; steps_total: number; is_fully_complete: boolean };
    questionnaires: {
        baseline: FullQuestionnaire[];
        multiagent: FullQuestionnaire[];
        within_subject_difference: number | null;
    };
    exit_survey: {
        survey_id: string; preferred_system_raw: string; preferred_system_actual: string | null;
        preference_reasoning: string; interface_rating: number; experienced_fatigue: string;
        technical_issues: string | null; additional_feedback: string | null; submitted_at: string;
    } | null;
}

interface FullQuestionnaire {
    response_id: string; scenario_id: number; condition: string;
    likert_scores: Record<string, number>;
    mean_score: number;
    open_ended: {
        strengths: string; concerns: string; trust_reasoning: string;
        persona_consistency: string | null; debate_value: string | null;
    };
    metadata: {
        time_to_complete_seconds: number | null; is_valid: boolean; quality_note: string | null;
        submitted_at: string;
    };
}

interface RQSummary {
    generated_at: string;
    rq1_trust_and_quality: {
        n_baseline: number; n_multiagent: number;
        composite_mean_score: {
            baseline: number | null; multiagent: number | null;
            baseline_stdev: number | null; multiagent_stdev: number | null;
            cohen_d: number | null;
        };
        per_item_baseline: Record<string, { mean: number | null; stdev: number | null }>;
        per_item_multiagent: Record<string, { mean: number | null; stdev: number | null }>;
    };
    rq2_persona_consistency: {
        total_turns_coded: number;
        per_persona: Record<string, { turns_coded: number; mean_consistency: number | null; pct_fully_consistent: number }>;
        hallucination_summary: { total_coded: number; none: number; minor: number; major: number };
    };
    rq3_consensus_efficiency: {
        baseline_generation: { n: number; mean_seconds: number | null; stdev_seconds: number | null };
        multiagent_debates: {
            n: number; consensus_reached: number; consensus_rate_pct: number;
            mean_turns: number | null; mean_duration_seconds: number | null;
        };
    };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const SCENARIO_LABELS: Record<number, string> = {
    1: 'Payment Migration', 2: 'Analytics Pipeline',
    3: 'Auth Modernisation', 4: 'Media Storage',
};

const METRIC_LABELS: Record<string, string> = {
    trust_overall: 'Trust', risk_awareness: 'Risk Awareness',
    technical_soundness: 'Technical', balance: 'Balance',
    actionability: 'Actionability', completeness: 'Completeness',
};

const CONDITION_ORDER_LABELS: Record<string, string> = {
    baseline_first: 'Baseline → Multi-Agent',
    multiagent_first: 'Multi-Agent → Baseline',
};

function fmt(n: number | null | undefined, decimals = 2): string {
    if (n === null || n === undefined) return '—';
    return n.toFixed(decimals);
}

function CohenBadge({ d }: { d: number | null }) {
    if (d === null) return <span className="text-slate-400 text-xs">—</span>;
    const abs = Math.abs(d);
    const positive = d > 0;
    const size = abs >= 0.8 ? 'Large' : abs >= 0.5 ? 'Medium' : abs >= 0.2 ? 'Small' : 'Negligible';
    const color = positive
        ? abs >= 0.5 ? 'bg-emerald-100 text-emerald-700' : 'bg-green-50 text-green-600'
        : abs >= 0.5 ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-500';
    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${color}`}>
            {positive ? <TrendingUp size={10} /> : d < 0 ? <TrendingDown size={10} /> : <Minus size={10} />}
            d={d > 0 ? '+' : ''}{fmt(d)} · {size}
        </span>
    );
}

function ProgressDots({ done, total }: { done: number; total: number }) {
    return (
        <div className="flex gap-1">
            {Array.from({ length: total }).map((_, i) => (
                <div
                    key={i}
                    className={`w-2 h-2 rounded-full transition-colors ${i < done ? 'bg-cyan-500' : 'bg-slate-200'}`}
                />
            ))}
        </div>
    );
}

function LikertBar({ label, value }: { label: string; value: number | null }) {
    if (value === null) return null;
    const pct = ((value - 1) / 6) * 100;
    const color = value >= 5 ? 'bg-emerald-500' : value >= 3 ? 'bg-amber-400' : 'bg-red-400';
    return (
        <div className="space-y-1">
            <div className="flex justify-between text-xs">
                <span className="text-slate-500">{label}</span>
                <span className="font-bold text-slate-700">{value}/7</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
            </div>
        </div>
    );
}

function SectionHeader({ icon: Icon, title, subtitle, color = 'bg-cyan-600' }: {
    icon: React.ElementType; title: string; subtitle: string; color?: string;
}) {
    return (
        <div className="flex items-center gap-3">
            <div className={`p-2 ${color} rounded-xl`}><Icon size={18} className="text-white" /></div>
            <div>
                <h3 className="text-base font-black text-slate-900">{title}</h3>
                <p className="text-xs text-slate-500">{subtitle}</p>
            </div>
        </div>
    );
}

// ── Sub-views ─────────────────────────────────────────────────────────────────

function OverviewPanel({ data }: { data: Overview }) {
    const { participants, questionnaires, debates, exit_surveys, rq2_persona_codings } = data;

    const prefTotal = exit_surveys.preferred_baseline + exit_surveys.preferred_multiagent + exit_surveys.no_preference_or_unsure;
    const multiPct = prefTotal ? Math.round((exit_surveys.preferred_multiagent / prefTotal) * 100) : 0;
    const basePct = prefTotal ? Math.round((exit_surveys.preferred_baseline / prefTotal) * 100) : 0;
    const invalidQ = questionnaires.total - questionnaires.valid;
    const inProgress = participants.total - participants.completed;

    return (
        <div className="space-y-6">
            {/* KPI row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                    { label: 'Participants', value: participants.total, sub: `${participants.completed} complete`, icon: Users, color: 'bg-cyan-500' },
                    { label: 'Completion Rate', value: `${participants.completion_rate_pct}%`, sub: `${inProgress} in progress`, icon: CheckCircle2, color: 'bg-emerald-500' },
                    { label: 'Questionnaires', value: questionnaires.valid, sub: `${invalidQ} invalid`, icon: ClipboardCheck, color: 'bg-blue-500' },
                    { label: 'Debates', value: debates.total, sub: `${debates.consensus_rate_pct}% consensus`, icon: MessageSquare, color: 'bg-violet-500' },
                ].map(({ label, value, sub, icon: Icon, color }) => (
                    <div key={label} className="bg-white border border-slate-200 rounded-2xl p-4 flex items-center gap-3">
                        <div className={`p-2.5 ${color} rounded-xl flex-shrink-0`}><Icon size={18} className="text-white" /></div>
                        <div className="min-w-0">
                            <p className="text-2xl font-black text-slate-900 leading-none">{value}</p>
                            <p className="text-xs text-slate-500 mt-0.5 truncate">{label}</p>
                            <p className="text-xs text-slate-400 truncate">{sub}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* RQ1 preview + condition balance */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* RQ1 trust preview */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                    <SectionHeader icon={BarChart3} title="RQ1 — Trust Preview" subtitle="Composite Likert mean (1–7)" color="bg-cyan-500" />
                    <div className="space-y-3">
                        {[
                            { label: 'Baseline (Cond. A)', value: questionnaires.mean_trust_score.baseline, n: null, color: 'bg-slate-400' },
                            { label: 'Multi-Agent (Cond. B)', value: questionnaires.mean_trust_score.multiagent, n: null, color: 'bg-cyan-500' },
                        ].map(({ label, value, color }) => (
                            <div key={label}>
                                <div className="flex justify-between text-xs mb-1">
                                    <span className="font-semibold text-slate-600">{label}</span>
                                    <span className="font-black text-slate-800">{fmt(value)}/7</span>
                                </div>
                                <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                                    <div className={`h-full ${color} rounded-full transition-all duration-700`}
                                        style={{ width: `${value !== null ? ((value - 1) / 6) * 100 : 0}%` }} />
                                </div>
                            </div>
                        ))}
                        <div className="pt-2 flex items-center justify-between border-t border-slate-100">
                            <span className="text-xs text-slate-500">Effect size (Cohen's d)</span>
                            <span className="text-xs text-slate-400">N/A</span>
                        </div>
                    </div>
                </div>

                {/* Preference tally */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                    <SectionHeader icon={Award} title="Exit Survey — Preferences" subtitle="Which system did participants prefer?" color="bg-amber-500" />
                    <div className="space-y-3">
                        {[
                            { label: 'Preferred Multi-Agent', count: exit_surveys.preferred_multiagent, pct: multiPct, color: 'bg-cyan-500' },
                            { label: 'Preferred Baseline', count: exit_surveys.preferred_baseline, pct: basePct, color: 'bg-slate-400' },
                            { label: 'No preference / Unsure', count: exit_surveys.no_preference_or_unsure, pct: prefTotal ? Math.round((exit_surveys.no_preference_or_unsure / prefTotal) * 100) : 0, color: 'bg-slate-200' },
                        ].map(({ label, count, pct, color }) => (
                            <div key={label}>
                                <div className="flex justify-between text-xs mb-1">
                                    <span className="text-slate-600">{label}</span>
                                    <span className="font-bold text-slate-700">{count} ({pct}%)</span>
                                </div>
                                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                    <div className={`h-full ${color} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="pt-2 border-t border-slate-100 flex justify-between text-xs text-slate-400">
                        <span>RQ2 codings: {rq2_persona_codings.total_codings} turns</span>
                        <span>Data quality: {questionnaires.validity_rate_pct}%</span>
                    </div>
                </div>
            </div>

            {/* Condition balance */}
            <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Counterbalancing Check</p>
                <div className="flex items-center gap-4">
                    <div className="flex-1">
                        <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-600">Baseline First</span>
                            <span className="font-bold">{participants.condition_balance.baseline_first}</span>
                        </div>
                        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                            <div className="h-full bg-slate-500 rounded-full" style={{ width: `${participants.condition_balance.baseline_first + participants.condition_balance.multiagent_first > 0 ? Math.round(participants.condition_balance.baseline_first / (participants.condition_balance.baseline_first + participants.condition_balance.multiagent_first) * 100) : 50}%` }} />
                        </div>
                    </div>
                    <div className="text-xs text-slate-400 font-mono">{participants.condition_balance.baseline_first}:{participants.condition_balance.multiagent_first}</div>
                    <div className="flex-1">
                        <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-600">Multi-Agent First</span>
                            <span className="font-bold">{participants.condition_balance.multiagent_first}</span>
                        </div>
                        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                            <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${participants.condition_balance.baseline_first + participants.condition_balance.multiagent_first > 0 ? Math.round(participants.condition_balance.multiagent_first / (participants.condition_balance.baseline_first + participants.condition_balance.multiagent_first) * 100) : 50}%` }} />
                        </div>
                    </div>
                </div>
                <p className="text-xs text-slate-400 mt-2">Ideal ratio is 50:50. A ±10% deviation is acceptable.</p>
            </div>
        </div>
    );
}

function ParticipantRow({ p, onViewDetail, onDelete, onInvalidate }: {
    p: ParticipantListItem;
    onViewDetail: () => void;
    onDelete: () => void;
    onInvalidate: () => void;
}) {
    const [expanded, setExpanded] = useState(false);
    const diff = p.questionnaire_summary.condition_difference;
    const diffColor = diff === null ? '' : diff > 0 ? 'text-emerald-600' : diff < 0 ? 'text-red-500' : 'text-slate-500';

    return (
        <div className={`border rounded-xl overflow-hidden transition-all ${p.experiment.completed_at ? 'border-emerald-200 bg-emerald-50/20' : 'border-slate-200 bg-white'}`}>
            <div className="flex items-center gap-3 p-4">
                <div className="w-8 h-8 rounded-full bg-cyan-100 text-cyan-700 font-black text-sm flex items-center justify-center flex-shrink-0">
                    {p.participant_id}
                </div>
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold text-slate-800 truncate">{p.user.email ?? `User #${p.user.id}`}</p>
                    <p className="text-xs text-slate-500">{p.demographics.experience_level} · {CONDITION_ORDER_LABELS[p.experiment.assigned_condition_order] ?? p.experiment.assigned_condition_order}</p>
                </div>
                <div className="hidden sm:flex items-center gap-4">
                    <ProgressDots done={p.progress.steps_completed} total={p.progress.steps_total} />
                    {diff !== null && (
                        <span className={`text-xs font-bold ${diffColor}`}>
                            {diff > 0 ? '+' : ''}{fmt(diff)}
                        </span>
                    )}
                    {p.experiment.completed_at && (
                        <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-semibold">Complete</span>
                    )}
                </div>
                <div className="flex items-center gap-1 ml-2">
                    <button onClick={onViewDetail} title="Deep dive" className="p-1.5 text-slate-400 hover:text-cyan-600 hover:bg-cyan-50 rounded-lg transition">
                        <Eye size={14} />
                    </button>
                    <button onClick={onInvalidate} title="Invalidate responses" className="p-1.5 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition">
                        <ShieldOff size={14} />
                    </button>
                    <button onClick={onDelete} title="Delete participant data" className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition">
                        <Trash2 size={14} />
                    </button>
                    <button onClick={() => setExpanded(e => !e)} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg transition">
                        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                </div>
            </div>
            {expanded && (
                <div className="border-t border-slate-100 p-4 bg-slate-50 grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-xs text-slate-400 mb-1">Baseline Mean</p>
                        <p className="text-lg font-black text-slate-800">{fmt(p.questionnaire_summary.baseline.mean_score)}/7</p>
                        <p className="text-xs text-slate-400">Trust: {p.questionnaire_summary.baseline.trust_overall ?? '—'}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-xs text-slate-400 mb-1">Multi-Agent Mean</p>
                        <p className="text-lg font-black text-cyan-700">{fmt(p.questionnaire_summary.multiagent.mean_score)}/7</p>
                        <p className="text-xs text-slate-400">Trust: {p.questionnaire_summary.multiagent.trust_overall ?? '—'}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-xs text-slate-400 mb-1">Preference</p>
                        <p className="text-sm font-bold text-slate-700 capitalize">{p.exit_survey.preferred_system_actual ?? '—'}</p>
                        <p className="text-xs text-slate-400">Fatigue: {p.exit_survey.experienced_fatigue ?? '—'}</p>
                    </div>
                </div>
            )}
        </div>
    );
}

function ParticipantDetailModal({ detail, onClose }: { detail: ParticipantDetail; onClose: () => void }) {
    const allQ = [...detail.questionnaires.baseline, ...detail.questionnaires.multiagent];
    return (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between rounded-t-2xl">
                    <div>
                        <h3 className="font-black text-slate-900">Participant #{detail.participant_id}</h3>
                        <p className="text-xs text-slate-500">{detail.user.email}</p>
                    </div>
                    <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 rounded-lg"><XCircle size={20} /></button>
                </div>
                <div className="p-6 space-y-6">
                    {/* Demographics */}
                    <div>
                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Demographics</p>
                        <div className="grid grid-cols-3 gap-3">
                            {[
                                { label: 'Level', value: detail.demographics.experience_level_display },
                                { label: 'Years Exp.', value: detail.demographics.years_experience },
                                { label: 'AI Familiarity', value: `${detail.demographics.familiarity_with_ai}/7` },
                            ].map(({ label, value }) => (
                                <div key={label} className="bg-slate-50 rounded-xl p-3 text-center">
                                    <p className="text-xs text-slate-400 mb-1">{label}</p>
                                    <p className="text-sm font-bold text-slate-800">{value}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Questionnaires */}
                    {allQ.map(q => (
                        <div key={q.response_id} className={`border rounded-xl p-4 space-y-3 ${!q.metadata.is_valid ? 'border-red-200 bg-red-50/30' : 'border-slate-200'}`}>
                            <div className="flex items-center gap-2">
                                <span className={`px-2 py-1 rounded-lg text-xs font-bold ${q.condition.toLowerCase() === 'multiagent' ? 'bg-cyan-100 text-cyan-700' : 'bg-slate-100 text-slate-600'}`}>
                                    {q.condition === 'MULTIAGENT' ? 'Multi-Agent' : 'Baseline'}
                                </span>
                                <span className="text-xs text-slate-500">{SCENARIO_LABELS[q.scenario_id]}</span>
                                <span className="ml-auto text-lg font-black text-slate-800">{q.mean_score}/7</span>
                                {!q.metadata.is_valid && <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full">Invalid</span>}
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                                {Object.entries(q.likert_scores).map(([k, v]) => (
                                    <LikertBar key={k} label={METRIC_LABELS[k] ?? k} value={v} />
                                ))}
                            </div>
                            {q.open_ended.trust_reasoning && (
                                <div className="bg-slate-50 rounded-lg p-3">
                                    <p className="text-xs text-slate-400 mb-1">Trust reasoning</p>
                                    <p className="text-xs text-slate-700 italic">"{q.open_ended.trust_reasoning}"</p>
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Exit survey */}
                    {detail.exit_survey && (
                        <div className="border border-amber-200 bg-amber-50/30 rounded-xl p-4 space-y-2">
                            <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Exit Survey</p>
                            <p className="text-sm font-bold text-slate-800 capitalize">
                                Preferred: {detail.exit_survey.preferred_system_actual ?? detail.exit_survey.preferred_system_raw}
                            </p>
                            <p className="text-xs text-slate-600">"{detail.exit_survey.preference_reasoning}"</p>
                            <div className="flex gap-4 text-xs text-slate-500">
                                <span>Interface: {detail.exit_survey.interface_rating}/7</span>
                                <span>Fatigue: {detail.exit_survey.experienced_fatigue}</span>
                            </div>
                        </div>
                    )}

                    {detail.questionnaires.within_subject_difference !== null && (
                        <div className={`rounded-xl p-4 text-center ${detail.questionnaires.within_subject_difference > 0 ? 'bg-emerald-50 border border-emerald-200' : 'bg-red-50 border border-red-200'}`}>
                            <p className="text-xs text-slate-500 mb-1">Within-Subject Δ (Multi-Agent − Baseline)</p>
                            <p className={`text-3xl font-black ${detail.questionnaires.within_subject_difference > 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                                {detail.questionnaires.within_subject_difference > 0 ? '+' : ''}{fmt(detail.questionnaires.within_subject_difference)}
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function RQSummaryPanel({ data }: { data: RQSummary }) {
    const { rq1_trust_and_quality, rq2_persona_consistency, rq3_consensus_efficiency } = data;
    const items = Object.entries(METRIC_LABELS);

    return (
        <div className="space-y-6">
            {/* RQ1 */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                <SectionHeader icon={BarChart3} title="RQ1 — Trust & Quality" subtitle="Baseline vs Multi-Agent composite means" color="bg-cyan-500" />
                <div className="grid grid-cols-2 gap-4">
                    {[
                        { label: 'Baseline Mean', val: rq1_trust_and_quality.composite_mean_score.baseline, sd: rq1_trust_and_quality.composite_mean_score.baseline_stdev, n: rq1_trust_and_quality.n_baseline, accent: 'text-slate-700 bg-slate-50 border-slate-200' },
                        { label: 'Multi-Agent Mean', val: rq1_trust_and_quality.composite_mean_score.multiagent, sd: rq1_trust_and_quality.composite_mean_score.multiagent_stdev, n: rq1_trust_and_quality.n_multiagent, accent: 'text-cyan-700 bg-cyan-50 border-cyan-200' },
                    ].map(({ label, val, sd, n, accent }) => (
                        <div key={label} className={`rounded-xl border p-4 text-center ${accent}`}>
                            <p className="text-xs font-bold uppercase tracking-wider opacity-60 mb-1">{label} (n={n})</p>
                            <p className="text-4xl font-black">{fmt(val)}</p>
                            <p className="text-xs opacity-50 mt-1">SD={fmt(sd)} · /7.00</p>
                        </div>
                    ))}
                </div>
                <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                    <span className="text-xs text-slate-500">Cohen's d effect size</span>
                    <CohenBadge d={rq1_trust_and_quality.composite_mean_score.cohen_d} />
                </div>
                <div className="space-y-2">
                    {items.map(([key, label]) => {
                        const b = rq1_trust_and_quality.per_item_baseline[key]?.mean ?? null;
                        const m = rq1_trust_and_quality.per_item_multiagent[key]?.mean ?? null;
                        const diff = b !== null && m !== null ? m - b : null;
                        return (
                            <div key={key} className="flex items-center gap-3 text-xs">
                                <span className="w-28 text-slate-500 flex-shrink-0">{label}</span>
                                <div className="flex-1 flex gap-1">
                                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                                        <div className="h-full bg-slate-400 rounded-full" style={{ width: `${b !== null ? ((b - 1) / 6) * 100 : 0}%` }} />
                                    </div>
                                    <div className="flex-1 h-2 bg-cyan-50 rounded-full overflow-hidden">
                                        <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${m !== null ? ((m - 1) / 6) * 100 : 0}%` }} />
                                    </div>
                                </div>
                                <span className={`w-10 text-right font-bold ${diff === null ? 'text-slate-300' : diff > 0 ? 'text-emerald-600' : diff < 0 ? 'text-red-500' : 'text-slate-400'}`}>
                                    {diff !== null ? (diff > 0 ? '+' : '') + fmt(diff) : '—'}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* RQ2 */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                <SectionHeader icon={Target} title="RQ2 — Persona Consistency" subtitle="Manual coding results (20% sample)" color="bg-violet-500" />
                <div className="space-y-3">
                    {Object.entries(rq2_persona_consistency.per_persona).map(([persona, stats]) => (
                        <div key={persona} className="bg-slate-50 rounded-xl p-3">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-bold text-slate-700 capitalize">{persona.replace('_', ' ')}</span>
                                <span className="text-xs text-slate-500">{stats.turns_coded} turns coded</span>
                            </div>
                            <div className="flex gap-4 text-xs">
                                <div>
                                    <p className="text-slate-400">Consistency</p>
                                    <p className="font-black text-slate-800">{fmt(stats.mean_consistency)}</p>
                                </div>
                                <div>
                                    <p className="text-slate-400">Fully in-char</p>
                                    <p className="font-black text-slate-800">{stats.pct_fully_consistent}%</p>
                                </div>
                            </div>
                            <div className="mt-2 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                <div className="h-full bg-violet-500 rounded-full" style={{ width: `${(stats.mean_consistency ?? 0) * 100}%` }} />
                            </div>
                        </div>
                    ))}
                    <div className="flex gap-3 text-xs text-center">
                        {[
                            { label: 'No Hallucination', val: rq2_persona_consistency.hallucination_summary.none, color: 'bg-emerald-100 text-emerald-700' },
                            { label: 'Minor', val: rq2_persona_consistency.hallucination_summary.minor, color: 'bg-amber-100 text-amber-700' },
                            { label: 'Major', val: rq2_persona_consistency.hallucination_summary.major, color: 'bg-red-100 text-red-700' },
                        ].map(({ label, val, color }) => (
                            <div key={label} className={`flex-1 rounded-lg p-2 ${color}`}>
                                <p className="font-black text-lg">{val}</p>
                                <p className="font-medium">{label}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* RQ3 */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                <SectionHeader icon={Zap} title="RQ3 — Consensus Efficiency" subtitle="Generation time: Baseline vs Multi-Agent" color="bg-amber-500" />
                <div className="grid grid-cols-2 gap-4">
                    {[
                        {
                            label: 'Baseline Generation', icon: Clock,
                            stats: [
                                { k: 'n', v: String(rq3_consensus_efficiency.baseline_generation.n) },
                                { k: 'Mean (s)', v: fmt(rq3_consensus_efficiency.baseline_generation.mean_seconds, 1) },
                                { k: 'SD', v: fmt(rq3_consensus_efficiency.baseline_generation.stdev_seconds, 1) },
                            ],
                            accent: 'border-slate-200',
                        },
                        {
                            label: 'Multi-Agent Debate', icon: MessageSquare,
                            stats: [
                                { k: 'n', v: String(rq3_consensus_efficiency.multiagent_debates.n) },
                                { k: 'Mean (s)', v: fmt(rq3_consensus_efficiency.multiagent_debates.mean_duration_seconds, 1) },
                                { k: 'Consensus', v: `${rq3_consensus_efficiency.multiagent_debates.consensus_rate_pct}%` },
                                { k: 'Avg Turns', v: fmt(rq3_consensus_efficiency.multiagent_debates.mean_turns, 1) },
                            ],
                            accent: 'border-cyan-200',
                        },
                    ].map(({ label, stats, accent }) => (
                        <div key={label} className={`border ${accent} rounded-xl p-4`}>
                            <p className="text-xs font-bold text-slate-500 mb-3">{label}</p>
                            <div className="space-y-2">
                                {stats.map(({ k, v }) => (
                                    <div key={k} className="flex justify-between text-xs">
                                        <span className="text-slate-400">{k}</span>
                                        <span className="font-bold text-slate-700">{v}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────────────────────

type Tab = 'overview' | 'participants' | 'rq-summary';

export function AdminExperimentData() {
    const [tab, setTab] = useState<Tab>('overview');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const [overview, setOverview] = useState<Overview | null>(null);
    const [participants, setParticipants] = useState<ParticipantListItem[]>([]);
    const [rqSummary, setRqSummary] = useState<RQSummary | null>(null);
    const [selectedDetail, setSelectedDetail] = useState<ParticipantDetail | null>(null);

    // Reset state
    const [resetConfirm, setResetConfirm] = useState('');
    const [keepParticipants, setKeepParticipants] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [showResetPanel, setShowResetPanel] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const [ov, parts, rq] = await Promise.all([
                experimentDataApi.getOverview(),
                experimentDataApi.getParticipants(),
                experimentDataApi.getRQSummary(),
            ]);
            setOverview(ov as Overview | null);
            setParticipants((parts as { participants?: unknown }).participants as unknown as ParticipantListItem[] || []);
            setRqSummary(rq as unknown as RQSummary | null);
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } }; message?: string };
            const detail = error?.response?.data?.detail ?? error?.message ?? 'Unknown error';
            setError(`Failed to load experiment data: ${detail}`);
            console.error('[AdminExperimentData] load error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleViewDetail = async (id: number) => {
        try {
            const d = await experimentDataApi.getParticipantDetail(id);
            setSelectedDetail(d as unknown as ParticipantDetail | null);
        } catch {
            alert('Failed to load participant detail.');
        }
    };

    const handleDelete = async (id: number, email: string) => {
        if (!confirm(`Delete all data for participant #${id} (${email})?\nTheir user account will be kept.`)) return;
        try {
            await experimentDataApi.deleteParticipant(id);
            setParticipants(ps => ps.filter(p => p.participant_id !== id));
            load();
        } catch {
            alert('Delete failed.');
        }
    };

    const handleInvalidate = async (id: number) => {
        const reason = prompt('Reason for invalidating this participant\'s responses:');
        if (!reason || reason.trim().length < 5) return;
        try {
            await experimentDataApi.invalidateParticipant(id, reason);
            alert('Responses flagged as invalid. They will be excluded from valid_only queries.');
            load();
        } catch {
            alert('Invalidation failed.');
        }
    };

    const handleReset = async () => {
        if (resetConfirm !== 'CONFIRM_RESET') {
            alert('You must type exactly: CONFIRM_RESET');
            return;
        }
        setResetting(true);
        try {
            await experimentDataApi.resetAllData(keepParticipants);
            setShowResetPanel(false);
            setResetConfirm('');
            alert('✅ Experiment data reset successfully.');
            load();
        } catch {
            alert('Reset failed. Check permissions and try again.');
        } finally {
            setResetting(false);
        }
    };

    if (loading) return (
        <div className="space-y-3 animate-pulse">
            {[1, 2, 3].map(i => <div key={i} className="h-20 bg-slate-100 rounded-2xl" />)}
        </div>
    );

    if (error) return (
        <div className="flex items-center gap-3 bg-red-50 border border-red-100 rounded-xl p-4 text-red-700">
            <AlertTriangle size={18} />
            <span className="text-sm">{error}</span>
            <button onClick={load} className="ml-auto text-sm font-semibold underline">Retry</button>
        </div>
    );

    return (
        <div className="space-y-6">

            {/* Header */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-cyan-600 rounded-xl"><FlaskConical size={20} className="text-white" /></div>
                    <div>
                        <h2 className="text-xl font-black text-slate-900">Experiment Data</h2>
                        <p className="text-sm text-slate-500">Full study dashboard — participants, scores, RQ analytics</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setShowResetPanel(s => !s)}
                        className="flex items-center gap-2 px-3 py-2 text-sm font-semibold text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition"
                    >
                        <Trash2 size={14} /> Reset Data
                    </button>
                    <button
                        onClick={load}
                        className="flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition"
                    >
                        <RefreshCw size={14} /> Refresh
                    </button>
                </div>
            </div>

            {/* Reset panel */}
            {showResetPanel && (
                <div className="bg-red-50 border border-red-300 rounded-2xl p-5 space-y-4">
                    <div className="flex items-center gap-2 text-red-700">
                        <AlertTriangle size={18} />
                        <p className="font-black text-sm">Danger Zone — Irreversible Data Reset</p>
                    </div>
                    <p className="text-xs text-red-600">
                        This will permanently delete: all PersonaCoding records, ExitSurvey records, QuestionnaireResponse records, DebateSession records, and optionally all Participant records. Proposals, Projects, and User accounts are <strong>never</strong> touched.
                    </p>
                    <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                        <input type="checkbox" checked={keepParticipants} onChange={e => setKeepParticipants(e.target.checked)} className="rounded" />
                        Keep participant demographics &amp; consent records (only delete responses)
                    </label>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={resetConfirm}
                            onChange={e => setResetConfirm(e.target.value)}
                            placeholder="Type CONFIRM_RESET to proceed"
                            className="flex-1 px-3 py-2 text-sm border border-red-300 rounded-lg font-mono bg-white focus:outline-none focus:ring-2 focus:ring-red-400"
                        />
                        <button
                            onClick={handleReset}
                            disabled={resetting || resetConfirm !== 'CONFIRM_RESET'}
                            className="px-4 py-2 text-sm font-bold text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-40 transition"
                        >
                            {resetting ? 'Resetting…' : 'Reset'}
                        </button>
                        <button onClick={() => setShowResetPanel(false)} className="px-3 py-2 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50">Cancel</button>
                    </div>
                </div>
            )}

            {/* Tab bar */}
            <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit">
                {([
                    { id: 'overview', label: '📊 Overview' },
                    { id: 'participants', label: `👥 Participants (${participants.length})` },
                    { id: 'rq-summary', label: '🔬 RQ Summary' },
                ] as const).map(({ id, label }) => (
                    <button
                        key={id}
                        onClick={() => setTab(id)}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${tab === id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* Tab content */}
            {tab === 'overview' && overview && <OverviewPanel data={overview} />}

            {tab === 'participants' && (
                <div className="space-y-3">
                    {participants.length === 0 ? (
                        <div className="text-center py-16 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
                            <Users size={40} className="mx-auto text-slate-300 mb-3" />
                            <p className="text-slate-500 font-medium">No participants registered yet.</p>
                        </div>
                    ) : (
                        participants.map(p => (
                            <ParticipantRow
                                key={p.participant_id}
                                p={p}
                                onViewDetail={() => handleViewDetail(p.participant_id)}
                                onDelete={() => handleDelete(p.participant_id, p.user.email ?? '')}
                                onInvalidate={() => handleInvalidate(p.participant_id)}
                            />
                        ))
                    )}
                </div>
            )}

            {tab === 'rq-summary' && rqSummary && <RQSummaryPanel data={rqSummary} />}

            {selectedDetail && (
                <ParticipantDetailModal detail={selectedDetail} onClose={() => setSelectedDetail(null)} />
            )}
        </div>
    );
}