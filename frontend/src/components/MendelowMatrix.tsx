/**
 * MendelowMatrix.tsx
 *
 * Mendelow's Power-Interest Matrix visualisation.
 * Axes: Influence (Y) × Interest (X), both LOW/MEDIUM/HIGH → 3×3 grid.
 * Each cell is colour-coded by strategic zone.
 * Stakeholders are plotted as sentiment-coloured dots with tooltips.
 *
 * --- INTEGRATION ---
 * In ProjectDetails.tsx, above the Stakeholder Directory table:
 *
 *   import { MendelowMatrix } from '../components/MendelowMatrix';
 *   ...
 *   {stakeholders.length > 0 && (
 *       <MendelowMatrix stakeholders={stakeholders} />
 *   )}
 */

import React, { useState } from 'react';
import type { Stakeholder } from '../types';
import { Sentiment, InfluenceLevel, InterestLevel } from '../types';

interface Props {
    stakeholders: Stakeholder[];
}

// ── Grid axis order (LOW → MEDIUM → HIGH, visually bottom-to-top for Y) ──────
const INTEREST_COLS: InterestLevel[] = ['LOW', 'MEDIUM', 'HIGH'];
const INFLUENCE_ROWS: InfluenceLevel[] = ['HIGH', 'MEDIUM', 'LOW']; // top = HIGH

// ── Cell zone config ──────────────────────────────────────────────────────────
interface ZoneConfig {
    label: string;
    sublabel: string;
    bg: string;
    border: string;
    text: string;
}

