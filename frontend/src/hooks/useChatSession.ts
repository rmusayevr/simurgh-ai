import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api/client';
import type { ChatMessage, ProposalVariation } from '../types';

interface UseChatSessionResult {
    chatHistory: ChatMessage[];
    chatInput: string;
    chatLoading: boolean;
    chatEndRef: React.RefObject<HTMLDivElement | null>;
    setChatInput: (val: string) => void;
    handleSendMessage: () => Promise<void>;
    // Returns the updated variation with synced chat_history (for caller to persist)
    updatedVariation: ProposalVariation | null;
}

/**
 * Manages chat with a proposal variation's AI persona.
 * Resets when variationId changes.
 * Caller is responsible for syncing updatedVariation back into proposal state.
 */
export function useChatSession(
    selectedVariation: ProposalVariation | null,
    onError: (title: string, message: string, onConfirm: () => void, type?: 'danger' | 'info') => void,
): UseChatSessionResult {
    const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
    const [chatInput, setChatInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const [updatedVariation, setUpdatedVariation] = useState<ProposalVariation | null>(null);
    const chatEndRef = useRef<HTMLDivElement>(null);

    // ── Reset on variation change ──────────────────────────────────────────────
    useEffect(() => {
        setChatHistory(
            selectedVariation?.chat_history
                ? JSON.parse(JSON.stringify(selectedVariation.chat_history))
                : []
        );
        setUpdatedVariation(null);
        setChatInput('');
    }, [selectedVariation?.id, selectedVariation?.chat_history]);

    // ── Auto-scroll ────────────────────────────────────────────────────────────
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatHistory]);

    // ── Send message ───────────────────────────────────────────────────────────
    const handleSendMessage = useCallback(async () => {
        const message = chatInput.trim();
        if (!message || !selectedVariation) return;

        const userMsg: ChatMessage = { role: 'user', content: message };
        const optimisticHistory = [...chatHistory, userMsg];
        setChatHistory(optimisticHistory);
        setChatInput('');
        setChatLoading(true);

        try {
            const res = await api.post<{ updated_history: ChatMessage[]; response: string }>(
                `/proposals/variations/${selectedVariation.id}/chat`,
                { message, history: optimisticHistory }
            );

            const serverHistory = res.data.updated_history ?? [
                ...optimisticHistory,
                { role: 'assistant' as const, content: res.data.response },
            ];

            setChatHistory(serverHistory);
            const updated = { ...selectedVariation, chat_history: serverHistory };
            setUpdatedVariation(updated);
        } catch {
            setChatHistory(chatHistory); // revert optimistic
            onError('Error', 'Failed to send message. Please try again.', () => { });
        } finally {
            setChatLoading(false);
        }
    }, [chatInput, chatHistory, selectedVariation, onError]);

    return {
        chatHistory, chatInput, chatLoading, chatEndRef,
        setChatInput, handleSendMessage, updatedVariation,
    };
}