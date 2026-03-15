import { useEffect, useState } from 'react';
import {
    Zap, Trash2, RotateCcw, CheckCircle,
    Clock, AlertTriangle, Loader2
} from 'lucide-react';
import { adminApi } from '../../api/client';
import { ConfirmModal } from '../modals/ConfirmModal';

export const AdminMissions = () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [proposals, setProposals] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    const [modalConfig, setModalConfig] = useState<{
        isOpen: boolean;
        title: string;
        message: string;
        type: 'danger' | 'info';
        onConfirm: () => void;
    }>({
        isOpen: false,
        title: '',
        message: '',
        type: 'info',
        onConfirm: () => { },
    });

    const loadProposals = async () => {
        setLoading(true);
        try {
            const res = await adminApi.getProposals();
            setProposals(res.data);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadProposals(); }, []);

    const triggerReset = (id: number) => {
        setModalConfig({
            isOpen: true,
            title: "Reset Mission Status?",
            message: "This will move the mission back to DRAFT status so it can be re-executed. Current AI variations will be preserved.",
            type: 'info',
            onConfirm: async () => {
                await adminApi.updateProposalStatus(id, 'DRAFT');
                setModalConfig(prev => ({ ...prev, isOpen: false }));
                loadProposals();
            }
        });
    };

    const triggerDelete = (id: number) => {
        setModalConfig({
            isOpen: true,
            title: "Delete Mission Permanently?",
            message: "Warning: This will delete the mission, all uploaded documents, and all AI variations. This cannot be undone.",
            type: 'danger',
            onConfirm: async () => {
                await adminApi.deleteProposal(id);
                setModalConfig(prev => ({ ...prev, isOpen: false }));
                setProposals(prev => prev.filter(p => p.id !== id));
            }
        });
    };

    if (loading) return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-cyan-600" size={32} /></div>;

    return (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm animate-in fade-in duration-500">
            <div className="p-4 border-b border-slate-100 flex items-center gap-2">
                <Zap className="text-amber-500" size={20} />
                <h2 className="font-bold text-slate-800">System Missions Explorer</h2>
            </div>

            <table className="w-full text-left border-collapse">
                <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                        <th className="p-4 text-xs font-black text-slate-400 uppercase">Project / Owner</th>
                        <th className="p-4 text-xs font-black text-slate-400 uppercase text-center">Status</th>
                        <th className="p-4 text-xs font-black text-slate-400 uppercase text-right">Control</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                    {proposals.length === 0 ? (
                        <tr><td colSpan={3} className="p-8 text-center text-slate-400 italic">No missions found.</td></tr>
                    ) : (
                        proposals.map(p => (
                            <tr key={p.id} className="hover:bg-slate-50/50 transition-colors group">
                                <td className="p-4">
                                    <p className="font-bold text-slate-800">{p.project_name}</p>
                                    <p className="text-xs text-slate-500 truncate max-w-[200px]">{p.task_description}</p>
                                </td>
                                <td className="p-4">
                                    <div className="flex justify-center">
                                        <StatusBadge status={p.status} />
                                    </div>
                                </td>
                                <td className="p-4 text-right">
                                    <div className="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={() => triggerReset(p.id)}
                                            className="p-2 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                                            title="Reset to Draft"
                                        >
                                            <RotateCcw size={16} />
                                        </button>
                                        <button
                                            onClick={() => triggerDelete(p.id)}
                                            className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                            title="Permanent Delete"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))
                    )}
                </tbody>
            </table>

            <ConfirmModal
                isOpen={modalConfig.isOpen}
                title={modalConfig.title}
                message={modalConfig.message}
                type={modalConfig.type}
                onClose={() => setModalConfig(prev => ({ ...prev, isOpen: false }))}
                onConfirm={modalConfig.onConfirm}
            />
        </div>
    );
};

const StatusBadge = ({ status }: { status: string }) => {
    const s = status.toLowerCase();
    if (s === 'COMPLETED') return <span className="flex items-center gap-1 text-emerald-600 text-[10px] font-bold uppercase"><CheckCircle size={12} /> Success</span>;
    if (s === 'PROCESSING') return <span className="flex items-center gap-1 text-blue-600 text-[10px] font-bold uppercase"><Clock size={12} /> Active</span>;
    if (s === 'FAILED') return <span className="flex items-center gap-1 text-red-600 text-[10px] font-bold uppercase"><AlertTriangle size={12} /> Error</span>;
    return <span className="text-slate-400 text-[10px] font-bold uppercase tracking-widest">{status}</span>;
};