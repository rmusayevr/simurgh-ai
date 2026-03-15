import React from 'react';
import { AlertTriangle } from 'lucide-react';

interface MaintenanceBannerProps {
    isActive: boolean;
}

export const MaintenanceBanner: React.FC<MaintenanceBannerProps> = ({ isActive }) => {
    if (!isActive) return null;

    return (
        <div className="bg-amber-500 text-white px-4 py-2 flex items-center justify-center gap-2 text-sm font-bold shadow-md relative z-50 animate-in slide-in-from-top duration-300">
            <AlertTriangle size={16} className="fill-white text-amber-500" />
            <span>SYSTEM IN MAINTENANCE MODE — External access is disabled.</span>
        </div>
    );
};