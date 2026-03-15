import React from 'react';
import { Gavel, CheckCircle2, Loader2, FileText } from 'lucide-react';
import type { Proposal, ProposalVariation } from '../../types';

interface DetailModalFooterProps {
    proposal: Proposal | null;
    selectedVariation: ProposalVariation;
    isDownloading: boolean;
    onDownload: () => void;
    onApprove: () => void;
    isExportingJira?: boolean;
    onExportJira?: () => void;
    userRole: string;
    jiraLink?: string | null;
    confluenceLink?: string | null;
    onExportConfluence?: () => void;
}

export const DetailModalFooter: React.FC<DetailModalFooterProps> = ({
    proposal,
    selectedVariation,
    isDownloading,
    onDownload,
    onApprove,
    userRole,
}) => {
    const isSelected = proposal?.selected_variation_id === selectedVariation.id;
    const hasOtherSelection = proposal?.selected_variation_id && !isSelected;
    const canApprove = userRole === 'OWNER';

    return (
        <div className="bg-white border-t border-slate-200 p-6 flex justify-between items-center flex-shrink-0">
            <div className="text-sm text-slate-500">
                {isSelected ? (
                    <div className="flex items-center gap-4">
                        <span className="flex items-center gap-2 text-emerald-600 font-bold bg-emerald-50 px-3 py-1 rounded-full">
                            <CheckCircle2 size={16} /> Strategy Officially Adopted
                        </span>

                        {/* DOWNLOAD BUTTON */}
                        <button
                            onClick={onDownload}
                            disabled={isDownloading}
                            className="flex items-center gap-2 text-slate-600 hover:text-blue-600 font-medium transition disabled:opacity-50"
                        >
                            {isDownloading ? (
                                <Loader2 size={16} className="animate-spin" />
                            ) : (
                                <FileText size={16} />
                            )}
                            {isDownloading ? "Generating Report..." : "Download Report"}
                        </button>
                        <div className="h-4 w-px bg-slate-300 mx-2"></div>

                    </div>
                ) : hasOtherSelection ? (
                    <span>Another strategy is currently active.</span>
                ) : (
                    <span>Decision pending approval.</span>
                )}
            </div>

            {!isSelected && canApprove && (
                <button
                    onClick={onApprove}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-2 rounded-lg font-bold transition-colors flex items-center gap-2"
                >
                    <Gavel size={18} />
                    Approve Strategy
                </button>
            )}
        </div>
    );
};