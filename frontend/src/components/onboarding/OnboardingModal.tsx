/**
 * OnboardingModal.tsx
 *
 * Shown ONCE on first login via localStorage key 'onboarding_v1_seen'.
 * A 4-step paginated modal walking through the core workflow.
 *
 * --- INTEGRATION ---
 * In Dashboard.tsx, add at the bottom of the return, inside the outer div:
 *
 *   import { OnboardingModal } from '../components/onboarding/OnboardingModal';
 *   ...
 *   <OnboardingModal />
 */

import React, { useEffect, useState } from 'react';
import { X, FolderOpen, Users, FileText, Zap, ArrowRight, ChevronLeft, Sparkles } from 'lucide-react';

const STORAGE_KEY = 'onboarding_v1_seen';

interface Step {
    icon: React.ReactNode;
    accentClass: string;
    bgClass: string;
    stepLabel: string;
    title: string;
    body: string;
    tip: string;
}

const STEPS: Step[] = [
    {
        icon: <FolderOpen size={30} />,
        accentClass: 'text-cyan-600',
        bgClass: 'bg-cyan-50',
        stepLabel: 'Step 1 of 4',
        title: 'Create a Project',
        body: 'A project is your workspace for one architectural initiative — it holds your documents, stakeholders, and all generated proposals. Click New Project on the Dashboard to get started.',
        tip: 'Give it a specific name like "Payment Service Migration" rather than "New Project". The AI reads the name as context.',
    },
    {
        icon: <Users size={30} />,
        accentClass: 'text-violet-600',
        bgClass: 'bg-violet-50',
        stepLabel: 'Step 2 of 4',
        title: 'Add Stakeholders',
        body: 'Open the Stakeholders tab and profile the people whose buy-in you need. Set their Influence level, Interest level, and current Sentiment. This context is injected into every AI debate session.',
        tip: 'A Resistant, High-Influence stakeholder will directly shape how the Legacy Keeper persona argues. Without stakeholders, proposals are technically sound but politically naive.',
    },
    {
        icon: <FileText size={30} />,
        accentClass: 'text-sky-600',
        bgClass: 'bg-sky-50',
        stepLabel: 'Step 3 of 4',
        title: 'Upload Context Files',
        body: 'Open the Context Files tab and upload your real project documents — RFCs, architecture specs, meeting notes, compliance requirements. The AI retrieves the most relevant sections to ground every proposal in your actual constraints.',
        tip: 'Wait until all files show a green COMPLETED badge before generating. Files are still being indexed while they show PENDING or PROCESSING.',
    },
    {
        icon: <Zap size={30} />,
        accentClass: 'text-emerald-600',
        bgClass: 'bg-emerald-50',
        stepLabel: 'Step 4 of 4',
        title: 'Convene the Council',
        body: 'Open the AI Generator tab, click New Session, and describe your architectural challenge in detail. Then click Convene Council — three AI personas (Legacy Keeper, Innovator, Mediator) will debate the problem and each write a distinct proposal.',
        tip: 'The more specific your task description, the sharper the proposals. Include your current stack, team size, key constraints, and the political context.',
    },
];

