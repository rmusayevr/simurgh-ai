import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, ZoomIn, ZoomOut, RotateCcw, Move } from 'lucide-react';
import { MermaidDiagram } from '../MermaidDiagram';

interface DiagramModalProps {
    isOpen: boolean;
    onClose: () => void;
    chart: string;
}

export const DiagramModal: React.FC<DiagramModalProps> = ({ isOpen, onClose, chart }) => {
    const [zoom, setZoom] = useState(2.5);
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
    const containerRef = useRef<HTMLDivElement>(null);

    const handleZoomIn = useCallback((e?: React.MouseEvent) => {
        e?.stopPropagation();
        setZoom(prev => Math.min(prev + 0.25, 5));
    }, []);

    const handleZoomOut = useCallback((e?: React.MouseEvent) => {
        e?.stopPropagation();
        setZoom(prev => Math.max(prev - 0.25, 0.5));
    }, []);

    const handleReset = useCallback((e?: React.MouseEvent) => {
        e?.stopPropagation();
        setZoom(2.5);
        setPan({ x: 0, y: 0 });
    }, []);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (!isOpen) return;

            if (e.key === 'Escape') {
                onClose();
            } else if (e.key === '+' || e.key === '=') {
                handleZoomIn();
            } else if (e.key === '-') {
                handleZoomOut();
            } else if (e.key === '0') {
                handleReset();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, onClose, handleZoomIn, handleZoomOut, handleReset]);

    if (!isOpen) return null;

    const handleMouseDown = (e: React.MouseEvent) => {
        if (e.target === containerRef.current || (e.target as HTMLElement).closest('.diagram-content')) {
            setIsDragging(true);
            setDragStart({
                x: e.clientX - pan.x,
                y: e.clientY - pan.y
            });
        }
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!isDragging) return;

        setPan({
            x: e.clientX - dragStart.x,
            y: e.clientY - dragStart.y
        });
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    const handleWheel = (e: React.WheelEvent) => {
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.25 : 0.25;
            setZoom(prev => Math.max(0.5, Math.min(5, prev + delta)));
        }
    };

    return (
        <div
            className="fixed inset-0 z-[60] bg-slate-900/90 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200"
            onClick={onClose}
        >
            {/* Close Button */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onClose();
                }}
                className="absolute top-6 right-6 p-2 bg-white/10 text-white hover:bg-white/20 rounded-full transition-all z-50"
                aria-label="Close diagram"
            >
                <X size={24} />
            </button>

            {/* Toolbar */}
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-slate-800/90 p-2 rounded-xl border border-slate-700 shadow-2xl z-50">
                <button
                    onClick={handleZoomOut}
                    className="p-2 text-slate-300 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                    title="Zoom Out (-)"
                    aria-label="Zoom out"
                >
                    <ZoomOut size={20} />
                </button>
                <span className="text-xs font-mono text-slate-400 min-w-[3rem] text-center">
                    {Math.round(zoom * 100)}%
                </span>
                <button
                    onClick={handleZoomIn}
                    className="p-2 text-slate-300 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                    title="Zoom In (+)"
                    aria-label="Zoom in"
                >
                    <ZoomIn size={20} />
                </button>
                <div className="w-px h-6 bg-slate-700 mx-1" />
                <button
                    onClick={handleReset}
                    className="p-2 text-slate-300 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                    title="Reset Zoom & Pan (0)"
                    aria-label="Reset view"
                >
                    <RotateCcw size={18} />
                </button>
                <div className="w-px h-6 bg-slate-700 mx-1" />
                <div className="flex items-center gap-1.5 px-2 text-slate-400 text-xs">
                    <Move size={16} />
                    <span>Drag to pan</span>
                </div>
            </div>

            {/* Scrollable Container with Panning */}
            <div
                ref={containerRef}
                className={`w-full h-full overflow-hidden flex items-center justify-center p-8 ${isDragging ? 'cursor-grabbing' : 'cursor-grab'
                    }`}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
                onClick={e => e.stopPropagation()}
            >
                {/* Zoom & Pan Target */}
                <div
                    className="diagram-content bg-white p-12 rounded-lg shadow-2xl transition-transform duration-200 ease-out select-none"
                    style={{
                        transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                        transformOrigin: 'center'
                    }}
                >
                    <MermaidDiagram chart={chart} />
                </div>
            </div>

            {/* Keyboard Shortcuts Hint */}
            <div className="absolute top-6 left-6 bg-slate-800/90 p-3 rounded-lg border border-slate-700 text-xs text-slate-300 z-50">
                <div className="font-semibold mb-1 text-white">Keyboard Shortcuts</div>
                <div className="space-y-0.5">
                    <div><kbd className="bg-slate-700 px-1.5 py-0.5 rounded">+</kbd> Zoom in</div>
                    <div><kbd className="bg-slate-700 px-1.5 py-0.5 rounded">-</kbd> Zoom out</div>
                    <div><kbd className="bg-slate-700 px-1.5 py-0.5 rounded">0</kbd> Reset</div>
                    <div><kbd className="bg-slate-700 px-1.5 py-0.5 rounded">Esc</kbd> Close</div>
                    <div><kbd className="bg-slate-700 px-1.5 py-0.5 rounded">Ctrl</kbd> + <kbd className="bg-slate-700 px-1.5 py-0.5 rounded">Scroll</kbd> Zoom</div>
                </div>
            </div>
        </div>
    );
};