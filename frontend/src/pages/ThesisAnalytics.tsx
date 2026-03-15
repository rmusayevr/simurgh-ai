import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Download, TrendingUp, Users, Activity, ShieldCheck, MessageSquareText, Loader2, ChevronDown, ChevronUp, ThumbsUp, ThumbsDown, Minus } from 'lucide-react';
import { evaluationApi, thesisApi } from '../api/client';
import type { ThematicTheme } from '../types';

export function ThesisAnalytics() {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        evaluationApi.exportResponses(false)
            .then(data => setStats(data))
            .catch(() => setError('Failed to load research data.'))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="p-8 text-center text-slate-500">Loading Research Data...</div>;
    if (error) return <div className="p-8 text-center text-red-500">{error}</div>;

    const baselineMeans = stats?.baseline_means ?? {};
    const multiagentMeans = stats?.multiagent_means ?? {};

    const comparisonChartData = [
        { name: 'Overall Trust', Baseline: baselineMeans.trust_overall ?? 0, MultiAgent: multiagentMeans.trust_overall ?? 0 },
        { name: 'Risk Awareness', Baseline: baselineMeans.risk_awareness ?? 0, MultiAgent: multiagentMeans.risk_awareness ?? 0 },
        { name: 'Actionability', Baseline: baselineMeans.actionability ?? 0, MultiAgent: multiagentMeans.actionability ?? 0 },
    ];

    const trustDiff = (stats?.mean_difference ?? 0);

    return (
        <div className="max-w-7xl mx-auto p-6 space-y-8 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex justify-between items-center bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Thesis Data Dashboard</h1>
                    <p className="text-slate-500">Real-time analysis for Chapter 5 (Results)</p>
                </div>
                <button
                    onClick={() => thesisApi.downloadThesisZip()}
                    className="flex items-center gap-2 bg-cyan-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-cyan-700 transition"
                >
                    <Download size={18} /> Export ZIP for SPSS/R
                </button>
            </div>

            {/* Key Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <MetricCard
                    label="Total Responses"
                    value={stats?.total_responses ?? 0}
                    icon={<Users size={20} className="text-blue-600" />}
                />
                <MetricCard
                    label="Valid Responses"
                    value={stats?.valid_responses ?? 0}
                    subvalue={`${stats?.invalid_count ?? 0} flagged invalid`}
                    icon={<ShieldCheck size={20} className="text-emerald-600" />}
                />
                <MetricCard
                    label="Multi-Agent Mean Trust"
                    value={(stats?.multiagent_mean_trust ?? 0).toFixed(2)}
                    subvalue={`n=${stats?.multiagent_count ?? 0}`}
                    icon={<Activity size={20} className="text-cyan-600" />}
                />
                <MetricCard
                    label="Trust Δ (Multi − Baseline)"
                    value={`${trustDiff >= 0 ? '+' : ''}${trustDiff.toFixed(2)}`}
                    icon={<TrendingUp size={20} className="text-amber-600" />}
                />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm h-[400px]">
                    <h3 className="font-bold text-slate-900 mb-6 flex items-center gap-2">
                        <Activity size={20} className="text-slate-400" />
                        Condition Comparison (Likert 1–7)
                    </h3>
                    <ResponsiveContainer width="100%" height="85%">
                        <BarChart data={comparisonChartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                            <XAxis dataKey="name" />
                            <YAxis domain={[0, 7]} />
                            <Tooltip cursor={{ fill: '#f8fafc' }} />
                            <Legend />
                            <Bar dataKey="Baseline" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="MultiAgent" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm h-[400px] overflow-y-auto">
                    <h3 className="font-bold text-slate-900 mb-4">Live Hypothesis Tracking</h3>
                    <div className="space-y-4">
                        <HypothesisCheck
                            id="H1"
                            text="Multi-agent proposals are perceived as less risky."
                            confirmed={(multiagentMeans.risk_awareness ?? 0) > (baselineMeans.risk_awareness ?? 0)}
                            diff={(multiagentMeans.risk_awareness ?? 0) - (baselineMeans.risk_awareness ?? 0)}
                        />
                        <HypothesisCheck
                            id="H2"
                            text="Multi-agent system creates higher trust."
                            confirmed={trustDiff > 0}
                            diff={trustDiff}
                        />
                        <HypothesisCheck
                            id="H3"
                            text="Multi-agent proposals are more actionable."
                            confirmed={(multiagentMeans.actionability ?? 0) > (baselineMeans.actionability ?? 0)}
                            diff={(multiagentMeans.actionability ?? 0) - (baselineMeans.actionability ?? 0)}
                        />
                    </div>
                    <div className="mt-6 p-4 bg-slate-50 rounded-lg text-xs text-slate-500">
                        * Statistical significance (p-value) must be verified in SPSS/R using the ZIP export.
                    </div>
                </div>
            </div>

            {/* Thematic Analysis */}
            <ThematicAnalysisPanel />
        </div>
    );
}

// ─── Thematic Analysis Panel ─────────────────────────────────────────────────

type AnalysisField = 'what_worked_well' | 'what_could_improve' | 'additional_comments';

const FIELD_LABELS: Record<AnalysisField, string> = {
    what_worked_well: 'What worked well?',
    what_could_improve: 'What could improve?',
    additional_comments: 'Additional comments',
};

