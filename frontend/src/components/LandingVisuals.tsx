import { MoreHorizontal, ArrowUpRight, Search, BrainCircuit, ShieldCheck, Terminal, Sparkles, Activity, Users } from 'lucide-react';

export const DashboardMockup = () => {
    return (
        <div className="rounded-3xl bg-white border border-slate-200 overflow-hidden shadow-[0_32px_64px_-16px_rgba(79,70,229,0.15)] animate-in fade-in zoom-in-95 duration-1000">
            {/* --- Browser-style Header --- */}
            <div className="border-b border-slate-100 p-4 flex items-center justify-between bg-white/80 backdrop-blur-md sticky top-0 z-10">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5 mr-6">
                        <div className="w-3 h-3 rounded-full bg-red-400/20"></div>
                        <div className="w-3 h-3 rounded-full bg-amber-400/20"></div>
                        <div className="w-3 h-3 rounded-full bg-emerald-400/20"></div>
                    </div>
                    <div className="flex items-center gap-2 bg-slate-50 px-4 py-2 rounded-xl text-[11px] text-slate-400 w-80 border border-slate-100 font-mono">
                        <Search size={12} className="opacity-50" />
                        <span>app.simurgh.ai/project/alpha-nexus</span>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-purple-500 ring-2 ring-slate-100 shadow-sm"></div>
                </div>
            </div>

            <div className="flex h-[520px]">
                {/* --- Sidebar: High-Fidelity Match --- */}
                <div className="w-20 bg-slate-950 border-r border-slate-800 flex flex-col items-center py-8 gap-6">
                    <div className="w-10 h-10 rounded-xl bg-cyan-600 flex items-center justify-center text-white shadow-xl shadow-cyan-500/40 ring-1 ring-white/20">
                        <BrainCircuit size={20} />
                    </div>

                    {/* Nav Item Mockups */}
                    {[1, 2, 3].map((i) => (
                        <div key={i} className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${i === 1 ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-600'}`}>
                            <div className={`w-5 h-5 rounded ${i === 1 ? 'bg-cyan-400/30' : 'bg-current opacity-20'}`}></div>
                        </div>
                    ))}

                    {/* Admin Shield - Just like your sidebar */}
                    <div className="mt-auto mb-2 w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500">
                        <ShieldCheck size={20} />
                    </div>
                </div>

                {/* --- Main Content Area --- */}
                <div className="flex-1 flex flex-col bg-slate-50/50 relative">

                    {/* Dashboard Header */}
                    <div className="p-8 pb-4 flex justify-between items-end">
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Active Simulation</span>
                            </div>
                            <h2 className="text-2xl font-black text-slate-900 tracking-tight">Project Alpha Nexus</h2>
                        </div>
                        <div className="flex gap-3">
                            <div className="h-11 px-5 rounded-2xl bg-cyan-600 shadow-xl shadow-cyan-500/20 flex items-center gap-3 transition-transform hover:scale-105 cursor-pointer">
                                <Sparkles size={16} className="text-white" />
                                <span className="text-xs font-bold text-white">Generate Strategy</span>
                            </div>
                        </div>
                    </div>

                    <div className="p-8 grid grid-cols-12 gap-6 flex-1">

                        {/* Left: Project Health Matrix (3-column style) */}
                        <div className="col-span-8 space-y-6">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-white p-5 rounded-3xl border border-slate-200/60 shadow-sm">
                                    <div className="flex justify-between items-start mb-4">
                                        <div className="p-2 bg-emerald-50 text-emerald-600 rounded-xl"><Activity size={18} /></div>
                                        <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">+12%</span>
                                    </div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Consensus Score</p>
                                    <p className="text-2xl font-black text-slate-900">84%</p>
                                </div>
                                <div className="bg-white p-5 rounded-3xl border border-slate-200/60 shadow-sm">
                                    <div className="flex justify-between items-start mb-4">
                                        <div className="p-2 bg-red-50 text-red-600 rounded-xl"><Users size={18} /></div>
                                        <span className="text-[10px] font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">Risk</span>
                                    </div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Stakeholder Friction</p>
                                    <p className="text-2xl font-black text-slate-900">High</p>
                                </div>
                            </div>

                            {/* Main Analysis Chart Area */}
                            <div className="bg-white rounded-3xl border border-slate-200/60 p-6 shadow-sm flex-1 min-h-[180px]">
                                <div className="flex justify-between items-center mb-6">
                                    <div className="flex items-center gap-2">
                                        <Terminal size={14} className="text-slate-400" />
                                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Sentiment Heatmap</span>
                                    </div>
                                    <MoreHorizontal size={16} className="text-slate-300" />
                                </div>
                                <div className="flex items-end justify-between gap-4 h-24">
                                    {[40, 75, 50, 95, 65, 85, 45, 90, 60].map((h, i) => (
                                        <div key={i} className="flex-1 bg-slate-50 rounded-full h-full relative overflow-hidden">
                                            <div
                                                className={`absolute bottom-0 w-full transition-all duration-1000 ${h > 80 ? 'bg-cyan-500' : h > 50 ? 'bg-cyan-400/60' : 'bg-cyan-200'}`}
                                                style={{ height: `${h}%` }}
                                            ></div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Right: AI Persona Stack */}
                        <div className="col-span-4 flex flex-col gap-4">
                            <div className="bg-white rounded-3xl border border-slate-200/60 p-6 shadow-sm flex-1">
                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-6">Agent Personas</span>
                                <div className="space-y-6">
                                    {[
                                        { color: 'bg-emerald-500', name: 'The Mediator', status: 'Stable' },
                                        { color: 'bg-amber-500', name: 'The Innovator', status: 'Conflict' },
                                        { color: 'bg-cyan-500', name: 'The Legacy', status: 'Aligned' }
                                    ].map((persona, i) => (
                                        <div key={i} className="flex items-center gap-3">
                                            <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-white shadow-lg ${persona.color}`}>
                                                <BrainCircuit size={16} />
                                            </div>
                                            <div className="flex-1">
                                                <div className="h-3 w-20 bg-slate-900 rounded-full mb-1"></div>
                                                <div className="h-2 w-10 bg-slate-100 rounded-full"></div>
                                            </div>
                                            <div className={`text-[8px] font-black px-2 py-0.5 rounded-md ${persona.status === 'Conflict' ? 'bg-red-50 text-red-600' : 'bg-slate-50 text-slate-500'}`}>
                                                {persona.status}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Mini System Health */}
                            <div className="bg-slate-950 rounded-2xl p-4 flex items-center justify-between border border-slate-800 shadow-xl">
                                <div className="flex items-center gap-3">
                                    <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.8)] animate-pulse"></div>
                                    <div className="h-2 w-16 bg-slate-700 rounded-full"></div>
                                </div>
                                <ArrowUpRight size={14} className="text-slate-500" />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};