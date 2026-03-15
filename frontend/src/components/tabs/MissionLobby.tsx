import React from 'react';
import { Plus, Clock, ArrowRight } from 'lucide-react';
import type { Proposal } from '../../types';

interface MissionLobbyProps {
    missions: Proposal[];
    onSelect: (mission: Proposal) => void;
    onCreateNew: () => void;
    canCreate: boolean;
}

export const MissionLobby: React.FC<MissionLobbyProps> = ({ missions, onSelect, onCreateNew, canCreate }) => {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900">Session Control</h2>
                    <p className="text-slate-500">Select an active session to enter the Debate Workspace.</p>
                </div>

                {canCreate && (
                    <button
                        onClick={onCreateNew}
                        className="bg-slate-900 hover:bg-black text-white px-5 py-2.5 rounded-xl font-bold flex items-center gap-2 shadow-lg hover:shadow-xl transition-all"
                    >
                        <Plus size={18} /> New Session
                    </button>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Active Cards */}
                {missions.map(mission => (
                    <div
                        key={mission.id}
                        onClick={() => onSelect(mission)}
                        className="group bg-white p-6 rounded-2xl border border-slate-200 hover:border-blue-400 hover:shadow-md cursor-pointer transition-all relative overflow-hidden"
                    >
                        <div className="flex justify-between items-start mb-4">
                            <span className={`px-2 py-1 text-[10px] font-bold uppercase tracking-wider rounded border ${mission.status === 'PROCESSING'
                                ? 'bg-amber-50 text-amber-600 border-amber-100'
                                : 'bg-slate-100 text-slate-500 border-slate-200'
                                }`}>
                                {mission.status}
                            </span>
                            <span className="text-xs text-slate-400 flex items-center gap-1">
                                <Clock size={12} /> {new Date(mission.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </span>
                        </div>

                        <h3 className="font-bold text-slate-800 text-lg mb-2 line-clamp-2 group-hover:text-blue-600 transition-colors">
                            {mission.task_description}
                        </h3>

                        <div className="flex items-center gap-2 mt-4 text-sm font-bold text-slate-400 group-hover:text-blue-500">
                            Enter Debate Workspace <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                        </div>

                        {/* Processing Animation Overlay */}
                        {mission.status === 'PROCESSING' && (
                            <div className="absolute top-0 right-0 p-3">
                                <span className="relative flex h-3 w-3">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
                                </span>
                            </div>
                        )}
                    </div>
                ))}

                {/* Empty State */}
                {missions.length === 0 && (
                    <div className="col-span-full py-12 text-center bg-slate-50 rounded-2xl border-2 border-dashed border-slate-200 text-slate-400">
                        <p>No active sessions.</p>
                        {canCreate && <p className="text-sm">Start a new one above.</p>}
                    </div>
                )}
            </div>
        </div>
    );
};