function ThematicAnalysisPanel() {
    const [field, setField] = useState<AnalysisField>('what_worked_well');
    const [running, setRunning] = useState(false);
    const [result, setResult] = useState<{ field: string; response_count: number; themes: ThematicTheme[] } | null>(null);
    const [error, setError] = useState('');
    const [expanded, setExpanded] = useState<number | null>(null);

    const run = async () => {
        setRunning(true);
        setResult(null);
        setError('');
        setExpanded(null);
        try {
            const data = await thesisApi.runThematicAnalysis(field);
            setResult(data);
        } catch (e: unknown) {
            const error = e as { response?: { data?: { detail?: string } } };
            setError(error?.response?.data?.detail ?? 'Analysis failed. Check backend logs.');
        } finally {
            setRunning(false);
        }
    };

    const sentimentIcon = (s: string) => {
        if (s === 'positive') return <ThumbsUp size={14} className="text-emerald-500" />;
        if (s === 'negative') return <ThumbsDown size={14} className="text-red-400" />;
        return <Minus size={14} className="text-slate-400" />;
    };

    return (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-violet-100 rounded-lg">
                        <MessageSquareText size={20} className="text-violet-600" />
                    </div>
                    <div>
                        <h3 className="font-bold text-slate-900">Thematic Analysis</h3>
                        <p className="text-xs text-slate-500">LLM-assisted inductive coding · Section 3.4.2 · Researcher only</p>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <select
                        value={field}
                        onChange={e => setField(e.target.value as AnalysisField)}
                        className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-slate-50 focus:ring-2 focus:ring-violet-500 outline-none"
                    >
                        {(Object.entries(FIELD_LABELS) as [AnalysisField, string][]).map(([k, v]) => (
                            <option key={k} value={k}>{v}</option>
                        ))}
                    </select>
                    <button
                        onClick={run}
                        disabled={running}
                        className="flex items-center gap-2 bg-violet-600 text-white px-4 py-2 rounded-lg font-bold text-sm hover:bg-violet-700 transition disabled:opacity-60"
                    >
                        {running ? <Loader2 size={16} className="animate-spin" /> : <MessageSquareText size={16} />}
                        {running ? 'Analysing…' : 'Run Analysis'}
                    </button>
                </div>
            </div>

            {error && (
                <div className="p-4 bg-red-50 text-red-600 rounded-xl border border-red-100 text-sm">{error}</div>
            )}

            {result && (
                <div className="space-y-4">
                    <p className="text-sm text-slate-500">
                        Field: <span className="font-semibold text-slate-700">{FIELD_LABELS[result.field as AnalysisField] ?? result.field}</span>
                        {' · '}{result.response_count} responses analysed · {result.themes.length} themes identified
                    </p>

                    {result.themes.map((theme, i) => (
                        <div key={i} className="border border-slate-200 rounded-xl overflow-hidden">
                            <button
                                onClick={() => setExpanded(expanded === i ? null : i)}
                                className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition text-left"
                            >
                                <div className="flex items-center gap-3">
                                    {sentimentIcon(theme.sentiment)}
                                    <span className="font-semibold text-slate-800">{theme.name}</span>
                                    <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">
                                        n={theme.frequency}
                                    </span>
                                </div>
                                {expanded === i ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                            </button>

                            {expanded === i && (
                                <div className="px-4 pb-4 space-y-3 border-t border-slate-100 pt-3">
                                    <p className="text-sm text-slate-600">{theme.description}</p>
                                    {theme.example_quotes.length > 0 && (
                                        <div className="space-y-2">
                                            <p className="text-xs font-bold text-slate-400 uppercase">Example quotes</p>
                                            {theme.example_quotes.map((q, qi) => (
                                                <blockquote key={qi} className="text-sm italic text-slate-600 border-l-2 border-violet-300 pl-3">
                                                    "{q}"
                                                </blockquote>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}

                    <p className="text-xs text-slate-400 pt-2">
                        * AI-generated themes are a starting codebook only. Refine manually before reporting in Chapter 5.
                    </p>
                </div>
            )}

            {!result && !running && !error && (
                <div className="py-8 text-center text-slate-400 text-sm border border-dashed border-slate-200 rounded-xl">
                    Select a survey field and click Run Analysis to extract themes.
                </div>
            )}
        </div>
    );
}

// ─── Subcomponents ────────────────────────────────────────────────────────────
interface MetricCardProps {
    label: string;
    value: React.ReactNode;
    subvalue?: string;
    icon: React.ReactNode;
}

function MetricCard({ label, value, subvalue, icon }: MetricCardProps) {
    return (
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex justify-between items-start mb-2">
                <span className="text-slate-500 font-medium text-xs uppercase">{label}</span>
                <div className="p-2 bg-slate-50 rounded-lg">{icon}</div>
            </div>
            <div className="text-2xl font-bold text-slate-900">{value}</div>
            {subvalue && <div className="text-xs text-slate-400 mt-1">{subvalue}</div>}
        </div>
    );
}

interface HypothesisCheckProps {
    id: string;
    text: string;
    confirmed: boolean;
    diff: number;
}

function HypothesisCheck({ id, text, confirmed, diff }: HypothesisCheckProps) {
    return (
        <div className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${confirmed ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                {id}
            </div>
            <div>
                <p className="text-sm font-medium text-slate-800">{text}</p>
                <p className={`text-xs mt-1 ${confirmed ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {confirmed ? 'Currently Supported' : 'Data Inconclusive'} (Delta: {diff > 0 ? '+' : ''}{diff.toFixed(2)})
                </p>
            </div>
        </div>
    );
}