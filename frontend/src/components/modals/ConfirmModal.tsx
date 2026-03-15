import React from 'react';
import { Trash2, AlertTriangle } from 'lucide-react';

interface ConfirmModalProps {
    isOpen: boolean;
    title: string;
    message: string;
    type: 'danger' | 'info' | 'success' | 'danger';
    onClose: () => void;
    onConfirm: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
    isOpen, title, message, type, onClose, onConfirm
}) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="p-6 text-center">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4 ${type === 'danger' ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'
                        }`}>
                        {type === 'danger' ? <Trash2 size={24} /> : <AlertTriangle size={24} />}
                    </div>

                    <h3 className="text-lg font-bold text-slate-900 mb-2">{title}</h3>
                    <p className="text-sm text-slate-500 mb-6 leading-relaxed">{message}</p>

                    <div className="flex gap-3">
                        <button
                            onClick={onClose}
                            className="flex-1 py-2.5 rounded-xl font-bold text-slate-600 hover:bg-slate-100 transition border border-slate-200"
                        >
                            Keep It
                        </button>
                        <button
                            onClick={onConfirm}
                            className={`flex-1 py-2.5 rounded-xl font-bold text-white transition shadow-sm ${type === 'danger' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
                                }`}
                        >
                            {type === 'danger' ? 'Yes, Discard' : 'Confirm'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};