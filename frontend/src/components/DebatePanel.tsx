import React, { useEffect, useRef } from 'react';
import { Shield, Zap, Scale, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { DebateTurn } from '../types';

interface Props {
    history: DebateTurn[];
    isDebating: boolean;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getPersonaIcon(persona: string): React.ReactNode {
    switch (persona.toLowerCase()) {
        case 'LEGACY_KEEPER': return <Shield className="w-5 h-5 text-blue-600" />;
        case 'INNOVATOR': return <Zap className="w-5 h-5 text-orange-500" />;
        case 'MEDIATOR': return <Scale className="w-5 h-5 text-purple-600" />;
        default: return <div className="w-5 h-5 bg-slate-400 rounded-full" />;
    }
}

function getPersonaName(persona: string): string {
    switch (persona.toLowerCase()) {
        case 'LEGACY_KEEPER': return 'Legacy Keeper';
        case 'INNOVATOR': return 'The Innovator';
        case 'MEDIATOR': return 'The Mediator';
        default: return persona;
    }
}

function getSentimentStyle(sentiment: string | null | undefined): string {
    if (!sentiment) return '';
    switch (sentiment.toLowerCase()) {
        case 'agree': return 'bg-emerald-100 text-emerald-700';
        case 'disagree': return 'bg-red-100 text-red-700';
        case 'neutral': return 'bg-slate-100 text-slate-600';
        default: return 'bg-slate-100 text-slate-600';
    }
}

function getTurnBubbleStyle(persona: string): string {
    switch (persona.toLowerCase()) {
        case 'MEDIATOR': return 'bg-purple-50 border-l-4 border-l-purple-400 border border-purple-100 text-purple-900';
        case 'LEGACY_KEEPER': return 'bg-white border border-slate-200 text-slate-800';
        default: return 'bg-orange-50/40 border border-orange-100 text-slate-800';
    }
}

// ─── Component ────────────────────────────────────────────────────────────────

export const DebatePanel: React.FC<Props> = ({ history, isDebating }) => {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history, isDebating]);

    if (history.length === 0 && !isDebating) {
        return (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50 p-8">
                <Scale size={48} className="mb-4 opacity-50" />
                <h3 className="text-lg font-semibold text-slate-600">Council Adjourned</h3>
                <p className="text-sm">Convene the council to begin the architectural debate.</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-slate-50 rounded-xl border border-slate-200 overflow-hidden shadow-inner">
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth"
            >
                {history.map((turn, idx) => (
                    <div
                        key={idx}
                        className={`flex gap-3 animate-in fade-in slide-in-from-bottom-4 duration-500 ${turn.persona === 'MEDIATOR' ? 'justify-center max-w-[95%] mx-auto' : ''
                            }`}
                    >
                        {/* Persona icon */}
                        <div className="mt-1 bg-white p-2 rounded-xl shadow-sm h-fit border border-slate-100 ring-1 ring-slate-200/50 flex-shrink-0">
                            {getPersonaIcon(turn.persona)}
                        </div>

                        <div className="flex-1 max-w-[85%]">
                            {/* Turn header */}
                            <div className="flex items-center gap-2 mb-1.5 px-1">
                                <span className="font-bold text-[11px] text-slate-700 uppercase tracking-widest">
                                    {getPersonaName(turn.persona)}
                                </span>
                                <span className="text-[9px] text-slate-400 font-mono bg-slate-200/50 px-1.5 py-0.5 rounded">
                                    Turn {turn.turn_number + 1}
                                </span>
                                {turn.sentiment && (
                                    <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${getSentimentStyle(turn.sentiment)}`}>
                                        {turn.sentiment}
                                    </span>
                                )}
                            </div>

                            {/* Response bubble */}
                            <div className={`p-4 rounded-2xl text-sm leading-relaxed shadow-sm prose prose-slate prose-sm max-w-none ${getTurnBubbleStyle(turn.persona)}`}>
                                <ReactMarkdown>{turn.response}</ReactMarkdown>
                            </div>

                            {/* Key points */}
                            {turn.key_points.length > 0 && (
                                <div className="mt-2 pl-2 space-y-1">
                                    {turn.key_points.map((point, i) => (
                                        <div key={i} className="flex items-start gap-1.5 text-[11px] text-slate-500">
                                            <ChevronRight className="w-3 h-3 mt-0.5 flex-shrink-0 text-slate-400" />
                                            <span>{point}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {/* Typing indicator */}
                {isDebating && (
                    <div className="flex items-start gap-3 animate-pulse px-2">
                        <div className="mt-1 w-9 h-9 bg-slate-200 rounded-xl flex-shrink-0" />
                        <div className="flex-1 space-y-2">
                            <div className="h-3 w-24 bg-slate-200 rounded" />
                            <div className="h-16 w-3/4 bg-slate-200 rounded-2xl" />
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};