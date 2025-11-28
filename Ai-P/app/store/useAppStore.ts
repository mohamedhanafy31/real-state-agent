import { create } from 'zustand';
import type { AppState, BlobState, ConnectionStatus, ConnectionQuality, Language, GalleryUnit } from '@/types';

interface AppStore extends AppState {
    // Connection actions
    setConnectionStatus: (status: ConnectionStatus) => void;
    setWebSocket: (ws: WebSocket | null) => void;
    setSessionId: (id: string | null) => void;
    setConnectionQuality: (quality: ConnectionQuality) => void;

    // Blob actions
    setBlobState: (state: BlobState) => void;
    setAudioLevel: (level: number) => void;
    setFrequencyData: (data: number[]) => void;

    // Audio actions
    setIsRecording: (recording: boolean) => void;
    setIsPlaying: (playing: boolean) => void;
    incrementRecordingDuration: () => void;
    resetRecordingDuration: () => void;
    addToAudioQueue: (buffer: ArrayBuffer) => void;
    clearAudioQueue: () => void;

    // Content actions
    setTranscript: (text: string | null) => void;
    appendResponse: (text: string) => void;
    clearResponse: () => void;
    setGalleryItems: (items: GalleryUnit[]) => void;
    appendGalleryItems: (items: GalleryUnit[]) => void;
    clearGallery: () => void;
    setIsStreaming: (streaming: boolean) => void;
    toggleUnitSelection: (unitId: string) => void;
    clearSelectedUnits: () => void;
    keepOnlySelectedUnitsAndLock: () => void;

    // UI actions
    setMicButtonEnabled: (enabled: boolean) => void;
    setShowImages: (show: boolean) => void;
    setErrorMessage: (message: string | null) => void;
    incrementSessionTimer: () => void;
    resetSessionTimer: () => void;

    // Settings actions
    setLanguage: (lang: Language) => void;
}

