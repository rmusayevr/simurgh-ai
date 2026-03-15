import { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    CheckCircle, Loader2, FileText, Gavel, AlertCircle,
    BookOpen, Users, BarChart2, Clock, ChevronRight, FlaskConical,
    Shield, Zap, Scale, CheckCircle2,
    type LucideIcon,
} from 'lucide-react';
import { experimentApi } from '../../api/client';
import type { BaselineVariationRead, DebateResult, ParticipantRead } from '../../types';
import { ConditionOrder } from '../../types';
import { STATIC_EXPERIMENT_DATA } from '../../data/staticExperimentData';
import { EXPERIMENT_SCENARIOS, pickScenario } from '../../config/experiment';

import { TrustQuestionnaire } from './TrustQuestionnaire';
import { ExitSurvey } from './ExitSurvey';
import ReactMarkdown from 'react-markdown';
import type { Components } from "react-markdown";
import remarkGfm from 'remark-gfm';

// ─── Markdown helpers (ported from ProposalDetailPage) ────────────────────────────

const BASELINE_CFG = {
    accent: '#475569',
    bg: '#f8fafc',
    border: '#cbd5e1',
} as const;

const normalizeMarkdown = (text: string): string => {
    if (!text) return text;
    return text
        .replace(/(\d+)\)\s+/g, (_, n) => `\n${n}. `)
        .replace(/\n{3,}/g, '\n\n')
        .trim();
};

const buildMdComponents = (cfg: { accent: string; bg: string; border: string }): Components => ({
    h1: ({ children }) => (
        <h1 className="text-2xl font-black text-slate-900 mb-4 mt-2 pb-3 border-b-2" style={{ borderColor: cfg.border }}>{children}</h1>
    ),
    h2: ({ children }) => (
        <div className="flex items-center gap-2 mt-10 mb-4">
            <div className="w-1 h-5 rounded-full shrink-0" style={{ background: cfg.accent }} />
            <h2 className="text-lg font-black text-slate-900">{children}</h2>
        </div>
    ),
    h3: ({ children }) => (
        <h3 className="text-base font-bold text-slate-800 mt-6 mb-2 flex items-center gap-2">
            <span className="inline-block w-1.5 h-1.5 rounded-full shrink-0" style={{ background: cfg.accent }} />
            {children}
        </h3>
    ),
    h4: ({ children }) => <h4 className="text-sm font-bold text-slate-700 mt-4 mb-1">{children}</h4>,
    p: ({ children }) => <p className="text-slate-600 leading-7 my-3 text-[15px]">{children}</p>,
    ul: ({ children }) => <ul className="my-3 space-y-2 ml-1">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal list-outside ml-6 my-3 space-y-2">{children}</ol>,
    li: ({ children }) => (
        <li className="flex items-start gap-2.5 text-slate-600 leading-7 text-[15px]">
            <span className="mt-2.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: cfg.accent }} />
            <span>{children}</span>
        </li>
    ),
    strong: ({ children }) => <strong className="font-bold text-slate-800">{children}</strong>,
    em: ({ children }) => <em className="italic text-slate-500">{children}</em>,
    code: ({ children, className }) => {
        const isBlock = className?.includes('language-');
        return isBlock
            ? <code className="block bg-slate-950 text-emerald-300 rounded-xl px-6 py-4 my-4 text-sm font-mono overflow-x-auto whitespace-pre leading-6">{children}</code>
            : <code className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded text-sm font-mono">{children}</code>;
    },
    pre: ({ children }) => <pre className="bg-slate-950 rounded-xl my-4 overflow-x-auto shadow-inner">{children}</pre>,
    blockquote: ({ children }) => (
        <blockquote className="border-l-4 pl-5 my-5 py-2 italic text-slate-500 rounded-r-lg" style={{ borderColor: cfg.accent, background: cfg.bg }}>
            {children}
        </blockquote>
    ),
    hr: () => <hr className="border-slate-200 my-8" />,
    table: ({ children }) => (
        <div className="overflow-x-auto my-6 rounded-xl border border-slate-200 shadow-sm">
            <table className="w-full text-sm border-collapse">{children}</table>
        </div>
    ),
    thead: ({ children }) => <thead>{children}</thead>,
    tbody: ({ children }) => <tbody className="divide-y divide-slate-100">{children}</tbody>,
    tr: ({ children }) => <tr className="hover:bg-slate-50 transition-colors">{children}</tr>,
    th: ({ children }) => (
        <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-wider text-slate-600 border-b-2 border-slate-200" style={{ background: cfg.bg }}>
            {children}
        </th>
    ),
    td: ({ children }) => <td className="px-4 py-3 text-slate-600">{children}</td>,
    a: ({ children, href }) => (
        <a href={href} target="_blank" rel="noopener noreferrer"
            className="font-medium underline underline-offset-2 transition-colors"
            style={{ color: cfg.accent }}>
            {children}
        </a>
    ),
});


