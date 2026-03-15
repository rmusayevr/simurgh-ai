import { useEffect, useState } from 'react';
import { adminApi } from '../../api/client';
import { BarChart3, TrendingUp, AlertCircle, FileSearch } from 'lucide-react';
import { StatCard } from '../../pages/AdminPage'; // Adjust if needed

interface AnalyticsData {
    top_referenced_document: string;
    avg_stakeholder_sentiment: number;
}

export const AdminAnalytics = () => {
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const res = await adminApi.getAnalytics();
                setData(res.data as unknown as AnalyticsData);
            } catch {
                setError("Failed to load analytics data.");
            } finally {
                setLoading(false);
            }
        };
        fetchAnalytics();
    }, []);

    if (loading) {
        return (
            <div className="bg-slate-900 p-8 rounded-3xl shadow-xl h-full min-h-[300px] flex flex-col gap-6 animate-pulse">
                {/* Header Skeleton */}
                <div className="flex items-center gap-3">
                    <div className="w-6 h-6 bg-slate-800 rounded-md"></div>
                    <div className="h-5 bg-slate-800 rounded-md w-48"></div>
                </div>

                {/* Top RAG Card Skeleton */}
                <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50 space-y-3">
                    <div className="h-4 bg-slate-700 rounded w-1/3"></div>
                    <div className="h-4 bg-slate-700 rounded w-full"></div>
                </div>

                {/* Sentiment Card Skeleton */}
                <div className="bg-slate-800 rounded-2xl p-5 border border-slate-700 mt-auto">
                    <div className="h-4 bg-slate-700 rounded w-1/2 mb-4"></div>
                    <div className="h-8 bg-slate-700 rounded w-1/3"></div>
                </div>
            </div>
        );
    }
    if (error) return <div className="p-4 bg-red-50 text-red-600 rounded-xl border border-red-100 flex items-center gap-2"><AlertCircle size={18} /><span>{error}</span></div>;
    if (!data) return null;

    return (
        <div className="bg-slate-900 p-8 rounded-3xl text-white shadow-xl h-full">
            <div className="flex items-center gap-3 mb-6">
                <BarChart3 className="text-cyan-400" />
                <h3 className="text-lg font-bold">Agent Experiment Metrics</h3>
            </div>

            <div className="space-y-6">
                <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
                    <div className="flex items-center gap-2 text-slate-400 mb-2">
                        <FileSearch size={16} />
                        <span className="text-xs font-bold uppercase tracking-wider">Top RAG Document</span>
                    </div>
                    <p className="text-cyan-300 font-mono text-sm break-all">
                        {data.top_referenced_document}
                    </p>
                </div>

                <StatCard
                    title="Avg Stakeholder Sentiment"
                    value={`${(data.avg_stakeholder_sentiment * 100).toFixed(0)}%`}
                    icon={TrendingUp}
                    color="bg-emerald-500"
                />
            </div>
        </div>
    );
};