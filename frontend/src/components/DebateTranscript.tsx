import React, { useEffect, useRef, useState } from 'react';
import { Shield, Zap, Scale, CheckCircle2, Loader2, AlertCircle, Flame } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import type { DebateTurn } from '../types';
import { AgentPersona } from '../types';

// ── Persona config ─────────────────────────────────────────────────────────────
// Kept local to avoid circular imports. Mirrors ProposalDetailPage PERSONA map.
const PERSONA_CONFIG = {
    [AgentPersona.LEGACY_KEEPER]: {
        name: 'Legacy Keeper',
        tagline: 'Stability · Proven patterns · Risk mitigation',
        Icon: Shield,
        bubble: 'bg-amber-50 border-amber-200',
        badge: 'bg-amber-100 text-amber-800 border border-amber-200',
        avatar: 'bg-amber-100 text-amber-600',
        dot: 'bg-amber-400',
        name_color: 'text-amber-700',
    },
    [AgentPersona.INNOVATOR]: {
        name: 'Innovator',
        tagline: 'Modern arch · Scalability · Future-proof',
        Icon: Zap,
        bubble: 'bg-violet-50 border-violet-200',
        badge: 'bg-violet-100 text-violet-800 border border-violet-200',
        avatar: 'bg-violet-100 text-violet-600',
        dot: 'bg-violet-400',
        name_color: 'text-violet-700',
    },
    [AgentPersona.MEDIATOR]: {
        name: 'Mediator',
        tagline: 'Balanced trade-offs · Pragmatic · Team-focused',
        Icon: Scale,
        bubble: 'bg-sky-50 border-sky-200',
        badge: 'bg-sky-100 text-sky-800 border border-sky-200',
        avatar: 'bg-sky-100 text-sky-600',
        dot: 'bg-sky-400',
        name_color: 'text-sky-700',
    },
} as const;

// Accent colours for markdown list bullet tinting
const PERSONA_ACCENTS: Record<string, string> = {
    [AgentPersona.LEGACY_KEEPER]: '#b45309',
    [AgentPersona.INNOVATOR]: '#7c3aed',
    [AgentPersona.MEDIATOR]: '#0369a1',
};

// Debate turns store persona as uppercase string — normalise for lookup
function resolvePersona(persona: string): keyof typeof PERSONA_CONFIG {
    const upper = persona.toUpperCase();
    if (upper === 'LEGACY_KEEPER') return AgentPersona.LEGACY_KEEPER;
    if (upper === 'INNOVATOR') return AgentPersona.INNOVATOR;
    if (upper === 'MEDIATOR') return AgentPersona.MEDIATOR;
    return AgentPersona.MEDIATOR; // fallback
}

// ── Sentiment badge ────────────────────────────────────────────────────────────
const SENTIMENT_CONFIG: Record<string, { label: string; classes: string }> = {
    contentious: { label: 'Contentious', classes: 'bg-red-50 text-red-700 border border-red-200' },
    agreeable: { label: 'Agreeable', classes: 'bg-emerald-50 text-emerald-700 border border-emerald-200' },
    neutral: { label: 'Neutral', classes: 'bg-slate-100 text-slate-600 border border-slate-200' },
};

