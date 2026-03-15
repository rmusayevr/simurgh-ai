import { useEffect, useState } from 'react';
import { Save, Power, Cpu, Loader2, CheckCircle2 } from 'lucide-react';
import { adminApi, api } from '../../api/client';
import { ConfirmModal } from '../modals/ConfirmModal';

interface SystemSettings {
    maintenance_mode: boolean;
    allow_registrations: boolean;
    openai_model: string;
}

export const AdminSettings = () => {
    const [settings, setSettings] = useState<SystemSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [successMsg, setSuccessMsg] = useState('');

    const [pendingAction, setPendingAction] = useState<{
        type: 'save' | 'toggle';
        key?: keyof SystemSettings;
        newValue?: boolean;
    } | null>(null);

    useEffect(() => {
        api.get<SystemSettings>('/admin/settings')
            .then(res => setSettings(res.data))
            .catch(err => console.error(err))
            .finally(() => setLoading(false));
    }, []);

    const initiateSave = () => {
        setPendingAction({ type: 'save' });
    };

    const initiateToggle = (key: keyof SystemSettings) => {
        if (!settings) return;
        setPendingAction({
            type: 'toggle',
            key,
            newValue: !settings[key] as boolean
        });
    };

    const executeAction = async () => {
        if (!settings || !pendingAction) return;

        setSaving(true);
        setPendingAction(null);

        try {
            if (pendingAction.type === 'save') {
                await api.patch('/admin/settings', settings);
                setSuccessMsg('System configuration updated successfully.');
            } else if (pendingAction.type === 'toggle' && pendingAction.key) {
                const payload = { [pendingAction.key]: pendingAction.newValue };
                await adminApi.updateSettings(payload);

                setSettings(prev => prev ? { ...prev, [pendingAction.key!]: pendingAction.newValue! } : null);
                setSuccessMsg(`${pendingAction.key.replace('_', ' ')} updated.`);
            }

            setTimeout(() => setSuccessMsg(''), 3000);
        } catch (err) {
            console.error(err);
            alert('Operation failed. Please check server logs.');

        } finally {
            setSaving(false);
        }
    };

    const getModalContent = () => {
        if (!pendingAction) return { title: '', message: '', type: 'info' as const };

        if (pendingAction.type === 'save') {
            return {
                title: 'Save Configuration?',
                message: 'This will apply changes to the global AI model settings. This affects all new strategies generated.',
                type: 'info' as const
            };
        }

        if (pendingAction.key === 'maintenance_mode') {
            return {
                title: pendingAction.newValue ? 'Enable Maintenance Mode?' : 'Disable Maintenance Mode?',
                message: pendingAction.newValue
                    ? 'Warning: This will block all standard users from accessing the dashboard. Only Superusers will have access.'
                    : 'This will restore access for all users. Are you sure?',
                type: pendingAction.newValue ? 'danger' as const : 'success' as const
            };
        }

        if (pendingAction.key === 'allow_registrations') {
            return {
                title: pendingAction.newValue ? 'Enable Registrations?' : 'Disable Registrations?',
                message: pendingAction.newValue
                    ? 'New users will be able to sign up freely.'
                    : 'New sign-ups will be blocked. Existing users can still log in.',
                type: 'info' as const
            };
        }

        return { title: 'Update Setting?', message: 'Are you sure?', type: 'info' as const };
    };

    const modalContent = getModalContent();

    if (loading) return <div className="p-8 text-slate-400">Loading Configuration...</div>;
    if (!settings) return null;

    return (
        <div className="max-w-3xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4">

            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-900">System Configuration</h2>
                    <p className="text-slate-500">Manage global application behavior.</p>
                </div>
                {successMsg && (
                    <div className="flex items-center gap-2 text-emerald-600 bg-emerald-50 px-4 py-2 rounded-lg text-sm font-bold animate-in fade-in">
                        <CheckCircle2 size={16} /> {successMsg}
                    </div>
                )}
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center gap-3">
                    <Power className="text-slate-400" size={20} />
                    <h3 className="font-bold text-slate-700">Access Control</h3>
                </div>

                <div className="p-6 space-y-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="font-bold text-slate-900">Maintenance Mode</div>
                            <div className="text-sm text-slate-500 max-w-md">
                                If enabled, only Superusers can log in. Regular users will see a "Under Maintenance" screen.
                            </div>
                        </div>
                        <button
                            onClick={() => initiateToggle('maintenance_mode')}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${settings.maintenance_mode ? 'bg-red-600' : 'bg-slate-200'
                                }`}
                        >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition duration-200 ease-in-out ${settings.maintenance_mode ? 'translate-x-6' : 'translate-x-1'
                                }`} />
                        </button>
                    </div>

                    <hr className="border-slate-100" />

                    <div className="flex items-center justify-between">
                        <div>
                            <div className="font-bold text-slate-900">Allow New Registrations</div>
                            <div className="text-sm text-slate-500 max-w-md">
                                If disabled, the "Sign Up" page will be hidden. Only Admins can manually create users.
                            </div>
                        </div>
                        <button
                            onClick={() => initiateToggle('allow_registrations')}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${settings.allow_registrations ? 'bg-emerald-500' : 'bg-slate-200'
                                }`}
                        >
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition duration-200 ease-in-out ${settings.allow_registrations ? 'translate-x-6' : 'translate-x-1'
                                }`} />
                        </button>
                    </div>
                </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center gap-3">
                    <Cpu className="text-slate-400" size={20} />
                    <h3 className="font-bold text-slate-700">AI Engine Configuration</h3>
                </div>
                <div className="p-6">
                    <label className="block text-sm font-bold text-slate-700 mb-2">Default LLM Model</label>
                    <div className="flex gap-4">
                        <select
                            value={settings.openai_model}
                            onChange={(e) => setSettings({ ...settings, openai_model: e.target.value })}
                            className="flex-1 border border-slate-300 rounded-lg px-4 py-2 text-slate-700 focus:ring-2 focus:ring-cyan-500 outline-none bg-white"
                        >
                            <option value="claude-sonnet-4-20250514">Claude 4 Sonnet (Recommended)</option>
                            <option value="gpt-4-turbo">GPT-4 Turbo (Legacy)</option>
                        </select>
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                        This setting controls which model generates the initial strategies. Chat may use a different context window.
                    </p>
                </div>
            </div>

            <div className="flex justify-end pt-4">
                <button
                    onClick={initiateSave}
                    disabled={saving}
                    className="flex items-center gap-2 bg-slate-900 text-white px-6 py-3 rounded-xl font-bold hover:bg-slate-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl"
                >
                    {saving ? <Loader2 className="animate-spin" size={20} /> : <Save size={20} />}
                    {saving ? 'Saving Changes...' : 'Save Configuration'}
                </button>
            </div>

            <ConfirmModal
                isOpen={!!pendingAction}
                title={modalContent.title}
                message={modalContent.message}
                type={modalContent.type}
                onClose={() => setPendingAction(null)}
                onConfirm={executeAction}
            />
        </div>
    );
};