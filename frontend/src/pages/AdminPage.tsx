import React, { useState, useEffect, useCallback } from 'react';
import {
    Users, ShieldAlert, LayoutDashboard, Zap, Logs, FlaskConical,
    ArrowLeft, TrendingUp, LogOut, Loader2, Cpu, Settings, UserCheck,
} from 'lucide-react';
import { adminApi } from '../api/client';
import type { AdminUser, UserProfile } from '../types';

import { AdminStats } from '../components/admin/AdminStats';
import { AdminUsers } from '../components/admin/AdminUsers';
import { AdminProjects } from '../components/admin/AdminProjects';
import { AdminPrompts } from '../components/admin/AdminPrompts';
import { AdminSettings } from '../components/admin/AdminSettings';
import { AdminMissions } from '../components/admin/AdminMissions';
import { AdminLogs } from '../components/admin/AdminLogs';
import { AdminVerification } from '../components/admin/AdminVerification';
import { AdminAnalytics } from '../components/admin/AdminAnalytics';
import { AdminRecentActivityFeed } from '../components/admin/AdminRecentActivityFeed';
import { AdminExperimentData } from '../components/admin/AdminExperimentData';
import { PersonaVerificationTool } from '../pages/PersonaVerification';


interface AdminPageProps {
    currentUser: UserProfile;
    onLogout: () => void;
    onBackToApp: () => void;
    defaultTab?: string;
}

interface StatCardProps {
    title: string;
    value: string | number;
    icon: React.ElementType;
    color: string;
    loading?: boolean;
}

export const StatCard = ({ title, value, icon: Icon, color, loading }: StatCardProps) => (
    <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-center gap-4 transition-transform hover:scale-[1.02]">
        <div className={`p-4 rounded-xl ${color} text-white shadow-lg`}>
            <Icon size={24} />
        </div>
        <div>
            <p className="text-slate-500 text-sm font-medium uppercase tracking-wide">{title}</p>
            {loading ? (
                <div className="h-8 w-16 bg-slate-100 animate-pulse rounded mt-1" />
            ) : (
                <h3 className="text-2xl font-bold text-slate-800">{value}</h3>
            )}
        </div>
    </div>
);

