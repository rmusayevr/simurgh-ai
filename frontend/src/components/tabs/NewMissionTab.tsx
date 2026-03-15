import React from 'react';
import { PlusCircle, Loader2, Zap } from 'lucide-react';

interface NewMissionTabProps {
    task: string;
    setTask: (task: string) => void;
    handleCreateDraft: () => void;
    loading: boolean;
}

export const NewMissionTab: React.FC<NewMissionTabProps> = ({
    task, setTask, handleCreateDraft, loading
}) => {
    return (
        <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-300">
            <div className="bg-white p-10 rounded-3xl border border-slate-200 shadow-xl">
                <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <PlusCircle size={32} />
                    </div>
                    <h2 className="text-2xl font-bold text-slate-900">New Debate Session</h2>
                    <p className="text-slate-500 mt-2">Define the architectural objective to open a session workspace.</p>
                </div>

                <div className="space-y-6">
                    <div>
                        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                            Session Objective
                        </label>
                        <textarea
                            className="w-full px-5 py-4 text-lg rounded-2xl border border-slate-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none h-48 resize-none bg-slate-50 focus:bg-white transition"
                            placeholder="e.g. We need to migrate our legacy monolith to microservices..."
                            value={task}
                            onChange={(e) => setTask(e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    <button
                        onClick={handleCreateDraft}
                        disabled={loading || !task}
                        className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold text-lg flex justify-center items-center gap-2 hover:bg-black hover:scale-[1.01] transition-all shadow-lg disabled:opacity-50 disabled:scale-100"
                    >
                        {loading ? <Loader2 className="animate-spin" /> : <Zap fill="currentColor" />}
                        Create Session Workspace
                    </button>
                </div>
            </div>
        </div>
    );
};