// ── Markdown components for debate bubble responses ──────────────────────────
// Lighter than the full PRD renderer — handles bold, lists, headings, code.
// Tinted to match each persona's accent colour via the `accentColor` prop.
const buildDebateMdComponents = (accentColor: string): Components => ({
    p: ({ children }) => <p className="text-sm text-slate-700 leading-relaxed mb-2 last:mb-0">{children}</p>,
    strong: ({ children }) => <strong className="font-bold text-slate-800">{children}</strong>,
    em: ({ children }) => <em className="italic text-slate-500">{children}</em>,
    h1: ({ children }) => <h2 className="text-base font-black text-slate-800 mt-3 mb-1.5 first:mt-0">{children}</h2>,
    h2: ({ children }) => <h2 className="text-base font-black text-slate-800 mt-3 mb-1.5 first:mt-0">{children}</h2>,
    h3: ({ children }) => <h3 className="text-sm font-bold text-slate-700 mt-2 mb-1">{children}</h3>,
    ul: ({ children }) => <ul className="my-2 space-y-1 ml-1">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal list-outside ml-5 my-2 space-y-1">{children}</ol>,
    li: ({ children }) => (
        <li className="flex items-start gap-2 text-sm text-slate-700 leading-relaxed">
            <span className="mt-[7px] w-1.5 h-1.5 rounded-full shrink-0" style={{ background: accentColor }} />
            <span>{children}</span>
        </li>
    ),
    code: ({ children }) => (
        <code className="bg-white/60 text-slate-700 px-1.5 py-0.5 rounded text-xs font-mono border border-slate-200">
            {children}
        </code>
    ),
    blockquote: ({ children }) => (
        <blockquote className="border-l-3 pl-3 my-2 italic text-slate-500" style={{ borderColor: accentColor }}>
            {children}
        </blockquote>
    ),
    hr: () => <hr className="border-slate-200 my-3" />,
});

// ── Sub-components ─────────────────────────────────────────────────────────────

