import { useEffect, useState } from 'react';
import { adminApi } from '../../api/client';
import { CheckCircle2, AlertCircle, Database, FileText } from 'lucide-react';
import type { VerificationData } from '../../types';


export const AdminVerification = () => {
    const [data, setData] = useState<VerificationData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchVerification = async () => {
            try {
                setLoading(true);
                setError(null);
                const res = await adminApi.getVerification();
                setData(res);
            } catch (e: unknown) {
                const error = e as { response?: { status?: number } };
                console.error('Verification fetch error:', error);
                setError(error?.response?.status === 404
                    ? 'Verification endpoint not found. Check router paths.'
                    : 'Failed to load verification data.');
            } finally {
                setLoading(false);
            }
        };
        fetchVerification();
    }, []);

    if (loading) {
        return (
            <div className="space-y-6">
                {/* Stat Cards Skeleton */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {[1, 2].map(i => (
                        <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 h-[100px] animate-pulse flex justify-between items-center">
                            <div className="space-y-2 w-1/2">
                                <div className="h-3 bg-slate-100 rounded w-3/4"></div>
                                <div className="h-8 bg-slate-100 rounded w-1/2"></div>
                            </div>
                            <div className="w-8 h-8 bg-slate-100 rounded-full"></div>
                        </div>
                    ))}
                </div>

                {/* Table Skeleton */}
                <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden min-h-[250px] animate-pulse">
                    <div className="h-12 bg-slate-50 border-b border-slate-200"></div>
                    <div className="p-4 space-y-4">
                        {[1, 2, 3].map(i => (
                            <div key={i} className="flex justify-between items-center pb-4 border-b border-slate-100">
                                <div className="h-4 bg-slate-100 rounded w-1/3"></div>
                                <div className="h-4 bg-slate-100 rounded w-1/4"></div>
                                <div className="h-4 bg-slate-100 rounded w-1/6"></div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 bg-red-50 text-red-600 rounded-xl border border-red-100 flex items-center gap-2">
                <AlertCircle size={18} />
                <span>{error}</span>
            </div>
        );
    }

    if (!data || !data.documents) {
        return (
            <div className="p-8 text-slate-500 bg-slate-50 rounded-xl border border-slate-200 text-center">
                No verification data available at this time.
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="bg-cyan-50 p-4 rounded-xl border border-cyan-100 flex justify-between items-center">
                    <div>
                        <p className="text-cyan-600 text-xs font-bold uppercase">Total Chunks</p>
                        <h2 className="text-2xl font-black text-cyan-900">{data.total_chunks}</h2>
                    </div>
                    <Database className="text-cyan-200" size={32} />
                </div>

                <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-100 flex justify-between items-center">
                    <div>
                        <p className="text-emerald-600 text-xs font-bold uppercase">Total Documents</p>
                        <h2 className="text-2xl font-black text-emerald-900">{data.total_documents}</h2>
                    </div>
                    <FileText className="text-emerald-200" size={32} />
                </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                            <th className="p-4 text-xs font-bold text-slate-500 uppercase">Document Name</th>
                            <th className="p-4 text-xs font-bold text-slate-500 uppercase">Uploaded</th>
                            <th className="p-4 text-xs font-bold text-slate-500 uppercase">Chunks</th>
                            <th className="p-4 text-xs font-bold text-slate-500 uppercase">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.documents.map((doc) => (
                            <tr key={doc.filename} className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors">
                                <td className="p-4 font-medium text-slate-700">{doc.filename}</td>
                                <td className="p-4 text-sm text-slate-500">
                                    {new Date(doc.created_at).toLocaleDateString()}
                                </td>
                                <td className="p-4 text-slate-600">
                                    <div className="flex items-center gap-2">
                                        <Database size={14} className="text-slate-400" />
                                        {doc.chunk_count}
                                    </div>
                                </td>
                                <td className="p-4">
                                    {doc.status === 'COMPLETED' ? (
                                        <span className="text-emerald-600 bg-emerald-50 px-2 py-1 rounded text-xs font-bold flex items-center gap-1 w-fit">
                                            <CheckCircle2 size={12} /> Verified
                                        </span>
                                    ) : (
                                        <span className="text-amber-600 bg-amber-50 px-2 py-1 rounded text-xs font-bold flex items-center gap-1 w-fit">
                                            <AlertCircle size={12} /> {doc.status}
                                        </span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};