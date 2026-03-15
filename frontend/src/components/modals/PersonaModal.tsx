import React, { useState, useEffect, useCallback } from 'react';
import { X, Sparkles, Loader2, Save } from 'lucide-react';

interface PersonaModalProps {
    isOpen: boolean;
    mode: 'create' | 'edit';
    initialData?: { id?: number; name: string; slug: string; system_prompt: string; is_active: boolean };
    isSaving: boolean;
    onClose: () => void;
    onSave: (data: { name: string; slug: string; system_prompt: string; is_active: boolean }) => Promise<void>;
}

export const PersonaModal: React.FC<PersonaModalProps> = ({
    isOpen,
    mode,
    initialData,
    isSaving,
    onClose,
    onSave
}) => {
    const getInitialData = useCallback(() => {
        if (initialData) {
            return {
                name: initialData.name,
                slug: initialData.slug,
                system_prompt: initialData.system_prompt,
                is_active: initialData.is_active
            };
        }
        return {
            name: '',
            slug: '',
            system_prompt: 'You are an AI expert specializing in...',
            is_active: true
        };
    }, [initialData]);

    const [formData, setFormData] = useState(getInitialData);

    /* eslint-disable react-hooks/set-state-in-effect */
    useEffect(() => {
        if (isOpen) {
            setFormData(getInitialData());
        }
    }, [isOpen, getInitialData]);
    /* eslint-enable react-hooks/set-state-in-effect */

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await onSave(formData);
        } catch {
            if (formData.is_active) {
                setFormData((prev: { name: string; slug: string; system_prompt: string; is_active: boolean }) => ({ ...prev, is_active: false }));
            }
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <h3 className="font-bold text-slate-800 flex items-center gap-2">
                        <Sparkles size={16} className="text-cyan-600" />
                        {mode === 'create' ? 'Create New Persona' : 'Edit Persona Details'}
                    </h3>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-4">
                    {/* Active Toggle */}
                    <div className="flex items-center justify-between bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <span className="text-sm font-bold text-slate-700">Status</span>
                        <button
                            type="button"
                            onClick={() => setFormData((prev: { name: string; slug: string; system_prompt: string; is_active: boolean }) => ({ ...prev, is_active: !prev.is_active }))}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${formData.is_active ? 'bg-emerald-500' : 'bg-slate-300'
                                }`}
                        >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${formData.is_active ? 'translate-x-6' : 'translate-x-1'
                                }`} />
                        </button>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Display Name</label>
                        <input
                            required
                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500 outline-none transition-all"
                            value={formData.name}
                            onChange={e => setFormData({ ...formData, name: e.target.value })}
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Slug (Unique ID)</label>
                        <input
                            required
                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono text-slate-600 bg-slate-50 focus:ring-2 focus:ring-cyan-500 outline-none transition-all"
                            value={formData.slug}
                            onChange={e => setFormData({ ...formData, slug: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
                        />
                    </div>

                    {mode === 'create' && (
                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Initial System Prompt</label>
                            <textarea
                                required
                                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm h-24 resize-none focus:ring-2 focus:ring-cyan-500 outline-none transition-all"
                                value={formData.system_prompt}
                                onChange={e => setFormData({ ...formData, system_prompt: e.target.value })}
                            />
                        </div>
                    )}

                    <div className="pt-2 flex gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-50 rounded-xl transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={isSaving}
                            className="flex-1 py-2.5 bg-cyan-600 text-white text-sm font-bold rounded-xl hover:bg-cyan-700 flex items-center justify-center gap-2 transition-colors"
                        >
                            {isSaving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                            {mode === 'create' ? 'Create Persona' : 'Save Changes'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};