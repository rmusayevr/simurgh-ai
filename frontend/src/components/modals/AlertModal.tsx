import React from 'react';
import { AlertCircle, CheckCircle2, XCircle } from 'lucide-react';

interface AlertModalProps {
    isOpen: boolean;
    title: string;
    message: string;
    type?: 'error' | 'success' | 'info';
    onClose: () => void;
}

export const AlertModal: React.FC<AlertModalProps> = ({
    isOpen, title, message, type = 'error', onClose
}) => {
    if (!isOpen) return null;

    const getIcon = () => {
        switch (type) {
            case 'success': return <CheckCircle2 size={24} />;
            case 'error': return <XCircle size={24} />;
            default: return <AlertCircle size={24} />;
        }
    };

    const getStyles = () => {
        switch (type) {
            case 'success': return 'bg-emerald-50 text-emerald-600';
            case 'error': return 'bg-red-50 text-red-600';
            default: return 'bg-blue-50 text-blue-600';
        }
    };

    const getButtonStyles = () => {
        switch (type) {
            case 'success': return 'bg-emerald-600 hover:bg-emerald-700';
            case 'error': return 'bg-red-600 hover:bg-red-700';
            default: return 'bg-blue-600 hover:bg-blue-700';
        }
    };

    return (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="p-6 text-center">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4 ${getStyles()}`}>
                        {getIcon()}
                    </div>

                    <h3 className="text-lg font-bold text-slate-900 mb-2">{title}</h3>
                    <p className="text-sm text-slate-500 mb-6 leading-relaxed">{message}</p>

                    <button
                        onClick={onClose}
                        className={`w-full py-2.5 rounded-xl font-bold text-white transition shadow-sm ${getButtonStyles()}`}
                    >
                        Okay, got it
                    </button>
                </div>
            </div>
        </div>
    );
};