/**
 * VariationCard.tsx
 */

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
    Shield, Zap, Scale,
    ChevronDown, ChevronUp,
    CheckCircle2, Circle, TrendingUp
} from 'lucide-react';

interface ProposalVariation {
    id: number;
    agent_persona: 'LEGACY_KEEPER' | 'INNOVATOR' | 'MEDIATOR';
    structured_prd: string;
    reasoning: string;
    trade_offs: string;
    confidence_score: number;
    created_at: string;
}

interface Props {
    variation: ProposalVariation;
    isSelected: boolean;
    onSelect: () => void;
    isSelecting: boolean;
}

const PERSONA_CONFIG = {
    LEGACY_KEEPER: {
        name: 'Legacy Keeper',
        icon: Shield,
        color: 'blue',
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-200',
        textColor: 'text-blue-900',
        badgeColor: 'bg-blue-100',
        buttonColor: 'bg-blue-600 hover:bg-blue-700',
        description: 'Prioritizes stability and proven patterns',
    },
    INNOVATOR: {
        name: 'Innovator',
        icon: Zap,
        color: 'purple',
        bgColor: 'bg-purple-50',
        borderColor: 'border-purple-200',
        textColor: 'text-purple-900',
        badgeColor: 'bg-purple-100',
        buttonColor: 'bg-purple-600 hover:bg-purple-700',
        description: 'Champions modern architecture and innovation',
    },
    MEDIATOR: {
        name: 'Mediator',
        icon: Scale,
        color: 'green',
        bgColor: 'bg-green-50',
        borderColor: 'border-green-200',
        textColor: 'text-green-900',
        badgeColor: 'bg-green-100',
        buttonColor: 'bg-green-600 hover:bg-green-700',
        description: 'Balances trade-offs pragmatically',
    },
} as const;

const VariationCard: React.FC<Props> = ({
    variation,
    isSelected,
    onSelect,
    isSelecting,
}) => {
    const [expanded, setExpanded] = useState(false);
    const config = PERSONA_CONFIG[variation.agent_persona];
    const Icon = config.icon;

    const previewLength = 500;
    const prdPreview = variation.structured_prd.substring(0, previewLength);
    const hasMore = variation.structured_prd.length > previewLength;

    return (
        <div
            className={`
                relative rounded-lg border-2 transition-all duration-200
                ${isSelected ? 'ring-4 ring-offset-2 ring-yellow-400 border-yellow-400' : config.borderColor}
                ${isSelected ? 'shadow-xl' : 'shadow-md hover:shadow-lg'}
                bg-white
            `}
        >
            {isSelected && (
                <div className="absolute -top-3 -right-3 bg-yellow-400 text-yellow-900 rounded-full p-2 shadow-lg z-10">
                    <CheckCircle2 className="w-6 h-6" />
                </div>
            )}

            <div className="p-6">
                {/* Header */}
                <div className={`${config.bgColor} rounded-lg p-4 mb-4`}>
                    <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                            <div className={`${config.badgeColor} p-2 rounded-lg`}>
                                <Icon className={`w-6 h-6 ${config.textColor}`} />
                            </div>
                            <div>
                                <h3 className={`text-lg font-bold ${config.textColor}`}>
                                    {config.name}
                                </h3>
                                <p className={`text-sm ${config.textColor} opacity-75`}>
                                    {config.description}
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Confidence Score */}
                    <div className="flex items-center gap-2">
                        <TrendingUp className={`w-4 h-4 ${config.textColor}`} />
                        <span className={`text-sm font-medium ${config.textColor}`}>
                            Confidence: {variation.confidence_score}%
                        </span>
                        <div className="flex-1 h-2 bg-white rounded-full overflow-hidden">
                            <div
                                className={`h-full bg-${config.color}-600`}
                                style={{ width: `${variation.confidence_score}%` }}
                            />
                        </div>
                    </div>
                </div>

                {/* PRD Preview */}
                <div className="mb-4">
                    <div className="prose prose-sm max-w-none">
                        <ReactMarkdown>
                            {expanded ? variation.structured_prd : prdPreview}
                        </ReactMarkdown>
                    </div>

                    {hasMore && (
                        <button
                            onClick={() => setExpanded(!expanded)}
                            className="mt-2 flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
                        >
                            {expanded ? (
                                <><ChevronUp className="w-4 h-4" /> Show less</>
                            ) : (
                                <><ChevronDown className="w-4 h-4" /> Read full proposal</>
                            )}
                        </button>
                    )}
                </div>

                {/* Reasoning & Trade-offs */}
                {expanded && (
                    <div className="space-y-3 mb-4 pt-4 border-t">
                        {variation.reasoning && (
                            <div>
                                <h4 className="font-semibold text-sm text-gray-700 mb-1">Reasoning</h4>
                                <p className="text-sm text-gray-600">{variation.reasoning}</p>
                            </div>
                        )}
                        {variation.trade_offs && (
                            <div>
                                <h4 className="font-semibold text-sm text-gray-700 mb-1">Trade-offs</h4>
                                <p className="text-sm text-gray-600">{variation.trade_offs}</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Selection Button */}
                <button
                    onClick={onSelect}
                    disabled={isSelecting || isSelected}
                    className={`
                        w-full py-3 px-4 rounded-lg font-semibold text-white
                        transition-all duration-200 flex items-center justify-center gap-2
                        ${isSelected ? 'bg-gray-400 cursor-default' : config.buttonColor}
                        disabled:opacity-50 disabled:cursor-not-allowed
                    `}
                >
                    {isSelected ? (
                        <><CheckCircle2 className="w-5 h-5" /> Selected</>
                    ) : (
                        <><Circle className="w-5 h-5" /> Select This Proposal</>
                    )}
                </button>
            </div>
        </div>
    );
};

export default VariationCard;
