import { useCallback, useEffect, useState, useRef } from 'react';
import { RefreshCw, Pause, Play, Search, AlertCircle } from 'lucide-react';
import { adminApi } from '../../api/client';

export const AdminLogs = () => {
    const [logs, setLogs] = useState<string[]>([]);
    const [filter, setFilter] = useState("");
    const [loading, setLoading] = useState(true);
    const [isPaused, setIsPaused] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    const filteredLogs = Array.isArray(logs)
        ? logs.filter(line => line.toLowerCase().includes(filter.toLowerCase()))
        : [];

    const fetchLogs = useCallback(async () => {
        if (isPaused) return;

        setLoading(true);
        try {
            const res = await adminApi.getLogs();
            setLogs(res.data.logs);
        } catch (e) {
            console.error("Log fetch error:", e);
            setLogs(["[SYSTEM ERROR]: Unable to reach log stream."]);
        } finally {
            setLoading(false);
        }
    }, [isPaused]);

    useEffect(() => {
        fetchLogs();
        const interval = setInterval(fetchLogs, 3000);
        return () => clearInterval(interval);
    }, [fetchLogs]);

    useEffect(() => {
        if (scrollRef.current && !isPaused) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs, isPaused]);

    const getLogColor = (line: string) => {
        const lower = line.toLowerCase();
        if (lower.includes('error') || lower.includes('critical')) return 'text-red-400 font-bold';
        if (lower.includes('warning')) return 'text-amber-400';
        if (lower.includes('info')) return 'text-emerald-400';
        return 'text-slate-400';
    };

    return (
        <div className="bg-slate-900 rounded-2xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col h-[650px] animate-in fade-in duration-500">
            {/* Terminal Header */}
            <div className="bg-slate-800/80 p-4 flex flex-col md:flex-row justify-between items-center gap-4 border-b border-slate-700">
                <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-500/80" />
                        <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                        <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                    </div>
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] ml-2">Kernel_Log_Monitor</span>
                </div>

                <div className="flex items-center gap-2 w-full md:w-auto">
                    {/* Search Bar */}
                    <div className="relative flex-1 md:w-64">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
                        <input
                            type="text"
                            placeholder="Filter logs (e.g. 'error')..."
                            value={filter}
                            onChange={(e) => setFilter(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-9 pr-4 py-1.5 text-xs text-slate-300 outline-none focus:ring-1 focus:ring-cyan-500 transition-all"
                        />
                    </div>

                    {/* Controls */}
                    <button
                        onClick={() => setIsPaused(!isPaused)}
                        className={`p-2 rounded-lg transition-all flex items-center gap-2 text-xs font-bold ${isPaused ? 'bg-cyan-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                            }`}
                    >
                        {isPaused ? <Play size={14} fill="currentColor" /> : <Pause size={14} fill="currentColor" />}
                        {isPaused ? 'RESUME' : 'FREEZE'}
                    </button>

                    <button onClick={fetchLogs} className="p-2 bg-slate-700 text-slate-300 hover:bg-slate-600 rounded-lg">
                        <RefreshCw size={14} className={loading && !isPaused ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            {/* Log Output */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-6 font-mono text-[11px] leading-relaxed selection:bg-cyan-500/30"
            >
                {filteredLogs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-slate-600 gap-2">
                        <AlertCircle size={24} />
                        <p className="italic">{filter ? 'No logs match your filter.' : 'Awaiting system output...'}</p>
                    </div>
                ) : (
                    filteredLogs.map((line, i) => (
                        <div key={i} className="group flex gap-4 border-b border-slate-800/30 py-0.5 hover:bg-white/5 transition-colors">
                            <span className="text-slate-700 select-none min-w-[30px]">{i + 1}</span>
                            <span className={`${getLogColor(line)} break-all`}>{line}</span>
                        </div>
                    ))
                )}
            </div>

            {/* Status Footer */}
            <div className="bg-slate-800/30 px-6 py-2 border-t border-slate-800 flex justify-between items-center">
                <div className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-tighter">
                    <span className="text-slate-500">Buffer: {logs.length} Lines</span>
                    <span className={isPaused ? "text-amber-500" : "text-emerald-500"}>
                        {isPaused ? "• PAUSED" : "• STREAMING"}
                    </span>
                </div>
                <span className="text-[10px] text-slate-600 font-mono italic">
                    {new Date().toLocaleTimeString()}
                </span>
            </div>
        </div>
    );
};