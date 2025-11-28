// Application State Types
export type BlobState = 'silent' | 'listening' | 'thinking' | 'speaking';

export type ConnectionStatus = 'disconnected' | 'connecting' | 'authenticating' | 'connected' | 'closing';

export type ConnectionQuality = 'good' | 'degraded' | 'poor';

export type Language = 'ar-EG' | 'en-US';

// WebSocket Message Types - Client to Server
export interface StartSessionMessage {
    type: 'start_session';
    session_id: string;
    auth: string;
    metadata: {
        lang: Language;
        sample_rate: number;
        encoding: string;
        user_id?: string;
        device_type: string;
        client_version: string;
        voice_used?: string;
    };
}

export interface AudioChunkMessage {
    type: 'audio_chunk';
    session_id: string;
    seq: number;
    audio_data: string; // Base64 encoded
    timestamp: number;
}

export interface EndStreamMessage {
    type: 'end_stream';
    session_id: string;
    reason?: string;
}

export interface TextMessage {
    type: 'text_message';
    session_id: string;
    text: string;
    timestamp: number;
}

// WebSocket Message Types - Server to Client
export interface TranscriptMessage {
    type: 'transcript';
    session_id: string;
    text: string;
    is_final: boolean;
    confidence: number;
    language: string;
    timestamp: number;
}

export interface RagMetadataMessage {
    type: 'rag_metadata';
    session_id: string;
    sources_count?: number;
    query_type?: string;
    processing_time_ms?: number;
    num_chunks?: number;
    top_score?: number;
    num_structured_units?: number;
    structured_units?: Array<{
        [key: string]: any;
        image_url?: string;
    }>;
    unit_selector?: {
        code?: string;
        error?: string;
    };
    unit_selector_relevance_score?: number;
    timestamp?: number;
}

export interface RagChunkMessage {
    type: 'rag_chunk';
    session_id: string;
    chunk: string;  // Backend sends 'chunk' not 'text'
    is_last: boolean;  // Backend sends 'is_last' not 'is_final'
    // Optional fields that may be present
    chunk_index?: number;
    text?: string;  // For backward compatibility
    is_final?: boolean;  // For backward compatibility
    has_images?: boolean;
    image_urls?: string[];
    timestamp?: number;
}

export interface TtsQueueUpdateMessage {
    type: 'tts_queue_update';
    session_id: string;
    queued: number;
    next_seq: number;
    voice_used?: string;
    timestamp?: number;
}

export interface TtsAudioMessage {
    type: 'tts_audio';
    session_id: string;
    seq: number;
    audio_base64: string; // Base64 encoded MP3
    audio_data?: string;
    chunk_index?: number;
    format: string;
    is_last: boolean;
    is_final_chunk?: boolean;
    voice_used?: string;
    timestamp?: number;
}

export interface ErrorMessage {
    type: 'error';
    session_id: string;
    code: number;  // Backend sends int, not string
    message: string;
    error_type?: string;  // Backend uses error_type, not details
    timestamp?: number;
}

export interface SessionClosedMessage {
    type: 'session_closed';
    session_id: string;
    reason: string;
    message: string;
    timestamp: number;
}

export type ServerMessage =
    | TranscriptMessage
    | RagMetadataMessage
    | RagChunkMessage
    | TtsQueueUpdateMessage
    | TtsAudioMessage
    | ErrorMessage
    | SessionClosedMessage;

// Application State
export interface AppState {
    connection: {
        status: ConnectionStatus;
        websocket: WebSocket | null;
        sessionId: string | null;
        quality: ConnectionQuality;
        lastPingTime: number;
    };

    blob: {
        state: BlobState;
        audioLevel: number; // 0-100
        frequencyData: number[]; // 5 bands for speaking state
    };

    audio: {
        isRecording: boolean;
        isPlaying: boolean;
        recordingDuration: number;
        playbackProgress: number;
        audioQueue: ArrayBuffer[];
    };

    content: {
        transcript: string | null;
        response: string;
        gallery: GalleryUnit[];
        isStreaming: boolean;
    };

    ui: {
        micButtonEnabled: boolean;
        showImages: boolean;
        slideBarExpanded: boolean;
        errorMessage: string | null;
        sessionTimer: number;
    };

    settings: {
        language: Language;
        autoPlayAudio: boolean;
        showTranscript: boolean;
        theme: 'dark';
    };
}

export interface GalleryUnit {
    id: string;
    title: string;
    subtitle?: string;
    description?: string;
    imageUrl: string;
    tags: string[];
    highlights: Array<{
        label: string;
        value: string;
    }>;
    metrics?: Array<{
        label: string;
        value: string;
    }>;
    raw?: Record<string, any>;
}

// Audio Processing Types
export interface FrequencyBands {
    low: number;           // 0-200Hz
    lowMid: number;        // 200-600Hz
    mid: number;           // 600-2000Hz
    midHigh: number;       // 2000-6000Hz
    high: number;          // 6000Hz+
}

export interface AudioAnalysisResult {
    bands: FrequencyBands;
    overall: number;
    timestamp: number;
}