const TurnBubble: React.FC<{ turn: DebateTurn; isNew: boolean }> = ({ turn, isNew }) => {
    const key = resolvePersona(turn.persona);
    const cfg = PERSONA_CONFIG[key];
    const { Icon } = cfg;
    const sentiment = turn.sentiment ? SENTIMENT_CONFIG[turn.sentiment.toLowerCase()] : null;

    return (
        <div className={`flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-400 ${isNew ? 'duration-300' : 'duration-0'}`}>
            {/* Avatar */}
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${cfg.avatar}`}>
                <Icon size={16} />
            </div>

            {/* Bubble */}
            <div className="flex-1 min-w-0">
                {/* Header */}
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className={`text-xs font-bold ${cfg.name_color}`}>{cfg.name}</span>
                    <span className="text-[10px] text-slate-400 font-mono">Turn {turn.turn_number}</span>
                    {sentiment && (
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${sentiment.classes}`}>
                            {turn.sentiment === 'contentious' && <Flame size={9} className="inline mr-1" />}
                            {sentiment.label}
                        </span>
                    )}
                </div>

                {/* Message */}
                <div className={`px-4 py-3 rounded-2xl rounded-tl-sm border ${cfg.bubble}`}>
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={buildDebateMdComponents(PERSONA_ACCENTS[key])}
                    >
                        {turn.response}
                    </ReactMarkdown>
                </div>

                {/* Key points */}
                {turn.key_points && turn.key_points.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                        {turn.key_points.slice(0, 3).map((point, i) => (
                            <span key={i} className="text-[10px] text-slate-500 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-full">
                                {point}
                            </span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

const ThinkingIndicator: React.FC<{ nextPersona?: string }> = ({ nextPersona }) => {
    const key = nextPersona ? resolvePersona(nextPersona) : null;
    const cfg = key ? PERSONA_CONFIG[key] : null;

    return (
        <div className="flex gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${cfg ? cfg.avatar : 'bg-slate-100 text-slate-400'}`}>
                {cfg ? <cfg.Icon size={16} /> : <Loader2 size={16} className="animate-spin" />}
            </div>
            <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                    <span className={`text-xs font-bold ${cfg ? cfg.name_color : 'text-slate-500'}`}>
                        {cfg ? cfg.name : 'Council'}
                    </span>
                    <span className="text-[10px] text-slate-400">is thinking...</span>
                </div>
                <div className="px-4 py-3 rounded-2xl rounded-tl-sm border border-slate-200 bg-slate-50 flex items-center gap-2">
                    <div className="flex gap-1">
                        {[0, 1, 2].map(i => (
                            <div
                                key={i}
                                className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
                                style={{ animationDelay: `${i * 150}ms` }}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

const ConsensusReachedBanner: React.FC = () => (
    <div className="flex items-center gap-3 p-4 bg-emerald-50 border border-emerald-200 rounded-2xl">
        <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
            <CheckCircle2 size={18} className="text-emerald-600" />
        </div>
        <div>
            <p className="text-sm font-bold text-emerald-800">Consensus reached</p>
            <p className="text-xs text-emerald-600 mt-0.5">
                The Council aligned on a unified direction. Generating proposals now...
            </p>
        </div>
    </div>
);

const PersonaLegend: React.FC = () => (
    <div className="flex items-center gap-3 flex-wrap">
        {Object.values(PERSONA_CONFIG).map(cfg => (
            <div key={cfg.name} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium ${cfg.badge}`}>
                <cfg.Icon size={11} />
                {cfg.name}
            </div>
        ))}
    </div>
);

// ── Main component ─────────────────────────────────────────────────────────────

interface DebateTranscriptProps {
    turns: DebateTurn[];
    consensusReached: boolean;
    totalTurns: number;
    initialLoading: boolean;
    isComplete: boolean;
    error: string | null;
    /** Whether to show the live thinking indicator (pass false for replay mode) */
    live?: boolean;
}

export const DebateTranscript: React.FC<DebateTranscriptProps> = ({
    turns,
    consensusReached,
    totalTurns,
    initialLoading,
    isComplete,
    error,
    live = true,
}) => {
    const bottomRef = useRef<HTMLDivElement>(null);
    const lastScrolledCount = useRef(0);
    const [seenTurnNumbers, setSeenTurnNumbers] = useState<Set<number>>(new Set());

    // Auto-scroll when new turns arrive; mark them as seen after a short delay
    // so the entrance animation plays before they lose their "new" styling.
    useEffect(() => {
        if (turns.length <= lastScrolledCount.current) return;
        lastScrolledCount.current = turns.length;
        bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
        const newNumbers = turns.map(t => t.turn_number);
        const timer = setTimeout(() => {
            setSeenTurnNumbers(new Set(newNumbers));
        }, 600);
        return () => clearTimeout(timer);
    }, [turns.length]); // eslint-disable-line react-hooks/exhaustive-deps

    // Determine next persona for thinking indicator
    const TURN_ORDER = [AgentPersona.LEGACY_KEEPER, AgentPersona.INNOVATOR, AgentPersona.MEDIATOR];
    const nextPersona = turns.length > 0
        ? TURN_ORDER[turns.length % TURN_ORDER.length]
        : AgentPersona.LEGACY_KEEPER;

    // ── Initial loading ────────────────────────────────────────────────────────
    if (initialLoading) {
        return (
            <div className="flex flex-col items-center justify-center py-16 gap-4">
                <Loader2 size={32} className="animate-spin text-cyan-500" />
                <p className="text-sm font-medium text-slate-500">Waiting for the Council to convene...</p>
                <PersonaLegend />
            </div>
        );
    }

    // ── Error ──────────────────────────────────────────────────────────────────
    if (error && turns.length === 0) {
        return (
            <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-2xl">
                <AlertCircle size={18} className="text-red-500 shrink-0" />
                <p className="text-sm text-red-700">{error}</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-2">
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <PersonaLegend />
                {totalTurns > 0 && (
                    <span className="text-xs font-mono text-slate-400">
                        {turns.length} / {totalTurns} turns
                    </span>
                )}
            </div>

            {/* Turns */}
            <div className="flex flex-col gap-4">
                {turns.map((turn) => (
                    <TurnBubble
                        key={turn.turn_number}
                        turn={turn}
                        isNew={!seenTurnNumbers.has(turn.turn_number)}
                    />
                ))}
            </div>

            {/* Thinking indicator (live mode only, not yet complete) */}
            {live && !isComplete && !consensusReached && turns.length > 0 && (
                <div className="mt-2">
                    <ThinkingIndicator nextPersona={nextPersona} />
                </div>
            )}

            {/* Consensus banner */}
            {consensusReached && (
                <div className="mt-2">
                    <ConsensusReachedBanner />
                </div>
            )}

            {/* Scroll anchor */}
            <div ref={bottomRef} />
        </div>
    );
};