export const AdminPage: React.FC<AdminPageProps> = ({ currentUser, onLogout, onBackToApp, defaultTab }) => {
    const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'projects' | 'prompts' | 'settings' | 'proposals' | 'logs' | 'experiment' | 'persona-coding'>(
        (defaultTab ?? 'overview') as 'overview' | 'users' | 'projects' | 'prompts' | 'settings' | 'proposals' | 'logs' | 'experiment' | 'persona-coding'
    );
    const [users, setUsers] = useState<AdminUser[]>([]);
    interface AdminStatsData {
        // Matches GET /admin/health response shape
        status: string;
        timestamp: string;
        database: string;
        counts: {
            users: number;
            projects: number;
            proposals: number;
            processing_proposals: number;
            stakeholders: number;
            chunks: number;
        };
        queue: {
            pending_tasks: number;
        };
        workers: {
            online: number;
        };
        recent_activity?: Array<{
            proposal_id: number;
            user_email: string;
            project_name: string;
            task_preview: string;
            status: string;
            created_at: string;
        }>;
    }

    const [stats, setStats] = useState<AdminStatsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');

    const [workerStatus, setWorkerStatus] = useState<'online' | 'offline' | 'loading'>('loading');

    const loadData = useCallback(async () => {
        try {
            const [usersRes, statsRes, workerRes] = await Promise.all([
                adminApi.getUsers(),
                adminApi.getStats(),
                adminApi.getWorkerHealth()
            ]);
            setUsers(usersRes.data);
            setStats(statsRes as unknown as AdminStatsData);
            setWorkerStatus(workerRes.data.status);
        } catch {
            setWorkerStatus('offline');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (currentUser) loadData();
    }, [currentUser, loadData]);


    const handleToggleStatus = async (user: AdminUser) => {
        try {
            await adminApi.toggleUserStatus(user.id, !user.is_active);
            setUsers(users.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u));
        } catch {
            alert("Failed to update user status");
        }
    };

    const handleDeleteUser = async (user: AdminUser) => {
        try {
            await adminApi.deleteUser(user.id);
            setUsers(users.filter(u => u.id !== user.id));
        } catch {
            alert("Failed to delete user");
        }
    };

    const filteredUsers = users.filter(u =>
        u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
        u.full_name?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 size={48} className="text-cyan-600 animate-spin" />
                    <p className="text-slate-500 font-medium">Loading Admin Console...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
            <header className="bg-slate-900 text-white px-8 py-4 flex justify-between items-center shadow-md z-10 sticky top-0">
                <div className="flex items-center gap-4">
                    <div className="bg-cyan-500 p-2 rounded-lg">
                        <ShieldAlert size={24} className="text-white" />
                    </div>
                    <div>
                        <h1 className="font-bold text-xl tracking-tight">Admin Console</h1>
                        <p className="text-xs text-slate-400">System Management</p>
                    </div>
                </div>

                <div className="flex items-center gap-6">
                    <button onClick={onBackToApp} className="flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-white transition-colors bg-slate-800/50 px-3 py-1.5 rounded-lg border border-slate-700">
                        <ArrowLeft size={16} /> Back to App
                    </button>
                    <div className="flex items-center gap-3">
                        <div className="text-right hidden md:block">
                            <p className="text-sm font-bold">{currentUser.full_name}</p>
                            <p className="text-xs text-cyan-400">Super Admin</p>
                        </div>
                        <button onClick={onLogout} className="ml-2 text-slate-400 hover:text-red-400 transition-colors">
                            <LogOut size={20} />
                        </button>
                    </div>
                </div>
            </header>

            <main className="flex-1 max-w-7xl w-full mx-auto p-8">
                <div className="flex gap-6 border-b border-slate-200 mb-8 overflow-x-auto">
                    {[
                        { id: 'overview', label: 'Overview', icon: LayoutDashboard },
                        { id: 'users', label: 'Users', icon: Users },
                        { id: 'projects', label: 'Projects', icon: TrendingUp },
                        { id: 'proposals', label: 'Missions', icon: Zap },
                        { id: 'prompts', label: 'AI Personas', icon: Cpu },
                        { id: 'logs', label: 'Logs', icon: Logs },
                        { id: 'settings', label: 'System', icon: Settings },
                        { id: 'experiment', label: 'Experiment', icon: FlaskConical },
                        { id: 'persona-coding', label: 'Persona Coding', icon: UserCheck },
                    ].map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id as typeof activeTab)}
                            className={`flex items-center gap-2 pb-4 px-2 text-sm font-bold transition-all border-b-2 whitespace-nowrap ${activeTab === tab.id
                                ? 'border-cyan-600 text-cyan-600'
                                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                                }`}
                        >
                            <tab.icon size={18} />
                            {tab.label}
                        </button>
                    ))}
                </div>

                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {activeTab === 'overview' && (
                        <div className="space-y-6 animate-in fade-in duration-500">

                            <AdminStats stats={stats} workerStatus={workerStatus} />

                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                                <div className="lg:col-span-2">
                                    <h3 className="text-lg font-bold text-slate-900 mb-4 tracking-tight">Knowledge Base Verification</h3>
                                    <AdminVerification />
                                </div>
                                <div className="lg:col-span-1">
                                    <h3 className="text-lg font-bold text-slate-900 mb-4 tracking-tight">Agent Performance</h3>
                                    <AdminAnalytics />
                                </div>
                            </div>

                            <div className="pt-4">
                                <h3 className="text-lg font-bold text-slate-900 mb-4 tracking-tight">Live System Feed</h3>
                                <AdminRecentActivityFeed activities={stats?.recent_activity || []} totalMissions={stats?.counts?.proposals} />
                            </div>

                        </div>
                    )}

                    {activeTab === 'users' && (
                        <AdminUsers
                            users={filteredUsers}
                            searchTerm={searchTerm}
                            setSearchTerm={setSearchTerm}
                            onToggleStatus={handleToggleStatus}
                            onDelete={handleDeleteUser}
                            onRefresh={loadData}
                        />
                    )}

                    {activeTab === 'projects' && <AdminProjects />}
                    {activeTab === 'proposals' && <AdminMissions />}
                    {activeTab === 'prompts' && <AdminPrompts />}
                    {activeTab === 'logs' && <AdminLogs />}
                    {activeTab === 'settings' && <AdminSettings />}
                    {activeTab === 'experiment' && <AdminExperimentData />}
                    {activeTab === 'persona-coding' && (
                        <div className="space-y-4">
                            <div className="flex items-center gap-3 pb-2 border-b border-slate-200">
                                <div className="w-9 h-9 bg-cyan-100 text-cyan-600 rounded-lg flex items-center justify-center">
                                    <UserCheck size={20} />
                                </div>
                                <div>
                                    <h2 className="text-lg font-bold text-slate-900">Persona Deviation Coding</h2>
                                    <p className="text-sm text-slate-500">
                                        Researcher tool — manually code agent persona fidelity for RQ1 &amp; RQ2 (Section 3.4.2).
                                    </p>
                                </div>
                            </div>
                            <PersonaVerificationTool />
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
};