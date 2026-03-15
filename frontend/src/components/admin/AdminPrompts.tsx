import { useState, useEffect, useCallback } from 'react';
import type { PromptTemplate } from '../../types';
import { Save, Loader2, Sparkles, Cpu, Wand2, Plus, Settings, Trash2 } from 'lucide-react';
import { ConfirmModal } from '../modals/ConfirmModal';
import { PersonaModal } from '../modals/PersonaModal';
import { AlertModal } from '../modals/AlertModal';
import { api } from '../../api/client';

export const AdminPrompts = () => {
    const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [localPrompt, setLocalPrompt] = useState("");

    const [isConfirmOpen, setIsConfirmOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<{ id: number, name: string } | null>(null);

    const [alertState, setAlertState] = useState<{ isOpen: boolean; title: string; message: string; type: 'error' | 'success' }>({
        isOpen: false, title: '', message: '', type: 'error'
    });

    const [modalState, setModalState] = useState<{ isOpen: boolean; mode: 'create' | 'edit' }>({
        isOpen: false, mode: 'create'
    });

    const [loading, setLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);

    const fetchPrompts = useCallback(async () => {
        try {
            const res = await api.get('/admin/prompts');
            setPrompts(res.data);
            if (res.data.length > 0 && !selectedId) {
                if (!selectedId || !res.data.find((p: PromptTemplate) => p.id === selectedId)) {
                    setSelectedId(res.data[0].id);
                    setLocalPrompt(res.data[0].system_prompt);
                }
            }
        } finally {
            setLoading(false);
        }
    }, [selectedId]);

    useEffect(() => { fetchPrompts(); }, [fetchPrompts]);

    const selectedPersona = prompts.find(p => p.id === selectedId);
    const isDirty = selectedPersona?.system_prompt !== localPrompt;

    const showAlert = (title: string, message: string, type: 'error' | 'success' = 'error') => {
        setAlertState({ isOpen: true, title, message, type });
    };

    const handleSelect = (p: PromptTemplate) => {
        if (isDirty) {
            if (!window.confirm("You have unsaved changes. Discard them?")) return;
        }
        setSelectedId(p.id);
        setLocalPrompt(p.system_prompt);
    };

    const handlePromptSave = async () => {
        setIsSaving(true);
        try {
            await api.patch(`/admin/prompts/${selectedId}`, { system_prompt: localPrompt });
            await fetchPrompts();
            setIsConfirmOpen(false);
            showAlert('Success', 'System logic updated successfully.', 'success');
        } catch {
            showAlert('Deployment Failed', 'Could not update the system prompt. Please try again.');
        } finally {
            setIsSaving(false);
        }
    };

    const handleModalSave = async (data: Partial<PromptTemplate>) => {
        setIsSaving(true);
        try {
            if (modalState.mode === 'create') {
                const res = await api.post('/admin/prompts', data);
                await fetchPrompts();
                setSelectedId(res.data.id);
                setLocalPrompt(res.data.system_prompt);
            } else {
                await api.patch(`/admin/prompts/${selectedId}`, data);
                await fetchPrompts();
            }
            setModalState({ ...modalState, isOpen: false });
        } catch (error: unknown) {
            console.error("Operation failed", error);
            const msg = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Operation failed.";

            showAlert('Action Blocked', msg, 'error');
            throw error;
        } finally {
            setIsSaving(false);
        }
    };

    const confirmDelete = async () => {
        if (!deleteTarget) return;

        setIsSaving(true);
        try {
            await api.delete(`/admin/prompts/${deleteTarget.id}`);

            if (selectedId === deleteTarget.id) {
                setSelectedId(null);
                setLocalPrompt("");
            }

            await fetchPrompts();
            setDeleteTarget(null);
            showAlert('Deleted', 'Persona removed successfully.', 'success');
        } catch {
            showAlert('Delete Failed', 'Could not delete this persona.');
        } finally {
            setIsSaving(false);
        }
    };

    if (loading) return <Loader2 className="animate-spin mx-auto mt-20" />;

    return (
        <div className="grid grid-cols-12 gap-8 h-[700px] animate-in fade-in duration-500 relative">
            <div className="col-span-4 flex flex-col gap-3 overflow-y-auto pr-2">
                <div className="px-2 pb-2 flex justify-between items-center">
                    <h3 className="text-sm font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <Sparkles size={14} /> Active Personas
                    </h3>
                    <button
                        onClick={() => setModalState({ isOpen: true, mode: 'create' })}
                        className="text-xs bg-cyan-50 text-cyan-600 px-2 py-1 rounded-lg hover:bg-cyan-100 font-bold flex items-center gap-1 transition-colors"
                    >
                        <Plus size={12} /> New
                    </button>
                </div>
                {prompts.map(p => (
                    <button
                        key={p.id}
                        onClick={() => handleSelect(p)}
                        className={`group w-full text-left p-4 rounded-2xl border transition-all duration-200 relative ${selectedId === p.id
                            ? 'bg-white border-cyan-500 shadow-xl ring-1 ring-cyan-500/20'
                            : 'bg-slate-50 border-transparent hover:border-slate-300 text-slate-600'
                            }`}
                    >
                        <div className={`absolute top-4 right-4 w-2 h-2 rounded-full ${p.is_active ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                        <div className="flex items-start gap-3">
                            <div className={`p-2 rounded-lg ${selectedId === p.id ? 'bg-cyan-600 text-white' : 'bg-slate-200 text-slate-500'}`}>
                                <Cpu size={18} />
                            </div>
                            <div>
                                <p className="font-black text-slate-800 text-sm leading-tight">{p.name}</p>
                                <span className="text-[10px] font-mono text-slate-400">{p.slug}</span>
                            </div>
                        </div>
                    </button>
                ))}
            </div>

            {selectedPersona ? (
                <div className="col-span-8 flex flex-col bg-slate-950 rounded-3xl border border-slate-800 shadow-2xl overflow-hidden relative">
                    <div className="p-5 bg-slate-900/50 border-b border-slate-800 flex justify-between items-center">
                        <div className="flex items-center gap-4">
                            <div>
                                <h4 className="text-white font-bold text-lg leading-none flex items-center gap-2">
                                    {selectedPersona.name}
                                    {!selectedPersona.is_active && <span className="text-[10px] bg-slate-700 text-slate-300 px-2 py-0.5 rounded-full">INACTIVE</span>}
                                </h4>
                                <p className="text-[10px] text-slate-500 font-mono mt-1">{selectedPersona.slug.toUpperCase()}.LOG</p>
                            </div>

                            <div className="flex items-center gap-1">
                                <button
                                    onClick={() => setModalState({ isOpen: true, mode: 'edit' })}
                                    className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                                    title="Edit Details"
                                >
                                    <Settings size={16} />
                                </button>
                                <button
                                    onClick={() => setDeleteTarget({ id: selectedPersona.id, name: selectedPersona.name })}
                                    className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-950/30 rounded-lg transition-colors"
                                    title="Delete Persona"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>

                        <button
                            onClick={() => setIsConfirmOpen(true)}
                            disabled={!isDirty || isSaving}
                            className={`px-6 py-2 rounded-xl text-sm font-bold flex items-center gap-2 transition-all ${isDirty
                                ? 'bg-cyan-600 text-white hover:bg-cyan-500'
                                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                                }`}
                        >
                            {isSaving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                            Deploy
                        </button>
                    </div>

                    <div className="flex-1 relative group">
                        <textarea
                            value={localPrompt}
                            onChange={(e) => setLocalPrompt(e.target.value)}
                            className="w-full h-full p-8 font-mono text-sm bg-transparent text-cyan-100/90 resize-none outline-none leading-relaxed"
                            spellCheck={false}
                        />
                        <div className="absolute top-0 right-0 p-8 pointer-events-none opacity-20 group-focus-within:opacity-40 transition-opacity">
                            <Wand2 size={120} className="text-cyan-500" />
                        </div>
                    </div>
                </div>
            ) : (
                <div className="col-span-8 flex flex-col items-center justify-center text-slate-400">
                    <Sparkles size={48} className="mb-4 text-slate-300" />
                    <p>Select a persona to edit or create a new one.</p>
                </div>
            )}

            <PersonaModal
                isOpen={modalState.isOpen}
                mode={modalState.mode}
                initialData={modalState.mode === 'edit' ? selectedPersona : undefined}
                isSaving={isSaving}
                onClose={() => setModalState({ ...modalState, isOpen: false })}
                onSave={handleModalSave}
            />

            <ConfirmModal
                isOpen={isConfirmOpen}
                title="Deploy Logic?"
                message="This will update the AI's behavior immediately."
                onConfirm={handlePromptSave}
                onClose={() => setIsConfirmOpen(false)}
                type="info"
            />

            <ConfirmModal
                isOpen={!!deleteTarget}
                title={`Delete ${deleteTarget?.name}?`}
                message="Are you sure? This action cannot be undone and will remove this persona from all future councils."
                onConfirm={confirmDelete}
                onClose={() => setDeleteTarget(null)}
                type="danger"
            />

            <AlertModal
                isOpen={alertState.isOpen}
                title={alertState.title}
                message={alertState.message}
                type={alertState.type}
                onClose={() => setAlertState(prev => ({ ...prev, isOpen: false }))}
            />
        </div>
    );
};