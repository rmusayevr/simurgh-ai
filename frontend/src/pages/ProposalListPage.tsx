/**
 * ProposalListPage.tsx
 * 
 * List view of all proposals for a project.
 * 
 * Features:
 * - Shows proposal status (DRAFT, PROCESSING, COMPLETED, FAILED)
 * - Displays variation count badge (should be 3 for completed)
 * - Quick navigation to detail view
 * - Status filtering
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    FileText,
    CheckCircle2,
    XCircle,
    Loader2,
    Plus,
    Eye,
    type LucideIcon
} from 'lucide-react';
import { api } from '../api/client';

interface ProposalListItem {
    id: number;
    project_id: number;
    task_description: string;
    status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
    selected_variation_id: number | null;
    variation_count: number;
    created_at: string;
    updated_at: string;
}

type StatusConfig = {
    icon: LucideIcon;
    color: string;
    bg: string;
    text: string;
    label: string;
    animate?: boolean;
};

const STATUS_CONFIG: Record<
    'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED',
    StatusConfig
> = {
    DRAFT: {
        icon: FileText,
        color: 'gray',
        bg: 'bg-gray-100',
        text: 'text-gray-700',
        label: 'Draft',
    },
    PROCESSING: {
        icon: Loader2,
        color: 'blue',
        bg: 'bg-blue-100',
        text: 'text-blue-700',
        label: 'Processing',
        animate: true,
    },
    COMPLETED: {
        icon: CheckCircle2,
        color: 'green',
        bg: 'bg-green-100',
        text: 'text-green-700',
        label: 'Completed',
    },
    FAILED: {
        icon: XCircle,
        color: 'red',
        bg: 'bg-red-100',
        text: 'text-red-700',
        label: 'Failed',
    },
};

export const ProposalListPage = () => {
    const { projectId } = useParams<{ projectId: string }>();
    const navigate = useNavigate();

    const [proposals, setProposals] = useState<ProposalListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState<string | null>(null);

    const fetchProposals = useCallback(async () => {
        try {
            const params = statusFilter ? { status: statusFilter } : {};
            const response = await api.get(`/api/v1/proposals/project/${projectId}`, { params });
            setProposals(response.data);
        } catch (error) {
            console.error('Failed to fetch proposals:', error);
        } finally {
            setLoading(false);
        }
    }, [projectId, statusFilter]);

    useEffect(() => {
        fetchProposals();

        // Poll every 5 seconds if any proposals are processing
        const hasProcessing = proposals.some(p => p.status === 'PROCESSING');
        if (hasProcessing) {
            const interval = setInterval(fetchProposals, 5000);
            return () => clearInterval(interval);
        }
    }, [projectId, statusFilter, fetchProposals, proposals]);

    const filteredProposals = statusFilter
        ? proposals.filter(p => p.status === statusFilter)
        : proposals;

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Architectural Proposals</h2>
                    <p className="text-gray-600 mt-1">
                        {filteredProposals.length} proposal{filteredProposals.length !== 1 ? 's' : ''}
                    </p>
                </div>
                <button
                    onClick={() => navigate(`/projects/${projectId}/proposals/new`)}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                    <Plus className="w-5 h-5" />
                    New Proposal
                </button>
            </div>

            {/* Status Filter */}
            <div className="flex gap-2">
                <button
                    onClick={() => setStatusFilter(null)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${!statusFilter
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                >
                    All
                </button>
                {Object.entries(STATUS_CONFIG).map(([status, config]) => (
                    <button
                        key={status}
                        onClick={() => setStatusFilter(status)}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${statusFilter === status
                            ? `${config.bg} ${config.text}`
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                    >
                        {config.label}
                    </button>
                ))}
            </div>

            {/* Proposals List */}
            {filteredProposals.length === 0 ? (
                <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
                    <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        No proposals yet
                    </h3>
                    <p className="text-gray-600 mb-4">
                        Create your first architectural proposal to get started
                    </p>
                    <button
                        onClick={() => navigate(`/projects/${projectId}/proposals/new`)}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                    >
                        Create Proposal
                    </button>
                </div>
            ) : (
                <div className="grid gap-4">
                    {filteredProposals.map((proposal) => {
                        const config = STATUS_CONFIG[proposal.status];
                        const Icon = config.icon;

                        return (
                            <div
                                key={proposal.id}
                                className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow cursor-pointer"
                                onClick={() => navigate(`/proposals/${proposal.id}`)}
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        {/* Status Badge */}
                                        <div className="flex items-center gap-3 mb-3">
                                            <div className={`${config.bg} px-3 py-1 rounded-full flex items-center gap-2`}>
                                                <Icon
                                                    className={`w-4 h-4 ${config.text} ${config.animate ? 'animate-spin' : ''}`}
                                                />
                                                <span className={`text-sm font-medium ${config.text}`}>
                                                    {config.label}
                                                </span>
                                            </div>

                                            {/* Variation Count Badge */}
                                            {proposal.status === 'COMPLETED' && (
                                                <div className="bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm font-medium">
                                                    {proposal.variation_count === 3 ? '✓' : '⚠️'} {proposal.variation_count} Proposals
                                                </div>
                                            )}

                                            {/* Selection Badge */}
                                            {proposal.selected_variation_id && (
                                                <div className="bg-green-50 text-green-700 px-3 py-1 rounded-full text-sm font-medium">
                                                    ✓ Selected
                                                </div>
                                            )}
                                        </div>

                                        {/* Task Description */}
                                        <p className="text-gray-900 font-medium mb-2 line-clamp-2">
                                            {proposal.task_description}
                                        </p>

                                        {/* Metadata */}
                                        <div className="flex items-center gap-4 text-sm text-gray-500">
                                            <span>
                                                Created {new Date(proposal.created_at).toLocaleDateString()}
                                            </span>
                                            {proposal.updated_at !== proposal.created_at && (
                                                <span>
                                                    Updated {new Date(proposal.updated_at).toLocaleDateString()}
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* View Button */}
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            navigate(`/proposals/${proposal.id}`);
                                        }}
                                        className="ml-4 p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                                    >
                                        <Eye className="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
