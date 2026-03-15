import { useRef, useState } from 'react';
import { X } from 'lucide-react';

interface TagInputProps {
    label: string;
    tags: string[];
    onChange: (tags: string[]) => void;
    placeholder?: string;
    suggestions?: string[];
    disabled?: boolean;
    maxTags?: number;
}

export const TagInput = ({
    label,
    tags,
    onChange,
    placeholder = 'Type and press Enter or comma...',
    suggestions = [],
    disabled = false,
    maxTags = 10,
}: TagInputProps) => {
    const [input, setInput] = useState('');
    const inputRef = useRef<HTMLInputElement>(null);

    const addTag = (raw: string) => {
        const value = raw.trim().toLowerCase();
        if (!value || tags.includes(value) || tags.length >= maxTags) return;
        onChange([...tags, value]);
        setInput('');
    };

    const removeTag = (tag: string) => {
        onChange(tags.filter(t => t !== tag));
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            addTag(input);
        } else if (e.key === 'Backspace' && !input && tags.length > 0) {
            removeTag(tags[tags.length - 1]);
        }
    };

    const handleBlur = () => {
        if (input.trim()) addTag(input);
    };

    // Suggestions not yet in the tags list
    const visibleSuggestions = suggestions.filter(s => !tags.includes(s));

    return (
        <div>
            <label className="block text-xs font-black text-slate-500 uppercase tracking-wider mb-2">
                {label}
            </label>

            {/* Pill container + input */}
            <div
                className={`min-h-[44px] w-full flex flex-wrap gap-1.5 items-center px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus-within:bg-white focus-within:ring-2 focus-within:ring-cyan-500 transition-all cursor-text ${disabled ? 'opacity-50 pointer-events-none' : ''}`}
                onClick={() => inputRef.current?.focus()}
            >
                {tags.map(tag => (
                    <span
                        key={tag}
                        className="inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wider text-cyan-700 bg-cyan-50 border border-cyan-100 px-2 py-0.5 rounded-lg"
                    >
                        {tag}
                        <button
                            type="button"
                            onClick={e => { e.stopPropagation(); removeTag(tag); }}
                            className="text-cyan-400 hover:text-cyan-700 transition-colors ml-0.5"
                            aria-label={`Remove ${tag}`}
                        >
                            <X size={10} strokeWidth={3} />
                        </button>
                    </span>
                ))}
                <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onBlur={handleBlur}
                    placeholder={tags.length === 0 ? placeholder : ''}
                    disabled={disabled}
                    className="flex-1 min-w-[120px] bg-transparent outline-none text-sm text-slate-700 placeholder:text-slate-400 font-sans py-0.5"
                />
            </div>

            {/* Quick-pick suggestions */}
            {visibleSuggestions.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                    {visibleSuggestions.map(s => (
                        <button
                            key={s}
                            type="button"
                            onClick={() => addTag(s)}
                            disabled={disabled}
                            className="text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-100 hover:bg-cyan-50 hover:text-cyan-700 hover:border-cyan-200 border border-slate-200 px-2 py-0.5 rounded-lg transition-colors"
                        >
                            + {s}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};