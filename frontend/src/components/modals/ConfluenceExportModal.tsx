import { useState, useEffect } from 'react';
import { X, Loader2, ExternalLink, CheckCircle2, AlertCircle, ChevronDown } from 'lucide-react';
import { api } from '../../api/client';

type Preset = 'internal_tech_review' | 'executive_presentation' | 'public_documentation';

interface ConfluenceExportStatus {
    exported: boolean;
    page_id: string | null;
    page_url: string | null;
    space_key: string | null;
    exported_at: string | null;
}

interface ExportResult {
    page_id: string;
    page_url: string;
    title: string;
    preset: string;
    space_key: string;
}

interface Props {
    proposalId: number;
    isOpen: boolean;
    onClose: () => void;
}

const PRESETS: { value: Preset; label: string; description: string; audience: string }[] = [
    {
        value: 'internal_tech_review',
        label: 'Internal Tech Review',
        description: 'Full content — architecture, risks, trade-offs, persona reasoning',
        audience: 'Engineering team, Tech Leads, Architects',
    },
    {
        value: 'executive_presentation',
        label: 'Executive Presentation',
        description: 'Executive summary + key risks + timeline only',
        audience: 'CTO, VP Engineering, Product leadership',
    },
    {
        value: 'public_documentation',
        label: 'Public Documentation',
        description: 'Architecture spec only — no internal data or sentiment',
        audience: 'External teams, vendors, public wiki',
    },
];

