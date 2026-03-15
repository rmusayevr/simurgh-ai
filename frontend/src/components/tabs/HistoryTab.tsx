import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { Clock, Zap, Shield, Cpu, Trophy, ExternalLink, ScrollText } from 'lucide-react';
import type { ProposalListItem } from '../../types';

interface HistoryTabProps {
    history: ProposalListItem[];
}

export const HistoryTab: React.FC<HistoryTabProps> = ({ history }) => {
    const navigate = useNavigate();
    const { id: projectId } = useParams<{ id: string }>();
    const location = useLocation();
    const locationState = location.state as { highlightId?: number } | null;
    const highlightId: number | undefined = locationState?.highlightId;

    const [flashId, setFlashId] = useState<number | undefined>(highlightId);
    useEffect(() => {
        if (!highlightId) return;
        const t = setTimeout(() => setFlashId(undefined), 3000);
        const s = setTimeout(() => {
            document.getElementById(`history-card-${highlightId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
        return () => { clearTimeout(t); clearTimeout(s); };
    }, [highlightId]);

    const handleOpen = (proposal: ProposalListItem) => {
        navigate(`/project/${projectId}/proposal/${proposal.id}`);
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 animate-in fade-in slide-in-from-right-4 duration-300">

            {/* --- SIDEBAR LIST --- */}
            <div className="lg:col-span-3 h-[calc(100vh-150px)] min-h-[500px] bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
                <div className="p-4 border-b border-slate-100 bg-slate-50 font-bold text-slate-700 flex items-center gap-2">
                    <Clock size={16} /> Session Log
                </div>
                <div className="overflow-y-auto flex-1 p-2 space-y-2">
                    {history.length === 0 && (
                        <p className="text-center text-slate-400 text-sm p-8">No completed sessions.</p>
                    )}
                    {history.map(h => {
                        const hasWinner = !!h.selected_variation_id;
                        const isFlashing = flashId === h.id;

                        return (
                            <div
                                key={h.id}
                                onClick={() => handleOpen(h)}
                                className={`p-3 rounded-xl border cursor-pointer transition-all relative overflow-hidden group
                                    ${isFlashing
                                        ? 'ring-2 ring-emerald-400 ring-offset-1 bg-emerald-50/60 border-emerald-300'
                                        : hasWinner
                                            ? 'bg-emerald-50/30 border-emerald-100 hover:border-emerald-300'
                                            : 'bg-white border-transparent hover:bg-slate-50 hover:border-slate-100'
                                    }`}
                            >
                                {/* Green stripe for winners */}
                                {hasWinner && <div className="absolute left-0 top-0 bottom-0 w-1 bg-emerald-400" />}

                                <div className="flex justify-between items-start mb-1 pl-2">
                                    <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">
                                        #{h.id}
                                    </span>
                                    <span className="text-[10px] text-slate-400">
                                        {new Date(h.created_at).toLocaleDateString()}
                                    </span>
                                </div>
                                <p className="text-xs font-medium line-clamp-2 pl-2 text-slate-600 group-hover:text-slate-900">
                                    {h.task_description}
                                </p>

                                {hasWinner && (
                                    <div className="flex items-center gap-1 mt-2 pl-2 text-[10px] font-bold text-emerald-600">
                                        <Trophy size={10} /> Decision Made
                                    </div>
                                )}

                                <div className="absolute right-2 bottom-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <ExternalLink size={12} className="text-slate-400" />
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* --- MAIN CONTENT (info panel) --- */}
            <div className="lg:col-span-9">
                {history.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-300 border-2 border-dashed border-slate-200 rounded-3xl min-h-[500px]">
                        <ScrollText size={64} className="mb-4 opacity-20" />
                        <p>No completed sessions yet.</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {history.map(h => {
                            const hasWinner = !!h.selected_variation_id;
                            const variationCount = h.variation_count ?? 0;
                            const isFlashing = flashId === h.id;

                            return (
                                <div
                                    id={`history-card-${h.id}`}
                                    key={h.id}
                                    onClick={() => handleOpen(h)}
                                    className={`bg-white p-6 rounded-2xl border cursor-pointer transition-all group hover:shadow-md relative overflow-hidden
                                        ${isFlashing
                                            ? 'ring-2 ring-emerald-400 ring-offset-2 border-emerald-300 shadow-emerald-100 shadow-lg'
                                            : hasWinner
                                                ? 'border-emerald-200 hover:border-emerald-400'
                                                : 'border-slate-200 hover:border-cyan-300'
                                        }`}
                                >
                                    {hasWinner && (
                                        <div className="absolute top-0 right-0 bg-emerald-500 text-white text-[10px] font-black px-3 py-1 rounded-bl-xl flex items-center gap-1">
                                            <Trophy size={10} className="text-yellow-300" /> Decision Made
                                        </div>
                                    )}

                                    <div className="flex items-start gap-3 mb-3">
                                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0
                                            ${hasWinner ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-500'}`}>
                                            <Cpu size={20} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs text-slate-400 mb-1">Session #{h.id}</p>
                                            <p className="text-sm font-bold text-slate-800 line-clamp-2 group-hover:text-cyan-700 transition-colors">
                                                {h.task_description}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Variation badges */}
                                    <div className="flex items-center gap-2 mb-3">
                                        {variationCount > 0 ? (
                                            <>
                                                <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 bg-amber-50 text-amber-700 rounded-full border border-amber-100">
                                                    <Shield size={10} /> Legacy Keeper
                                                </span>
                                                <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 bg-purple-50 text-purple-700 rounded-full border border-purple-100">
                                                    <Zap size={10} /> Innovator
                                                </span>
                                                <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-100">
                                                    <Cpu size={10} /> Mediator
                                                </span>
                                            </>
                                        ) : (
                                            <span className="text-[10px] text-slate-400">No variations</span>
                                        )}
                                    </div>

                                    <div className="flex items-center justify-between text-xs text-slate-400">
                                        <span>{new Date(h.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                                        <span className="font-bold text-cyan-500 group-hover:text-cyan-700 flex items-center gap-1 transition-colors">
                                            View Proposals <ExternalLink size={12} />
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};