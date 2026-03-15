import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    securityLevel: 'loose',
    themeVariables: {
        primaryColor: '#dbeafe',
        primaryTextColor: '#1e3a8a',
        primaryBorderColor: '#2563eb',
        lineColor: '#64748b',
        secondaryColor: '#f1f5f9',
        tertiaryColor: '#fff',
    },
});

const normalizeMermaid = (input: string): string => {
    return input
        .trim()
        .replace(/^```mermaid\s*/i, '')
        .replace(/^```/i, '')
        .replace(/```$/i, '')
        .trim();
};

interface MermaidProps {
    chart: string;
}

export const MermaidDiagram: React.FC<MermaidProps> = ({ chart }) => {
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!ref.current) return;

        const id = `mermaid-${Math.random().toString(36).slice(2)}`;
        const source = normalizeMermaid(chart);

        ref.current.innerHTML = '';

        mermaid
            .render(id, source)
            .then(({ svg }) => {
                if (ref.current) {
                    ref.current.innerHTML = svg;
                }
            })
            .catch(err => {
                console.error('Mermaid render error:', err);
                if (ref.current) {
                    ref.current.innerHTML = `
                        <pre class="text-red-500 text-xs whitespace-pre-wrap">
Failed to render Mermaid diagram.

${source}
                        </pre>
                    `;
                }
            });
    }, [chart]);

    return (
        <div className="w-full flex justify-center bg-slate-50 p-6 rounded-lg border border-slate-100 overflow-x-auto">
            <div ref={ref} />
        </div>
    );
};
