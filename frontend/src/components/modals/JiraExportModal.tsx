import { useState, useEffect } from 'react';
import { X, Loader2, ExternalLink, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../../api/client';

interface JiraExportStatus {
    exported: boolean;
    epic_key: string | null;
    epic_url: string | null;
    project_key: string | null;
    exported_at: string | null;
}

interface ExportResult {
    epic_key: string;
    epic_url: string;
    project_key: string;
    stories: { key: string; url: string; title: string }[];
}

interface Props {
    proposalId: number;
    isOpen: boolean;
    onClose: () => void;
}

export const JiraExportModal = ({ proposalId, isOpen, onClose }: Props) => {
    const [projectKey, setProjectKey] = useState('');
    const [loading, setLoading] = useState(false);
    const [statusLoading, setStatusLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [status, setStatus] = useState<JiraExportStatus | null>(null);
    const [result, setResult] = useState<ExportResult | null>(null);

    useEffect(() => {
        if (!isOpen) return;
        setResult(null);
        setError(null);

        const loadStatus = async () => {
            setStatusLoading(true);
            try {
                const res = await api.get<JiraExportStatus>(`/proposals/${proposalId}/jira/status`);
                setStatus(res.data);
                if (res.data.project_key) setProjectKey(res.data.project_key);
            } catch {
                setStatus(null);
            } finally {
                setStatusLoading(false);
            }
        };
        loadStatus();
    }, [isOpen, proposalId]);

    const handleExport = async () => {
        const key = projectKey.trim().toUpperCase();
        if (!key) { setError('Please enter a Jira project key.'); return; }

        setLoading(true);
        setError(null);

        try {
            const res = await api.post<ExportResult>(`/proposals/${proposalId}/export/jira`, {
                jira_project_key: key,
            });
            setResult(res.data);
            setStatus({
                exported: true,
                epic_key: res.data.epic_key,
                epic_url: res.data.epic_url,
                project_key: res.data.project_key,
                exported_at: new Date().toISOString(),
            });
        } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: string } } };
            setError(e?.response?.data?.detail || 'Jira export failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={e => { if (e.target === e.currentTarget) onClose(); }}
        >
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200 border border-slate-100">

                {/* Header */}
                <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <div className="flex items-center gap-3">
                        {/* Jira logo */}
                        <div className="w-8 h-8 rounded-lg bg-[#0052CC] flex items-center justify-center shrink-0">
                            <svg width="16" height="16" viewBox="0 0 32 32" fill="none">
                                <path d="M15.271 13.219c-.379-.484-1.044-.452-1.44.065L8.073 21.7a.906.906 0 0 0 .729 1.453h6.891a.906.906 0 0 0 .74-.384c1.609-2.31 1.036-7.474-.162-9.55z" fill="#2684FF" />
                                <path d="M15.938 3.26C13.108 7.484 13.264 12.72 15.31 16.7l3.332 6.073a.907.907 0 0 0 .794.477h6.891a.906.906 0 0 0 .73-1.452C26.35 21 16.826 4.633 16.826 4.633c-.213-.368-.619-.574-1.021-.514a.906.906 0 0 0-.867.141z" fill="#2684FF" />
                            </svg>
                        </div>
                        <h3 className="font-bold text-lg text-slate-800">Export to Jira</h3>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-2 rounded-lg hover:bg-slate-100 transition">
                        <X size={18} />
                    </button>
                </div>

                <div className="p-6 space-y-5">

                    {/* Already exported banner */}
                    {!result && status?.exported && (
                        <div className="flex items-start gap-3 p-4 bg-emerald-50 border border-emerald-100 rounded-xl text-sm">
                            <CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                            <div>
                                <p className="font-bold text-emerald-800 mb-1">Already exported</p>
                                <p className="text-emerald-700">
                                    Epic{' '}
                                    <a href={status.epic_url ?? '#'} target="_blank" rel="noopener noreferrer"
                                        className="font-mono font-bold hover:underline">
                                        {status.epic_key}
                                    </a>
                                    {' '}exists in project <span className="font-mono font-bold">{status.project_key}</span>.
                                    You can re-export to create a new epic.
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Success result */}
                    {result && (
                        <div className="space-y-3">
                            <div className="flex items-start gap-3 p-4 bg-emerald-50 border border-emerald-100 rounded-xl">
                                <CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                                <div>
                                    <p className="font-bold text-emerald-800 mb-1">Export successful</p>
                                    <a href={result.epic_url} target="_blank" rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1.5 text-sm font-mono font-bold text-emerald-700 hover:text-emerald-900">
                                        {result.epic_key} <ExternalLink size={12} />
                                    </a>
                                </div>
                            </div>
                            {result.stories.length > 0 && (
                                <div className="border border-slate-200 rounded-xl overflow-hidden">
                                    <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200">
                                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                                            {result.stories.length} stories created
                                        </p>
                                    </div>
                                    <div className="divide-y divide-slate-100">
                                        {result.stories.map(s => (
                                            <div key={s.key} className="flex items-center justify-between px-4 py-2.5">
                                                <span className="text-sm text-slate-700">{s.title}</span>
                                                <a href={s.url} target="_blank" rel="noopener noreferrer"
                                                    className="text-xs font-mono font-bold text-[#0052CC] hover:underline flex items-center gap-1">
                                                    {s.key} <ExternalLink size={10} />
                                                </a>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Export form — always shown so users can re-export */}
                    {!result && (
                        <>
                            <div>
                                <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2">
                                    Jira Project Key <span className="text-red-400">*</span>
                                </label>
                                <input
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-[#0052CC]/20 focus:border-[#0052CC] outline-none transition-all font-mono font-bold text-slate-900 uppercase placeholder:normal-case placeholder:font-normal placeholder:text-slate-400"
                                    placeholder="e.g. PROJ"
                                    value={projectKey}
                                    onChange={e => setProjectKey(e.target.value.toUpperCase())}
                                    onKeyDown={e => e.key === 'Enter' && handleExport()}
                                    maxLength={20}
                                    disabled={loading}
                                />
                                <p className="text-xs text-slate-400 mt-1.5">
                                    Find this in your Jira project URL: jira.atlassian.net/jira/software/projects/<strong>PROJ</strong>/boards
                                </p>
                            </div>

                            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500 space-y-1">
                                <p className="font-bold text-slate-700">What gets exported:</p>
                                <p>• 1 Epic — proposal title + persona + confidence score</p>
                                <p>• Up to 4 Stories — Overview, Architecture, Risks, Timeline</p>
                            </div>

                            {error && (
                                <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-100 rounded-xl text-sm text-red-600">
                                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                                    <p>{error}</p>
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-3">
                    <button onClick={onClose}
                        className="px-5 py-2.5 text-slate-600 font-bold hover:bg-slate-200 rounded-xl transition-colors">
                        {result ? 'Close' : 'Cancel'}
                    </button>
                    {!result && (
                        <button
                            onClick={handleExport}
                            disabled={loading || !projectKey.trim() || statusLoading}
                            className="px-6 py-2.5 bg-[#0052CC] hover:bg-[#0747A6] text-white font-bold rounded-xl transition-all disabled:opacity-50 flex items-center gap-2 shadow-sm"
                        >
                            {loading && <Loader2 size={16} className="animate-spin" />}
                            {loading ? 'Exporting…' : status?.exported ? 'Re-export' : 'Export to Jira'}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};