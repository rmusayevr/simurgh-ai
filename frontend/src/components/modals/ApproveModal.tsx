import React from 'react';
import { Shield, AlertTriangle } from 'lucide-react';

interface ApprovalModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    personaName: string;
    isOverwriting: boolean;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
    isOpen, onClose, onConfirm, personaName, isOverwriting
}) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/80 backdrop-blur-sm animate-in fade-in duration-200 p-4">
            <div className="bg-white w-full max-w-md rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="p-6 text-center">
                    <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
                        <Shield size={32} />
                    </div>
                    <h3 className="text-xl font-bold text-slate-900 mb-2">Confirm Strategy Adoption</h3>

                    {isOverwriting ? (
                        <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 mb-4 text-left">
                            <p className="text-orange-800 text-sm font-bold flex items-center gap-2">
                                <AlertTriangle size={16} /> Warning: Overwrite
                            </p>
                            <p className="text-orange-700 text-xs mt-1">
                                You have already approved a different strategy. Proceeding will overwrite that decision.
                            </p>
                        </div>
                    ) : (
                        <p className="text-slate-500 text-sm mb-6">
                            You are about to officially adopt the <strong>{personaName}</strong> proposal.
                        </p>
                    )}

                    <div className="flex gap-3">
                        <button onClick={onClose} className="flex-1 py-3 rounded-xl font-bold text-slate-600 hover:bg-slate-100 transition">
                            Cancel
                        </button>
                        <button onClick={onConfirm} className="flex-1 py-3 rounded-xl font-bold bg-blue-600 text-white hover:bg-blue-700 transition shadow-lg">
                            Confirm Adoption
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};