const ZONE: Record<string, ZoneConfig> = {
    // High influence
    'HIGH-LOW': { label: 'Keep Satisfied', sublabel: 'Manage carefully', bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700' },
    'HIGH-MEDIUM': { label: 'Key Players', sublabel: 'Manage closely', bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700' },
    'HIGH-HIGH': { label: 'Key Players', sublabel: 'Manage closely', bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700' },
    // Medium influence
    'MEDIUM-LOW': { label: 'Monitor', sublabel: 'Minimal effort', bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-500' },
    'MEDIUM-MEDIUM': { label: 'Keep Informed', sublabel: 'Show consideration', bg: 'bg-sky-50', border: 'border-sky-200', text: 'text-sky-700' },
    'MEDIUM-HIGH': { label: 'Key Players', sublabel: 'Manage closely', bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700' },
    // Low influence
    'LOW-LOW': { label: 'Monitor', sublabel: 'Minimal effort', bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-500' },
    'LOW-MEDIUM': { label: 'Keep Informed', sublabel: 'Show consideration', bg: 'bg-sky-50', border: 'border-sky-200', text: 'text-sky-700' },
    'LOW-HIGH': { label: 'Keep Informed', sublabel: 'Show consideration', bg: 'bg-sky-50', border: 'border-sky-200', text: 'text-sky-700' },
};

// ── Sentiment → dot colour ────────────────────────────────────────────────────
const SENTIMENT_DOT: Record<Sentiment, { bg: string; ring: string; label: string }> = {
    CHAMPION: { bg: 'bg-emerald-500', ring: 'ring-emerald-200', label: 'Champion' },
    SUPPORTIVE: { bg: 'bg-green-400', ring: 'ring-green-200', label: 'Supportive' },
    NEUTRAL: { bg: 'bg-slate-400', ring: 'ring-slate-200', label: 'Neutral' },
    CONCERNED: { bg: 'bg-amber-400', ring: 'ring-amber-200', label: 'Concerned' },
    RESISTANT: { bg: 'bg-orange-500', ring: 'ring-orange-200', label: 'Resistant' },
    BLOCKER: { bg: 'bg-red-600', ring: 'ring-red-200', label: 'Blocker' },
};

// ── Stakeholder dot with tooltip ──────────────────────────────────────────────
const StakeholderDot: React.FC<{ person: Stakeholder; index: number; total: number }> = ({
    person, index,
}) => {
    const [hovered, setHovered] = useState(false);
    const dot = SENTIMENT_DOT[person.sentiment];

    // Spread dots within the cell using a small offset based on index
    const offsets = [
        { x: 0, y: 0 }, { x: 14, y: -8 }, { x: -12, y: 10 },
        { x: 16, y: 12 }, { x: -14, y: -10 }, { x: 6, y: 16 },
    ];
    const off = offsets[index % offsets.length];

    return (
        <div
            className="absolute"
            style={{ transform: `translate(${off.x}px, ${off.y}px)` }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            {/* Dot */}
            <div className={`
                w-7 h-7 rounded-full ${dot.bg} ring-2 ${dot.ring}
                flex items-center justify-center cursor-default
                transition-transform duration-150 hover:scale-125 hover:z-50
                shadow-sm text-white font-black text-[10px] select-none
            `}>
                {person.name.charAt(0).toUpperCase()}
            </div>

            {/* Tooltip */}
            {hovered && (
                <div className="absolute z-[200] bottom-full left-1/2 -translate-x-1/2 mb-2 w-44 pointer-events-none"
                    style={{ animation: 'mm-tip 120ms ease both' }}>
                    <div className="bg-slate-900 rounded-xl px-3 py-2.5 shadow-xl">
                        <p className="text-white font-bold text-xs truncate">{person.name}</p>
                        <p className="text-slate-400 text-[11px] truncate">{person.role}</p>
                        <div className="flex items-center gap-1.5 mt-1.5">
                            <div className={`w-2 h-2 rounded-full ${dot.bg}`} />
                            <span className="text-slate-300 text-[11px]">{dot.label}</span>
                        </div>
                        {person.department && (
                            <p className="text-slate-500 text-[10px] mt-1">{person.department}</p>
                        )}
                    </div>
                    <div className="w-0 h-0 border-4 border-transparent border-t-slate-900 absolute top-full left-1/2 -translate-x-1/2" />
                </div>
            )}
        </div>
    );
};

// ── Main component ────────────────────────────────────────────────────────────
export const MendelowMatrix: React.FC<Props> = ({ stakeholders }) => {
    // Group stakeholders by cell key
    const cellMap: Record<string, Stakeholder[]> = {};
    for (const s of stakeholders) {
        const key = `${s.influence}-${s.interest}`;
        if (!cellMap[key]) cellMap[key] = [];
        cellMap[key].push(s);
    }

    const axisLabel = 'text-[10px] font-black uppercase tracking-widest text-slate-400';

    return (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
            <style>{`@keyframes mm-tip{from{opacity:0;transform:translateX(-50%) translateY(4px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}`}</style>

            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-start justify-between">
                <div>
                    <h3 className="font-bold text-slate-700">Mendelow's Power-Interest Matrix</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                        Stakeholders plotted by influence and interest. Dot colour = sentiment.
                    </p>
                </div>
                {/* Sentiment legend */}
                <div className="flex flex-wrap gap-x-3 gap-y-1 justify-end max-w-xs">
                    {(Object.entries(SENTIMENT_DOT) as [Sentiment, typeof SENTIMENT_DOT[Sentiment]][]).map(([, cfg]) => (
                        <div key={cfg.label} className="flex items-center gap-1">
                            <div className={`w-2.5 h-2.5 rounded-full ${cfg.bg}`} />
                            <span className="text-[10px] text-slate-500 font-medium">{cfg.label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Matrix */}
            <div className="p-6">
                <div className="flex gap-3">

                    {/* Y-axis label */}
                    <div className="flex items-center justify-center w-5 shrink-0">
                        <span className={`${axisLabel} [writing-mode:vertical-rl] rotate-180`}>
                            Influence (Power)
                        </span>
                    </div>

                    {/* Grid + X-axis */}
                    <div className="flex-1 min-w-0">

                        {/* Row labels + cells */}
                        {INFLUENCE_ROWS.map((influence) => (
                            <div key={influence} className="flex gap-2 mb-2 items-stretch">
                                {/* Row label */}
                                <div className="w-14 shrink-0 flex items-center justify-end pr-2">
                                    <span className={`${axisLabel} text-right leading-tight`}>
                                        {influence.charAt(0) + influence.slice(1).toLowerCase()}
                                    </span>
                                </div>

                                {/* Cells */}
                                {INTEREST_COLS.map((interest) => {
                                    const key = `${influence}-${interest}`;
                                    const zone = ZONE[key];
                                    const people = cellMap[key] ?? [];

                                    return (
                                        <div
                                            key={key}
                                            className={`
                                                relative flex-1 min-h-[100px] rounded-xl border-2
                                                ${zone.bg} ${zone.border}
                                                flex flex-col justify-between p-3
                                                transition-all duration-150
                                                ${people.length > 0 ? 'shadow-sm' : ''}
                                            `}
                                        >
                                            {/* Zone label */}
                                            <div>
                                                <p className={`text-[10px] font-black uppercase tracking-wide ${zone.text} leading-tight`}>
                                                    {zone.label}
                                                </p>
                                                <p className={`text-[9px] ${zone.text} opacity-60 mt-0.5`}>
                                                    {zone.sublabel}
                                                </p>
                                            </div>

                                            {/* Dots cluster */}
                                            {people.length > 0 && (
                                                <div className="relative flex items-center justify-center mt-2 h-10">
                                                    {people.map((p, i) => (
                                                        <StakeholderDot
                                                            key={p.id}
                                                            person={p}
                                                            index={i}
                                                            total={people.length}
                                                        />
                                                    ))}
                                                </div>
                                            )}

                                            {/* Count badge */}
                                            {people.length > 0 && (
                                                <div className={`absolute top-2 right-2 w-4 h-4 rounded-full ${zone.text} bg-white border ${zone.border} flex items-center justify-center text-[9px] font-black`}>
                                                    {people.length}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        ))}

                        {/* X-axis labels */}
                        <div className="flex gap-2 mt-1">
                            <div className="w-14 shrink-0" />
                            {INTEREST_COLS.map(interest => (
                                <div key={interest} className="flex-1 text-center">
                                    <span className={axisLabel}>
                                        {interest.charAt(0) + interest.slice(1).toLowerCase()}
                                    </span>
                                </div>
                            ))}
                        </div>

                        {/* X-axis title */}
                        <div className="flex gap-2 mt-1">
                            <div className="w-14 shrink-0" />
                            <div className="flex-1 text-center">
                                <span className={axisLabel}>Interest</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};