// ─── Council persona config ───────────────────────────────────────────────────

const COUNCIL_PERSONA: Record<string, {
    name: string; icon: LucideIcon;
    accent: string; bg: string; border: string;
    pill: string; description: string;
}> = {
    LEGACY_KEEPER: {
        name: 'Legacy Keeper', icon: Shield,
        accent: '#b45309', bg: '#fffbeb', border: '#fcd34d',
        pill: 'bg-amber-100 text-amber-800 border-amber-300',
        description: 'Stability · Risk mitigation · Proven patterns',
    },
    INNOVATOR: {
        name: 'The Innovator', icon: Zap,
        accent: '#7c3aed', bg: '#f5f3ff', border: '#c4b5fd',
        pill: 'bg-violet-100 text-violet-800 border-violet-300',
        description: 'Modern architecture · Scalability · Velocity',
    },
    MEDIATOR: {
        name: 'The Mediator', icon: Scale,
        accent: '#0369a1', bg: '#f0f9ff', border: '#7dd3fc',
        pill: 'bg-sky-100 text-sky-800 border-sky-300',
        description: 'Balanced trade-offs · Pragmatic · Consensus',
    },
};

const SENTIMENT_STYLE: Record<string, string> = {
    agree: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
    disagree: 'bg-red-100 text-red-700 border border-red-200',
    neutral: 'bg-slate-100 text-slate-600 border border-slate-200',
};

// ─── Single debate turn card ──────────────────────────────────────────────────

