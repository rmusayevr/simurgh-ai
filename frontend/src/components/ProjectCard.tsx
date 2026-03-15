import type { ProjectListItem } from '../types';
import { Folder, ArrowRight, FileText, Users, Cpu, Archive } from 'lucide-react';

interface ProjectCardProps {
    project: ProjectListItem;
    onClick: (id: number) => void;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project, onClick }) => {
    // Safely parse tags (handle null/undefined gracefully)
    const tagList = project.tags
        ? project.tags.split(',').map(t => t.trim()).filter(Boolean).slice(0, 3)
        : [];

    const lastActivity = new Date(project.last_activity_at).toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', year: 'numeric',
    });

    return (
        <div
            onClick={() => onClick(project.id)}
            // Fixed the className string interpolation syntax bug
            className={`bg-white p-6 rounded-2xl border transition-all duration-200 cursor-pointer group flex flex-col gap-4 h-full ${project.is_archived
                ? 'border-slate-200 opacity-60 hover:opacity-100 bg-slate-50/50 hover:shadow-sm'
                : 'border-slate-200 hover:shadow-lg hover:shadow-cyan-500/5 hover:border-cyan-300 hover:-translate-y-1'
                }`}
        >
            {/* Card header */}
            <div className="flex justify-between items-start">
                <div className={`p-3 rounded-xl transition-colors duration-200 ${project.is_archived
                    ? 'bg-slate-200/50 text-slate-500'
                    : 'bg-cyan-50 text-cyan-600 group-hover:bg-cyan-600 group-hover:text-white'
                    }`}>
                    {project.is_archived ? <Archive size={20} /> : <Folder size={20} />}
                </div>
                <ArrowRight size={18} className="text-slate-300 group-hover:text-cyan-500 transition-colors group-hover:translate-x-1" />
            </div>

            {/* Title + description */}
            <div className="flex-1 mt-2">
                <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-lg font-bold text-slate-900 leading-tight line-clamp-1 group-hover:text-cyan-900 transition-colors">
                        {project.name}
                    </h3>
                    {project.is_archived && (
                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-500 bg-slate-200/50 px-2 py-1 rounded-md shrink-0">
                            Archived
                        </span>
                    )}
                </div>
                <p className="text-slate-500 text-sm line-clamp-2 min-h-[2.5rem] leading-relaxed">
                    {project.description || 'No description provided.'}
                </p>
            </div>

            {/* Tags Container */}
            <div className="min-h-[28px]">
                {tagList.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                        {tagList.map(tag => (
                            <span
                                key={tag}
                                className="text-[10px] font-bold uppercase tracking-wider text-cyan-700 bg-cyan-50/80 border border-cyan-100/50 px-2.5 py-1 rounded-lg"
                            >
                                {tag}
                            </span>
                        ))}
                    </div>
                ) : (
                    // Placeholder to maintain card height consistency when no tags exist
                    <div className="flex gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-50 border border-slate-100 px-2.5 py-1 rounded-lg">
                            Uncategorized
                        </span>
                    </div>
                )}
            </div>

            {/* Stats row */}
            <div className="flex items-center gap-4 text-xs font-medium text-slate-500 pt-4 mt-1 border-t border-slate-100">
                <span className="flex items-center gap-1.5" title="Missions">
                    <Cpu size={14} className={project.is_archived ? '' : 'text-cyan-400'} />
                    {project.proposal_count}
                </span>
                <span className="flex items-center gap-1.5" title="Documents">
                    <FileText size={14} className={project.is_archived ? '' : 'text-emerald-400'} />
                    {project.document_count}
                </span>
                <span className="flex items-center gap-1.5" title="Members">
                    <Users size={14} className={project.is_archived ? '' : 'text-amber-400'} />
                    {project.member_count}
                </span>
                <span className="ml-auto text-[10px] font-bold uppercase tracking-wider text-slate-400 bg-slate-50 px-2 py-1 rounded-md">
                    {lastActivity}
                </span>
            </div>
        </div>
    );
};