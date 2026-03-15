import { useState, useEffect } from 'react';
import { CheckCircle, Save, ArrowRight, RefreshCw, Shield, Zap, Scale } from 'lucide-react';
import { thesisApi } from '../api/client';
import { InCharacterRating, HallucinationRating } from '../types';
import type { Transcript, PersonaCodingCreate } from '../types';

// Narrow persona type to match PersonaCodingCreate
type ValidPersona = 'LEGACY_KEEPER' | 'INNOVATOR' | 'MEDIATOR';

// Typed coding state — mirrors the required fields of PersonaCodingCreate
interface CodingState {
    in_character: InCharacterRating | '';
    hallucination: HallucinationRating;
    notes: string;
    quality_attributes: string[];
}

const EMPTY_CODING: CodingState = {
    in_character: '',
    hallucination: HallucinationRating.NONE,
    notes: '',
    quality_attributes: [],
};

export function PersonaVerificationTool() {
    const [transcripts, setTranscripts] = useState<Transcript[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [complete, setComplete] = useState(false);
    const [coding, setCoding] = useState<CodingState>(EMPTY_CODING);

    const loadSample = async () => {
        setLoading(true);
        try {
            const data = await thesisApi.getVerificationSample();
            if (data.length === 0) {
                setComplete(true);
            } else {
                setTranscripts(data);
                setCurrentIndex(0);
                setComplete(false);
            }
        } catch (err) {
            console.error('Failed to load sample', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadSample(); }, []);

    const handleAttributeToggle = (attr: string) => {
        setCoding(prev => ({
            ...prev,
            quality_attributes: prev.quality_attributes.includes(attr)
                ? prev.quality_attributes.filter(a => a !== attr)
                : [...prev.quality_attributes, attr],
        }));
    };

    const handleSave = async () => {
        if (!coding.in_character) {
            alert('Please select if the agent was in character.');
            return;
        }

        const current = transcripts[currentIndex];

        // Guard: ensure persona is one of the three valid values
        const validPersonas: ValidPersona[] = ['LEGACY_KEEPER', 'INNOVATOR', 'MEDIATOR'];
        if (!validPersonas.includes(current.persona as ValidPersona)) {
            alert(`Unknown persona "${current.persona}" — cannot submit.`);
            return;
        }

        const payload: PersonaCodingCreate = {
            debate_id: current.debate_id,
            turn_index: current.turn_index,
            persona: (current.persona as string).toLowerCase() as 'legacy_keeper' | 'innovator' | 'mediator',
            in_character: coding.in_character,   // narrowed above — empty string guarded
            hallucination: coding.hallucination,
            notes: coding.notes || null,
            quality_attributes: coding.quality_attributes,
            bias_alignment: true,                 // default; no UI control yet
            coder_id: 0,                          // overridden server-side from auth token
        };

        setSaving(true);
        try {
            await thesisApi.submitVerification(payload);

            if (currentIndex < transcripts.length - 1) {
                setCurrentIndex(prev => prev + 1);
                setCoding(EMPTY_CODING);
            } else {
                await loadSample();
            }
        } catch (err) {
            console.error('Failed to save', err);
            alert('Failed to save coding. See console for details.');
        } finally {
            setSaving(false);
        }
    };

    if (loading) return (
        <div className="p-12 text-center text-slate-500">Loading sample batch...</div>
    );

    if (complete) return (
        <div className="p-12 text-center bg-emerald-50 rounded-xl border border-emerald-100">
            <CheckCircle size={48} className="mx-auto text-emerald-600 mb-4" />
            <h2 className="text-2xl font-bold text-emerald-900">Coding Complete!</h2>
            <p className="text-emerald-700 mt-2">No more uncoded transcripts found in the current sample set.</p>
            <button onClick={loadSample} className="mt-4 text-emerald-700 font-bold underline flex items-center gap-2 mx-auto">
                <RefreshCw size={14} /> Check for new debates
            </button>
        </div>
    );

    const current = transcripts[currentIndex];
    const attributes = ['Reliability', 'Performance', 'Security', 'Maintainability', 'Scalability', 'Cost', 'Usability'];

    return (
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-8 animate-in fade-in duration-300 h-[calc(100vh-100px)]">

            {/* LEFT: Transcript Viewer */}
            <div className="flex flex-col bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden h-full">
                <div className="p-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <span className="bg-slate-200 text-slate-600 text-xs font-bold px-2 py-1 rounded">
                            Batch: {currentIndex + 1} / {transcripts.length}
                        </span>
                        <span className="text-slate-400 text-sm">Turn #{current.turn_index}</span>
                    </div>
                    <div className="text-xs text-slate-400 font-mono">{current.debate_id.slice(0, 8)}...</div>
                </div>

                <div className="flex-1 p-8 overflow-y-auto">
                    <div className="flex items-center gap-3 mb-6">
                        <div className={`p-3 rounded-xl border ${current.persona === 'LEGACY_KEEPER' ? 'bg-blue-50 border-blue-100 text-blue-700' :
                                current.persona === 'INNOVATOR' ? 'bg-orange-50 border-orange-100 text-orange-700' :
                                    'bg-purple-50 border-purple-100 text-purple-700'
                            }`}>
                            {current.persona === 'LEGACY_KEEPER' && <Shield size={24} />}
                            {current.persona === 'INNOVATOR' && <Zap size={24} />}
                            {current.persona === 'MEDIATOR' && <Scale size={24} />}
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900 capitalize">
                                {current.persona.replace('_', ' ')}
                            </h2>
                            <p className="text-slate-500 text-sm">Analysis Target</p>
                        </div>
                    </div>

                    <div className="prose prose-slate max-w-none">
                        <p className="text-lg leading-relaxed whitespace-pre-wrap text-slate-800">
                            {current.response}
                        </p>
                    </div>
                </div>
            </div>

            {/* RIGHT: Coding Panel */}
            <div className="flex flex-col h-full space-y-6">
                <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex-1 flex flex-col">
                    <div className="flex items-center gap-2 mb-6 border-b border-slate-100 pb-4">
                        <div className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center font-bold">RQ2</div>
                        <h3 className="font-bold text-slate-900">Persona Verification Coding</h3>
                    </div>

                    <div className="space-y-8 flex-1 overflow-y-auto pr-2">

                        {/* 1. Character Consistency */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 uppercase mb-3">
                                1. Did the agent stay in character?
                            </label>
                            <div className="grid grid-cols-3 gap-3">
                                {([InCharacterRating.YES, InCharacterRating.PARTIAL, InCharacterRating.NO] as const).map(opt => (
                                    <button
                                        key={opt}
                                        onClick={() => setCoding(prev => ({ ...prev, in_character: opt }))}
                                        className={`py-3 px-4 rounded-xl border font-medium capitalize transition-all ${coding.in_character === opt
                                                ? 'bg-indigo-600 text-white border-indigo-600 shadow-md scale-105'
                                                : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300'
                                            }`}
                                    >
                                        {opt}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* 2. Quality Attributes */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 uppercase mb-3">
                                2. Mentioned Quality Attributes
                            </label>
                            <div className="flex flex-wrap gap-2">
                                {attributes.map(attr => (
                                    <button
                                        key={attr}
                                        onClick={() => handleAttributeToggle(attr)}
                                        className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${coding.quality_attributes.includes(attr)
                                                ? 'bg-blue-100 text-blue-800 border-blue-200'
                                                : 'bg-slate-50 text-slate-500 border-slate-200 hover:bg-slate-100'
                                            }`}
                                    >
                                        {attr}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* 3. Hallucinations */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 uppercase mb-3">
                                3. Hallucination Check
                            </label>
                            <select
                                value={coding.hallucination}
                                onChange={e => setCoding(prev => ({
                                    ...prev,
                                    hallucination: e.target.value as HallucinationRating,
                                }))}
                                className="w-full p-3 rounded-xl border border-slate-200 bg-slate-50 focus:ring-2 focus:ring-indigo-500 outline-none"
                            >
                                <option value={HallucinationRating.NONE}>No hallucination detected</option>
                                <option value={HallucinationRating.MINOR}>Minor inaccuracy (dates/names)</option>
                                <option value={HallucinationRating.MAJOR}>Major hallucination (invented facts/docs)</option>
                            </select>
                        </div>

                        {/* 4. Notes */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 uppercase mb-3">
                                4. Qualitative Notes
                            </label>
                            <textarea
                                value={coding.notes}
                                onChange={e => setCoding(prev => ({ ...prev, notes: e.target.value }))}
                                placeholder="Context, reasoning, or specific anomalies..."
                                className="w-full p-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-indigo-500 outline-none h-32 resize-none"
                            />
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="pt-6 mt-6 border-t border-slate-100">
                        <button
                            onClick={handleSave}
                            disabled={saving || !coding.in_character}
                            className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold text-lg hover:bg-black transition flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {saving ? <RefreshCw className="animate-spin" /> : <Save />}
                            Save Coding & Next
                            <ArrowRight size={20} />
                        </button>
                        {!coding.in_character && (
                            <p className="text-center text-xs text-slate-400 mt-2">
                                Select a character consistency rating to continue
                            </p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
