export const SimurghMark = ({ size = 36 }: { size?: number }) => (
    <svg width={size} height={size} viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg" fill="none">
        <defs>
            <linearGradient id="smwT" x1="0" y1="1" x2="1" y2="0">
                <stop offset="0%" stopColor="#f97316" />
                <stop offset="50%" stopColor="#eab308" />
                <stop offset="100%" stopColor="#84cc16" />
            </linearGradient>
            <linearGradient id="smwB" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
            <linearGradient id="smbd" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ffffff" />
                <stop offset="100%" stopColor="#e0f2fe" />
            </linearGradient>
        </defs>
        {/* Wings */}
        <path d="M44 44 C34 34,20 26,8 28 C16 30,26 36,34 44" fill="url(#smwT)" opacity="0.95" />
        <path d="M43 50 C30 46,16 46,8 54 C16 52,28 50,36 54" fill="url(#smwB)" opacity="0.85" />
        <path d="M52 44 C62 34,76 26,88 28 C80 30,70 36,62 44" fill="url(#smwT)" opacity="0.95" />
        <path d="M53 50 C66 46,80 46,88 54 C80 52,68 50,60 54" fill="url(#smwB)" opacity="0.85" />
        {/* Tail — 3 feathers */}
        <line x1="44" y1="66" x2="32" y2="86" stroke="#0e7490" strokeWidth="2.2" strokeLinecap="round" />
        <line x1="48" y1="68" x2="48" y2="88" stroke="#0891b2" strokeWidth="2.8" strokeLinecap="round" />
        <line x1="52" y1="66" x2="64" y2="86" stroke="#0e7490" strokeWidth="2.2" strokeLinecap="round" />
        {/* Tail eye motif */}
        <circle cx="48" cy="88" r="4" fill="#064e3b" />
        <circle cx="48" cy="88" r="2.4" fill="#22d3ee" />
        <circle cx="48" cy="88" r="1" fill="#083344" />
        <circle cx="47.2" cy="87.2" r="0.5" fill="white" />
        {/* Body */}
        <ellipse cx="48" cy="55" rx="7" ry="10" fill="url(#smbd)" stroke="#bae6fd" strokeWidth="0.5" />
        {/* Head */}
        <circle cx="48" cy="36" r="8" fill="url(#smbd)" stroke="#bae6fd" strokeWidth="0.5" />
        {/* Crown feathers */}
        <path d="M45 29 C43 23,42 18,43 14" stroke="#f97316" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        <path d="M48 28 C48 22,48 17,49 13" stroke="#06b6d4" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        <path d="M51 29 C53 23,56 18,58 15" stroke="#a855f7" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        <circle cx="43" cy="14" r="2" fill="#f97316" />
        <circle cx="49" cy="13" r="2" fill="#06b6d4" />
        <circle cx="58" cy="15" r="2" fill="#a855f7" />
        {/* Beak */}
        <path d="M52 34 L59 30 L52 38 Z" fill="#f97316" />
        {/* Eye */}
        <circle cx="52" cy="35" r="3" fill="#0ea5e9" />
        <circle cx="52" cy="35" r="1.4" fill="#083344" />
        <circle cx="51.3" cy="34.3" r="0.5" fill="white" />
    </svg>
);