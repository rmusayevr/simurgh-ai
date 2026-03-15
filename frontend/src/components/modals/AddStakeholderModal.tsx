import React, { useState, useEffect } from 'react';
import { X, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import { InfluenceLevel, InterestLevel, Sentiment } from '../../types';
import type { Stakeholder } from '../../types'
import { HintTooltip } from '../onboarding/HintTooltip';

interface Props {
    projectId: string;
    isOpen: boolean;
    onClose: () => void;
    onSuccess: (stakeholder: Stakeholder) => void;
    initialData?: Stakeholder | null;
}

interface FormData {
    name: string;
    role: string;
    department: string;
    influence: InfluenceLevel;
    interest: InterestLevel;
    sentiment: Sentiment;
}

export const AddStakeholderModal = ({ projectId, isOpen, onClose, onSuccess, initialData }: Props) => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [formData, setFormData] = useState<FormData>({
        name: '',
        role: '',
        department: '',
        influence: InfluenceLevel.MEDIUM,
        interest: InterestLevel.MEDIUM,
        sentiment: Sentiment.NEUTRAL
    });

    useEffect(() => {
        if (initialData) {
            setFormData({
                name: initialData.name,
                role: initialData.role,
                department: initialData.department || '',
                influence: initialData.influence,
                interest: initialData.interest,
                sentiment: initialData.sentiment
            });
        } else {
            setFormData({
                name: '',
                role: '',
                department: '',
                influence: InfluenceLevel.MEDIUM,
                interest: InterestLevel.MEDIUM,
                sentiment: Sentiment.NEUTRAL
            });
        }
        setError(null);
    }, [initialData, isOpen]);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            let res;
            if (initialData) {
                // EDIT MODE
                res = await api.patch<Stakeholder>(`/stakeholders/${initialData.id}`, formData);
            } else {
                // CREATE MODE
                res = await api.post<Stakeholder>(`/stakeholders/project/${projectId}`, formData);
            }
            onSuccess(res.data);
            onClose();
        } catch (err: unknown) {
            console.error("Failed to save stakeholder", err);
            const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                ?? 'Failed to save stakeholder. Please try again.';
            setError(typeof message === 'string' ? message : JSON.stringify(message));
        } finally {
            setLoading(false);
        }
    };


    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg overflow-hidden animate-in zoom-in-95">
                <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
                    <h3 className="font-bold text-slate-800">
                        {initialData ? 'Edit Stakeholder' : 'Add Stakeholder'}
                    </h3>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    {error && (
                        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
                            {error}
                        </div>
                    )}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="col-span-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">Name</label>
                            <input
                                required className="w-full mt-1 px-3 py-2 border rounded-lg"
                                placeholder="e.g. Sarah Connor"
                                value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase">Role</label>
                            <input
                                required className="w-full mt-1 px-3 py-2 border rounded-lg"
                                placeholder="e.g. CTO"
                                value={formData.role} onChange={e => setFormData({ ...formData, role: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase">Department</label>
                            <input
                                className="w-full mt-1 px-3 py-2 border rounded-lg"
                                placeholder="e.g. Engineering"
                                value={formData.department} onChange={e => setFormData({ ...formData, department: e.target.value })}
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1">
                                Influence
                                <HintTooltip title="Organisational power" text="How much authority this person has to approve, block, or redirect the project. HIGH = executive or budget owner." />
                            </label>
                            <select
                                className="w-full mt-1 px-2 py-2 border rounded-lg bg-white"
                                value={formData.influence}
                                onChange={e => setFormData({ ...formData, influence: e.target.value as InfluenceLevel })}
                            >
                                {Object.values(InfluenceLevel).map(v => (
                                    <option key={v} value={v}>{v.charAt(0) + v.slice(1).toLowerCase()}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1">
                                Interest
                                <HintTooltip title="Stake in the outcome" text="How much this person cares about this specific project. HIGH = directly affected by the outcome." />
                            </label>
                            <select
                                className="w-full mt-1 px-2 py-2 border rounded-lg bg-white"
                                value={formData.interest}
                                onChange={e => setFormData({ ...formData, interest: e.target.value as InterestLevel })}
                            >
                                {Object.values(InterestLevel).map(v => (
                                    <option key={v} value={v}>{v.charAt(0) + v.slice(1).toLowerCase()}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1">
                                Sentiment
                                <HintTooltip title="Current disposition" text="Champion = actively sponsors. Supportive = will vote yes. Neutral = no opinion. Concerned = has doubts. Resistant = pushing back. Blocker = high-influence opponent." side="left" />
                            </label>
                            <select
                                className="w-full mt-1 px-2 py-2 border rounded-lg bg-white"
                                value={formData.sentiment}
                                onChange={e => setFormData({ ...formData, sentiment: e.target.value as Sentiment })}
                            >
                                {Object.values(Sentiment).map(v => (
                                    <option key={v} value={v}>{v.charAt(0) + v.slice(1).toLowerCase()}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="pt-4 flex justify-end gap-2">
                        <button type="button" onClick={onClose} className="px-4 py-2 text-slate-600 font-bold hover:bg-slate-100 rounded-lg">Cancel</button>
                        <button
                            type="submit" disabled={loading}
                            className="px-6 py-2 bg-cyan-600 text-white font-bold rounded-lg hover:bg-cyan-700 flex items-center gap-2"
                        >
                            {loading ? <Loader2 size={16} className="animate-spin" /> : (initialData ? 'Save Changes' : 'Add Person')}
                        </button>
                    </div>
                </form>
            </div >
        </div >
    );
};