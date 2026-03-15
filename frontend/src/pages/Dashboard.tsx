import { OnboardingModal } from '../components/onboarding/OnboardingModal';
import { OnboardingChecklist } from '../components/onboarding/OnboardingChecklist';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Loader2, X, FolderOpen, Archive, Search, Tag } from 'lucide-react';
import { api } from '../api/client';
import type { ProjectListItem } from '../types';
import { ProjectCard } from '../components/ProjectCard';
import { TagInput } from '../components/TagInput';

const DOMAIN_TAGS = ['fintech', 'healthcare', 'e-commerce', 'logistics', 'saas', 'internal-tool'];
const SCALE_TAGS = ['startup', 'enterprise', 'migration', 'greenfield'];
const STACK_TAGS = ['microservices', 'monolith', 'cloud-native', 'on-premise', 'python', 'java', 'node', 'react', 'postgresql', 'kubernetes'];

export const Dashboard = () => {
    const navigate = useNavigate();

    const [projects, setProjects] = useState<ProjectListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [fetchError, setFetchError] = useState(false);
    const [includeArchived, setIncludeArchived] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [projectName, setProjectName] = useState('');
    const [projectDesc, setProjectDesc] = useState('');
    const [projectTags, setProjectTags] = useState<string[]>([]);
    const [projectTechStack, setProjectTechStack] = useState<string[]>([]);
    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);
    const [activeTagFilter, setActiveTagFilter] = useState<string | null>(null);

    const nameInputRef = useRef<HTMLInputElement>(null);

    const fetchProjects = useCallback(async () => {
        setLoading(true);
        setFetchError(false);
        try {
            const res = await api.get<ProjectListItem[]>('/projects/', {
                params: includeArchived ? { include_archived: true } : undefined,
            });
            setProjects(res.data);
        } catch {
            setFetchError(true);
        } finally {
            setLoading(false);
        }
    }, [includeArchived]);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    // ── Filtering ─────────────────────────────────────────────────────────────
    const filteredProjects = projects.filter(p => {
        const matchesSearch =
            p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase()));
        const matchesTag = !activeTagFilter ||
            (p.tags && p.tags.split(',').map(t => t.trim()).includes(activeTagFilter));
        return matchesSearch && matchesTag;
    });

    // Collect all unique tags across all projects for the filter bar
    const allTags = Array.from(new Set(
        projects.flatMap(p => p.tags ? p.tags.split(',').map(t => t.trim()).filter(Boolean) : [])
    )).sort();

    // ── Modal helpers ───────────────────────────────────────────────────────────
    const openModal = useCallback(() => {
        setProjectName('');
        setProjectDesc('');
        setProjectTags([]);
        setProjectTechStack([]);
        setCreateError(null);
        setIsModalOpen(true);
        setTimeout(() => nameInputRef.current?.focus(), 50);
    }, []);

    const closeModal = useCallback(() => {
        if (creating) return;
        setIsModalOpen(false);
    }, [creating]);

    // ── Create project ──────────────────────────────────────────────────────────
    const handleCreate = useCallback(async () => {
        const name = projectName.trim();
        if (!name) return;

        setCreating(true);
        setCreateError(null);

        try {
            const res = await api.post<ProjectListItem>('/projects/', {
                name,
                description: projectDesc.trim() || null,
                tags: projectTags.length > 0 ? projectTags.join(',') : null,
                tech_stack: projectTechStack.length > 0 ? projectTechStack.join(',') : null,
            });
            setProjects(prev => [res.data, ...prev]);
            setIsModalOpen(false);
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } }; message?: string };
            const detail = error?.response?.data?.detail || error?.message || 'Failed to create project. Please try again.';
            setCreateError(detail);
        } finally {
            setCreating(false);
        }
    }, [projectName, projectDesc, projectTags, projectTechStack]);

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === 'Enter' && !e.shiftKey) handleCreate();
            if (e.key === 'Escape') closeModal();
        },
        [handleCreate, closeModal]
    );

    return (
        <div className="min-h-screen bg-slate-50 font-sans">
            <div className="max-w-7xl mx-auto p-8 animate-in fade-in duration-500">

                {/* Header Section */}
                <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center mb-8 gap-6">
                    <div>
                        <h1 className="text-3xl font-black text-slate-900 flex items-center gap-3 tracking-tight">
                            <div className="p-2 bg-cyan-100 rounded-xl text-cyan-600">
                                <FolderOpen size={24} />
                            </div>
                            My Projects
                        </h1>
                        <p className="text-slate-500 mt-2 font-medium">
                            Manage your workspaces, wisdom containers, and proposals.
                        </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto">
                        {/* Search Bar */}
                        <div className="relative flex-1 lg:w-64">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                            <input
                                type="text"
                                placeholder="Search projects..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-cyan-500 outline-none shadow-sm transition-all"
                            />
                        </div>

                        <button
                            onClick={() => setIncludeArchived(v => !v)}
                            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-bold transition-all ${includeArchived
                                ? 'bg-slate-800 border-slate-800 text-white shadow-md'
                                : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50 shadow-sm'
                                }`}
                            title={includeArchived ? 'Hide archived projects' : 'Show archived projects'}
                        >
                            <Archive size={16} />
                            <span className="hidden sm:inline">{includeArchived ? 'Hide Archived' : 'Show Archived'}</span>
                        </button>

                        <button
                            onClick={openModal}
                            className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-700 text-white px-5 py-2.5 rounded-xl font-bold transition-all shadow-md shadow-cyan-600/20 hover:shadow-lg hover:-translate-y-0.5"
                        >
                            <Plus size={18} strokeWidth={3} />
                            New Project
                        </button>
                    </div>
                </div>

                {/* Onboarding Checklist */}
                <OnboardingChecklist
                    hasProjects={projects.length > 0}
                    onCreateProject={openModal}
                />

                {/* Tag filter bar — only shown when projects have tags */}
                {allTags.length > 0 && (
                    <div className="flex flex-wrap items-center gap-2 mb-6">
                        <Tag size={14} className="text-slate-400 shrink-0" />
                        <button
                            onClick={() => setActiveTagFilter(null)}
                            className={`text-[11px] font-bold uppercase tracking-wider px-3 py-1 rounded-lg border transition-all ${!activeTagFilter
                                ? 'bg-cyan-600 text-white border-cyan-600 shadow-sm'
                                : 'bg-white text-slate-500 border-slate-200 hover:border-slate-300'
                                }`}
                        >
                            All
                        </button>
                        {allTags.map(tag => (
                            <button
                                key={tag}
                                onClick={() => setActiveTagFilter(activeTagFilter === tag ? null : tag)}
                                className={`text-[11px] font-bold uppercase tracking-wider px-3 py-1 rounded-lg border transition-all ${activeTagFilter === tag
                                    ? 'bg-cyan-600 text-white border-cyan-600 shadow-sm'
                                    : 'bg-white text-slate-500 border-slate-200 hover:bg-cyan-50 hover:text-cyan-700 hover:border-cyan-200'
                                    }`}
                            >
                                {tag}
                            </button>
                        ))}
                    </div>
                )}

                {/* Content Section */}
                {loading ? (
                    // Skeleton Grid
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                        {[1, 2, 3, 4, 5, 6].map(i => (
                            <div key={i} className="bg-white rounded-2xl border border-slate-200 p-6 h-48 animate-pulse flex flex-col justify-between shadow-sm">
                                <div>
                                    <div className="h-6 bg-slate-100 rounded-md w-3/4 mb-3"></div>
                                    <div className="h-4 bg-slate-50 rounded-md w-full mb-2"></div>
                                    <div className="h-4 bg-slate-50 rounded-md w-5/6"></div>
                                </div>
                                <div className="flex justify-between items-center mt-4 pt-4 border-t border-slate-50">
                                    <div className="h-4 bg-slate-100 rounded-md w-1/3"></div>
                                    <div className="h-8 w-8 bg-slate-100 rounded-full"></div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : fetchError ? (
                    <div className="text-center py-24 bg-white rounded-3xl border border-red-100 shadow-sm">
                        <div className="w-16 h-16 bg-red-50 text-red-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
                            <X size={32} />
                        </div>
                        <p className="text-slate-800 font-bold text-lg mb-2">Failed to load workspace</p>
                        <p className="text-slate-500 mb-6">We couldn't reach the server. Check your connection.</p>
                        <button
                            onClick={fetchProjects}
                            className="bg-cyan-50 text-cyan-700 px-6 py-2.5 rounded-xl font-bold hover:bg-cyan-100 transition-colors"
                        >
                            Retry Connection
                        </button>
                    </div>
                ) : projects.length === 0 ? (
                    // Absolute Empty State
                    <div className="text-center py-24 bg-white rounded-3xl border border-dashed border-slate-300">
                        <div className="w-16 h-16 bg-slate-50 text-slate-400 rounded-2xl flex items-center justify-center mx-auto mb-4">
                            <FolderOpen size={32} />
                        </div>
                        <h3 className="text-xl font-bold text-slate-800 mb-2">Workspace is empty</h3>
                        <p className="text-slate-500 mb-8 max-w-sm mx-auto">
                            {includeArchived
                                ? 'No active or archived projects found in your system.'
                                : 'Get started by creating your first project to organize your documents and proposals.'}
                        </p>
                        <button
                            onClick={openModal}
                            className="bg-cyan-600 text-white px-6 py-3 rounded-xl font-bold hover:bg-cyan-700 transition-all shadow-md shadow-cyan-600/20"
                        >
                            Create First Project
                        </button>
                    </div>
                ) : filteredProjects.length === 0 ? (
                    // Search Empty State
                    <div className="text-center py-24 bg-transparent">
                        <Search size={48} className="mx-auto text-slate-300 mb-4" />
                        <h3 className="text-lg font-bold text-slate-700 mb-1">No matches found</h3>
                        <p className="text-slate-500">We couldn't find any projects matching "{searchQuery}"</p>
                        <button
                            onClick={() => setSearchQuery('')}
                            className="mt-4 text-cyan-600 font-bold hover:text-cyan-700"
                        >
                            Clear Search
                        </button>
                    </div>
                ) : (
                    // Project Grid
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 animate-in slide-in-from-bottom-4 duration-500">
                        {filteredProjects.map(project => (
                            <ProjectCard
                                key={project.id}
                                project={project}
                                onClick={id => navigate(`/project/${id}`)}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Create Project Modal */}
            {isModalOpen && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200"
                    onClick={e => { if (e.target === e.currentTarget) closeModal(); }}
                    onKeyDown={handleKeyDown}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="modal-title"
                >
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200 border border-slate-100">
                        {/* Modal header */}
                        <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                            <h3 id="modal-title" className="font-bold text-lg text-slate-800 tracking-tight">Create New Project</h3>
                            <button
                                onClick={closeModal}
                                disabled={creating}
                                className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 p-2 rounded-lg transition disabled:opacity-40"
                                aria-label="Close"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Modal body */}
                        <div className="p-6 space-y-5">
                            <div>
                                <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2" htmlFor="project-name">
                                    Project Name <span className="text-red-400">*</span>
                                </label>
                                <input
                                    id="project-name"
                                    ref={nameInputRef}
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-cyan-500 outline-none transition-all font-medium text-slate-900 placeholder:text-slate-400 font-sans"
                                    placeholder="e.g. Finance System Migration"
                                    value={projectName}
                                    onChange={e => setProjectName(e.target.value)}
                                    maxLength={200}
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2" htmlFor="project-desc">
                                    Description <span className="text-slate-400 font-medium normal-case">(optional)</span>
                                </label>
                                <textarea
                                    id="project-desc"
                                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-cyan-500 outline-none h-28 resize-none transition-all text-sm text-slate-700 placeholder:text-slate-400"
                                    placeholder="Brief context about the goals and scope of this workspace..."
                                    value={projectDesc}
                                    onChange={e => setProjectDesc(e.target.value)}
                                    maxLength={2000}
                                />
                            </div>

                            <TagInput
                                label="Tags"
                                tags={projectTags}
                                onChange={setProjectTags}
                                placeholder="e.g. fintech, migration..."
                                suggestions={DOMAIN_TAGS.concat(SCALE_TAGS)}
                                disabled={creating}
                            />

                            <TagInput
                                label="Tech Stack"
                                tags={projectTechStack}
                                onChange={setProjectTechStack}
                                placeholder="e.g. python, postgresql..."
                                suggestions={STACK_TAGS}
                                disabled={creating}
                            />

                            {createError && (
                                <div className="p-3 bg-red-50 border border-red-100 rounded-xl flex items-start gap-2 text-red-600 text-sm">
                                    <X size={16} className="mt-0.5 shrink-0" />
                                    <p className="font-medium">{createError}</p>
                                </div>
                            )}
                        </div>

                        {/* Modal footer */}
                        <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-3">
                            <button
                                onClick={closeModal}
                                disabled={creating}
                                className="px-5 py-2.5 text-slate-600 font-bold hover:bg-slate-200 rounded-xl transition-colors disabled:opacity-40"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleCreate}
                                disabled={creating || !projectName.trim()}
                                className="px-6 py-2.5 bg-cyan-600 text-white font-bold rounded-xl hover:bg-cyan-700 transition-all disabled:opacity-50 flex items-center gap-2 shadow-sm"
                            >
                                {creating && <Loader2 size={16} className="animate-spin" />}
                                {creating ? 'Initializing...' : 'Create Project'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
            <OnboardingModal />
        </div>
    );
};