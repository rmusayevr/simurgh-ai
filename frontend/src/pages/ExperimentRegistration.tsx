import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, AlertCircle, Loader2, BookOpen, Clock, Shield, Users } from 'lucide-react';
import { experimentApi } from '../api/client';
import type { ParticipantCreate } from '../types';
import { ExperienceLevel, ExperienceLevelLabels } from '../types';

// ─── Sub-components ───────────────────────────────────────────────────────────

function ConsentCheckbox({
    id,
    label,
    checked,
    onChange,
}: {
    id: string;
    label: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
}) {
    return (
        <label
            htmlFor={id}
            className="flex items-start gap-3 cursor-pointer group"
        >
            <div className="relative mt-0.5 shrink-0">
                <input
                    id={id}
                    type="checkbox"
                    checked={checked}
                    onChange={e => onChange(e.target.checked)}
                    className="peer sr-only"
                />
                <div className="w-5 h-5 rounded border-2 border-slate-300 peer-checked:border-cyan-600 peer-checked:bg-cyan-600 transition-colors flex items-center justify-center">
                    {checked && (
                        <svg className="w-3 h-3 text-white" viewBox="0 0 12 10" fill="none">
                            <path d="M1 5l3.5 3.5L11 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    )}
                </div>
            </div>
            <span className="text-slate-700 group-hover:text-slate-900 transition-colors leading-snug">
                {label}
            </span>
        </label>
    );
}

function LikertScale({
    value,
    onChange,
    lowLabel,
    highLabel,
}: {
    value: number | null;
    onChange: (v: number) => void;
    lowLabel: string;
    highLabel: string;
}) {
    return (
        <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400 w-28 shrink-0">{lowLabel}</span>
                <div className="flex flex-1 justify-between gap-1">
                    {[1, 2, 3, 4, 5, 6, 7].map(n => (
                        <button
                            key={n}
                            type="button"
                            onClick={() => onChange(n)}
                            className={`
                                w-9 h-9 rounded-lg text-sm font-bold border-2 transition-all
                                ${value === n
                                    ? 'bg-cyan-600 border-cyan-600 text-white shadow-md scale-110'
                                    : 'bg-white border-slate-200 text-slate-500 hover:border-cyan-300 hover:text-cyan-600'
                                }
                            `}
                        >
                            {n}
                        </button>
                    ))}
                </div>
                <span className="text-xs text-slate-400 w-28 shrink-0 text-right">{highLabel}</span>
            </div>
        </div>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function ExperimentRegistration() {
    const navigate = useNavigate();

    // Consent state
    const [consent1, setConsent1] = useState(false);
    const [consent2, setConsent2] = useState(false);
    const [consent3, setConsent3] = useState(false);

    // Demographics state
    const [experienceLevel, setExperienceLevel] = useState<ExperienceLevel | ''>('');
    const [yearsExperience, setYearsExperience] = useState<string>('');
    const [aiLikert, setAiLikert] = useState<number | null>(null);

    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const allConsentGiven = consent1 && consent2 && consent3;
    const canSubmit =
        allConsentGiven &&
        experienceLevel !== '' &&
        yearsExperience !== '' &&
        parseInt(yearsExperience) >= 0 &&
        aiLikert !== null;

    const handleSubmit = async () => {
        if (!canSubmit) {
            setError('Please complete all fields and tick all consent checkboxes before continuing.');
            return;
        }

        setSubmitting(true);
        setError('');

        const payload: ParticipantCreate = {
            experience_level: experienceLevel as ExperienceLevel,
            years_experience: parseInt(yearsExperience),
            familiarity_with_ai: aiLikert!,
            consent_given: true,
        };

        try {
            await experimentApi.register(payload);
            navigate('/experiment');
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: unknown } } };
            const msg = error?.response?.data?.detail ?? 'Registration failed. Please try again.';
            setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 py-12 px-4">
            <div className="max-w-2xl mx-auto space-y-8">

                {/* ── Header ── */}
                <div className="text-center space-y-3">
                    <div className="inline-flex items-center gap-2 bg-cyan-50 text-cyan-700 px-4 py-1.5 rounded-full text-sm font-semibold border border-cyan-100">
                        <BookOpen size={15} />
                        Master's Thesis Research Study
                    </div>
                    <h1 className="text-3xl font-bold text-slate-900">
                        AI for Software Architecture
                    </h1>
                    <p className="text-slate-500 text-lg">
                        Eötvös Loránd University · Computer Science MSc
                    </p>
                </div>

                {/* ── Study Info ── */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h2 className="font-bold text-slate-900 text-lg mb-4">About this study</h2>
                    <p className="text-slate-600 leading-relaxed mb-5">
                        This study evaluates whether a <strong>multi-agent AI system</strong> — where
                        three AI personas debate architectural trade-offs — produces more trustworthy
                        proposals than a single AI agent. You will review AI-generated proposals for
                        two software architecture scenarios and rate them on a short questionnaire.
                    </p>
                    <div className="grid grid-cols-3 gap-4">
                        {[
                            { icon: <Clock size={18} className="text-cyan-500" />, label: 'Time required', value: '30–40 minutes' },
                            { icon: <Shield size={18} className="text-emerald-500" />, label: 'Your data', value: 'Anonymised in publication' },
                            { icon: <Users size={18} className="text-amber-500" />, label: 'Target group', value: 'Developers & architects' },
                        ].map(item => (
                            <div key={item.label} className="bg-slate-50 rounded-xl p-3 text-center">
                                <div className="flex justify-center mb-1">{item.icon}</div>
                                <div className="text-xs text-slate-400 mb-0.5">{item.label}</div>
                                <div className="text-sm font-semibold text-slate-700">{item.value}</div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* ── Consent ── */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h2 className="font-bold text-slate-900 text-lg mb-1">Informed Consent</h2>
                    <p className="text-slate-500 text-sm mb-5">
                        Please read and tick each statement to confirm your agreement.
                    </p>
                    <div className="space-y-4">
                        <ConsentCheckbox
                            id="consent1"
                            label="I consent to participate in this research study and understand its purpose as described above."
                            checked={consent1}
                            onChange={setConsent1}
                        />
                        <ConsentCheckbox
                            id="consent2"
                            label="I understand that my responses will be recorded, analysed, and reported in anonymised form in a Master's thesis."
                            checked={consent2}
                            onChange={setConsent2}
                        />
                        <ConsentCheckbox
                            id="consent3"
                            label="I understand that I can withdraw from this study at any time without consequence, and that my data will not be used if I withdraw."
                            checked={consent3}
                            onChange={setConsent3}
                        />
                    </div>

                    {allConsentGiven && (
                        <div className="mt-4 flex items-center gap-2 text-emerald-700 bg-emerald-50 px-4 py-2.5 rounded-lg text-sm font-medium border border-emerald-100">
                            <CheckCircle size={16} />
                            All consent items confirmed
                        </div>
                    )}
                </div>

                {/* ── Demographics ── */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h2 className="font-bold text-slate-900 text-lg mb-1">About You</h2>
                    <p className="text-slate-500 text-sm mb-6">
                        Used only for demographic reporting in Chapter 5. Not linked to your responses.
                    </p>

                    <div className="space-y-7">
                        {/* Experience level */}
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-2">
                                What best describes your current role?
                                <span className="text-red-400 ml-1">*</span>
                            </label>
                            <select
                                value={experienceLevel}
                                onChange={e => setExperienceLevel(e.target.value as ExperienceLevel)}
                                className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-slate-800 bg-white focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 outline-none transition"
                            >
                                <option value="" disabled>Select your experience level…</option>
                                {Object.entries(ExperienceLevelLabels).map(([val, label]) => (
                                    <option key={val} value={val}>{label}</option>
                                ))}
                            </select>
                        </div>

                        {/* Years experience */}
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-2">
                                Years of software development experience
                                <span className="text-red-400 ml-1">*</span>
                            </label>
                            <input
                                type="number"
                                min="0"
                                max="50"
                                value={yearsExperience}
                                onChange={e => setYearsExperience(e.target.value)}
                                placeholder="e.g. 3"
                                className="w-32 px-3 py-2.5 border border-slate-200 rounded-lg text-slate-800 focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 outline-none transition"
                            />
                            <span className="ml-2 text-slate-400 text-sm">years</span>
                        </div>

                        {/* AI familiarity */}
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1">
                                How familiar are you with AI coding tools (e.g. ChatGPT, GitHub Copilot, Claude)?
                                <span className="text-red-400 ml-1">*</span>
                            </label>
                            <p className="text-xs text-slate-400 mb-3">
                                This is a Technology Acceptance baseline — it helps control for prior AI enthusiasm in the analysis.
                            </p>
                            <LikertScale
                                value={aiLikert}
                                onChange={setAiLikert}
                                lowLabel="1 — Never used them"
                                highLabel="7 — Use them daily"
                            />
                            {aiLikert !== null && (
                                <p className="mt-2 text-xs text-cyan-600 font-medium">
                                    Selected: {aiLikert}/7
                                </p>
                            )}
                        </div>
                    </div>
                </div>

                {/* ── Error ── */}
                {error && (
                    <div className="flex items-start gap-3 bg-red-50 text-red-700 p-4 rounded-xl border border-red-100">
                        <AlertCircle size={18} className="shrink-0 mt-0.5" />
                        <span className="text-sm">{error}</span>
                    </div>
                )}

                {/* ── Submit ── */}
                <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={submitting || !canSubmit}
                    className={`
                        w-full py-4 rounded-xl font-bold text-white text-lg flex items-center justify-center gap-3 transition-all
                        ${canSubmit && !submitting
                            ? 'bg-cyan-600 hover:bg-cyan-700 shadow-md hover:shadow-lg'
                            : 'bg-slate-300 cursor-not-allowed'
                        }
                    `}
                >
                    {submitting ? (
                        <>
                            <Loader2 size={20} className="animate-spin" />
                            Registering…
                        </>
                    ) : (
                        <>
                            <CheckCircle size={20} />
                            I agree — Start the Study
                        </>
                    )}
                </button>

                {!canSubmit && !submitting && (
                    <p className="text-center text-sm text-slate-400">
                        Complete all fields and tick all consent checkboxes to continue.
                    </p>
                )}

            </div>
        </div>
    );
}