import React, { useState, useEffect } from 'react';
import { Loader2, DollarSign, Zap, TrendingUp, Database } from 'lucide-react';
import { adminApi } from '../../api/client';
import type { TokenUsageSummary } from '../../types';

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = (n: number) => n.toLocaleString();
const fmtCost = (n: number) =>
    n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;

const StatCard: React.FC<{
    label: string;
    value: string;
    icon: React.ElementType;
    color: string;
}> = ({ label, value, icon: Icon, color }) => (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 flex items-center gap-4">
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
            <Icon size={20} />
        </div>
        <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
            <p className="text-xl font-bold text-slate-900 mt-0.5">{value}</p>
        </div>
    </div>
);

// Simple bar chart using divs — no Chart.js dependency needed
const DailyChart: React.FC<{ data: TokenUsageSummary['daily'] }> = ({ data }) => {
    if (!data.length) return <p className="text-sm text-slate-400 text-center py-8">No data for this period.</p>;
    const max = Math.max(...data.map(d => d.cost_usd), 0.0001);
    return (
        <div className="flex items-end gap-1 h-32">
            {data.map(d => (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group relative">
                    <div
                        className="w-full bg-cyan-500 rounded-t transition-all hover:bg-cyan-600"
                        style={{ height: `${Math.max((d.cost_usd / max) * 112, 2)}px` }}
                    />
                    {/* Tooltip */}
                    <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-slate-900 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none z-10">
                        {d.date}<br />{fmtCost(d.cost_usd)} · {fmt(d.calls)} calls
                    </div>
                </div>
            ))}
        </div>
    );
};

// ── Main component ────────────────────────────────────────────────────────────

export const AdminTokenUsage: React.FC = () => {
    const [data, setData] = useState<TokenUsageSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [days, setDays] = useState(30);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        adminApi.getTokenUsage(days)
            .then(d => { if (!cancelled) { setData(d); setError(null); setLoading(false); } })
            .catch(() => { if (!cancelled) { setError('Failed to load token usage data.'); setLoading(false); } });
        return () => { cancelled = true; };
    }, [days]);

    if (loading) return (
        <div className="flex items-center justify-center py-24">
            <Loader2 size={32} className="animate-spin text-cyan-600" />
        </div>
    );

    if (error || !data) return (
        <div className="text-center py-24 text-slate-400">
            <p>{error ?? 'No data available.'}</p>
        </div>
    );

    return (
        <div className="space-y-6">
            {/* Controls */}
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-slate-900">Token Cost Dashboard</h2>
                <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-500">Last</span>
                    {[7, 30, 90].map(d => (
                        <button
                            key={d}
                            onClick={() => setDays(d)}
                            className={`px-3 py-1.5 rounded-lg text-sm font-bold transition-colors ${days === d
                                ? 'bg-cyan-600 text-white'
                                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                }`}
                        >
                            {d}d
                        </button>
                    ))}
                </div>
            </div>

            {/* Stat cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard label="Total cost" value={fmtCost(data.total_cost_usd)} icon={DollarSign} color="bg-emerald-100 text-emerald-600" />
                <StatCard label="API calls" value={fmt(data.total_calls)} icon={Zap} color="bg-cyan-100 text-cyan-600" />
                <StatCard label="Input tokens" value={fmt(data.total_input_tokens)} icon={TrendingUp} color="bg-violet-100 text-violet-600" />
                <StatCard label="Cache reads" value={fmt(data.total_cache_read_tokens)} icon={Database} color="bg-amber-100 text-amber-600" />
            </div>

            {/* Daily chart */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-bold text-slate-700 mb-4">Daily cost (USD)</h3>
                <DailyChart data={data.daily} />
                <div className="flex justify-between mt-2">
                    <span className="text-[10px] text-slate-400">{data.daily[0]?.date ?? ''}</span>
                    <span className="text-[10px] text-slate-400">{data.daily[data.daily.length - 1]?.date ?? ''}</span>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* By operation */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
                    <h3 className="text-sm font-bold text-slate-700 mb-4">Cost by operation</h3>
                    <div className="space-y-3">
                        {data.by_operation.slice(0, 10).map(op => {
                            const pct = data.total_cost_usd > 0
                                ? (op.cost_usd / data.total_cost_usd) * 100
                                : 0;
                            return (
                                <div key={op.operation}>
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="text-xs font-mono text-slate-600 truncate max-w-[60%]">{op.operation}</span>
                                        <div className="flex items-center gap-3">
                                            <span className="text-xs text-slate-400">{fmt(op.calls)} calls</span>
                                            <span className="text-xs font-bold text-slate-700">{fmtCost(op.cost_usd)}</span>
                                        </div>
                                    </div>
                                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                        <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${pct}%` }} />
                                    </div>
                                </div>
                            );
                        })}
                        {!data.by_operation.length && <p className="text-sm text-slate-400 text-center py-4">No operations recorded.</p>}
                    </div>
                </div>

                {/* By user */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
                    <h3 className="text-sm font-bold text-slate-700 mb-4">Cost by user</h3>
                    <div className="space-y-2">
                        {data.by_user.slice(0, 10).map((u, i) => (
                            <div key={u.user_id ?? `bg-${i}`} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                                <div>
                                    <p className="text-xs font-medium text-slate-700 truncate max-w-[200px]">
                                        {u.email ?? 'background task'}
                                    </p>
                                    <p className="text-[10px] text-slate-400">{fmt(u.calls)} calls</p>
                                </div>
                                <span className="text-sm font-bold text-slate-900">{fmtCost(u.cost_usd)}</span>
                            </div>
                        ))}
                        {!data.by_user.length && <p className="text-sm text-slate-400 text-center py-4">No usage recorded.</p>}
                    </div>
                </div>
            </div>

            {/* Cache savings */}
            <div className="bg-slate-50 rounded-2xl border border-slate-200 p-5">
                <h3 className="text-sm font-bold text-slate-700 mb-3">Prompt cache summary</h3>
                <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                        <p className="text-lg font-bold text-slate-900">{fmt(data.total_cache_creation_tokens)}</p>
                        <p className="text-xs text-slate-500">Cache writes</p>
                    </div>
                    <div>
                        <p className="text-lg font-bold text-emerald-600">{fmt(data.total_cache_read_tokens)}</p>
                        <p className="text-xs text-slate-500">Cache hits (cheap)</p>
                    </div>
                    <div>
                        <p className="text-lg font-bold text-slate-900">
                            {data.total_cache_read_tokens + data.total_cache_creation_tokens > 0
                                ? `${Math.round((data.total_cache_read_tokens / (data.total_cache_read_tokens + data.total_cache_creation_tokens)) * 100)}%`
                                : '—'}
                        </p>
                        <p className="text-xs text-slate-500">Hit rate</p>
                    </div>
                </div>
            </div>
        </div>
    );
};