export const OnboardingModal: React.FC = () => {
    const [visible, setVisible] = useState(false);
    const [step, setStep] = useState(0);
    const [dir, setDir] = useState<'fwd' | 'bck'>('fwd');
    const [animKey, setAnimKey] = useState(0);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
    }, []);

    const dismiss = () => {
        localStorage.setItem(STORAGE_KEY, '1');
        setVisible(false);
    };

    const goTo = (next: number, direction: 'fwd' | 'bck') => {
        setDir(direction);
        setAnimKey(k => k + 1);
        setStep(next);
    };

    if (!visible) return null;

    const s = STEPS[step];
    const isLast = step === STEPS.length - 1;

    return (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
            style={{ animation: 'ob-bg 200ms ease both' }}>
            <style>{`
                @keyframes ob-bg  { from{opacity:0} to{opacity:1} }
                @keyframes ob-fwd { from{opacity:0;transform:translateX(20px)} to{opacity:1;transform:translateX(0)} }
                @keyframes ob-bck { from{opacity:0;transform:translateX(-20px)} to{opacity:1;transform:translateX(0)} }
                @keyframes ob-in  { from{opacity:0;transform:scale(.96) translateY(8px)} to{opacity:1;transform:scale(1) translateY(0)} }
                .ob-fwd { animation: ob-fwd 260ms cubic-bezier(.22,1,.36,1) both }
                .ob-bck { animation: ob-bck 260ms cubic-bezier(.22,1,.36,1) both }
            `}</style>

            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-slate-100 overflow-hidden"
                style={{ animation: 'ob-in 280ms cubic-bezier(.22,1,.36,1) both' }}>

                {/* Header */}
                <div className="flex items-center justify-between px-6 pt-5 pb-4">
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-6 bg-gradient-to-br from-cyan-500 to-violet-600 rounded-lg flex items-center justify-center">
                            <Sparkles size={12} className="text-white" />
                        </div>
                        <span className="text-sm font-black text-slate-900 tracking-tight">
                            Welcome to Simurgh AI
                        </span>
                    </div>
                    <button onClick={dismiss}
                        className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 p-1.5 rounded-lg transition">
                        <X size={15} />
                    </button>
                </div>

                {/* Step dots */}
                <div className="flex items-center gap-1.5 px-6 mb-5">
                    {STEPS.map((_, i) => (
                        <div key={i}
                            className={`h-1 rounded-full transition-all duration-400 ${i === step ? 'w-6 bg-cyan-600' :
                                i < step ? 'w-3 bg-cyan-200' : 'w-3 bg-slate-200'
                                }`} />
                    ))}
                    <span className="ml-auto text-[11px] text-slate-400 font-bold tabular-nums">
                        {step + 1}/{STEPS.length}
                    </span>
                </div>

                {/* Step body */}
                <div key={animKey} className={`px-6 pb-3 ${dir === 'fwd' ? 'ob-fwd' : 'ob-bck'}`}>
                    <div className={`w-14 h-14 ${s.bgClass} ${s.accentClass} rounded-2xl flex items-center justify-center mb-4`}>
                        {s.icon}
                    </div>
                    <span className="inline-block text-[10px] font-black uppercase tracking-widest text-slate-400 bg-slate-100 px-2.5 py-1 rounded-full mb-2">
                        {s.stepLabel}
                    </span>
                    <h2 className="text-xl font-black text-slate-900 mb-2">{s.title}</h2>
                    <p className="text-sm text-slate-600 leading-relaxed mb-4">{s.body}</p>
                    <div className="bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 flex gap-2.5">
                        <span className="shrink-0 mt-0.5">💡</span>
                        <p className="text-xs text-amber-800 leading-relaxed">{s.tip}</p>
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-6 py-4">
                    <button onClick={() => goTo(step - 1, 'bck')}
                        disabled={step === 0}
                        className="flex items-center gap-1 text-sm font-bold text-slate-400 hover:text-slate-700 disabled:opacity-0 px-3 py-2 rounded-xl hover:bg-slate-100 transition">
                        <ChevronLeft size={14} /> Back
                    </button>

                    <div className="flex items-center gap-3">
                        <button onClick={dismiss}
                            className="text-sm text-slate-400 hover:text-slate-600 font-medium transition">
                            Skip
                        </button>
                        {isLast ? (
                            <button onClick={dismiss}
                                className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-700 text-white px-5 py-2.5 rounded-xl text-sm font-bold shadow-md shadow-cyan-200 transition-all hover:-translate-y-px">
                                <Zap size={13} fill="currentColor" /> Let's go
                            </button>
                        ) : (
                            <button onClick={() => goTo(step + 1, 'fwd')}
                                className="flex items-center gap-2 bg-slate-900 hover:bg-black text-white px-5 py-2.5 rounded-xl text-sm font-bold transition-all hover:-translate-y-px">
                                Next <ArrowRight size={13} />
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};