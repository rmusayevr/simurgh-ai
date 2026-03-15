import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    Settings,
    LogOut,
    Sparkles,
    ChevronLeft,
    ChevronRight,
    FlaskConical,
    BarChart2
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { SimurghMark } from '../../components/SimurghMark';

interface SidebarProps {
    activeTab: string;
    onTabChange: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
    const { logout, user } = useAuth();
    const [isCollapsed, setIsCollapsed] = useState(false);

    return (
        <aside className={`${isCollapsed ? 'w-20' : 'w-64'} bg-slate-950 border-r border-slate-800 flex flex-col h-full transition-all duration-300 relative z-20`}>

            {/* Header / Brand */}
            <div className={`p-6 flex items-center ${isCollapsed ? 'justify-center' : 'gap-3'} transition-all`}>
                <div className="min-w-[32px]">
                    <SimurghMark size={32} />
                </div>
                {!isCollapsed && (
                    <div className="overflow-hidden whitespace-nowrap animate-in fade-in">
                        <h1 className="font-black text-white text-lg tracking-tight">Simurgh <span className="text-cyan-400">AI</span></h1>
                    </div>
                )}
            </div>

            {/* Main Navigation */}
            <nav className="flex-1 px-3 py-4 space-y-2 overflow-y-auto custom-scrollbar overflow-x-hidden">
                {!isCollapsed && (
                    <div className="px-3 mb-4 whitespace-nowrap">
                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Main Menu</p>
                    </div>
                )}

                <button
                    onClick={() => onTabChange('dashboard')}
                    title={isCollapsed ? "Dashboard" : undefined}
                    className={`relative w-full flex items-center ${isCollapsed ? 'justify-center' : 'gap-3 px-3'} py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group ${activeTab === 'dashboard'
                        ? 'bg-cyan-500/10 text-cyan-400'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                        }`}
                >
                    {activeTab === 'dashboard' && (
                        <span className="absolute left-0 inset-y-2 w-1 bg-cyan-500 rounded-r-full" />
                    )}
                    <LayoutDashboard size={18} className={activeTab === 'dashboard' ? 'text-cyan-400' : 'group-hover:text-white transition-colors'} />
                    {!isCollapsed && <span className="whitespace-nowrap">Dashboard</span>}
                </button>

                {/* Research Section */}
                <div className={`pt-4 mt-4 border-t border-slate-800/50 ${isCollapsed ? 'flex flex-col items-center gap-1' : ''}`}>
                    {!isCollapsed && (
                        <div className="px-3 mb-2 whitespace-nowrap">
                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Research</p>
                        </div>
                    )}
                    {/* Single entry point — ExperimentInterface redirects to /register if not yet registered */}
                    <NavLink
                        to="/experiment"
                        title={isCollapsed ? "Experiment" : undefined}
                        className={({ isActive }) => `relative flex items-center ${isCollapsed ? 'justify-center w-10 h-10' : 'w-full gap-3 px-3 py-2.5'} rounded-xl text-sm font-medium transition-all duration-200 group ${isActive
                            ? 'bg-cyan-500/10 text-cyan-400'
                            : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                            }`}
                    >
                        {({ isActive }) => (
                            <>
                                {isActive && !isCollapsed && <span className="absolute left-0 inset-y-2 w-1 bg-cyan-500 rounded-r-full" />}
                                <FlaskConical size={18} className={isActive ? 'text-cyan-400' : 'group-hover:text-white transition-colors'} />
                                {!isCollapsed && <span className="whitespace-nowrap">Experiment</span>}
                            </>
                        )}
                    </NavLink>
                    {(user?.is_superuser || user?.role === 'ADMIN') && (
                        <NavLink
                            to="/thesis"
                            title={isCollapsed ? "Thesis Analytics" : undefined}
                            className={({ isActive }) => `relative flex items-center ${isCollapsed ? 'justify-center w-10 h-10' : 'w-full gap-3 px-3 py-2.5'} rounded-xl text-sm font-medium transition-all duration-200 group ${isActive
                                ? 'bg-cyan-500/10 text-cyan-400'
                                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                                }`}
                        >
                            {({ isActive }) => (
                                <>
                                    {isActive && !isCollapsed && <span className="absolute left-0 inset-y-2 w-1 bg-cyan-500 rounded-r-full" />}
                                    <BarChart2 size={18} className={isActive ? 'text-cyan-400' : 'group-hover:text-white transition-colors'} />
                                    {!isCollapsed && <span className="whitespace-nowrap">Thesis Analytics</span>}
                                </>
                            )}
                        </NavLink>
                    )}
                </div>

                {/* Admin Separator & Link */}
                {(user?.is_superuser || user?.role === 'ADMIN') && (
                    <div className={`pt-4 mt-4 border-t border-slate-800/50 ${isCollapsed ? 'flex justify-center' : ''}`}>
                        {!isCollapsed && (
                            <div className="px-3 mb-2 whitespace-nowrap">
                                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">System</p>
                            </div>
                        )}
                        <NavLink
                            to="/admin"
                            title={isCollapsed ? "Admin Console" : undefined}
                            className={({ isActive }) => `relative flex items-center ${isCollapsed ? 'justify-center w-10 h-10' : 'w-full gap-3 px-3 py-2.5'} rounded-xl text-sm font-bold transition-all duration-200 group ${isActive
                                ? 'bg-amber-500/10 text-amber-500 ring-1 ring-amber-500/20'
                                : 'text-slate-400 hover:text-amber-400 hover:bg-amber-500/5'
                                }`}
                        >
                            <Sparkles size={18} className="group-hover:animate-pulse" />
                            {!isCollapsed && <span className="whitespace-nowrap">Admin Console</span>}
                        </NavLink>
                    </div>
                )}
            </nav>

            {/* Bottom Actions: Settings & Logout */}
            <div className="p-3 border-t border-slate-800 space-y-1">
                <button
                    onClick={() => onTabChange('settings')}
                    title={isCollapsed ? "Settings" : undefined}
                    className={`w-full flex items-center ${isCollapsed ? 'justify-center py-2.5' : 'gap-3 px-3 py-2'} rounded-lg text-sm font-medium transition-all duration-200 ${activeTab === 'settings'
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                        }`}
                >
                    <Settings size={18} />
                    {!isCollapsed && <span>Settings</span>}
                </button>

                <button
                    onClick={logout}
                    title={isCollapsed ? "Logout" : undefined}
                    className={`w-full flex items-center ${isCollapsed ? 'justify-center py-2.5' : 'gap-3 px-3 py-2'} rounded-lg text-sm font-medium text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition-colors group`}
                >
                    <LogOut size={18} className="group-hover:-translate-x-1 transition-transform" />
                    {!isCollapsed && <span>Logout</span>}
                </button>
            </div>

            {/* Legal links — only shown when sidebar is expanded */}
            {!isCollapsed && (
                <div className="px-4 py-2 flex items-center gap-4 border-t border-slate-800">
                    <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors">Terms</a>
                    <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-[10px] text-slate-600 hover:text-slate-400 transition-colors">Privacy</a>
                </div>
            )}

            {/* User Profile Footer */}
            <div className={`p-4 bg-slate-900 border-t border-slate-800 flex items-center ${isCollapsed ? 'justify-center' : 'gap-3'}`}>
                <div className="min-w-[32px] w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-purple-500 flex items-center justify-center text-white text-xs font-bold ring-2 ring-slate-900 shadow-sm">
                    {user?.email?.charAt(0).toUpperCase()}
                </div>
                {!isCollapsed && (
                    <div className="flex-1 overflow-hidden whitespace-nowrap animate-in fade-in">
                        <p className="text-sm font-bold text-slate-200 truncate">{user?.full_name || 'User'}</p>
                        <p className="text-[10px] text-slate-500 truncate font-medium">{user?.email}</p>
                    </div>
                )}
            </div>

            {/* The Collapse Toggle Button */}
            <button
                onClick={() => setIsCollapsed(!isCollapsed)}
                className="absolute -right-3 top-8 bg-slate-800 border border-slate-700 text-slate-400 hover:text-white rounded-full p-1 shadow-lg z-50 transition-colors"
            >
                {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
        </aside>
    );
};