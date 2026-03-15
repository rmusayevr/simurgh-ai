import React from 'react';
import { Plus, Zap, History } from 'lucide-react';

export type GeneratorView = 'new' | 'active' | 'history';

interface GeneratorNavigationProps {
    activeTab: GeneratorView;
    setActiveTab: (tab: GeneratorView) => void;
    activeCount: number;
    historyCount: number;
    onHistoryClick?: () => void;
    canCreate: boolean;
}

export const GeneratorNavigation: React.FC<GeneratorNavigationProps> = ({
    activeTab,
    setActiveTab,
    activeCount,
    historyCount,
    onHistoryClick,
    canCreate,
}) => {
    return (
        <div className="flex justify-center mb-8">
            <div className="bg-slate-100 p-1 rounded-xl flex gap-1 shadow-inner">
                {/* NEW SESSION */}
                {canCreate && (
                    <button
                        onClick={() => setActiveTab('new')}
                        className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'new'
                                ? 'bg-white text-slate-900 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700'
                            }`}
                    >
                        <Plus size={16} /> New Session
                    </button>
                )}
                {/* ACTIVE MISSIONS (With Counter) */}
                <button
                    onClick={() => setActiveTab('active')}
                    className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'active'
                            ? 'bg-white text-blue-600 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700'
                        }`}
                >
                    <Zap size={16} className={activeTab === 'active' ? 'fill-current' : ''} />
                    Active
                    {activeCount > 0 && (
                        <span className="ml-1 bg-blue-100 text-blue-700 text-[10px] px-1.5 py-0.5 rounded-full border border-blue-200">
                            {activeCount}
                        </span>
                    )}
                </button>

                {/* HISTORY */}
                <button
                    onClick={() => {
                        setActiveTab('history');
                        if (onHistoryClick) onHistoryClick();
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'history'
                            ? 'bg-white text-slate-900 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700'
                        }`}
                >
                    <History size={16} /> History
                    <span className="bg-slate-200 text-slate-600 text-[10px] px-1.5 py-0.5 rounded-full">
                        {historyCount}
                    </span>
                </button>
            </div>
        </div>
    );
};