export const ConfluenceExportModal = ({ proposalId, isOpen, onClose }: Props) => {
    const [spaceKey, setSpaceKey] = useState('');
    const [preset, setPreset] = useState<Preset>('internal_tech_review');
    const [loading, setLoading] = useState(false);
    const [statusLoading, setStatusLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [status, setStatus] = useState<ConfluenceExportStatus | null>(null);
    const [result, setResult] = useState<ExportResult | null>(null);
    const [presetOpen, setPresetOpen] = useState(false);

    useEffect(() => {
        if (!isOpen) return;
        setResult(null);
        setError(null);

        const loadStatus = async () => {
            setStatusLoading(true);
            try {
                const res = await api.get<ConfluenceExportStatus>(
                    `/proposals/${proposalId}/confluence/status`
                );
                setStatus(res.data);
                if (res.data.space_key) setSpaceKey(res.data.space_key);
            } catch {
                setStatus(null);
            } finally {
                setStatusLoading(false);
            }
        };
        loadStatus();
    }, [isOpen, proposalId]);

    const handleExport = async () => {
        const key = spaceKey.trim().toUpperCase();
        if (!key) { setError('Please enter a Confluence space key.'); return; }

        setLoading(true);
        setError(null);

        try {
            const res = await api.post<ExportResult>(
                `/proposals/${proposalId}/export/confluence`,
                { space_key: key, preset }
            );
            setResult(res.data);
            setStatus({
                exported: true,
                page_id: res.data.page_id,
                page_url: res.data.page_url,
                space_key: res.data.space_key,
                exported_at: new Date().toISOString(),
            });
        } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: string } } };
            setError(e?.response?.data?.detail || 'Confluence export failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const selectedPreset = PRESETS.find(p => p.value === preset)!;

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={e => { if (e.target === e.currentTarget) onClose(); }}
        >
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg animate-in zoom-in-95 duration-200 border border-slate-100">

                {/* Header */}
                <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 rounded-t-2xl">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-[#0052CC] flex items-center justify-center shrink-0">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                                <path d="M11.53 2C6.29 2 2 6.29 2 11.53s4.29 9.53 9.53 9.53 9.53-4.29 9.53-9.53S16.77 2 11.53 2zm0 17.06A7.53 7.53 0 1 1 11.53 4a7.53 7.53 0 0 1 0 15.06zm3.54-9.53h-2.01V7.51a1.53 1.53 0 0 0-3.06 0v2.02H7.99a1.53 1.53 0 0 0 0 3.06h2.01v2.01a1.53 1.53 0 0 0 3.06 0V12.6h2.01a1.53 1.53 0 0 0 0-3.07z" />
                            </svg>
                        </div>
                        <h3 className="font-bold text-lg text-slate-800">Export to Confluence</h3>
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
                                    Page exists in space{' '}
                                    <span className="font-mono font-bold">{status.space_key}</span>.{' '}
                                    <a href={status.page_url ?? '#'} target="_blank" rel="noopener noreferrer"
                                        className="font-bold hover:underline flex-inline items-center gap-1">
                                        View page <ExternalLink size={11} className="inline" />
                                    </a>
                                </p>
                                <p className="text-emerald-600 text-xs mt-1">You can export again to create a new page.</p>
                            </div>
                        </div>
                    )}

                    {/* Success result */}
                    {result && (
                        <div className="flex items-start gap-3 p-4 bg-emerald-50 border border-emerald-100 rounded-xl">
                            <CheckCircle2 size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                            <div>
                                <p className="font-bold text-emerald-800 mb-1">Export successful</p>
                                <a href={result.page_url} target="_blank" rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1.5 text-sm font-bold text-emerald-700 hover:text-emerald-900">
                                    View in Confluence <ExternalLink size={12} />
                                </a>
                                <p className="text-xs text-emerald-600 mt-1 font-mono">{result.title}</p>
                            </div>
                        </div>
                    )}

                    {/* Export form */}
                    {!result && (
                        <>
                            {/* Space key */}
                            <div>
                                <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2">
                                    Confluence Space Key <span className="text-red-400">*</span>
                                </label>
                                <input
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-[#0052CC]/20 focus:border-[#0052CC] outline-none transition-all font-mono font-bold text-slate-900 uppercase placeholder:normal-case placeholder:font-normal placeholder:text-slate-400"
                                    placeholder="e.g. ARCH"
                                    value={spaceKey}
                                    onChange={e => setSpaceKey(e.target.value.toUpperCase())}
                                    onKeyDown={e => e.key === 'Enter' && !presetOpen && handleExport()}
                                    maxLength={50}
                                    disabled={loading}
                                />
                                <p className="text-xs text-slate-400 mt-1.5">
                                    Find this in your Confluence space URL: /wiki/spaces/<strong>ARCH</strong>/overview
                                </p>
                            </div>

                            {/* Preset selector */}
                            <div>
                                <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2">
                                    Export Preset
                                </label>
                                <div className="relative">
                                    <button
                                        type="button"
                                        onClick={() => setPresetOpen(v => !v)}
                                        disabled={loading}
                                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-left flex items-center justify-between hover:bg-white hover:border-slate-300 transition-all disabled:opacity-50"
                                    >
                                        <div>
                                            <p className="font-bold text-slate-900 text-sm">{selectedPreset.label}</p>
                                            <p className="text-xs text-slate-500 mt-0.5">{selectedPreset.audience}</p>
                                        </div>
                                        <ChevronDown size={16} className={`text-slate-400 transition-transform ${presetOpen ? 'rotate-180' : ''}`} />
                                    </button>

                                    {presetOpen && (
                                        <div className="absolute bottom-full left-0 right-0 mb-1 bg-white border border-slate-200 rounded-xl shadow-lg z-50 overflow-hidden">
                                            {PRESETS.map(p => (
                                                <button
                                                    key={p.value}
                                                    type="button"
                                                    onClick={() => { setPreset(p.value); setPresetOpen(false); }}
                                                    className={`w-full px-4 py-3 text-left hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0 ${preset === p.value ? 'bg-cyan-50/50' : ''}`}
                                                >
                                                    <div className="flex items-start justify-between gap-2">
                                                        <div>
                                                            <p className="font-bold text-slate-900 text-sm">{p.label}</p>
                                                            <p className="text-xs text-slate-500 mt-0.5">{p.description}</p>
                                                            <p className="text-xs text-slate-400 mt-0.5">Audience: {p.audience}</p>
                                                        </div>
                                                        {preset === p.value && (
                                                            <CheckCircle2 size={14} className="text-cyan-600 mt-0.5 shrink-0" />
                                                        )}
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
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
                <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-3 rounded-b-2xl">
                    <button onClick={onClose}
                        className="px-5 py-2.5 text-slate-600 font-bold hover:bg-slate-200 rounded-xl transition-colors">
                        {result ? 'Close' : 'Cancel'}
                    </button>
                    {!result && (
                        <button
                            onClick={handleExport}
                            disabled={loading || !spaceKey.trim() || statusLoading}
                            className="px-6 py-2.5 bg-[#0052CC] hover:bg-[#0747A6] text-white font-bold rounded-xl transition-all disabled:opacity-50 flex items-center gap-2 shadow-sm"
                        >
                            {loading && <Loader2 size={16} className="animate-spin" />}
                            {loading ? 'Exporting…' : status?.exported ? 'Re-export' : 'Export to Confluence'}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};