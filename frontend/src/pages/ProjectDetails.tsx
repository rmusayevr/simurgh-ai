import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation, Outlet } from 'react-router-dom';
import {
    ArrowLeft, Plus, Users, FileText, Bot, Loader2, Pencil, Check, X
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { hasPermission } from '../config/permissions';
import { AddStakeholderModal } from '../components/modals/AddStakeholderModal';
import { DocumentsTab } from '../components/tabs/DocumentsTab';
import { GeneratorTab } from '../components/tabs/GeneratorTab';
import { StakeholderRow } from '../components/StakeholderRow';
import { MendelowMatrix } from '../components/MendelowMatrix';
import { TagInput } from '../components/TagInput';
import type { Project, Stakeholder, ProjectRole } from '../types';

const DOMAIN_TAGS = ['fintech', 'healthcare', 'e-commerce', 'logistics', 'saas', 'internal-tool'];
const SCALE_TAGS = ['startup', 'enterprise', 'migration', 'greenfield'];
const STACK_TAGS = ['microservices', 'monolith', 'cloud-native', 'on-premise', 'python', 'java', 'node', 'react', 'postgresql', 'kubernetes'];

// ─── Tab definition ────────────────────────────────────────────────────────────
type TabId = 'stakeholders' | 'context' | 'generator';

interface Tab {
    id: TabId;
    label: string;
    icon: React.ReactNode;
    minRole?: ProjectRole;
}

const TABS: Tab[] = [
    { id: 'context', label: 'Context Files', icon: <FileText size={16} /> },
    { id: 'generator', label: 'AI Generator', icon: <Bot size={16} /> },
    { id: 'stakeholders', label: 'Stakeholders', icon: <Users size={16} /> },
];

// ─── TabButton ─────────────────────────────────────────────────────────────────
interface TabButtonProps {
    id: TabId;
    label: string;
    icon: React.ReactNode;
    active: boolean;
    onClick: (id: TabId) => void;
}

const TabButton = ({ id, label, icon, active, onClick }: TabButtonProps) => (
    <button
        onClick={() => onClick(id)}
        className={`flex items-center gap-2 pb-4 px-2 text-sm font-bold border-b-2 transition-all whitespace-nowrap ${active
            ? 'text-indigo-600 border-indigo-600'
            : 'text-slate-500 border-transparent hover:text-slate-800'
            }`}
    >
        {icon} {label}
    </button>
);

// ─── Derive active tab from current URL pathname ───────────────────────────────
const getActiveTabFromPath = (pathname: string): TabId => {
    if (pathname.includes('/stakeholders')) return 'stakeholders';
    if (pathname.includes('/generator')) return 'generator';
    return 'context';
};

// ─── Main component ────────────────────────────────────────────────────────────
export const ProjectDetails = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const { user } = useAuth();

    // ── State ──────────────────────────────────────────────────────────────────
    const [project, setProject] = useState<Project | null>(null);
    const [stakeholders, setStakeholders] = useState<Stakeholder[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState(false);

    const [editingStakeholder, setEditingStakeholder] = useState<Stakeholder | null>(null);
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);

    // ── Tag editing state ──────────────────────────────────────────────────────
    const [isEditingTags, setIsEditingTags] = useState(false);
    const [editTags, setEditTags] = useState<string[]>([]);
    const [editTechStack, setEditTechStack] = useState<string[]>([]);
    const [savingTags, setSavingTags] = useState(false);
    const [tagSaveError, setTagSaveError] = useState<string | null>(null);

    // ── Name / description editing state ──────────────────────────────────────
    const [isEditingInfo, setIsEditingInfo] = useState(false);
    const [editName, setEditName] = useState('');
    const [editDescription, setEditDescription] = useState('');
    const [savingInfo, setSavingInfo] = useState(false);
    const [infoSaveError, setInfoSaveError] = useState<string | null>(null);

    // ── Active tab — derived from URL path ─────────────────────────────────────
    const activeTab = getActiveTabFromPath(location.pathname);

    const setActiveTab = useCallback((tab: TabId) => {
        navigate(`/project/${id}/${tab}`, { replace: true });
    }, [navigate, id]);

    // ── Derived permissions ────────────────────────────────────────────────────
    const currentUserLink = project?.stakeholder_links?.find(l => l.user_id === user?.id);
    const currentRole: ProjectRole =
        project?.owner_id === user?.id
            ? 'OWNER'
            : (currentUserLink?.role ?? 'VIEWER');

    const isOwnerOrAdmin = currentRole === 'OWNER' || currentRole === 'ADMIN';
    const canEditContent = hasPermission(currentRole, 'EDIT_CONTENT');

    // ── Data loading ───────────────────────────────────────────────────────────
    const loadData = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        setLoadError(false);
        try {
            const [projRes, stakRes] = await Promise.all([
                api.get<Project>(`/projects/${id}`),
                api.get<Stakeholder[]>(`/stakeholders/project/${id}`),
            ]);
            setProject(projRes.data);
            setStakeholders(stakRes.data);
        } catch {
            setLoadError(true);
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => { loadData(); }, [loadData]);

    // ── Tag editing handlers ───────────────────────────────────────────────────
    const openTagEdit = useCallback(() => {
        if (!project) return;
        setEditTags(project.tags ? project.tags.split(',').map(t => t.trim()).filter(Boolean) : []);
        setEditTechStack(project.tech_stack ? project.tech_stack.split(',').map(t => t.trim()).filter(Boolean) : []);
        setTagSaveError(null);
        setIsEditingTags(true);
    }, [project]);

    const cancelTagEdit = useCallback(() => {
        setIsEditingTags(false);
        setTagSaveError(null);
    }, []);

    const saveTagEdit = useCallback(async () => {
        if (!id || !project) return;
        setSavingTags(true);
        setTagSaveError(null);
        try {
            const res = await api.patch<Project>(`/projects/${id}`, {
                tags: editTags.length > 0 ? editTags.join(',') : null,
                tech_stack: editTechStack.length > 0 ? editTechStack.join(',') : null,
            });
            setProject(res.data);
            setIsEditingTags(false);
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } }; message?: string };
            setTagSaveError(error?.response?.data?.detail || error?.message || 'Failed to save.');
        } finally {
            setSavingTags(false);
        }
    }, [id, project, editTags, editTechStack]);

    // ── Name / description handlers ────────────────────────────────────────────
    const openInfoEdit = useCallback(() => {
        if (!project) return;
        setEditName(project.name);
        setEditDescription(project.description ?? '');
        setInfoSaveError(null);
        setIsEditingInfo(true);
    }, [project]);

    const cancelInfoEdit = useCallback(() => {
        setIsEditingInfo(false);
        setInfoSaveError(null);
    }, []);

    const saveInfoEdit = useCallback(async () => {
        if (!id || !project) return;
        const name = editName.trim();
        if (!name) { setInfoSaveError('Project name is required.'); return; }
        setSavingInfo(true);
        setInfoSaveError(null);
        try {
            const res = await api.patch<Project>(`/projects/${id}`, {
                name,
                description: editDescription.trim() || null,
            });
            setProject(res.data);
            setIsEditingInfo(false);
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } }; message?: string };
            setInfoSaveError(error?.response?.data?.detail || error?.message || 'Failed to save.');
        } finally {
            setSavingInfo(false);
        }
    }, [id, project, editName, editDescription]);

    // ── Stakeholder CRUD callbacks ─────────────────────────────────────────────
    const handleEdit = useCallback((person: Stakeholder) => {
        setEditingStakeholder(person);
        setIsAddModalOpen(true);
    }, []);

    const handleDeleteSuccess = useCallback((deletedId: number) => {
        setStakeholders(prev => prev.filter(s => s.id !== deletedId));
    }, []);

    const handleModalSuccess = useCallback((savedPerson: Stakeholder) => {
        setStakeholders(prev =>
            editingStakeholder
                ? prev.map(s => s.id === savedPerson.id ? savedPerson : s)
                : [...prev, savedPerson]
        );
    }, [editingStakeholder]);

    const handleModalClose = useCallback(() => {
        setIsAddModalOpen(false);
        setTimeout(() => setEditingStakeholder(null), 200);
    }, []);

    const visibleTabs = TABS.filter(tab => {
        if (!tab.minRole) return true;
        return isOwnerOrAdmin;
    });

    // ── Derived tag lists for display ──────────────────────────────────────────
    const tagList = project?.tags ? project.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
    const techList = project?.tech_stack ? project.tech_stack.split(',').map(t => t.trim()).filter(Boolean) : [];

    // ── Loading / error states ─────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <Loader2 size={40} className="animate-spin text-indigo-600" />
            </div>
        );
    }

    if (loadError || !project) {
        return (
            <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4">
                <p className="text-slate-700 font-medium">Failed to load project.</p>
                <div className="flex gap-3">
                    <button
                        onClick={loadData}
                        className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition"
                    >
                        Retry
                    </button>
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-50 transition"
                    >
                        Back to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col">
            <header className="bg-white border-b border-slate-200 px-6 py-6">
                <div className="max-w-7xl mx-auto">
                    <button onClick={() => navigate('/dashboard')} className="flex items-center text-sm text-slate-500 hover:text-slate-900 mb-4 transition-colors">
                        <ArrowLeft size={16} className="mr-1" /> Back to Dashboard
                    </button>

                    <div className="flex justify-between items-start gap-4">
                        <div className="min-w-0 flex-1">
                            {/* ── Name / description display / edit ── */}
                            {isEditingInfo ? (
                                <div className="space-y-3 max-w-2xl">
                                    <div>
                                        <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-1.5">
                                            Project Name <span className="text-red-400">*</span>
                                        </label>
                                        <input
                                            autoFocus
                                            className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-indigo-500 outline-none transition-all font-bold text-xl text-slate-900 placeholder:text-slate-400"
                                            value={editName}
                                            onChange={e => setEditName(e.target.value)}
                                            maxLength={200}
                                            onKeyDown={e => { if (e.key === 'Escape') cancelInfoEdit(); }}
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-1.5">
                                            Description <span className="text-slate-400 font-medium normal-case">(optional)</span>
                                        </label>
                                        <textarea
                                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-indigo-500 outline-none h-24 resize-none transition-all text-sm text-slate-700 placeholder:text-slate-400"
                                            placeholder="Brief context about the goals and scope of this project..."
                                            value={editDescription}
                                            onChange={e => setEditDescription(e.target.value)}
                                            maxLength={2000}
                                            onKeyDown={e => { if (e.key === 'Escape') cancelInfoEdit(); }}
                                        />
                                    </div>
                                    {infoSaveError && (
                                        <p className="text-red-500 text-xs font-medium">{infoSaveError}</p>
                                    )}
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={saveInfoEdit}
                                            disabled={savingInfo || !editName.trim()}
                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-700 transition disabled:opacity-50"
                                        >
                                            {savingInfo
                                                ? <Loader2 size={12} className="animate-spin" />
                                                : <Check size={12} strokeWidth={3} />}
                                            Save
                                        </button>
                                        <button
                                            onClick={cancelInfoEdit}
                                            disabled={savingInfo}
                                            className="flex items-center gap-1.5 px-3 py-1.5 text-slate-500 text-xs font-bold rounded-lg hover:bg-slate-100 transition disabled:opacity-50"
                                        >
                                            <X size={12} strokeWidth={3} /> Cancel
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                <div className="group/info">
                                    <div className="flex items-center gap-2">
                                        <h1 className="text-3xl font-black text-slate-900 truncate">{project.name}</h1>
                                        {isOwnerOrAdmin && (
                                            <button
                                                onClick={openInfoEdit}
                                                className="opacity-0 group-hover/info:opacity-100 flex items-center gap-1 text-[11px] font-bold text-slate-400 hover:text-indigo-600 transition-all"
                                                title="Edit name and description"
                                            >
                                                <Pencil size={12} />
                                            </button>
                                        )}
                                    </div>
                                    {project.description ? (
                                        <p className="text-slate-500 max-w-2xl mt-1">{project.description}</p>
                                    ) : isOwnerOrAdmin ? (
                                        <button
                                            onClick={openInfoEdit}
                                            className="text-sm text-slate-400 hover:text-indigo-600 mt-1 transition-colors italic"
                                        >
                                            + Add a description
                                        </button>
                                    ) : (
                                        <p className="text-slate-400 max-w-2xl mt-1 italic text-sm">No description provided.</p>
                                    )}
                                </div>
                            )}

                            {/* ── Tag display / edit area ── */}
                            <div className="mt-4">
                                {isEditingTags ? (
                                    // Edit mode
                                    <div className="space-y-3 max-w-2xl">
                                        <TagInput
                                            label="Tags"
                                            tags={editTags}
                                            onChange={setEditTags}
                                            placeholder="e.g. fintech, migration..."
                                            suggestions={DOMAIN_TAGS.concat(SCALE_TAGS)}
                                            disabled={savingTags}
                                        />
                                        <TagInput
                                            label="Tech Stack"
                                            tags={editTechStack}
                                            onChange={setEditTechStack}
                                            placeholder="e.g. python, postgresql..."
                                            suggestions={STACK_TAGS}
                                            disabled={savingTags}
                                        />
                                        {tagSaveError && (
                                            <p className="text-red-500 text-xs font-medium">{tagSaveError}</p>
                                        )}
                                        <div className="flex items-center gap-2 pt-1">
                                            <button
                                                onClick={saveTagEdit}
                                                disabled={savingTags}
                                                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-700 transition disabled:opacity-50"
                                            >
                                                {savingTags
                                                    ? <Loader2 size={12} className="animate-spin" />
                                                    : <Check size={12} strokeWidth={3} />}
                                                Save
                                            </button>
                                            <button
                                                onClick={cancelTagEdit}
                                                disabled={savingTags}
                                                className="flex items-center gap-1.5 px-3 py-1.5 text-slate-500 text-xs font-bold rounded-lg hover:bg-slate-100 transition disabled:opacity-50"
                                            >
                                                <X size={12} strokeWidth={3} /> Cancel
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    // Display mode
                                    <div className="flex flex-wrap items-center gap-2">
                                        {/* Tag pills */}
                                        {tagList.map(tag => (
                                            <span key={tag} className="text-[11px] font-bold uppercase tracking-wider text-cyan-700 bg-cyan-50 border border-cyan-100 px-2.5 py-1 rounded-lg">
                                                {tag}
                                            </span>
                                        ))}
                                        {/* Tech stack pills — distinct colour */}
                                        {techList.map(tech => (
                                            <span key={tech} className="text-[11px] font-bold uppercase tracking-wider text-violet-700 bg-violet-50 border border-violet-100 px-2.5 py-1 rounded-lg">
                                                {tech}
                                            </span>
                                        ))}

                                        {/* Edit button — always visible to owners/admins */}
                                        {isOwnerOrAdmin ? (
                                            <button
                                                onClick={openTagEdit}
                                                className={`flex items-center gap-1 text-[11px] font-bold transition-colors ${tagList.length === 0 && techList.length === 0
                                                        ? 'text-slate-400 bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 border border-dashed border-slate-300 hover:border-indigo-300 px-2.5 py-1 rounded-lg'
                                                        : 'text-slate-400 hover:text-indigo-600 ml-1'
                                                    }`}
                                                title="Edit tags and tech stack"
                                            >
                                                <Pencil size={11} />
                                                {tagList.length === 0 && techList.length === 0 ? 'Add tags' : 'Edit tags'}
                                            </button>
                                        ) : (
                                            tagList.length === 0 && techList.length === 0 && (
                                                <span className="text-xs text-slate-400">No tags.</span>
                                            )
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>

                        {activeTab === 'stakeholders' && canEditContent && (
                            <button
                                onClick={() => setIsAddModalOpen(true)}
                                className="shrink-0 bg-indigo-600 text-white px-5 py-2.5 rounded-lg font-bold hover:bg-indigo-700 transition shadow-lg shadow-indigo-200 flex items-center gap-2"
                            >
                                <Plus size={18} /> Add Stakeholder
                            </button>
                        )}
                    </div>

                    <div className="flex items-center gap-6 mt-8 border-b border-slate-100 overflow-x-auto">
                        {visibleTabs.map(tab => (
                            <TabButton
                                key={tab.id}
                                id={tab.id}
                                label={tab.id === 'stakeholders' ? `Stakeholders (${stakeholders.length})` : tab.label}
                                icon={tab.icon}
                                active={activeTab === tab.id}
                                onClick={setActiveTab}
                            />
                        ))}
                    </div>
                </div>
            </header>

            <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8">
                {/* Stakeholders */}
                {activeTab === 'stakeholders' && (
                    <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">

                        {stakeholders.length > 0 && (
                            <MendelowMatrix stakeholders={stakeholders} />
                        )}

                        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                                <h3 className="font-bold text-slate-700">Stakeholder Directory</h3>
                                <p className="text-xs text-slate-400 mt-0.5">
                                    Stakeholder context is injected into every AI debate session.
                                </p>
                            </div>

                            {stakeholders.length === 0 ? (
                                <div className="text-center py-20">
                                    <Users size={48} className="mx-auto text-slate-300 mb-4" />
                                    <p className="text-slate-500 font-medium">No stakeholders yet.</p>
                                    <p className="text-slate-400 text-sm mt-1">Add stakeholders to enrich AI debate context.</p>
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left text-sm">
                                        <thead className="bg-slate-50 text-slate-400 font-black uppercase text-[10px] tracking-widest border-b border-slate-100">
                                            <tr>
                                                <th className="px-6 py-4">Name / Role</th>
                                                <th className="px-6 py-4">Department</th>
                                                <th className="px-6 py-4 text-center">Influence</th>
                                                <th className="px-6 py-4 text-center">Interest</th>
                                                <th className="px-6 py-4">Sentiment</th>
                                                <th className="px-6 py-4" />
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100">
                                            {stakeholders.map(person => (
                                                <StakeholderRow
                                                    key={person.id}
                                                    person={person}
                                                    onEdit={handleEdit}
                                                    onDelete={handleDeleteSuccess}
                                                />
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Context Files */}
                {activeTab === 'context' && (
                    <DocumentsTab projectId={project.id.toString()} />
                )}

                {/* AI Generator */}
                {activeTab === 'generator' && (
                    <GeneratorTab projectId={project.id.toString()} />
                )}
            </main>

            <AddStakeholderModal
                projectId={id!}
                isOpen={isAddModalOpen}
                onClose={handleModalClose}
                onSuccess={handleModalSuccess}
                initialData={editingStakeholder}
            />
            <Outlet />
        </div>
    );
};