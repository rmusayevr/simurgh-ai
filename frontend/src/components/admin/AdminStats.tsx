import React from 'react';
import {
    Users, FolderGit2, AlertTriangle, Activity, Database
} from 'lucide-react';

interface AdminStatsProps {
    stats: {
        status: string;
        timestamp: string;
        counts: {
            users: number;
            projects: number;
            proposals: number;
            processing_proposals: number;
        };
        queue: {
            pending_tasks: number;
        };
        workers: {
            online: number;
        };
    } | null;
    workerStatus: 'online' | 'offline' | 'loading' | 'error';
}

export const AdminStats: React.FC<AdminStatsProps> = ({ stats, workerStatus }) => {
    if (!stats) return <div className="p-8 text-slate-400 italic animate-pulse">Loading diagnostics...</div>;

    const isOptimal = stats.status === 'healthy';

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">System Overview</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* User Stat */}
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Total Users</p>
                        <p className="text-3xl font-black text-slate-900 mt-1">{stats.counts.users}</p>
                    </div>
                    <div className="p-3 bg-cyan-50 text-cyan-600 rounded-xl"><Users size={24} /></div>
                </div>

                {/* Projects Stat */}
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Active Projects</p>
                        <p className="text-3xl font-black text-slate-900 mt-1">{stats.counts.projects}</p>
                    </div>
                    <div className="p-3 bg-blue-50 text-blue-600 rounded-xl"><FolderGit2 size={24} /></div>
                </div>

                {/* AI ENGINE (Worker Status & Queue) */}
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">AI Engine</p>
                        <div className="flex items-center gap-2 mt-1">
                            <p className={`text-2xl font-black capitalize ${workerStatus === 'online' ? 'text-slate-900' : 'text-red-600'}`}>
                                {workerStatus}
                            </p>
                            {stats.queue.pending_tasks > 0 && (
                                <span className="bg-amber-100 text-amber-700 text-[10px] px-2 py-0.5 rounded-full font-bold animate-pulse">
                                    {stats.queue.pending_tasks} WAIT
                                </span>
                            )}
                            {stats.queue.pending_tasks === -1 && (
                                <span className="bg-red-100 text-red-600 text-[10px] px-2 py-0.5 rounded-full font-bold">
                                    REDIS ERR
                                </span>
                            )}
                        </div>
                    </div>
                    <div className={`p-3 rounded-xl text-white ${workerStatus === 'online' ? 'bg-emerald-500 shadow-lg shadow-emerald-200' : 'bg-red-500'}`}>
                        <Activity size={24} className={workerStatus === 'online' ? 'animate-pulse' : ''} />
                    </div>
                </div>

                {/* System Health */}
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">Database Health</p>
                        <div className="flex items-center gap-2 mt-1">
                            <span className="relative flex h-3 w-3">
                                <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${isOptimal ? 'animate-ping bg-green-400' : 'bg-amber-400'}`}></span>
                                <span className={`relative inline-flex rounded-full h-3 w-3 ${isOptimal ? 'bg-green-500' : 'bg-amber-500'}`}></span>
                            </span>
                            <span className={`text-sm font-bold uppercase ${isOptimal ? 'text-green-600' : 'text-amber-600'}`}>
                                {stats.status}
                            </span>
                        </div>
                    </div>
                    <div className="p-3 bg-slate-50 text-slate-600 rounded-xl"><Database size={24} /></div>
                </div>
            </div>

            {/* Warning for stuck missions */}
            {stats.counts.processing_proposals > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3 text-amber-800 animate-pulse">
                    <AlertTriangle className="text-amber-600" />
                    <span className="font-medium">
                        Attention: {stats.counts.processing_proposals} missions are currently processing or stuck.
                    </span>
                </div>
            )}
        </div>
    );
};