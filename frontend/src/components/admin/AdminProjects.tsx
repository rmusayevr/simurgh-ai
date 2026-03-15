import { useEffect, useState } from 'react';
import { Trash2, Search, Loader2, ExternalLink } from 'lucide-react';
import { adminApi } from '../../api/client';
import { ConfirmModal } from '../modals/ConfirmModal';
import { useNavigate } from 'react-router-dom';
import type { AdminProject } from '../../types';


export const AdminProjects = () => {
    const [projects, setProjects] = useState<AdminProject[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const navigate = useNavigate();


    const [confirmConfig, setConfirmConfig] = useState<{
        isOpen: boolean; title: string; message: string; type: 'danger' | 'info'; onConfirm: () => void;
    }>({ isOpen: false, title: '', message: '', type: 'info', onConfirm: () => { } });

    const fetchProjects = async () => {
        try {
            const res = await adminApi.getProjects();
            setProjects(res.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchProjects(); }, []);

    const handleDeleteClick = (project: AdminProject) => {
        setConfirmConfig({
            isOpen: true,
            title: "Purge Project?",
            message: `Danger: You are about to delete "${project.name}". This will wipe the database records, all associated missions, and all uploaded documents.`,
            type: 'danger',
            onConfirm: () => executeDelete(project.id)
        });
    };

    const executeDelete = async (id: number) => {
        try {
            await adminApi.deleteProject(id);
            setProjects(prev => prev.filter(p => p.id !== id));
            setConfirmConfig(prev => ({ ...prev, isOpen: false }));
        } catch {
            alert("Failed to delete project");
        }
    };

    const filtered = projects.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.owner_email.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (loading) return (
        <div className="flex items-center justify-center py-20 gap-3 text-slate-400">
            <Loader2 className="animate-spin text-cyan-500" />
            <span className="font-bold uppercase text-xs tracking-widest">Scanning Projects...</span>
        </div>
    );

    return (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden animate-in fade-in">
            {/* Header */}
            <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                <div>
                    <h3 className="font-bold text-slate-800 text-lg">Global Inventory</h3>
                    <p className="text-[10px] text-slate-400 font-black uppercase tracking-tighter">Active Project Clusters: {projects.length}</p>
                </div>
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                    <input
                        type="text"
                        placeholder="Search projects..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="pl-9 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-cyan-500 outline-none w-72 bg-white shadow-sm transition-all"
                    />
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 text-slate-400 uppercase text-[10px] font-black tracking-widest border-b border-slate-100">
                        <tr>
                            <th className="px-6 py-4">Project Architecture</th>
                            <th className="px-6 py-4">Stakeholder Email</th>
                            <th className="px-6 py-4 text-center">Payload</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {filtered.map((p) => (
                            <tr key={p.id} className="hover:bg-slate-50/80 transition-all group">
                                <td className="px-6 py-4">
                                    <div className="font-bold text-slate-900 group-hover:text-cyan-600 transition-colors">{p.name}</div>
                                    <div className="text-[10px] text-slate-400 truncate max-w-[200px] font-medium">{p.description || "No metadata provided"}</div>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="flex items-center gap-2">
                                        <div className="w-6 h-6 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-[10px] font-black text-slate-500">
                                            {p.owner_email.charAt(0).toUpperCase()}
                                        </div>
                                        <span className="text-slate-600 font-medium">{p.owner_email}</span>
                                    </div>
                                </td>
                                <td className="px-12 py-6 text-right">
                                    <div className="flex justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        {/* View Button */}
                                        <button
                                            onClick={() => navigate(`/project/${p.id}`)}
                                            className="p-2 text-slate-400 hover:text-cyan-600 hover:bg-cyan-50 rounded-lg transition-colors"
                                            title="External Link"
                                        >
                                            <ExternalLink size={18} />
                                        </button>

                                        {/* Delete Button */}
                                        <button
                                            onClick={() => handleDeleteClick(p)}
                                            className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                            title="Terminate"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* --- MODALS --- */}
            <ConfirmModal
                isOpen={confirmConfig.isOpen}
                title={confirmConfig.title}
                message={confirmConfig.message}
                type={confirmConfig.type}
                onClose={() => setConfirmConfig(prev => ({ ...prev, isOpen: false }))}
                onConfirm={confirmConfig.onConfirm}
            />
        </div>
    );
};