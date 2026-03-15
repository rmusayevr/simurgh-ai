import React from 'react';
import { Cpu, Activity, List, MessageSquare, ZoomIn, Scale, AlertCircle, Shield, Zap } from 'lucide-react';
import { MermaidDiagram } from '../MermaidDiagram';
import ReactMarkdown from 'react-markdown';

interface DetailModalBodyProps {
    activeView: 'Architecture' | 'Risks' | 'Specs' | 'Chat';
    setActiveView: (view: 'Architecture' | 'Risks' | 'Specs' | 'Chat') => void;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    currentData: any;

    chatHistory: { role: string, content: string }[];
    chatInput: string;
    setChatInput: (val: string) => void;
    handleSendMessage: () => void;
    chatLoading: boolean;
    chatEndRef: React.RefObject<HTMLDivElement | null>;

    onOpenDiagram: () => void;
}

export const DetailModalBody: React.FC<DetailModalBodyProps> = ({
    activeView,
    setActiveView,
    currentData,
    chatHistory,
    chatInput,
    setChatInput,
    handleSendMessage,
    chatLoading,
    chatEndRef,
    onOpenDiagram,
}) => {

    const tabs = [
        { id: 'Architecture', icon: Cpu, desc: "Solution & Diagram" },
        { id: 'Risks', icon: Activity, desc: "Threat Analysis" },
        { id: 'Specs', icon: List, desc: "Key Features" },
        { id: 'Chat', icon: MessageSquare, desc: "Interrogate Agent" }
    ] as const;

    return (
        <div className="flex-1 flex overflow-hidden">
            <div className="w-64 bg-slate-50 border-r border-slate-200 flex flex-col p-4 gap-2 flex-shrink-0">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveView(tab.id)}
                        className={`flex items-center gap-3 px-4 py-4 text-left rounded-xl transition-all duration-200 ${activeView === tab.id
                            ? 'bg-white shadow-sm border border-slate-200 text-blue-600 ring-1 ring-blue-500/20'
                            : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'
                            }`}
                    >
                        <tab.icon size={20} className={activeView === tab.id ? 'text-blue-600' : 'text-slate-400'} />
                        <div>
                            <div className="font-bold text-sm">{tab.id}</div>
                            <div className="text-[10px] opacity-70 font-medium">{tab.desc}</div>
                        </div>
                    </button>
                ))}
            </div>

            <div className="flex-1 overflow-y-auto bg-white relative">

                {activeView === 'Architecture' && (
                    <div className="p-10 max-w-4xl mx-auto space-y-10 animate-in fade-in duration-300">
                        {currentData?.compromise_analysis && currentData.compromise_analysis.strategy && (
                            <div className="bg-gradient-to-br from-cyan-50 to-white border border-cyan-100 rounded-2xl p-6 shadow-sm relative overflow-hidden">
                                <div className="absolute top-0 right-0 p-4 opacity-10">
                                    <Scale size={120} className="text-cyan-600 -rotate-12" />
                                </div>

                                <h4 className="flex items-center gap-2 text-xs font-black text-cyan-600 uppercase tracking-widest mb-4">
                                    <Scale size={16} /> Conflict Resolution Strategy
                                </h4>

                                <div className="relative z-10">
                                    <div className="mb-6">
                                        <h3 className="text-xl font-bold text-slate-800 mb-2">
                                            {currentData.compromise_analysis.strategy}
                                        </h3>
                                        <div className="flex items-center gap-2 text-cyan-700/60 text-sm italic">
                                            <AlertCircle size={14} />
                                            <span>Tension: {currentData.compromise_analysis.conflict_point}</span>
                                        </div>
                                    </div>

                                    <div className="relative mt-8">
                                        {/* Decorative VS Divider */}
                                        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-cyan-100 hidden md:block">
                                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white p-1 rounded-full border border-cyan-100 shadow-sm">
                                                <Scale size={14} className="text-cyan-400" />
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 relative z-10">
                                            {/* LEFT COLUMN: THE CONSERVATIVE PATH */}
                                            <div className="space-y-4">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <Shield size={16} className="text-slate-400" />
                                                    <span className="text-xs font-black text-slate-500 uppercase">Legacy Path</span>
                                                </div>
                                                <div className="bg-emerald-50 border-l-4 border-emerald-400 p-4 rounded-r-xl">
                                                    <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-wider">Win</p>
                                                    <p className="text-sm text-slate-700 font-medium">{currentData.compromise_analysis.benefit_to_legacy}</p>
                                                </div>
                                                <div className="bg-slate-50 border-l-4 border-slate-300 p-4 rounded-r-xl opacity-70">
                                                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Sacrifice</p>
                                                    <p className="text-xs text-slate-600 italic">{currentData.compromise_analysis.concession_from_legacy}</p>
                                                </div>
                                            </div>

                                            {/* RIGHT COLUMN: THE INNOVATION PATH */}
                                            <div className="space-y-4">
                                                <div className="flex items-center gap-2 mb-2 md:justify-end">
                                                    <span className="text-xs font-black text-cyan-500 uppercase">Innovator Path</span>
                                                    <Zap size={16} className="text-cyan-400" />
                                                </div>
                                                <div className="bg-blue-50 border-r-4 border-blue-400 p-4 rounded-l-xl text-right">
                                                    <p className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">Win</p>
                                                    <p className="text-sm text-slate-700 font-medium">{currentData.compromise_analysis.benefit_to_innovator}</p>
                                                </div>
                                                <div className="bg-slate-50 border-r-4 border-slate-300 p-4 rounded-l-xl text-right opacity-70">
                                                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Sacrifice</p>
                                                    <p className="text-xs text-slate-600 italic">{currentData.compromise_analysis.concession_from_innovator}</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="mt-4 p-3 bg-slate-900 rounded-xl">
                                        <p className="text-[10px] font-bold text-cyan-300 uppercase mb-1">Architectural Impact</p>
                                        <p className="text-xs text-slate-300 leading-relaxed">
                                            {currentData.compromise_analysis.long_term_impact}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                            <div className="md:col-span-2 space-y-2">
                                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Problem Analysis</h4>
                                <p className="text-slate-700 italic text-lg leading-relaxed font-serif border-l-4 border-slate-200 pl-4 py-1">
                                    "{currentData?.problem_statement}"
                                </p>
                            </div>
                            <div className="bg-slate-50 p-5 rounded-xl border border-slate-100">
                                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Stack</h4>
                                <div className="flex flex-wrap gap-2">
                                    {currentData?.tech_stack?.split(',').map((tech: string, i: number) => (
                                        <span key={i} className="px-3 py-1 bg-white text-slate-700 text-xs font-bold rounded-lg border border-slate-200 shadow-sm">
                                            {tech.trim()}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div>
                            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">
                                {currentData?.compromise_analysis ? "Implementation Details" : "Strategic Approach"}
                            </h4>
                            <div className="prose prose-slate max-w-none text-slate-600 leading-7">
                                {currentData?.proposed_solution}
                            </div>
                        </div>
                        <div className="border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                            <div className="bg-slate-50 px-4 py-2 border-b border-slate-200 flex justify-between items-center">
                                <span className="text-xs font-bold text-slate-500 uppercase">System Architecture</span>
                                <button onClick={onOpenDiagram} className="text-xs font-bold text-blue-600 flex items-center gap-1 hover:text-blue-700">
                                    <ZoomIn size={14} /> Full Screen
                                </button>
                            </div>
                            <div className="p-6 bg-white flex justify-center cursor-pointer hover:bg-slate-50" onClick={onOpenDiagram}>
                                {currentData?.mermaid_diagram && <MermaidDiagram chart={currentData.mermaid_diagram} />}
                            </div>
                        </div>
                    </div>
                )}

                {activeView === 'Risks' && (
                    <div className="p-10 max-w-3xl mx-auto space-y-6 animate-in fade-in duration-300">
                        <h3 className="text-2xl font-bold text-slate-900 mb-2">Risk Assessment</h3>
                        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                        {currentData?.technical_risks?.map((r: any, i: number) => (
                            <div key={i} className={`p-6 rounded-xl border-l-4 shadow-sm ${r.severity === 'High' ? 'bg-red-50 border-red-500' : 'bg-orange-50 border-orange-400'}`}>
                                <div className="flex justify-between items-start mb-3">
                                    <h4 className="text-lg font-bold text-slate-900">{r.risk}</h4>
                                    <span className="text-xs font-bold uppercase px-2 py-1 bg-white rounded border">{r.severity} Risk</span>
                                </div>
                                <div className="bg-white/60 p-4 rounded-lg text-sm">{r.mitigation}</div>
                            </div>
                        ))}
                    </div>
                )}

                {activeView === 'Specs' && (
                    <div className="p-10 max-w-4xl mx-auto animate-in fade-in duration-300">
                        <h3 className="text-2xl font-bold text-slate-900 mb-8">Feature Specs</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            {currentData?.key_features?.map((f: any, i: number) => (
                                <div key={i} className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm">
                                    <h4 className="font-bold text-slate-900 mb-2">{f.name}</h4>
                                    <p className="text-sm text-slate-500">{f.desc}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {activeView === 'Chat' && (
                    <div className="flex flex-col h-full bg-slate-50 animate-in fade-in duration-300">
                        <div className="flex-1 overflow-y-auto p-8 space-y-6">
                            {chatHistory.length === 0 && <p className="text-center text-slate-400 mt-20">Start the debate.</p>}
                            {chatHistory.map((msg, idx) => (
                                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    <div className={`max-w-[85%] p-4 rounded-2xl shadow-sm text-sm leading-relaxed ${msg.role === 'user'
                                        ? 'bg-blue-600 text-white rounded-br-none'
                                        : 'bg-white border border-slate-200 text-slate-700 rounded-bl-none'
                                        }`}>
                                        <div className="prose prose-sm max-w-none dark:prose-invert">
                                            {msg.role === 'user' ? (
                                                msg.content
                                            ) : (
                                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {chatLoading && (
                                <div className="flex justify-start">
                                    <div className="bg-white p-4 rounded-2xl rounded-bl-none border border-slate-200 shadow-sm flex items-center gap-2">
                                        <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
                                        <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-75" />
                                        <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-150" />
                                    </div>
                                </div>
                            )}
                            <div ref={chatEndRef} />
                        </div>
                        <div className="p-6 bg-white border-t border-slate-200">
                            <div className="flex gap-3">
                                <input
                                    className="flex-1 bg-slate-50 border rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500"
                                    placeholder="Ask a question..."
                                    value={chatInput}
                                    onChange={e => setChatInput(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && handleSendMessage()}
                                />
                                <button onClick={handleSendMessage} className="bg-blue-600 text-white px-6 rounded-xl font-bold hover:bg-blue-700">
                                    Send
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};