function DebateTurnCard({ turn, index }: { turn: import('../../types').DebateTurn; index: number }) {
    const cfg = COUNCIL_PERSONA[turn.persona] ?? COUNCIL_PERSONA.MEDIATOR;
    const Icon = cfg.icon;
    const isMediator = turn.persona === 'MEDIATOR';

    return (
        <div className={`flex gap-4 ${isMediator ? 'flex-col items-center' : ''}`}>
            {/* Turn number + persona icon */}
            <div className="flex flex-col items-center gap-1 shrink-0">
                <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center shadow-sm border"
                    style={{ background: cfg.bg, borderColor: cfg.border }}
                >
                    <Icon size={18} style={{ color: cfg.accent }} />
                </div>
                {!isMediator && (
                    <div className="w-px flex-1 min-h-[24px]" style={{ background: cfg.border }} />
                )}
            </div>

            {/* Content */}
            <div className={`flex-1 pb-2 ${isMediator ? 'w-full' : ''}`}>
                {/* Header */}
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${cfg.pill}`}>
                        <Icon size={10} /> {cfg.name}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                        Turn {index + 1}
                    </span>
                    {turn.sentiment && (
                        <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${SENTIMENT_STYLE[turn.sentiment.toLowerCase()] ?? SENTIMENT_STYLE.neutral}`}>
                            {turn.sentiment}
                        </span>
                    )}
                </div>

                {/* Bubble */}
                <div
                    className={`rounded-2xl p-5 border shadow-sm ${isMediator ? 'border-2' : ''}`}
                    style={{
                        background: cfg.bg,
                        borderColor: cfg.border,
                    }}
                >
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={buildMdComponents(cfg)}
                    >
                        {normalizeMarkdown(turn.response)}
                    </ReactMarkdown>
                </div>

                {/* Key points */}
                {turn.key_points && turn.key_points.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-2 pl-1">
                        {turn.key_points.map((pt, i) => (
                            <span
                                key={i}
                                className="inline-flex items-start gap-1 text-[11px] text-slate-500 bg-white border border-slate-200 rounded-lg px-2.5 py-1 leading-snug max-w-sm"
                            >
                                <ChevronRight size={10} className="mt-0.5 shrink-0 text-slate-400" />
                                {pt}
                            </span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

// ─── Intro Screen ─────────────────────────────────────────────────────────────
function IntroScreen({ participant, onBegin }: { participant: ParticipantRead; onBegin: () => void }) {
    const conditionOrder = participant.assigned_condition_order === ConditionOrder.BASELINE_FIRST
        ? ['Standard AI (Single Agent)', 'Council of Agents (Multi-Agent)']
        : ['Council of Agents (Multi-Agent)', 'Standard AI (Single Agent)'];

    return (
        <div className="max-w-3xl mx-auto space-y-6 animate-in fade-in duration-500">

            {/* Hero */}
            <div className="bg-gradient-to-br from-cyan-600 to-violet-700 rounded-3xl p-10 text-white text-center shadow-xl">
                <div className="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center mx-auto mb-5">
                    <FlaskConical size={32} className="text-white" />
                </div>
                <h1 className="text-3xl font-black mb-3">Architectural Decision Study</h1>
                <p className="text-cyan-200 text-lg max-w-xl mx-auto leading-relaxed">
                    Welcome to this MSc research study on AI-assisted software architecture decision-making.
                    Before you begin, please read the following carefully.
                </p>
            </div>

            {/* What you'll do */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
                <h2 className="text-lg font-black text-slate-900 mb-5 flex items-center gap-2">
                    <BookOpen size={18} className="text-cyan-500" /> What you'll do
                </h2>
                <div className="space-y-4">
                    {[
                        {
                            icon: FileText,
                            color: 'bg-blue-50 text-blue-600',
                            title: 'Read a real-world architecture scenario',
                            desc: 'You\'ll be presented with a technical challenge faced by a fictional co.',
                        },
                        {
                            icon: BarChart2,
                            color: 'bg-violet-50 text-violet-600',
                            title: 'Evaluate two AI-generated proposals',
                            desc: 'You\'ll review architectural proposals generated by two different AI systems — one at a time.',
                        },
                        {
                            icon: Users,
                            color: 'bg-emerald-50 text-emerald-600',
                            title: 'Complete short trust questionnaires',
                            desc: 'After each proposal, answer a brief questionnaire about your trust in the AI\'s recommendation.',
                        },
                    ].map(({ icon: Icon, color, title, desc }) => (
                        <div key={title} className="flex items-start gap-4">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
                                <Icon size={18} />
                            </div>
                            <div>
                                <p className="font-bold text-slate-800 text-sm">{title}</p>
                                <p className="text-sm text-slate-500 mt-0.5">{desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Session details */}
            <div className="grid grid-cols-2 gap-4">
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
                    <div className="flex items-center gap-2 mb-3">
                        <Clock size={15} className="text-slate-400" />
                        <span className="text-xs font-black text-slate-400 uppercase tracking-widest">Estimated Time</span>
                    </div>
                    <p className="text-2xl font-black text-slate-900">15–25 min</p>
                    <p className="text-sm text-slate-500 mt-1">Two conditions + questionnaires</p>
                </div>
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
                    <div className="flex items-center gap-2 mb-3">
                        <BarChart2 size={15} className="text-slate-400" />
                        <span className="text-xs font-black text-slate-400 uppercase tracking-widest">Your Session Order</span>
                    </div>
                    <div className="space-y-1">
                        {conditionOrder.map((label, i) => (
                            <div key={i} className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-cyan-100 text-cyan-700 text-xs font-black flex items-center justify-center shrink-0">{i + 1}</span>
                                <span className="text-sm font-medium text-slate-700">{label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Guidelines */}
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6">
                <h3 className="text-sm font-black text-amber-800 uppercase tracking-widest mb-3">Important Guidelines</h3>
                <ul className="space-y-2 text-sm text-amber-800">
                    <li className="flex items-start gap-2"><span className="mt-0.5 shrink-0">•</span> Both conditions present proposals for the <strong>same scenario</strong> — evaluate each on its own merits.</li>
                    <li className="flex items-start gap-2"><span className="mt-0.5 shrink-0">•</span> There are no right or wrong answers. We are studying your <strong>perception of AI-generated advice</strong>.</li>
                    <li className="flex items-start gap-2"><span className="mt-0.5 shrink-0">•</span> Please complete the study in a <strong>single sitting</strong> without interruption.</li>
                    <li className="flex items-start gap-2"><span className="mt-0.5 shrink-0">•</span> Your responses are <strong>anonymous</strong> and used only for academic research.</li>
                </ul>
            </div>

            {/* CTA */}
            <button
                onClick={onBegin}
                className="w-full py-4 bg-cyan-600 hover:bg-cyan-700 text-white rounded-2xl font-black text-lg flex items-center justify-center gap-3 transition-all hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0"
            >
                Begin Study <ChevronRight size={20} />
            </button>
        </div>
    );
}

// ─── Main Component ────────────────────────────────────────────────────────────
export function ExperimentInterface() {
    const navigate = useNavigate();

    // ── Load participant record ────────────────────────────────────────────────
    const [participant, setParticipant] = useState<ParticipantRead | null>(null);
    const [participantLoading, setParticipantLoading] = useState(true);

    useEffect(() => {
        experimentApi.getMyParticipant()
            .then(p => setParticipant(p))
            .catch(() => navigate('/experiment/register', { replace: true }))
            .finally(() => setParticipantLoading(false));
    }, [navigate]);

    // ── Experiment state ──────────────────────────────────────────────────────
    const sessionIdRef = useRef<string | null>(null);
    if (sessionIdRef.current === null) {
        // eslint-disable-next-line react-hooks/purity
        sessionIdRef.current = `session_${Date.now()}`;
    }
    const sessionId = sessionIdRef.current;
    const [showIntro, setShowIntro] = useState(true);   // Task 9: intro screen
    const [currentStep, setCurrentStep] = useState(0);
    const [loading, setLoading] = useState(false);
    const [baselineResult, setBaselineResult] = useState<BaselineVariationRead | null>(null);
    const [debateResult, setDebateResult] = useState<DebateResult | null>(null);
    const [showExitSurvey, setShowExitSurvey] = useState(false);
    const [experimentDone, setExperimentDone] = useState(false);

    const conditionSequence: ReadonlyArray<'baseline' | 'multiagent'> =
        participant?.assigned_condition_order === ConditionOrder.BASELINE_FIRST
            ? ['baseline', 'multiagent']
            : ['multiagent', 'baseline'];

    // Task 7: single scenario for both conditions, picked deterministically by participant id
    const assignedScenario = useMemo(
        () => participant ? pickScenario(participant.id!) : EXPERIMENT_SCENARIOS[0],
        [participant]
    );

    const EXPERIMENT_STEPS = 2;
    const currentCondition = conditionSequence[currentStep] ?? 'baseline';

    // ── Loading / error states ────────────────────────────────────────────────
    if (participantLoading) {
        return (
            <div className="flex items-center justify-center min-h-64">
                <Loader2 size={32} className="animate-spin text-cyan-600" />
            </div>
        );
    }

    if (!participant) {
        return (
            <div className="flex items-center justify-center min-h-64">
                <div className="flex items-center gap-3 text-red-600 bg-red-50 p-4 rounded-xl border border-red-100">
                    <AlertCircle size={20} />
                    <span>Registration required. Redirecting…</span>
                </div>
            </div>
        );
    }

    // ── Task 9: show intro first ───────────────────────────────────────────────
    // Already completed — don't let them restart
    if (participant.completed_at) {
        return (
            <div className="max-w-2xl mx-auto space-y-5 animate-in fade-in duration-500">
                <div className="p-10 text-center bg-emerald-50 rounded-2xl border border-emerald-200">
                    <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <CheckCircle size={36} className="text-emerald-600" />
                    </div>
                    <h2 className="text-2xl font-black text-emerald-900">You've Already Completed This Study</h2>
                    <p className="text-emerald-700 mt-2 leading-relaxed">
                        Your responses were recorded on{' '}
                        <span className="font-bold">
                            {new Date(participant.completed_at).toLocaleDateString('en-GB', {
                                day: 'numeric', month: 'long', year: 'numeric',
                            })}
                        </span>
                        .<br />Each participant may only complete the study once. Thank you for your contribution.
                    </p>
                </div>
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center space-y-4">
                    <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-violet-600 rounded-xl flex items-center justify-center mx-auto shadow-md shadow-cyan-200">
                        <FlaskConical size={18} className="text-white" />
                    </div>
                    <div>
                        <h3 className="text-lg font-black text-slate-900">Want to explore the full platform?</h3>
                        <p className="text-slate-500 text-sm mt-1 leading-relaxed">
                            The tool you evaluated is a real product. Try it with your own projects — free to use.
                        </p>
                    </div>
                    <a
                        href="/"
                        className="inline-flex items-center gap-2 px-6 py-3 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl font-bold text-sm transition-all hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0"
                    >
                        Try the full platform <ChevronRight size={16} />
                    </a>
                </div>
            </div>
        );
    }

    if (showIntro) {
        return <IntroScreen participant={participant} onBegin={() => setShowIntro(false)} />;
    }

    // ── Done states ───────────────────────────────────────────────────────────
    if (experimentDone) {
        return (
            <div className="max-w-2xl mx-auto space-y-5 animate-in fade-in duration-500">

                {/* Completion card */}
                <div className="p-10 text-center bg-emerald-50 rounded-2xl border border-emerald-200">
                    <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <CheckCircle size={36} className="text-emerald-600" />
                    </div>
                    <h2 className="text-2xl font-black text-emerald-900">Experiment Complete</h2>
                    <p className="text-emerald-700 mt-2 leading-relaxed">
                        Thank you for participating in this architectural decision study.<br />
                        Your responses have been recorded and will contribute to the research.
                    </p>
                </div>

                {/* Try the real product */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center space-y-4">
                    <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-violet-600 rounded-xl flex items-center justify-center mx-auto shadow-md shadow-cyan-200">
                        <FlaskConical size={18} className="text-white" />
                    </div>
                    <div>
                        <h3 className="text-lg font-black text-slate-900">Want to explore the full platform?</h3>
                        <p className="text-slate-500 text-sm mt-1 leading-relaxed">
                            The tool you just evaluated is a real product. You can use it to generate
                            architectural proposals, run multi-agent debates, and manage stakeholders
                            for your own projects — for free.
                        </p>
                    </div>
                    <a
                        href="/"
                        className="inline-flex items-center gap-2 px-6 py-3 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl font-bold text-sm transition-all hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0"
                    >
                        Try the full platform <ChevronRight size={16} />
                    </a>
                    <p className="text-xs text-slate-400">
                        No commitment required — create a free account and start your first mission.
                    </p>
                </div>
            </div>
        );
    }

    if (showExitSurvey) {
        return (
            <ExitSurvey
                participantId={participant.id!}
                conditionOrder={participant.assigned_condition_order}
                onComplete={() => setExperimentDone(true)}
            />
        );
    }

    // ── Run experiment (static pre-generated responses) ──────────────────────
    const runExperiment = async () => {
        setLoading(true);
        setBaselineResult(null);
        setDebateResult(null);

        // Brief simulated delay for realism
        await new Promise(resolve => setTimeout(resolve, 1800));

        const scenarioData = STATIC_EXPERIMENT_DATA[assignedScenario.id];
        if (!scenarioData) {
            alert('Static data not found for scenario ' + assignedScenario.id);
            setLoading(false);
            return;
        }

        if (currentCondition === 'baseline') {
            setBaselineResult(scenarioData.baseline);
        } else {
            setDebateResult(scenarioData.multiagent);
        }
        setLoading(false);
    };

    const handleQuestionnaireComplete = () => {
        setBaselineResult(null);
        setDebateResult(null);
        const nextStep = currentStep + 1;
        if (nextStep >= EXPERIMENT_STEPS) {
            setShowExitSurvey(true);
        } else {
            setCurrentStep(nextStep);
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-500">

            {/* Header / Progress */}
            <div className="flex items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <div>
                    <h2 className="text-lg font-bold text-slate-900">Thesis Evaluation Study</h2>
                    <p className="text-sm text-slate-500">Task {currentStep + 1} of {EXPERIMENT_STEPS}</p>
                </div>
                {/* Progress bar */}
                <div className="flex items-center gap-3">
                    <div className="w-32 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-cyan-500 rounded-full transition-all duration-500"
                            style={{ width: `${((currentStep) / EXPERIMENT_STEPS) * 100}%` }}
                        />
                    </div>
                    <div className="px-3 py-1 bg-slate-100 rounded-full text-xs font-mono font-bold text-slate-600 uppercase">
                        {currentCondition === 'baseline' ? 'Standard AI' : 'Council of Agents'}
                    </div>
                </div>
            </div>

            {/* Scenario — same for both conditions (Task 7) */}
            <div className="bg-blue-50 p-6 rounded-xl border border-blue-100">
                <h3 className="font-bold text-blue-900 mb-2">{assignedScenario.title}</h3>
                <p className="text-blue-800">{assignedScenario.description}</p>
            </div>

            {/* Execution Area */}
            <div className="min-h-[400px] bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                {!baselineResult && !debateResult && !loading && (
                    <div className="h-full flex flex-col items-center justify-center space-y-4 py-12">
                        <div className="p-4 bg-slate-50 rounded-full">
                            {currentCondition === 'baseline'
                                ? <FileText size={32} className="text-slate-400" />
                                : <Gavel size={32} className="text-slate-400" />}
                        </div>
                        <button
                            onClick={runExperiment}
                            className="bg-cyan-600 text-white px-6 py-3 rounded-lg font-bold hover:bg-cyan-700 transition flex items-center gap-2"
                        >
                            Generate Architecture Proposal
                        </button>
                    </div>
                )}

                {loading && (
                    <div className="h-full flex flex-col items-center justify-center space-y-4 py-12">
                        <Loader2 size={40} className="animate-spin text-cyan-600" />
                        <p className="text-slate-500 font-medium">
                            {currentCondition === 'baseline'
                                ? 'Generating Standard Proposal...'
                                : 'Convening the Council of Agents...'}
                        </p>
                    </div>
                )}

                {baselineResult && (
                    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                        {/* Header bar */}
                        <div className="flex items-center gap-3 px-8 py-4 border-b border-slate-100"
                            style={{ background: BASELINE_CFG.bg }}>
                            <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center shrink-0 shadow-sm">
                                <FileText size={15} style={{ color: BASELINE_CFG.accent }} />
                            </div>
                            <div>
                                <p className="text-xs font-black uppercase tracking-widest"
                                    style={{ color: BASELINE_CFG.accent }}>
                                    Full Architecture Proposal
                                </p>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    Generated by Standard AI · Confidence {Math.round((baselineResult.confidence_score ?? 0.82) * 100)}%
                                </p>
                            </div>
                        </div>
                        {/* Document body */}
                        <div className="px-10 py-8">
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={buildMdComponents(BASELINE_CFG)}
                            >
                                {normalizeMarkdown(baselineResult.structured_prd ?? baselineResult.reasoning ?? '')}
                            </ReactMarkdown>
                        </div>
                    </div>
                )}


                {debateResult && (
                    <div className="space-y-4">

                        {/* ── Council header card ───────────────────────── */}
                        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                            <div className="flex items-center gap-3 px-8 py-4 border-b border-slate-100 bg-slate-50">
                                <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center shrink-0 shadow-sm border border-slate-200">
                                    <Gavel size={15} className="text-slate-500" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-xs font-black uppercase tracking-widest text-slate-500">
                                        Council of Agents · Multi-Agent Debate
                                    </p>
                                    <p className="text-xs text-slate-400 mt-0.5">
                                        {debateResult.total_turns} turns · {debateResult.consensus_reached ? 'Consensus reached' : 'No consensus'} · {debateResult.debate_history?.length ?? 0} exchanges
                                    </p>
                                </div>
                                {/* Persona pills */}
                                <div className="hidden md:flex items-center gap-2 shrink-0">
                                    {(['LEGACY_KEEPER', 'INNOVATOR', 'MEDIATOR'] as const).map(p => {
                                        const cfg = COUNCIL_PERSONA[p];
                                        const Icon = cfg.icon;
                                        return (
                                            <span key={p} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border ${cfg.pill}`}>
                                                <Icon size={9} /> {cfg.name}
                                            </span>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* ── Debate turns ──────────────────────────── */}
                            <div className="px-8 py-8 space-y-8">
                                {(debateResult.debate_history ?? []).map((turn, i) => (
                                    <DebateTurnCard key={i} turn={turn} index={i} />
                                ))}
                            </div>
                        </div>

                        {/* ── Final consensus document ──────────────────── */}
                        {debateResult.final_consensus_proposal && (
                            <div className="bg-white rounded-2xl border-2 border-emerald-200 shadow-sm overflow-hidden">
                                <div className="flex items-center gap-3 px-8 py-4 border-b border-emerald-100 bg-emerald-50">
                                    <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center shrink-0 shadow-sm border border-emerald-200">
                                        <CheckCircle2 size={15} className="text-emerald-600" />
                                    </div>
                                    <div>
                                        <p className="text-xs font-black uppercase tracking-widest text-emerald-700">
                                            Final Consensus Proposal
                                        </p>
                                        <p className="text-xs text-emerald-600 mt-0.5">
                                            Agreed position of the Council · {debateResult.consensus_type ?? 'Consensus'}
                                        </p>
                                    </div>
                                </div>
                                <div className="px-10 py-8">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={buildMdComponents({
                                            accent: '#059669',
                                            bg: '#f0fdf4',
                                            border: '#a7f3d0',
                                        })}
                                    >
                                        {normalizeMarkdown(debateResult.final_consensus_proposal)}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {(baselineResult || debateResult) && (
                <div className="mt-8">
                    <TrustQuestionnaire
                        scenarioId={assignedScenario.id}
                        condition={currentCondition}
                        participantId={participant.id}
                        sessionId={sessionId}
                        orderInSession={currentStep + 1}
                        conditionOrder={participant.assigned_condition_order}
                        onComplete={handleQuestionnaireComplete}
                    />
                </div>
            )}
        </div>
    );
}