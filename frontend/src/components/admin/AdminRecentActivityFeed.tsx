import React from 'react';
import { History } from 'lucide-react';

interface ActivityFeedProps {
    activities: Array<{
        proposal_id: number;
        user_email: string;
        project_name: string;
        task_preview: string;
        status: string;
        created_at: string;
    }>;
    totalMissions?: number;
}

export const AdminRecentActivityFeed: React.FC<ActivityFeedProps> = ({ activities, totalMissions }) => {
    return (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div className="flex items-center gap-2">
                    <History size={18} className="text-slate-400" />
                    <h3 className="font-bold text-slate-800">Recent System Activity</h3>
                </div>
                <div className="flex items-center gap-2">
                    {totalMissions !== undefined && (
                        <span className="text-xs text-slate-500 font-bold bg-slate-100 px-2 py-1 rounded">
                            {totalMissions} Total Missions
                        </span>
                    )}
                    <span className="text-xs text-slate-400 font-black tracking-widest uppercase ml-2 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
                        Live Feed
                    </span>
                </div>
            </div>

            <div className="divide-y divide-slate-100">
                {activities && activities.length > 0 ? (
                    activities.map((act) => (
                        <div key={act.proposal_id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                            <div className="flex items-center gap-4">
                                <div className={`w-2 h-2 rounded-full ${act.status === 'COMPLETED' ? 'bg-emerald-400' :
                                    act.status === 'PROCESSING' ? 'bg-blue-400 animate-pulse' : 'bg-red-400'
                                    }`} />
                                <div>
                                    <p className="text-sm font-bold text-slate-700">{act.user_email}</p>
                                    <p className="text-xs text-slate-500 italic">
                                        "{act.task_preview}" <span className="text-slate-400 ml-1">({act.project_name})</span>
                                    </p>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="text-[10px] font-bold text-slate-400 uppercase">
                                    {new Date(act.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </p>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="p-8 text-center text-slate-400 italic">
                        No recent activity detected on the server.
                    </div>
                )}
            </div>
        </div>
    );
};