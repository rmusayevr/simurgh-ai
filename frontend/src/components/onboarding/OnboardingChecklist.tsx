/**
 * OnboardingChecklist.tsx
 *
 * A progress card shown on the Dashboard that tracks 4 setup milestones.
 * Each item auto-checks by querying the API. CTAs link to the relevant tab.
 * Disappears when all 4 are done (with a brief celebration), or on dismiss.
 * Persisted via localStorage key 'onboarding_checklist_v1_done'.
 *
 * --- INTEGRATION ---
 * In Dashboard.tsx, place above the project grid (inside the main div):
 *
 *   import { OnboardingChecklist } from '../components/onboarding/OnboardingChecklist';
 *   ...
 *   <OnboardingChecklist
 *       hasProjects={projects.length > 0}
 *       onCreateProject={openModal}   // the fn that opens the New Project modal
 *   />
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Circle, X, FolderOpen, Users, FileText, Zap, Trophy, ChevronRight } from 'lucide-react';
import { api } from '../../api/client';

const STORAGE_KEY = 'onboarding_checklist_v1_done';

interface Checks {
    project: boolean;
    stakeholder: boolean;
    document: boolean;
    proposal: boolean;
}

interface Props {
    hasProjects: boolean;
    onCreateProject: () => void;
}

// ─── Single checklist row ──────────────────────────────────────────────────
interface RowProps {
    done: boolean;
    title: string;
    hint: string;
    icon: React.ReactNode;
    cta: string;
    onCta: () => void;
    delay: number;
}

const Row: React.FC<RowProps> = ({ done, title, hint, icon, cta, onCta, delay }) => (
    <div className="flex items-start gap-3 py-3 border-b border-slate-50 last:border-0 group"
        style={{ animationDelay: `${delay}ms` }}>
        <div className="mt-0.5 shrink-0 transition-transform group-hover:scale-110">
            {done
                ? <CheckCircle2 size={17} className="text-emerald-500" />
                : <Circle size={17} className="text-slate-300" />}
        </div>

        <div className="flex-1 min-w-0">
            <p className={`text-sm font-bold leading-snug transition-all ${done ? 'text-slate-400 line-through decoration-slate-300' : 'text-slate-800'
                }`}>{title}</p>
            {!done && (
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{hint}</p>
            )}
        </div>

        {!done && (
            <button onClick={onCta}
                className="shrink-0 flex items-center gap-1 text-[11px] font-bold text-cyan-600 hover:text-white bg-cyan-50 hover:bg-cyan-600 px-2.5 py-1.5 rounded-lg transition-all whitespace-nowrap">
                {icon}
                {cta}
                <ChevronRight size={10} />
            </button>
        )}
    </div>
);

// ─── Main component ─────────────────────────────────────────────────────────
export const OnboardingChecklist: React.FC<Props> = ({ hasProjects, onCreateProject }) => {
    const navigate = useNavigate();

    const [hidden, setHidden] = useState(() => !!localStorage.getItem(STORAGE_KEY));
    const [checks, setChecks] = useState<Checks>({ project: false, stakeholder: false, document: false, proposal: false });
    const [pid, setPid] = useState<number | null>(null);
    const [celebrating, setCelebrating] = useState(false);

    // ── Fetch check states ──────────────────────────────────────────────────
    const refresh = useCallback(async () => {
        if (!hasProjects) return;
        try {
            const { data: projects } = await api.get<{ id: number }[]>('/projects/');
            if (!projects.length) return;
            const id = projects[0].id;
            setPid(id);

            const [st, doc, prop] = await Promise.allSettled([
                api.get<unknown[]>(`/stakeholders/project/${id}`),
                api.get<unknown[]>(`/documents/projects/${id}/documents`),
                api.get<unknown[]>(`/proposals/project/${id}`),
            ]);

            const stCount = st.status === 'fulfilled' ? (st.value.data as unknown[]).length : 0;
            const docCount = doc.status === 'fulfilled' ? (doc.value.data as unknown[]).length : 0;
            const propCount = prop.status === 'fulfilled' ? (prop.value.data as unknown[]).length : 0;

            setChecks({
                project: true,
                stakeholder: stCount > 0,
                document: docCount > 0,
                proposal: propCount > 0,
            });
        } catch { /* silent — checklist is non-critical */ }
    }, [hasProjects]);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (!hidden) refresh();
    }, [hidden, refresh]);

    // ── When all done: celebrate then auto-hide ─────────────────────────────
    const allDone = checks.project && checks.stakeholder && checks.document && checks.proposal;
    /* eslint-disable react-hooks/set-state-in-effect */
    useEffect(() => {
        if (allDone && !hidden) {
            setCelebrating(true);
            const t = setTimeout(() => {
                localStorage.setItem(STORAGE_KEY, '1');
                setHidden(true);
            }, 3200);
            return () => clearTimeout(t);
        }
    }, [allDone, hidden]);
    /* eslint-enable react-hooks/set-state-in-effect */

    const dismiss = () => {
        localStorage.setItem(STORAGE_KEY, '1');
        setHidden(true);
    };

    if (hidden) return null;

    const done = [checks.project, checks.stakeholder, checks.document, checks.proposal].filter(Boolean).length;
    const pct = (done / 4) * 100;

    return (
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden mb-6"
            style={{ animation: 'cl-in 400ms cubic-bezier(.22,1,.36,1) both' }}>
            <style>{`@keyframes cl-in{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}`}</style>

            {/* Header */}
            <div className="px-5 pt-4 pb-3 flex items-start gap-3">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                        {celebrating
                            ? <Trophy size={15} className="text-amber-500 animate-bounce" />
                            : <div className="w-4 h-4 rounded-full bg-cyan-600 flex items-center justify-center shrink-0">
                                <span className="text-[9px] text-white font-black leading-none">{done}</span>
                            </div>
                        }
                        <span className="text-sm font-black text-slate-900">
                            {celebrating ? "You're all set! 🎉" : 'Get started'}
                        </span>
                        {!celebrating && (
                            <span className="text-xs text-slate-400">{done}/4 complete</span>
                        )}
                    </div>
                    {/* Progress bar */}
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-cyan-500 to-violet-500 rounded-full transition-all duration-700"
                            style={{ width: `${pct}%` }} />
                    </div>
                </div>

                <button onClick={dismiss}
                    className="text-slate-300 hover:text-slate-500 hover:bg-slate-100 p-1.5 rounded-lg transition shrink-0 mt-0.5">
                    <X size={13} />
                </button>
            </div>

            {/* Rows */}
            {!celebrating && (
                <div className="px-5 pb-3">
                    <Row done={checks.project} delay={0}
                        title="Create your first project"
                        hint="A project holds your stakeholders, documents, and proposals for one initiative."
                        icon={<FolderOpen size={10} />} cta="New project"
                        onCta={onCreateProject} />
                    <Row done={checks.stakeholder} delay={60}
                        title="Add at least one stakeholder"
                        hint="The AI reads stakeholder profiles during every debate — the biggest quality lever."
                        icon={<Users size={10} />} cta="Stakeholders"
                        onCta={() => pid && navigate(`/project/${pid}/stakeholders`)} />
                    <Row done={checks.document} delay={120}
                        title="Upload a context file"
                        hint="Give the AI your real specs or RFCs so proposals reflect your actual constraints."
                        icon={<FileText size={10} />} cta="Context Files"
                        onCta={() => pid && navigate(`/project/${pid}/context`)} />
                    <Row done={checks.proposal} delay={180}
                        title="Generate your first proposal"
                        hint="Open AI Generator, describe the challenge, and click Convene Council."
                        icon={<Zap size={10} />} cta="AI Generator"
                        onCta={() => pid && navigate(`/project/${pid}/generator/new`)} />
                </div>
            )}

            {/* Celebration strip */}
            {celebrating && (
                <div className="px-5 pb-4">
                    <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-4 py-2.5 text-center font-medium">
                        Setup complete. This checklist will disappear in a moment.
                    </p>
                </div>
            )}
        </div>
    );
};