import { useState, useRef, useEffect } from 'react';
import { MoreHorizontal, Edit2, Trash2 } from 'lucide-react';
import { Sentiment } from '../types';
import type { Stakeholder } from '../types';
import { api } from '../api/client';
import { ConfirmModal } from './modals/ConfirmModal';

interface Props {
    person: Stakeholder;
    onEdit: (person: Stakeholder) => void;
    onDelete: (id: number) => void;
}

export const StakeholderRow = ({ person, onEdit, onDelete }: Props) => {
    const [isOpen, setIsOpen] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleDeleteClick = () => {
        setIsOpen(false);
        setShowDeleteConfirm(true);
    };

    const handleConfirmDelete = async () => {
        try {
            await api.delete(`/stakeholders/${person.id}`);
            onDelete(person.id);
            setShowDeleteConfirm(false);
        } catch (err) {
            console.error("Failed to delete", err);
        }
    };

    return (
        <>
            <tr className="hover:bg-slate-50/80 transition-colors border-b border-slate-50 last:border-0">
                <td className="px-6 py-4">
                    <div className="font-bold text-slate-900">{person.name}</div>
                    <div className="text-slate-500 text-xs">{person.role}</div>
                </td>
                <td className="px-6 py-4 text-slate-600">{person.department || '-'}</td>
                <td className="px-6 py-4"><Badge value={person.influence} /></td>
                <td className="px-6 py-4"><Badge value={person.interest} /></td>
                <td className="px-6 py-4">
                    <SentimentBadge value={person.sentiment} />
                </td>
                <td className="px-6 py-4 text-right relative">
                    <div ref={menuRef}>
                        <button
                            onClick={() => setIsOpen(!isOpen)}
                            className={`p-2 rounded-lg transition-colors ${isOpen ? 'bg-slate-200 text-slate-900' : 'text-slate-400 hover:text-cyan-600 hover:bg-slate-100'}`}
                        >
                            <MoreHorizontal size={18} />
                        </button>

                        {isOpen && (
                            <div className="absolute right-8 top-8 w-40 bg-white rounded-lg shadow-xl border border-slate-100 z-10 overflow-hidden animate-in fade-in zoom-in-95 duration-100">
                                <button
                                    onClick={() => { setIsOpen(false); onEdit(person); }}
                                    className="w-full text-left px-4 py-2.5 text-sm text-slate-600 hover:bg-slate-50 hover:text-cyan-600 flex items-center gap-2"
                                >
                                    <Edit2 size={14} /> Edit
                                </button>

                                <button
                                    onClick={handleDeleteClick}
                                    className="w-full text-left px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                                >
                                    <Trash2 size={14} /> Remove
                                </button>
                            </div>
                        )}
                    </div>
                </td>
            </tr>

            <ConfirmModal
                isOpen={showDeleteConfirm}
                title="Delete Stakeholder?"
                message={`Are you sure you want to remove ${person.name}?`}
                type="danger"
                onClose={() => setShowDeleteConfirm(false)}
                onConfirm={handleConfirmDelete}
            />
        </>
    );
};

// ... Badge and SentimentBadge components remain exactly as you have them ...
const Badge = ({ value }: { value: string }) => {
    const colors: Record<string, string> = {
        "HIGH": "bg-purple-100 text-purple-700",
        "MEDIUM": "bg-blue-100 text-blue-700",
        "LOW": "bg-slate-100 text-slate-600",
    };
    const label = value.charAt(0) + value.slice(1).toLowerCase();
    return <span className={`px-2 py-1 rounded text-xs font-bold ${colors[value] ?? 'bg-slate-100 text-slate-600'}`}>{label}</span>;
};

const SentimentBadge = ({ value }: { value: string }) => {
    const map: Record<string, string> = {
        [Sentiment.CHAMPION]: "bg-emerald-100 text-emerald-700",
        [Sentiment.SUPPORTIVE]: "bg-green-100 text-green-700",
        [Sentiment.NEUTRAL]: "bg-slate-100 text-slate-600",
        [Sentiment.CONCERNED]: "bg-orange-100 text-orange-700",
        [Sentiment.RESISTANT]: "bg-red-100 text-red-700",
        [Sentiment.BLOCKER]: "bg-red-900 text-white",
    };
    const label = value.charAt(0) + value.slice(1).toLowerCase();
    return <span className={`px-2 py-1 rounded-full text-xs font-bold ${map[value] ?? 'bg-slate-100 text-slate-600'}`}>{label}</span>;
};