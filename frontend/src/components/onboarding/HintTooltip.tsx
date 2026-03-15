/**
 * HintTooltip.tsx
 *
 * Tiny ? icon that shows an explanatory popover on hover/click.
 * Drop-in next to any label that needs contextual explanation.
 *
 * Usage:
 *   import { HintTooltip } from '../onboarding/HintTooltip';
 *
 *   <label className="flex items-center gap-1">
 *       Influence
 *       <HintTooltip text="How much organisational power this person has over the project decision." />
 *   </label>
 */

import React, { useEffect, useRef, useState } from 'react';
import { HelpCircle } from 'lucide-react';

interface Props {
    text: string;
    title?: string;
    /** Which side the popover opens. Defaults to 'top'. */
    side?: 'top' | 'bottom' | 'right' | 'left';
    iconSize?: number;
}

export const HintTooltip: React.FC<Props> = ({
    text,
    title,
    side = 'top',
    iconSize = 12,
}) => {
    const [open, setOpen] = useState(false);
    const wrapRef = useRef<HTMLSpanElement>(null);

    // Close on outside click
    useEffect(() => {
        if (!open) return;
        const h = (e: MouseEvent) => {
            if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener('mousedown', h);
        return () => document.removeEventListener('mousedown', h);
    }, [open]);

    // Popover + arrow placement
    const popover: Record<string, string> = {
        top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
        bottom: 'top-full  left-1/2 -translate-x-1/2 mt-2',
        right: 'left-full top-1/2 -translate-y-1/2 ml-2',
        left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    };
    const arrow: Record<string, string> = {
        top: 'top-full  left-1/2 -translate-x-1/2 border-t-slate-900',
        bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-slate-900',
        right: 'right-full top-1/2 -translate-y-1/2 border-r-slate-900',
        left: 'left-full  top-1/2 -translate-y-1/2 border-l-slate-900',
    };

    return (
        <span ref={wrapRef} className="relative inline-flex items-center">
            <button
                type="button"
                onMouseEnter={() => setOpen(true)}
                onMouseLeave={() => setOpen(false)}
                onClick={() => setOpen(v => !v)}
                className="normal-case text-slate-400 hover:text-cyan-500 transition-colors ml-0.5 focus:outline-none"
                aria-label="Show hint"
            >
                <HelpCircle size={iconSize} />
            </button>

            {open && (
                <span className={`absolute z-[300] ${popover[side]} w-52 pointer-events-none`}
                    style={{ animation: 'ht-in 140ms ease both' }}>
                    <style>{`@keyframes ht-in{from{opacity:0;transform:scale(.95)}to{opacity:1;transform:scale(1)}}`}</style>
                    <span className="block bg-slate-900 rounded-xl shadow-xl px-3.5 py-2.5 text-xs leading-relaxed normal-case tracking-normal font-normal">
                        {title && <span className="block font-bold text-white mb-1 tracking-normal">{title}</span>}
                        <span className="text-slate-300">{text}</span>
                    </span>
                    {/* Arrow */}
                    <span className={`absolute w-0 h-0 border-4 border-transparent ${arrow[side]}`} />
                </span>
            )}
        </span>
    );
};