export const useAppStore = create<AppStore>((set) => ({
    // Initial state
    connection: {
        status: 'disconnected',
        websocket: null,
        sessionId: null,
        quality: 'good',
        lastPingTime: 0,
    },

    blob: {
        state: 'silent',
        audioLevel: 0,
        frequencyData: [0, 0, 0, 0, 0],
    },

    audio: {
        isRecording: false,
        isPlaying: false,
        recordingDuration: 0,
        playbackProgress: 0,
        audioQueue: [],
    },

    content: {
        transcript: null,
        response: '',
        gallery: [],
        selectedUnitIds: [],
        selectionLocked: false,
        isStreaming: false,
    },

    ui: {
        micButtonEnabled: true,
        showImages: false,
        slideBarExpanded: false,
        errorMessage: null,
        sessionTimer: 0,
    },

    settings: {
        language: 'ar-EG',
        autoPlayAudio: true,
        showTranscript: true,
        theme: 'dark',
    },

    // Connection actions
    setConnectionStatus: (status) =>
        set((state) => ({
            connection: { ...state.connection, status },
        })),

    setWebSocket: (websocket) =>
        set((state) => ({
            connection: { ...state.connection, websocket },
        })),

    setSessionId: (sessionId) =>
        set((state) => ({
            connection: { ...state.connection, sessionId },
        })),

    setConnectionQuality: (quality) =>
        set((state) => ({
            connection: { ...state.connection, quality },
        })),

    // Blob actions
    setBlobState: (state: BlobState) =>
        set((prev) => {
            return {
                blob: { ...prev.blob, state },
            };
        }),

    setAudioLevel: (audioLevel) =>
        set((state) => ({
            blob: { ...state.blob, audioLevel },
        })),

    setFrequencyData: (frequencyData) =>
        set((state) => ({
            blob: { ...state.blob, frequencyData },
        })),

    // Audio actions
    setIsRecording: (isRecording) =>
        set((state) => ({
            audio: { ...state.audio, isRecording },
        })),

    setIsPlaying: (isPlaying) =>
        set((state) => ({
            audio: { ...state.audio, isPlaying },
        })),

    incrementRecordingDuration: () =>
        set((state) => ({
            audio: { ...state.audio, recordingDuration: state.audio.recordingDuration + 1 },
        })),

    resetRecordingDuration: () =>
        set((state) => ({
            audio: { ...state.audio, recordingDuration: 0 },
        })),

    addToAudioQueue: (buffer) =>
        set((state) => ({
            audio: { ...state.audio, audioQueue: [...state.audio.audioQueue, buffer] },
        })),

    clearAudioQueue: () =>
        set((state) => ({
            audio: { ...state.audio, audioQueue: [] },
        })),

    // Content actions
    setTranscript: (transcript) =>
        set((state) => ({
            content: { ...state.content, transcript },
        })),

    appendResponse: (text) =>
        set((state) => ({
            content: { ...state.content, response: state.content.response + text },
        })),

    clearResponse: () =>
        set((state) => ({
            content: { ...state.content, response: '' },
        })),

    setGalleryItems: (items) =>
        set((state) => ({
            content: { ...state.content, gallery: items, selectedUnitIds: [], selectionLocked: false },
            ui: { ...state.ui, showImages: items.length > 0 },
        })),

    appendGalleryItems: (items) =>
        set((state) => {
            const existing = state.content.gallery;
            const deduped = [...existing];
            items.forEach((item) => {
                if (!item) {
                    return;
                }
                const exists = deduped.some(
                    (entry) =>
                        entry.id === item.id ||
                        (entry.imageUrl && item.imageUrl && entry.imageUrl === item.imageUrl)
                );
                if (!exists) {
                    deduped.push(item);
                }
            });
            return {
                content: { ...state.content, gallery: deduped, selectedUnitIds: [], selectionLocked: false },
                ui: { ...state.ui, showImages: deduped.length > 0 },
            };
        }),

    clearGallery: () =>
        set((state) => ({
            content: { ...state.content, gallery: [], selectedUnitIds: [], selectionLocked: false },
            ui: { ...state.ui, showImages: false },
        })),

    setIsStreaming: (isStreaming) =>
        set((state) => ({
            content: { ...state.content, isStreaming },
        })),

    toggleUnitSelection: (unitId) =>
        set((state) => {
            const current = state.content.selectedUnitIds;
            const exists = current.includes(unitId);
            const next = exists ? current.filter((id) => id !== unitId) : [...current, unitId];
            return {
                content: { ...state.content, selectedUnitIds: next },
            };
        }),

    clearSelectedUnits: () =>
        set((state) => ({
            content: { ...state.content, selectedUnitIds: [], selectionLocked: false },
        })),

    keepOnlySelectedUnitsAndLock: () =>
        set((state) => {
            const ids = state.content.selectedUnitIds;
            if (!ids || ids.length === 0) {
                return state;
            }
            const filtered = state.content.gallery.filter((unit) => ids.includes(unit.id));
            return {
                content: {
                    ...state.content,
                    gallery: filtered,
                    selectedUnitIds: ids,
                    selectionLocked: true,
                },
                ui: {
                    ...state.ui,
                    showImages: filtered.length > 0,
                },
            };
        }),

    // UI actions
    setMicButtonEnabled: (micButtonEnabled) =>
        set((state) => ({
            ui: { ...state.ui, micButtonEnabled },
        })),

    setShowImages: (showImages) =>
        set((state) => ({
            ui: { ...state.ui, showImages },
        })),

    setErrorMessage: (errorMessage) =>
        set((state) => ({
            ui: { ...state.ui, errorMessage },
        })),

    incrementSessionTimer: () =>
        set((state) => ({
            ui: { ...state.ui, sessionTimer: state.ui.sessionTimer + 1 },
        })),

    resetSessionTimer: () =>
        set((state) => ({
            ui: { ...state.ui, sessionTimer: 0 },
        })),

    // Settings actions
    setLanguage: (language) =>
        set((state) => ({
            settings: { ...state.settings, language },
        })),
}));
