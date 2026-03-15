/**
 * ProposalDetailPage.tsx — redesigned with a document-reader layout.
 *
 * Layout:
 *   ┌─────────────────────────── sticky header ───────────────────────────────┐
 *   │  ← Missions  |  Council Proposals #7  |  [selected badge]  [PDF][Jira] │
 *   ├─────────────────┬───────────────────────────────────────────────────────┤
 *   │  LEFT RAIL      │  READING PANE                                         │
 *   │  (sticky)       │                                                       │
 *   │  • Legacy       │  [Persona header + actions]                           │
 *   │  • Innovator    │  [Reasoning | Trade-offs]                             │
 *   │  • Mediator     │  [Full PRD — no truncation]                           │
 *   │                 │  [Bottom CTA]                                         │
 *   └─────────────────┴───────────────────────────────────────────────────────┘
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    ArrowLeft, AlertCircle, CheckCircle2, Clock,
    Loader2, RefreshCw, MessageSquare, X,
    Shield, Zap, Scale, ChevronRight,
    TrendingUp, FileText, Brain, AlertTriangle, BookOpen,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'react-hot-toast';

import { api } from '../api/client';
import { debateApi } from '../api/client';
import { ProposalStatus, AgentPersona } from '../types';
import type { Proposal, ProposalVariation, ChatMessage, DebateTurn } from '../types';
import { useChatSession } from '../hooks/useChatSession';
import { DiagramModal } from '../components/modals/DiagramModal';
import { ApprovalModal } from '../components/modals/ApproveModal';
import { ConfirmModal } from '../components/modals/ConfirmModal';
import { DebateTranscript } from '../components/DebateTranscript';

// ─── Persona config ───────────────────────────────────────────────────────────
const PERSONA = {
    [AgentPersona.LEGACY_KEEPER]: {
        name: 'Legacy Keeper', short: 'Legacy', icon: Shield,
        accent: '#b45309', bg: '#fffbeb', border: '#fcd34d',
        pill: 'bg-amber-100 text-amber-800 border-amber-200',
        button: 'bg-amber-600 hover:bg-amber-700',
        description: 'Stability · Proven patterns · Risk mitigation',
    },
    [AgentPersona.INNOVATOR]: {
        name: 'Innovator', short: 'Innovator', icon: Zap,
        accent: '#7c3aed', bg: '#f5f3ff', border: '#c4b5fd',
        pill: 'bg-violet-100 text-violet-800 border-violet-200',
        button: 'bg-violet-600 hover:bg-violet-700',
        description: 'Modern arch · Scalability · Future-proof',
    },
    [AgentPersona.MEDIATOR]: {
        name: 'Mediator', short: 'Mediator', icon: Scale,
        accent: '#0369a1', bg: '#f0f9ff', border: '#7dd3fc',
        pill: 'bg-sky-100 text-sky-800 border-sky-200',
        button: 'bg-sky-600 hover:bg-sky-700',
        description: 'Balanced trade-offs · Pragmatic · Team-focused',
    },
    [AgentPersona.BASELINE]: {
        name: 'Baseline', short: 'Baseline', icon: FileText,
        accent: '#64748b', bg: '#f8fafc', border: '#cbd5e1',
        pill: 'bg-slate-100 text-slate-700 border-slate-200',
        button: 'bg-slate-600 hover:bg-slate-700',
        description: 'Single-agent baseline proposal',
    },
} as const;

const ORDER: AgentPersona[] = [AgentPersona.LEGACY_KEEPER, AgentPersona.INNOVATOR, AgentPersona.MEDIATOR, AgentPersona.BASELINE];

// ─── Confidence bar ───────────────────────────────────────────────────────────
const ConfidenceBar: React.FC<{ score: number; color: string }> = ({ score, color }) => (
    <div className="flex items-center gap-2">
        <TrendingUp size={11} style={{ color }} />
        <span className="text-xs font-bold" style={{ color }}>{score}%</span>
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all duration-500"
                style={{ width: `${score}%`, background: color }} />
        </div>
    </div>
);

// ─── Sidebar card (persona switcher) ─────────────────────────────────────────
const SidebarCard: React.FC<{
    variation: ProposalVariation;
    isActive: boolean;
    isSelected: boolean;
    onClick: () => void;
}> = ({ variation, isActive, isSelected, onClick }) => {
    const cfg = PERSONA[variation.agent_persona];
    const Icon = cfg.icon;

    return (
        <button
            onClick={onClick}
            className="w-full text-left rounded-xl border-2 p-4 transition-all duration-150 group"
            style={isActive
                ? { borderColor: cfg.border, background: cfg.bg }
                : { borderColor: '#e2e8f0', background: 'white' }
            }
        >
            <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg" style={{ background: isActive ? 'white' : cfg.bg }}>
                        <Icon size={13} style={{ color: cfg.accent }} />
                    </div>
                    <span className="text-sm font-bold text-slate-800">{cfg.name}</span>
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                    {isSelected && <CheckCircle2 size={13} className="text-emerald-500" />}
                    <ChevronRight size={13}
                        className="transition-transform text-slate-300 group-hover:text-slate-400"
                        style={isActive ? { transform: 'rotate(90deg)', color: '#64748b' } : {}} />
                </div>
            </div>
            <p className="text-xs text-slate-500 mb-2 leading-relaxed">{cfg.description}</p>
            <ConfidenceBar score={variation.confidence_score} color={cfg.accent} />
        </button>
    );
};

// ─── Chat panel ───────────────────────────────────────────────────────────────
const ChatPanel: React.FC<{
    variation: ProposalVariation;
    onClose: () => void;
    onHistoryUpdate: (variationId: number, history: ChatMessage[]) => void;
}> = ({ variation, onClose, onHistoryUpdate }) => {
    const cfg = PERSONA[variation.agent_persona];
    const noop = useCallback(() => { }, []);
    const { chatHistory, chatInput, chatLoading, chatEndRef, setChatInput, handleSendMessage, updatedVariation } =
        useChatSession(variation, noop);

    // Sync updated chat history back to parent whenever a new message lands
    useEffect(() => {
        if (updatedVariation) {
            onHistoryUpdate(updatedVariation.id, updatedVariation.chat_history);
        }
    }, [updatedVariation, onHistoryUpdate]);

    return (
        <div className="fixed inset-y-0 right-0 w-[400px] bg-white shadow-2xl border-l border-slate-200 flex flex-col z-50">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between"
                style={{ background: cfg.bg }}>
                <div>
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${cfg.pill} mb-1`}>
                        <cfg.icon size={10} /> {cfg.name}
                    </span>
                    <p className="text-sm font-semibold text-slate-700">Deep-Dive Debate Mode</p>
                </div>
                <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/60 transition-colors">
                    <X size={16} className="text-slate-500" />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/50">
                {chatHistory.length === 0 && (
                    <div className="text-center py-12 text-slate-400">
                        <MessageSquare size={28} className="mx-auto mb-3 opacity-30" />
                        <p className="text-sm">Ask {cfg.name} about their proposal,<br />trade-offs, or decisions.</p>
                    </div>
                )}
                {chatHistory.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[82%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed
                            ${msg.role === 'user'
                                ? 'bg-slate-800 text-white rounded-br-sm'
                                : 'bg-white text-slate-700 border border-slate-200 rounded-bl-sm shadow-sm'}`}>
                            {msg.content}
                        </div>
                    </div>
                ))}
                {chatLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
                            <Loader2 size={14} className="animate-spin text-slate-400" />
                        </div>
                    </div>
                )}
                <div ref={chatEndRef} />
            </div>

            <div className="p-4 border-t border-slate-100 bg-white">
                <div className="flex gap-2">
                    <input
                        value={chatInput}
                        onChange={e => setChatInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }}
                        placeholder={`Ask ${cfg.name}…`}
                        disabled={chatLoading}
                        className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:border-transparent transition-all"
                    />
                    <button onClick={handleSendMessage} disabled={chatLoading || !chatInput.trim()}
                        className="px-4 py-2.5 text-white rounded-xl font-bold text-sm disabled:opacity-50 transition-colors"
                        style={{ background: cfg.accent }}>
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
};

// ─── Normalize inline numbered lists to proper Markdown ──────────────────────
// Converts "1) foo. 2) bar" and "1. foo 2. bar" patterns into proper MD lists
const normalizeMarkdown = (text: string): string => {
    if (!text) return text;
    // Match patterns like "1) text 2) text" or "1. text 2. text" within a paragraph
    // Replace them with proper newline-separated markdown list items
    return text
        .replace(/(\d+)\)\s+/g, (_, n) => `\n${n}. `)
        .replace(/\n{3,}/g, '\n\n')
        .trim();
};

// ─── Inline Markdown components (for Reasoning / Trade-offs) ─────────────────
// Renders bold, italic, inline code and links — no block-level elements
const inlineComponents: Components = {
    p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
    strong: ({ children }) => <strong className="font-bold text-slate-800">{children}</strong>,
    em: ({ children }) => <em className="italic text-slate-500">{children}</em>,
    code: ({ children }) => <code className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>,
    a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-cyan-600 underline underline-offset-2">{children}</a>,
    ol: ({ children }) => <ol className="list-decimal list-outside ml-5 my-2 space-y-1">{children}</ol>,
    ul: ({ children }) => <ul className="list-disc list-outside ml-5 my-2 space-y-1">{children}</ul>,
    li: ({ children }) => <li className="leading-6">{children}</li>,
};

// ─── Full PRD Markdown components (persona-tinted) ────────────────────────────
const buildMdComponents = (cfg: typeof PERSONA[keyof typeof PERSONA]): Components => ({
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

// ─── Main page ────────────────────────────────────────────────────────────────
const ProposalDetailPage: React.FC = () => {
    const { id: projectId, proposalId } = useParams<{ id: string; proposalId: string }>();
    const navigate = useNavigate();

    const [proposal, setProposal] = useState<Proposal | null>(null);
    const [loading, setLoading] = useState(true);
    const [selecting, setSelecting] = useState(false);
    const [activePersona, setActivePersona] = useState<string>(AgentPersona.LEGACY_KEEPER);
    const [chatVariation, setChatVariation] = useState<ProposalVariation | null>(null);
    const [isDownloading, setIsDownloading] = useState(false);
    const [isApproveOpen, setIsApproveOpen] = useState(false);
    const [isDiagramOpen, setIsDiagramOpen] = useState(false);
    const [confirmState, setConfirmState] = useState<{
        isOpen: boolean; title: string; message: string; type: 'danger' | 'info'; onConfirm: () => void;
    }>({ isOpen: false, title: '', message: '', type: 'info', onConfirm: () => { } });

    // Task 2: ref to the main scroll container — scrolled to top on persona switch
    const [activeTab, setActiveTab] = useState<'proposals' | 'debate'>('proposals');
    const [debateTurns, setDebateTurns] = useState<DebateTurn[]>([]);
    const [debateConsensus, setDebateConsensus] = useState(false);
    const [debateLoading, setDebateLoading] = useState(false);
    const readingPaneRef = React.useRef<HTMLDivElement>(null);

    const fetchProposal = useCallback(async () => {
        if (!proposalId) return;
        try {
            const res = await api.get<Proposal>(`/proposals/${proposalId}`);
            setProposal(res.data);
        } catch { toast.error('Failed to load proposal'); }
        finally { setLoading(false); }
    }, [proposalId]);

    useEffect(() => { fetchProposal(); }, [fetchProposal]);
    useEffect(() => {
        if (proposal?.status !== ProposalStatus.PROCESSING) return;
        const t = setInterval(fetchProposal, 3000);
        return () => clearInterval(t);
    }, [proposal?.status, fetchProposal]);

    // Fetch debate history once when the proposal is COMPLETED
    useEffect(() => {
        if (!proposalId || proposal?.status !== ProposalStatus.COMPLETED) return;
        setDebateLoading(true);
        debateApi.getLatestDebate(Number(proposalId))
            .then(data => {
                setDebateTurns(data.debate_history ?? []);
                setDebateConsensus(data.consensus_reached ?? false);
            })
            .catch(() => { /* no debate session yet — silently ignore */ })
            .finally(() => setDebateLoading(false));
    }, [proposalId, proposal?.status]);

    // Scroll reading pane to top whenever the active persona changes (Task 2)
    useEffect(() => {
        readingPaneRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    }, [activePersona]);

    // Sync chat history from ChatPanel back into proposal.variations so next open sees it
    const handleHistoryUpdate = useCallback((variationId: number, history: ChatMessage[]) => {
        setProposal(prev => {
            if (!prev) return prev;
            return {
                ...prev,
                variations: prev.variations?.map(v =>
                    v.id === variationId ? { ...v, chat_history: history } : v
                ),
            };
        });
        // Also update chatVariation so the panel itself stays consistent
        setChatVariation(prev =>
            prev && prev.id === variationId ? { ...prev, chat_history: history } : prev
        );
    }, []);

    const handleSelectVariation = useCallback(async (variationId: number) => {
        if (!proposal) return;
        setSelecting(true);
        try {
            await api.post(`/proposals/${proposal.id}/select`, { variation_id: variationId });
            setProposal(prev => prev ? { ...prev, selected_variation_id: variationId } : null);
            toast.success('Strategy selected! Redirecting to accepted proposals…');
            setTimeout(() => {
                navigate(`/project/${projectId}/generator/history`, {
                    state: { highlightId: proposal.id },
                });
            }, 1200);
        } catch { toast.error('Failed to select proposal.'); }
        finally { setSelecting(false); }
    }, [proposal, projectId, navigate]);

    const handleDownloadPdf = useCallback(async () => {
        if (!proposal) return;
        setIsDownloading(true);
        try {
            const res = await api.get(`/proposals/${proposal.id}/export/pdf`, { responseType: 'blob' });
            const url = URL.createObjectURL(new Blob([res.data as BlobPart]));
            const a = Object.assign(document.createElement('a'), { href: url, download: `Architecture_${proposal.id}.pdf` });
            document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
        } catch { toast.error('PDF download failed.'); }
        finally { setIsDownloading(false); }
    }, [proposal]);

    const backPath = projectId ? `/project/${projectId}/generator/history` : '/dashboard';

    // ── Loading / error states ────────────────────────────────────────────────
    if (loading) return (
        <div className="min-h-screen flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
        </div>
    );
    if (!proposal) return (
        <div className="min-h-screen flex flex-col items-center justify-center gap-3">
            <AlertCircle size={36} className="text-slate-400" />
            <p className="text-slate-600 font-medium">Proposal not found.</p>
            <button onClick={() => navigate(backPath)} className="px-4 py-2 bg-cyan-600 text-white rounded-lg text-sm font-bold">Back</button>
        </div>
    );
    if (proposal.status === ProposalStatus.PROCESSING) return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-12 max-w-md text-center">
                <div className="relative inline-block mb-6">
                    <div className="absolute inset-0 bg-cyan-100 rounded-full animate-ping opacity-40" />
                    <div className="relative bg-white p-5 rounded-full border border-slate-100 shadow">
                        <Loader2 size={36} className="animate-spin text-cyan-600" />
                    </div>
                </div>
                <h2 className="text-xl font-black text-slate-900 mb-2">Council Deliberating…</h2>
                <p className="text-slate-500 text-sm mb-4">Generating 3 architectural proposals. Usually 1–2 min.</p>
                <div className="flex items-center justify-center gap-1.5 text-xs text-slate-400">
                    <Clock size={12} /> Started {new Date(proposal.created_at).toLocaleTimeString()}
                </div>
            </div>
        </div>
    );
    if (proposal.status === ProposalStatus.FAILED) return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center">
            <div className="bg-white rounded-2xl border border-red-200 shadow-sm p-12 max-w-md text-center">
                <AlertCircle size={40} className="text-red-500 mx-auto mb-4" />
                <h2 className="text-xl font-black mb-2">Generation Failed</h2>
                {proposal.error_message && <p className="text-sm text-red-500 mb-4 bg-red-50 p-3 rounded-lg">{proposal.error_message}</p>}
                <button onClick={() => navigate(backPath)}
                    className="flex items-center gap-2 px-5 py-2.5 bg-cyan-600 text-white rounded-xl font-bold mx-auto hover:bg-cyan-700">
                    <RefreshCw size={14} /> Back to Missions
                </button>
            </div>
        </div>
    );

    // ── Completed ─────────────────────────────────────────────────────────────
    const sorted = [...(proposal.variations ?? [])].sort(
        (a, b) => ORDER.indexOf(a.agent_persona) - ORDER.indexOf(b.agent_persona)
    );
    const active = sorted.find(v => v.agent_persona === activePersona) ?? sorted[0];
    const activeCfg = active ? PERSONA[active.agent_persona] : null;
    const selectedVar = sorted.find(v => v.id === proposal.selected_variation_id) ?? null;

    return (
        <>
            <div className="h-screen bg-slate-100 flex flex-col overflow-hidden">

                {/* ── Sticky header ─────────────────────────────────────────── */}
                <header className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-sm">
                    <div className="max-w-screen-2xl mx-auto px-6 py-3 flex items-center gap-4">
                        <button onClick={() => navigate(backPath)}
                            className="flex items-center gap-1.5 text-slate-400 hover:text-slate-700 font-bold text-xs uppercase tracking-wider transition-colors shrink-0">
                            <ArrowLeft size={14} /> Missions
                        </button>

                        <div className="flex-1 min-w-0">
                            <h1 className="text-sm font-black text-slate-900 truncate leading-tight">
                                Council Proposals
                                <span className="ml-2 text-slate-400 font-normal">#{proposal.id}</span>
                            </h1>
                            <p className="text-xs text-slate-500 truncate">{proposal.task_description}</p>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                            {selectedVar && (
                                <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-full">
                                    <CheckCircle2 size={12} />
                                    {PERSONA[selectedVar.agent_persona]?.name} selected
                                </span>
                            )}
                            {selectedVar && (
                                <>
                                    <button onClick={handleDownloadPdf} disabled={isDownloading}
                                        className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold transition-colors disabled:opacity-50">
                                        {isDownloading ? <Loader2 size={12} className="animate-spin" /> : <FileText size={12} />} PDF
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                </header>

                {/* ── Tab bar ──────────────────────────────────────────────── */}
                <div className="bg-white border-b border-slate-200">
                    <div className="max-w-screen-2xl mx-auto px-6 flex items-center gap-1">
                        {([
                            { id: 'proposals', label: 'Proposals', icon: BookOpen },
                            { id: 'debate', label: 'Debate Transcript', icon: MessageSquare },
                        ] as const).map(({ id, label, icon: Icon }) => (
                            <button
                                key={id}
                                onClick={() => setActiveTab(id)}
                                className={`flex items-center gap-2 px-4 py-3 text-sm font-bold border-b-2 transition-colors -mb-px ${activeTab === id
                                        ? 'border-cyan-600 text-cyan-600'
                                        : 'border-transparent text-slate-400 hover:text-slate-700'
                                    }`}
                            >
                                <Icon size={14} /> {label}
                                {id === 'debate' && debateTurns.length > 0 && (
                                    <span className="text-[10px] font-mono bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full">
                                        {debateTurns.length}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* ── Body ──────────────────────────────────────────────────── */}
                {activeTab === 'debate' ? (
                    <div className="flex-1 max-w-screen-2xl mx-auto w-full px-6 py-6 overflow-y-auto">
                        <DebateTranscript
                            turns={debateTurns}
                            consensusReached={debateConsensus}
                            totalTurns={debateTurns.length}
                            initialLoading={debateLoading}
                            isComplete={true}
                            error={null}
                            live={false}
                        />
                    </div>
                ) : (
                    <div ref={readingPaneRef} className="flex-1 max-w-screen-2xl mx-auto w-full px-6 py-6 flex gap-6 items-start overflow-y-auto">

                        {/* ── Left rail ──────────────────────────────────────────── */}
                        <aside className="w-64 shrink-0 flex flex-col gap-3 sticky top-[73px]">
                            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4">
                                <p className="text-xs font-black text-slate-400 uppercase tracking-widest mb-3 px-1">
                                    Proposals
                                </p>
                                <div className="flex flex-col gap-2">
                                    {sorted.map(v => (
                                        <SidebarCard
                                            key={v.id}
                                            variation={v}
                                            isActive={v.agent_persona === activePersona}
                                            isSelected={v.id === proposal.selected_variation_id}
                                            onClick={() => setActivePersona(v.agent_persona)}
                                        />
                                    ))}
                                </div>
                            </div>

                            {!selectedVar && (
                                <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                                    <p className="text-xs font-bold text-blue-700 mb-1">Next step</p>
                                    <p className="text-xs text-blue-600 leading-relaxed">
                                        Read each proposal then select the approach that best fits your project.
                                    </p>
                                </div>
                            )}
                        </aside>

                        {/* ── Reading pane ───────────────────────────────────────── */}
                        {active && activeCfg ? (
                            <main className="flex-1 min-w-0 flex flex-col gap-4">

                                {/* Persona header card */}
                                <div className="bg-white rounded-2xl border-2 shadow-sm overflow-hidden"
                                    style={{ borderColor: activeCfg.border }}>
                                    <div className="px-8 py-5 flex items-center justify-between gap-4"
                                        style={{ background: activeCfg.bg }}>
                                        <div className="flex items-center gap-4 min-w-0">
                                            <div className="p-3 rounded-xl bg-white/70 shadow-sm shrink-0">
                                                <activeCfg.icon size={22} style={{ color: activeCfg.accent }} />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                                                    <h2 className="text-xl font-black text-slate-900">{activeCfg.name}</h2>
                                                    {active.id === proposal.selected_variation_id && (
                                                        <span className="flex items-center gap-1 text-xs font-bold text-emerald-700 bg-emerald-100 border border-emerald-200 px-2 py-0.5 rounded-full">
                                                            <CheckCircle2 size={10} /> Selected
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="text-sm text-slate-600">{activeCfg.description}</p>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-3 shrink-0">
                                            <div className="text-right hidden md:block">
                                                <p className="text-xs text-slate-500 mb-1">Confidence</p>
                                                <div className="flex items-center gap-2">
                                                    <div className="w-28 h-2 bg-white/60 rounded-full overflow-hidden">
                                                        <div className="h-full rounded-full"
                                                            style={{ width: `${active.confidence_score}%`, background: activeCfg.accent }} />
                                                    </div>
                                                    <span className="text-sm font-black" style={{ color: activeCfg.accent }}>
                                                        {active.confidence_score}%
                                                    </span>
                                                </div>
                                            </div>
                                            <button
                                                onClick={() => setChatVariation(active)}
                                                className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm border-2 bg-white transition-all hover:shadow-md"
                                                style={{ borderColor: activeCfg.border, color: activeCfg.accent }}>
                                                <MessageSquare size={14} /> Debate
                                            </button>
                                            <button
                                                onClick={() => handleSelectVariation(active.id)}
                                                disabled={selecting || active.id === proposal.selected_variation_id}
                                                className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm text-white transition-all hover:shadow-md hover:-translate-y-0.5 disabled:opacity-70 disabled:cursor-default disabled:translate-y-0"
                                                style={{ background: active.id === proposal.selected_variation_id ? '#10b981' : activeCfg.accent }}>
                                                {active.id === proposal.selected_variation_id
                                                    ? <><CheckCircle2 size={14} /> Selected</>
                                                    : 'Select This'}
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                {/* ── Reasoning + Trade-offs ─────────────────────── */}
                                {(active.reasoning || active.trade_offs) && (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {active.reasoning && (
                                            <div className="relative bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden group">
                                                <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl" style={{ background: activeCfg.accent }} />
                                                <div className="pl-6 pr-5 pt-5 pb-5">
                                                    <div className="flex items-center gap-2 mb-3">
                                                        <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: activeCfg.bg }}>
                                                            <Brain size={14} style={{ color: activeCfg.accent }} />
                                                        </div>
                                                        <span className="text-xs font-black uppercase tracking-widest" style={{ color: activeCfg.accent }}>
                                                            Reasoning
                                                        </span>
                                                    </div>
                                                    <div className="text-sm text-slate-600 leading-relaxed">
                                                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={inlineComponents}>
                                                            {normalizeMarkdown(active.reasoning)}
                                                        </ReactMarkdown>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                        {active.trade_offs && (
                                            <div className="relative bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden group">
                                                <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl bg-amber-400" />
                                                <div className="pl-6 pr-5 pt-5 pb-5">
                                                    <div className="flex items-center gap-2 mb-3">
                                                        <div className="w-7 h-7 rounded-lg bg-amber-50 flex items-center justify-center shrink-0">
                                                            <AlertTriangle size={14} className="text-amber-500" />
                                                        </div>
                                                        <span className="text-xs font-black uppercase tracking-widest text-amber-600">
                                                            Trade-offs
                                                        </span>
                                                    </div>
                                                    <div className="text-sm text-slate-600 leading-relaxed">
                                                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={inlineComponents}>
                                                            {normalizeMarkdown(active.trade_offs)}
                                                        </ReactMarkdown>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* ── Full PRD ───────────────────────────────────── */}
                                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                                    <div className="flex items-center gap-3 px-8 py-4 border-b border-slate-100" style={{ background: activeCfg.bg }}>
                                        <div className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style={{ background: 'white' }}>
                                            <BookOpen size={15} style={{ color: activeCfg.accent }} />
                                        </div>
                                        <div>
                                            <p className="text-xs font-black uppercase tracking-widest" style={{ color: activeCfg.accent }}>
                                                Full Architecture Proposal
                                            </p>
                                            <p className="text-xs text-slate-500 mt-0.5">Generated by {activeCfg.name} · Confidence {active.confidence_score}%</p>
                                        </div>
                                    </div>
                                    <div className="px-10 py-8">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={buildMdComponents(activeCfg)}>
                                            {normalizeMarkdown(active.structured_prd)}
                                        </ReactMarkdown>
                                    </div>
                                </div>

                                {/* Bottom selection CTA */}
                                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex items-center justify-between gap-4">
                                    <div>
                                        <p className="font-bold text-slate-800">Finished reading?</p>
                                        <p className="text-sm text-slate-500">Select this proposal to proceed with {activeCfg.name}'s approach,
                                            or switch to another in the sidebar.</p>
                                    </div>
                                    <button
                                        onClick={() => handleSelectVariation(active.id)}
                                        disabled={selecting || active.id === proposal.selected_variation_id}
                                        className="flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-white transition-all hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-70 disabled:translate-y-0 shrink-0"
                                        style={{ background: active.id === proposal.selected_variation_id ? '#10b981' : activeCfg.accent }}>
                                        {active.id === proposal.selected_variation_id
                                            ? <><CheckCircle2 size={16} /> Selected</>
                                            : `Select ${activeCfg.name}`}
                                    </button>
                                </div>
                            </main>
                        ) : (
                            <main className="flex-1 flex items-center justify-center">
                                <div className="text-center text-slate-400">
                                    <AlertCircle size={36} className="mx-auto mb-3 opacity-30" />
                                    <p className="text-sm">No proposals generated.</p>
                                </div>
                            </main>
                        )}
                    </div>
                )}

            </div>

            {chatVariation && <ChatPanel variation={chatVariation} onClose={() => setChatVariation(null)} onHistoryUpdate={handleHistoryUpdate} />}

            {/* Modals */}
            <DiagramModal isOpen={isDiagramOpen} onClose={() => setIsDiagramOpen(false)} chart="" />
            <ApprovalModal
                isOpen={isApproveOpen} onClose={() => setIsApproveOpen(false)}
                onConfirm={async () => { if (selectedVar) await handleSelectVariation(selectedVar.id); setIsApproveOpen(false); }}
                personaName={selectedVar?.agent_persona ?? 'Strategy'} isOverwriting={false} />
            <ConfirmModal
                isOpen={confirmState.isOpen} title={confirmState.title} message={confirmState.message}
                type={confirmState.type}
                onClose={() => setConfirmState(s => ({ ...s, isOpen: false }))}
                onConfirm={() => { confirmState.onConfirm(); setConfirmState(s => ({ ...s, isOpen: false })); }} />
        </>
    );
};

export default ProposalDetailPage;