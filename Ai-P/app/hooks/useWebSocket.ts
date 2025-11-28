'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '@/store/useAppStore';
import type { GalleryUnit, ServerMessage, ErrorMessage } from '@/types';
import { v4 as uuidv4 } from 'uuid';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8040/ws/voice';
const STATIC_ORCHESTRATOR_TOKEN = process.env.NEXT_PUBLIC_ORCHESTRATOR_TOKEN;
const RECONNECT_ATTEMPTS = 3;
const RECONNECT_DELAY = [1000, 2000, 4000]; // Exponential backoff
const MAX_AUDIO_BUFFER_SIZE = 10 * 1024 * 1024; // 10MB (matches orchestrator limit)
const AUDIO_CHUNK_SEND_THROTTLE_MS = 50; // Throttle audio chunk sends to avoid overwhelming

interface UseWebSocketOptions {
    onTTSAudio?: (base64Audio: string) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
    const wsRef = useRef<WebSocket | null>(null);
    const sequenceRef = useRef(0);
    const reconnectAttemptsRef = useRef(0);
    const connectionStartTimeRef = useRef<number | null>(null);
    const lastMessageTimeRef = useRef<number | null>(null);
    const messageCountRef = useRef({ sent: 0, received: 0 });
    const audioChunkStatsRef = useRef({ count: 0, totalSize: 0, firstChunkTime: null as number | null, lastChunkTime: null as number | null });
    const onTTSAudioRef = useRef(options.onTTSAudio);
    const audioChunkQueueRef = useRef<Array<{base64Audio: string, sessionId: string, timestamp: number}>>([]);
    const audioChunkThrottleTimerRef = useRef<NodeJS.Timeout | null>(null);
    const ttsQueueInfoRef = useRef<{queued: number, nextSeq: number} | null>(null);
    const awaitingServerResponseRef = useRef(false);
    const tokenCacheRef = useRef<{ token: string; expiresAt: number } | null>(null);
    
    // Update ref when options change, but don't recreate callbacks
    useEffect(() => {
        onTTSAudioRef.current = options.onTTSAudio;
    }, [options.onTTSAudio]);

    const {
        setConnectionStatus,
        setWebSocket,
        setSessionId,
        setConnectionQuality,
        setBlobState,
        setTranscript,
        appendResponse,
        clearResponse,
        setGalleryItems,
        appendGalleryItems,
        clearGallery,
        setIsStreaming,
        setErrorMessage,
    } = useAppStore();

    const handleMessage = useCallback((event: MessageEvent) => {
        const receiveTime = performance.now();
        const messageSize = event.data instanceof Blob ? event.data.size : new Blob([event.data]).size;
        const timeSinceLastMessage = lastMessageTimeRef.current ? receiveTime - lastMessageTimeRef.current : null;
        
        try {
            const parseStart = performance.now();
            const message: ServerMessage = JSON.parse(event.data);
            const parseTime = performance.now() - parseStart;
            
            messageCountRef.current.received++;
            lastMessageTimeRef.current = receiveTime;

            console.log('[OrchestratorAPI] ⬇️ Message received:', {
                type: message.type,
                messageSize: messageSize,
                messageSizeKB: (messageSize / 1024).toFixed(2),
                parseTime: parseTime.toFixed(2) + 'ms',
                timeSinceLastMessage: timeSinceLastMessage ? timeSinceLastMessage.toFixed(2) + 'ms' : 'N/A',
                totalReceived: messageCountRef.current.received,
                timestamp: receiveTime,
                rawData: event.data instanceof Blob ? 'Blob' : event.data.substring(0, 200) + (event.data.length > 200 ? '...' : '')
            });

            switch (message.type) {
                case 'transcript':
                    console.log('[OrchestratorAPI] 📝 Transcript message:', {
                        is_final: message.is_final,
                        text: message.text,
                        textLength: message.text?.length || 0,
                        timestamp: receiveTime
                    });
                    if (message.is_final) {
                        awaitingServerResponseRef.current = false;
                        setTranscript(message.text);
                    }
                    break;

                case 'rag_metadata':
                    console.log('[OrchestratorAPI] 📚 RAG metadata received:', {
                        metadata: message,
                        structured_units_count: message.structured_units?.length || 0,
                        timestamp: receiveTime
                    });
                    clearResponse();
                    setIsStreaming(true);
                    clearGallery();
                    if (message.structured_units && Array.isArray(message.structured_units)) {
                        const normalizedUnits = normalizeStructuredUnits(
                            message.structured_units,
                            message.session_id
                        );
                        if (normalizedUnits.length > 0) {
                            console.info('[Images] Received structured units with images', {
                                count: normalizedUnits.length,
                                sessionId: message.session_id,
                                timestamp: receiveTime
                            });
                            setGalleryItems(normalizedUnits);
                        }
                    }
                    break;

                case 'rag_chunk':
                    // Backend sends 'chunk' and 'is_last', but we support both formats
                    const chunkText = message.chunk || message.text || '';
                    const isFinal = message.is_last !== undefined ? message.is_last : (message.is_final || false);
                    
                    console.log('[OrchestratorAPI] 📄 RAG chunk received:', {
                        chunk: chunkText.substring(0, 100) + (chunkText.length > 100 ? '...' : ''),
                        chunkLength: chunkText.length,
                        is_last: message.is_last,
                        is_final: message.is_final,
                        chunk_index: message.chunk_index,
                        has_images: message.has_images,
                        imageCount: message.image_urls?.length || 0,
                        imageUrls: message.image_urls || [],
                        timestamp: receiveTime
                    });
                    
                    if (chunkText) {
                        appendResponse(chunkText);
                    } else {
                        console.warn('[OrchestratorAPI] ⚠️ RAG chunk received with empty text/chunk');
                    }

                    if (message.has_images && Array.isArray(message.image_urls) && message.image_urls.length > 0) {
                        const validUrls = message.image_urls.filter(
                            (url: string) => typeof url === 'string' && url.trim().length > 0
                        );
                        if (validUrls.length > 0) {
                            console.info('[Images] Received image URLs from chunk', {
                                count: validUrls.length,
                                sessionId: message.session_id,
                                timestamp: receiveTime
                            });
                            const placeholders = createGalleryUnitsFromUrls(
                                validUrls,
                                message.session_id,
                                chunkText
                            );
                            if (placeholders.length) {
                                appendGalleryItems(placeholders);
                            }
                        }
                    }

                    if (isFinal) {
                        console.log('[OrchestratorAPI] ✅ RAG streaming complete');
                        setIsStreaming(false);
                    }
                    break;

                case 'tts_queue_update':
                    ttsQueueInfoRef.current = {
                        queued: message.queued || 0,
                        nextSeq: message.next_seq || 0
                    };
                    console.log('[OrchestratorAPI] 🔊 TTS queue update:', {
                        queued: message.queued,
                        nextSeq: message.next_seq,
                        timestamp: receiveTime
                    });
                    break;

                case 'tts_audio': {
                    const audioPayload = message.audio_base64 || message.audio_data;
                    const audioSize = audioPayload ? audioPayload.length : 0;
                    console.log('[OrchestratorAPI] 🎵 TTS audio received:', {
                        seq: message.seq,
                        chunkIndex: message.chunk_index,
                        audioSize: audioSize,
                        audioSizeKB: (audioSize / 1024).toFixed(2),
                        voiceUsed: message.voice_used,
                        timestamp: receiveTime
                    });
                    // This will be handled by the audio playback system
                    if (onTTSAudioRef.current && audioPayload) {
                        onTTSAudioRef.current(audioPayload);
                    }
                    break;
                }

                case 'error': {
                    if (!message || typeof message !== 'object') {
                        console.error('[OrchestratorAPI] ❌ Received malformed error payload:', message);
                        setErrorMessage('حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.');
                        setBlobState('silent');
                        break;
                    }

                    const payloadKeys = Object.keys(message);
                    if (payloadKeys.length === 0) {
                        console.warn('[OrchestratorAPI] ⚠️ Empty error payload received from orchestrator');
                        setErrorMessage('حدث خطأ غير متوقع مع الخادم. حاول مرة أخرى.');
                        awaitingServerResponseRef.current = false;
                        setBlobState('silent');
                        break;
                    }

                    const rawCode = (message as Partial<ErrorMessage>).code;
                    const rawType = (message as Partial<ErrorMessage>).error_type;
                    const rawMessage = (message as Partial<ErrorMessage>).message;

                    const errorCode = typeof rawCode === 'number' && Number.isFinite(rawCode)
                        ? rawCode
                        : undefined;
                    const errorMessage =
                        typeof rawMessage === 'string' && rawMessage.trim().length > 0
                            ? rawMessage
                            : 'حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.';
                    const errorType =
                        typeof rawType === 'string' && rawType.trim().length > 0
                            ? rawType
                            : 'unknown';
                    const isAudioTooLong = errorType === 'audio_too_long';
                    const isBufferOverflow = errorCode === 413 && !isAudioTooLong;
                    const shouldClearQueue = isBufferOverflow || isAudioTooLong;
                    const isTransientError =
                        typeof errorCode === 'number' &&
                        (errorCode >= 500 || errorCode === 408 || errorCode === 429);
                    const isInformationalError =
                        errorCode === undefined &&
                        errorType === 'unknown' &&
                        (rawMessage === undefined || rawMessage === null || String(rawMessage).trim().length === 0);

                    const errorContext = {
                        code: errorCode ?? 'unknown',
                        message: errorMessage,
                        error_type: errorType,
                        isBufferOverflow,
                        isAudioTooLong,
                        isTransientError,
                        timestamp: receiveTime,
                        payload: message
                    };
                    
                    if (isInformationalError) {
                        console.warn('[OrchestratorAPI] ⚠️ Generic error payload received:', errorContext);
                    } else {
                        console.error('[OrchestratorAPI] ❌ Error message:', errorContext);
                    }
                    
                    setErrorMessage(errorMessage);
                    awaitingServerResponseRef.current = false;
                    setBlobState('silent');
                    
                    // Clear audio queue for buffer overflow or long recordings
                    if (shouldClearQueue) {
                        console.warn('[OrchestratorAPI] ⚠️ Clearing audio chunk queue due to error', {
                            reason: isAudioTooLong ? 'audio_too_long' : 'buffer_overflow'
                        });
                        audioChunkQueueRef.current = [];
                        if (audioChunkThrottleTimerRef.current) {
                            clearTimeout(audioChunkThrottleTimerRef.current);
                            audioChunkThrottleTimerRef.current = null;
                        }
                        audioChunkStatsRef.current = { count: 0, totalSize: 0, firstChunkTime: null, lastChunkTime: null };
                    }
                    break;
                }

                case 'session_closed':
                    console.log('[OrchestratorAPI] 🔒 Session closed:', {
                        reason: message.reason,
                        session_id: message.session_id,
                        message: message.message,
                        timestamp: receiveTime
                    });
                    awaitingServerResponseRef.current = false;
                    setConnectionStatus('disconnected');
                    setBlobState('silent');
                    // Reset session ID so a new one will be created on next connection
                    setSessionId(null);
                    // Reset connection tracking to allow reconnection
                    reconnectAttemptsRef.current = 0;
                    
                    // IMPORTANT: The orchestrator closes the WebSocket after sending session_closed
                    // We need to close our side too and create a new connection for the next session
                    // Don't try to reuse this connection - it's already closed on the server side
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                        console.log('[OrchestratorAPI] 🔌 Closing WebSocket after session closure (server already closed it)');
                        try {
                            wsRef.current.close(1000, 'Session completed');
                        } catch {
                            // Connection might already be closed
                        }
                    }
                    wsRef.current = null;
                    setWebSocket(null);
                    break;
            }
        } catch (error) {
            console.error('[OrchestratorAPI] ⚠️ Failed to parse WebSocket message:', {
                error: error,
                dataType: typeof event.data,
                dataLength: event.data instanceof Blob ? event.data.size : event.data.length,
                dataPreview: event.data instanceof Blob ? 'Blob' : String(event.data).substring(0, 200),
                timestamp: receiveTime
            });
        }
    }, [
        setTranscript,
        appendResponse,
        clearResponse,
        setGalleryItems,
        appendGalleryItems,
        clearGallery,
        setIsStreaming,
        setErrorMessage,
        setBlobState,
        setConnectionStatus,
        setSessionId,
        setWebSocket
    ]);

    const fetchAuthToken = useCallback(async (): Promise<string | null> => {
        if (STATIC_ORCHESTRATOR_TOKEN) {
            return STATIC_ORCHESTRATOR_TOKEN;
        }

        const now = Date.now();
        if (
            tokenCacheRef.current &&
            tokenCacheRef.current.expiresAt - now > 15_000
        ) {
            return tokenCacheRef.current.token;
        }

        try {
            const response = await fetch('/api/orchestrator/token', {
                cache: 'no-store',
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(
                    `Token endpoint responded with ${response.status}: ${errorText}`,
                );
            }
            const data: { token: string; expires_at: string } =
                await response.json();
            if (!data.token || !data.expires_at) {
                throw new Error('Token endpoint returned an invalid payload');
            }
            const expiresAt = new Date(data.expires_at).getTime();
            tokenCacheRef.current = {
                token: data.token,
                expiresAt: Number.isFinite(expiresAt)
                    ? expiresAt
                    : now + 60_000,
            };
            return data.token;
        } catch (error) {
            console.error('[OrchestratorAPI] ❌ Failed to fetch auth token:', {
                error,
            });
            setErrorMessage('تعذر المصادقة مع الخادم. حاول مرة أخرى.');
            return null;
        }
    }, [setErrorMessage]);

    const connect = useCallback(function connectWithRetry(sessionId?: string) {
        const connectStartTime = performance.now();
        
        // If WebSocket is already open, check if we have an active session
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            const currentSessionId = useAppStore.getState().connection.sessionId;
            // If we have a session ID and it matches the requested one (or no specific one requested), we're good
            if (currentSessionId && (!sessionId || currentSessionId === sessionId)) {
                console.log('[OrchestratorAPI] ℹ️ WebSocket already connected with active session:', {
                    sessionId: currentSessionId,
                    timestamp: connectStartTime
                });
                return wsRef.current;
            }
            // If WebSocket is open but no session ID, the previous session was closed
            // The orchestrator closes the WebSocket after each session, so we should close and reconnect
            if (!currentSessionId) {
                console.log('[OrchestratorAPI] 🔄 WebSocket is open but session was closed, closing and reconnecting:', {
                    timestamp: connectStartTime
                });
                // Close the existing connection (server already closed it, but clean up our side)
                try {
                    wsRef.current.close(1000, 'Previous session completed');
                } catch {
                    // Connection might already be closed
                }
                wsRef.current = null;
                setWebSocket(null);
                // Fall through to create a new connection
            }
        }

        console.log('[OrchestratorAPI] 🔌 Initiating WebSocket connection:', {
            url: WS_URL,
            existingSessionId: sessionId,
            reconnectAttempt: reconnectAttemptsRef.current,
            timestamp: connectStartTime
        });

        setConnectionStatus('connecting');
        connectionStartTimeRef.current = connectStartTime;

        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;
        setWebSocket(ws);

        ws.onopen = async () => {
            const openTime = performance.now();
            const connectionTime = connectionStartTimeRef.current ? openTime - connectionStartTimeRef.current : 0;
            
            console.log('[OrchestratorAPI] ✅ WebSocket connection opened:', {
                connectionTime: connectionTime.toFixed(2) + 'ms',
                readyState: ws.readyState,
                protocol: ws.protocol,
                url: ws.url,
                timestamp: openTime
            });

            setConnectionStatus('authenticating');

            // Send start_session message
            const sid = sessionId || uuidv4();
            setSessionId(sid);

            const authToken = await fetchAuthToken();
            if (!authToken) {
                console.error('[OrchestratorAPI] ❌ Aborting session start, no auth token available');
                setConnectionStatus('disconnected');
                ws.close(1008, 'auth_failed');
                return;
            }

            const startSession = {
                type: 'start_session',
                session_id: sid,
                auth: authToken.startsWith('Bearer ') ? authToken : `Bearer ${authToken}`,
                metadata: {
                    lang: 'ar', // Force 'ar' to match backend logic (ar-EG causes fallback to en-US)
                    sample_rate: 16000,
                    voice_used: 'ar-EG-Standard-A',
                },
            };

            const sessionMessage = JSON.stringify(startSession);
            const sessionMessageSize = new Blob([sessionMessage]).size;
            const sendStartTime = performance.now();
            
            console.log('[OrchestratorAPI] 📤 Sending start_session:', {
                session_id: sid,
                messageSize: sessionMessageSize,
                messageSizeKB: (sessionMessageSize / 1024).toFixed(2),
                metadata: startSession.metadata,
                timestamp: sendStartTime
            });

            ws.send(sessionMessage);
            
            const sendTime = performance.now() - sendStartTime;
            console.log('[OrchestratorAPI] ✅ start_session sent:', {
                sendTime: sendTime.toFixed(2) + 'ms',
                timestamp: performance.now()
            });

            messageCountRef.current.sent++;
            audioChunkStatsRef.current = { count: 0, totalSize: 0, firstChunkTime: null, lastChunkTime: null };

            // Assume successful authentication (in production, wait for acknowledgment)
            setTimeout(() => {
                const authCompleteTime = performance.now();
                const totalAuthTime = authCompleteTime - openTime;
                
                console.log('[OrchestratorAPI] 🔐 Authentication complete (assumed):', {
                    session_id: sid,
                    authTime: totalAuthTime.toFixed(2) + 'ms',
                    timestamp: authCompleteTime
                });
                
                setConnectionStatus('connected');
                setConnectionQuality('good');
                reconnectAttemptsRef.current = 0;
            }, 500);
        };

        ws.onmessage = handleMessage;

        ws.onerror = (error) => {
            const errorTime = performance.now();
            const connectionDuration = connectionStartTimeRef.current ? errorTime - connectionStartTimeRef.current : 0;
            
            console.error('[OrchestratorAPI] ❌ WebSocket error:', {
                error: error,
                readyState: ws.readyState,
                connectionDuration: connectionDuration.toFixed(2) + 'ms',
                reconnectAttempt: reconnectAttemptsRef.current,
                timestamp: errorTime
            });
            
            setConnectionStatus('disconnected');
            setConnectionQuality('poor');
        };

        ws.onclose = (event) => {
            const closeTime = performance.now();
            const connectionDuration = connectionStartTimeRef.current ? closeTime - connectionStartTimeRef.current : 0;
            
            console.log('[OrchestratorAPI] 🔌 WebSocket connection closed:', {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean,
                connectionDuration: connectionDuration.toFixed(2) + 'ms',
                messagesSent: messageCountRef.current.sent,
                messagesReceived: messageCountRef.current.received,
                reconnectAttempt: reconnectAttemptsRef.current,
                maxReconnectAttempts: RECONNECT_ATTEMPTS,
                timestamp: closeTime
            });

            setConnectionStatus('disconnected');
            setWebSocket(null);

            if (awaitingServerResponseRef.current) {
                console.warn('[OrchestratorAPI] ⚠️ WebSocket closed while awaiting server response');
                awaitingServerResponseRef.current = false;
                setErrorMessage('تم قطع الاتصال أثناء معالجة الصوت. حاول مرة أخرى.');
            }

            // Attempt reconnection
            if (reconnectAttemptsRef.current < RECONNECT_ATTEMPTS) {
                const delay = RECONNECT_DELAY[reconnectAttemptsRef.current];
                
                console.log('[OrchestratorAPI] 🔄 Scheduling reconnection:', {
                    attempt: reconnectAttemptsRef.current + 1,
                    delay: delay + 'ms',
                    timestamp: closeTime
                });

                setTimeout(() => {
                    reconnectAttemptsRef.current++;
                    console.log('[OrchestratorAPI] 🔄 Attempting reconnection:', {
                        attempt: reconnectAttemptsRef.current,
                        timestamp: performance.now()
                    });
                    connectWithRetry(sessionId);
                }, delay);
            } else {
                console.log('[OrchestratorAPI] ⛔ Max reconnection attempts reached, giving up');
            }
        };

        return ws;
    }, [setConnectionStatus, setWebSocket, setSessionId, setConnectionQuality, handleMessage, setErrorMessage, fetchAuthToken]);

    // Internal function to actually send audio chunks
    const _sendAudioChunkImmediate = useCallback((base64Audio: string, sessionId: string, seq: number) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            return false;
        }

        const sendStartTime = performance.now();
        const audioSize = base64Audio.length;
        const clientTimestamp = Date.now() / 1000;

        // Check buffer size limit (10MB)
        const estimatedSize = audioChunkStatsRef.current.totalSize + audioSize;
        if (estimatedSize > MAX_AUDIO_BUFFER_SIZE) {
            console.warn('[OrchestratorAPI] ⚠️ Audio buffer size limit approaching:', {
                currentSize: audioChunkStatsRef.current.totalSize,
                currentSizeMB: (audioChunkStatsRef.current.totalSize / (1024 * 1024)).toFixed(2),
                newChunkSize: audioSize,
                estimatedTotal: estimatedSize,
                limit: MAX_AUDIO_BUFFER_SIZE,
                limitMB: (MAX_AUDIO_BUFFER_SIZE / (1024 * 1024)).toFixed(2)
            });
            // Still send, but warn - orchestrator will reject if over limit
        }

        // Track audio chunk statistics
        const previousLastChunkTime = audioChunkStatsRef.current.lastChunkTime;
        if (!audioChunkStatsRef.current.firstChunkTime) {
            audioChunkStatsRef.current.firstChunkTime = sendStartTime;
        }
        audioChunkStatsRef.current.lastChunkTime = sendStartTime;
        audioChunkStatsRef.current.count++;
        audioChunkStatsRef.current.totalSize += audioSize;

        const message = {
            type: 'audio_chunk',
            session_id: sessionId,
            seq: seq,
            audio_base64: base64Audio,
            timestamp: clientTimestamp,
        };

        const messageString = JSON.stringify(message);
        const messageSize = new Blob([messageString]).size;
        const timeSinceFirstChunk = audioChunkStatsRef.current.firstChunkTime 
            ? sendStartTime - audioChunkStatsRef.current.firstChunkTime 
            : 0;
        const timeSinceLastChunk = previousLastChunkTime 
            ? sendStartTime - previousLastChunkTime 
            : 0;

        console.log('[OrchestratorAPI] 📤 Sending audio_chunk:', {
            seq: seq,
            session_id: sessionId,
            audioSize: audioSize,
            audioSizeKB: (audioSize / 1024).toFixed(2),
            messageSize: messageSize,
            messageSizeKB: (messageSize / 1024).toFixed(2),
            clientTimestamp: clientTimestamp.toFixed(3),
            chunkNumber: audioChunkStatsRef.current.count,
            totalAudioSent: audioChunkStatsRef.current.totalSize,
            totalAudioSentKB: (audioChunkStatsRef.current.totalSize / 1024).toFixed(2),
            totalAudioSentMB: (audioChunkStatsRef.current.totalSize / (1024 * 1024)).toFixed(2),
            bufferUsagePercent: ((audioChunkStatsRef.current.totalSize / MAX_AUDIO_BUFFER_SIZE) * 100).toFixed(1),
            timeSinceFirstChunk: timeSinceFirstChunk > 0 ? timeSinceFirstChunk.toFixed(2) + 'ms' : 'N/A',
            timeSinceLastChunk: timeSinceLastChunk > 0 ? timeSinceLastChunk.toFixed(2) + 'ms' : 'N/A',
            timestamp: sendStartTime
        });

        wsRef.current.send(messageString);
        
        const sendTime = performance.now() - sendStartTime;
        messageCountRef.current.sent++;
        
        console.log('[OrchestratorAPI] ✅ audio_chunk sent:', {
            seq: seq,
            sendTime: sendTime.toFixed(2) + 'ms',
            totalSent: messageCountRef.current.sent,
            timestamp: performance.now()
        });
        
        return true;
    }, []);

    // Process queued audio chunks with throttling
    const _processAudioChunkQueue = useCallback(function processAudioChunkQueue() {
        if (audioChunkQueueRef.current.length === 0) {
            audioChunkThrottleTimerRef.current = null;
            return;
        }

        const chunk = audioChunkQueueRef.current.shift();
        if (!chunk) {
            audioChunkThrottleTimerRef.current = null;
            return;
        }

        const seq = ++sequenceRef.current;
        const sent = _sendAudioChunkImmediate(chunk.base64Audio, chunk.sessionId, seq);
        
        if (!sent) {
            // If send failed, put it back at the front
            audioChunkQueueRef.current.unshift(chunk);
            console.warn('[OrchestratorAPI] ⚠️ Failed to send audio chunk, will retry');
        }

        // Schedule next chunk if queue is not empty
        if (audioChunkQueueRef.current.length > 0) {
            audioChunkThrottleTimerRef.current = setTimeout(processAudioChunkQueue, AUDIO_CHUNK_SEND_THROTTLE_MS);
        } else {
            audioChunkThrottleTimerRef.current = null;
        }
    }, [_sendAudioChunkImmediate]);

    const sendAudioChunk = useCallback((base64Audio: string, sessionId: string) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.warn('[OrchestratorAPI] ⚠️ Cannot send audio chunk - WebSocket not connected:', {
                readyState: wsRef.current?.readyState,
                readyStateText: wsRef.current?.readyState === WebSocket.CONNECTING ? 'CONNECTING' :
                                 wsRef.current?.readyState === WebSocket.OPEN ? 'OPEN' :
                                 wsRef.current?.readyState === WebSocket.CLOSING ? 'CLOSING' :
                                 wsRef.current?.readyState === WebSocket.CLOSED ? 'CLOSED' : 'UNKNOWN',
                timestamp: performance.now()
            });
            return;
        }

        // Add to queue
        audioChunkQueueRef.current.push({
            base64Audio,
            sessionId,
            timestamp: performance.now()
        });

        // Start processing queue if not already processing
        if (!audioChunkThrottleTimerRef.current) {
            _processAudioChunkQueue();
        }
    }, [_processAudioChunkQueue]);

    const endStream = useCallback(async (sessionId: string, additionalMessages?: string) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.warn('[OrchestratorAPI] ⚠️ Cannot send end_stream - WebSocket not connected:', {
                readyState: wsRef.current?.readyState,
                timestamp: performance.now()
            });
            return;
        }

        const sendStartTime = performance.now();
        const totalChunks = audioChunkStatsRef.current.count;
        const totalAudioSize = audioChunkStatsRef.current.totalSize;
        const streamDuration = audioChunkStatsRef.current.firstChunkTime && audioChunkStatsRef.current.lastChunkTime
            ? audioChunkStatsRef.current.lastChunkTime - audioChunkStatsRef.current.firstChunkTime
            : 0;
        const avgChunkSize = totalChunks > 0 ? totalAudioSize / totalChunks : 0;
        const avgChunkRate = streamDuration > 0 ? (totalChunks / streamDuration) * 1000 : 0;

        console.log('[OrchestratorAPI] 📤 Sending end_stream:', {
            session_id: sessionId,
            reason: 'user_stopped',
            additionalMessages: additionalMessages ? `${additionalMessages.length} chars` : 'none',
            streamStats: {
                totalChunks: totalChunks,
                totalAudioSize: totalAudioSize,
                totalAudioSizeKB: (totalAudioSize / 1024).toFixed(2),
                streamDuration: streamDuration > 0 ? streamDuration.toFixed(2) + 'ms' : 'N/A',
                avgChunkSize: avgChunkSize > 0 ? avgChunkSize.toFixed(2) : 'N/A',
                avgChunkSizeKB: avgChunkSize > 0 ? (avgChunkSize / 1024).toFixed(2) : 'N/A',
                avgChunkRate: avgChunkRate > 0 ? avgChunkRate.toFixed(2) + ' chunks/s' : 'N/A'
            },
            timestamp: sendStartTime
        });

        const message: {
            type: string;
            session_id: string;
            reason: string;
            additional_messages?: string;
        } = {
            type: 'end_stream',
            session_id: sessionId,
            reason: 'user_stopped',
        };

        // Add additional_messages if provided
        if (additionalMessages) {
            message.additional_messages = additionalMessages;
        }

        const messageString = JSON.stringify(message);
        const messageSize = new Blob([messageString]).size;
        
        wsRef.current.send(messageString);
        awaitingServerResponseRef.current = true;
        
        const sendTime = performance.now() - sendStartTime;
        messageCountRef.current.sent++;
        
        console.log('[OrchestratorAPI] ✅ end_stream sent:', {
            session_id: sessionId,
            messageSize: messageSize,
            sendTime: sendTime.toFixed(2) + 'ms',
            timestamp: performance.now()
        });

        // Wait for any queued audio chunks to be sent before resetting
        // This ensures all chunks are sent before end_stream
        if (audioChunkQueueRef.current.length > 0) {
            console.log('[OrchestratorAPI] ⏳ Waiting for queued audio chunks to be sent:', {
                queuedChunks: audioChunkQueueRef.current.length,
                timestamp: performance.now()
            });
            
            // Wait for queue to drain (with timeout)
            const waitForQueue = new Promise<void>((resolve) => {
                const checkQueue = () => {
                    if (audioChunkQueueRef.current.length === 0 && !audioChunkThrottleTimerRef.current) {
                        resolve();
                    } else {
                        setTimeout(checkQueue, 10);
                    }
                };
                checkQueue();
                // Timeout after 2 seconds
                setTimeout(() => {
                    console.warn('[OrchestratorAPI] ⚠️ Timeout waiting for audio chunk queue to drain');
                    resolve();
                }, 2000);
            });
            
            await waitForQueue;
        }
        
        // Reset sequence and stats
        const previousSeq = sequenceRef.current;
        sequenceRef.current = 0;
        
        console.log('[OrchestratorAPI] 🔄 Stream ended, resetting sequence:', {
            previousSequence: previousSeq,
            newSequence: sequenceRef.current,
            timestamp: performance.now()
        });
    }, []);

    const disconnect = useCallback(() => {
        if (wsRef.current) {
            const disconnectTime = performance.now();
            const connectionDuration = connectionStartTimeRef.current 
                ? disconnectTime - connectionStartTimeRef.current 
                : 0;
            
            console.log('[OrchestratorAPI] 🔌 Disconnecting WebSocket:', {
                readyState: wsRef.current.readyState,
                connectionDuration: connectionDuration.toFixed(2) + 'ms',
                messagesSent: messageCountRef.current.sent,
                messagesReceived: messageCountRef.current.received,
                audioChunksSent: audioChunkStatsRef.current.count,
                timestamp: disconnectTime
            });
            
            wsRef.current.close();
            wsRef.current = null;
            setWebSocket(null);
            setConnectionStatus('disconnected');
            
            // Reset stats
            messageCountRef.current = { sent: 0, received: 0 };
            audioChunkStatsRef.current = { count: 0, totalSize: 0, firstChunkTime: null, lastChunkTime: null };
            connectionStartTimeRef.current = null;
            lastMessageTimeRef.current = null;
            audioChunkQueueRef.current = [];
            if (audioChunkThrottleTimerRef.current) {
                clearTimeout(audioChunkThrottleTimerRef.current);
                audioChunkThrottleTimerRef.current = null;
            }
            ttsQueueInfoRef.current = null;
            awaitingServerResponseRef.current = false;
        }
    }, [setWebSocket, setConnectionStatus]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    return {
        connect,
        sendAudioChunk,
        endStream,
        disconnect,
        isConnected: () => wsRef.current?.readyState === WebSocket.OPEN,
    };
}

const currencyFormatter = new Intl.NumberFormat('ar-EG', {
    maximumFractionDigits: 0,
});

const areaFormatter = new Intl.NumberFormat('ar-EG', {
    maximumFractionDigits: 0,
});

const sanitizeText = (value: unknown): string => {
    if (typeof value === 'string') {
        return value.trim();
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value.toString();
    }
    return '';
};

const formatCurrency = (value: unknown): string | undefined => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return undefined;
    }
    return `${currencyFormatter.format(numeric)} ج.م`;
};

const formatArea = (value: unknown): string | undefined => {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) {
        return undefined;
    }
    return `${areaFormatter.format(numeric)} م²`;
};

const ellipsize = (text: string | undefined, max = 80): string | undefined => {
    if (!text) {
        return undefined;
    }
    return text.length > max ? `${text.slice(0, max)}…` : text;
};

type StructuredUnit = Record<string, unknown>;

const normalizeStructuredUnits = (units: StructuredUnit[], sessionId: string): GalleryUnit[] => {
    if (!Array.isArray(units)) {
        return [];
    }
    return units
        .map((unit, index) => buildGalleryUnitFromStructuredUnit(unit, `${sessionId}-${index}`))
        .filter((unit): unit is GalleryUnit => Boolean(unit));
};

const buildGalleryUnitFromStructuredUnit = (unit: StructuredUnit, fallbackId: string): GalleryUnit | null => {
    if (!unit || typeof unit !== 'object') {
        return null;
    }

    const imageUrl = sanitizeText(
        unit.image_url ??
            unit.ImageURL ??
            unit.imageUrl ??
            unit.ImagePath ??
            unit.image_path ??
            unit.imagePath ??
            ''
    );

    if (!imageUrl) {
        return null;
    }

    const code = sanitizeText(unit.Code ?? unit.code ?? unit.Name ?? unit.name ?? fallbackId);
    const project = sanitizeText(unit.Project ?? unit.project);
    const location = sanitizeText(unit.Location ?? unit.location);
    const usage = sanitizeText(unit.Usage ?? unit.usage);
    const title =
        sanitizeText(unit.Name ?? unit.name ?? unit.Project ?? unit.project ?? '') ||
        (project ? `${project} – ${code}` : code) ||
        `وحدة ${fallbackId}`;
    const subtitle = location || project || undefined;
    const price = formatCurrency(unit.Price ?? unit.price);
    const area = formatArea(unit.Area ?? unit.area);
    const floor = sanitizeText(unit.Floor ?? unit.floor);
    const garden = formatArea(unit.Garden ?? unit.garden);
    const roof = formatArea(unit.Roof ?? unit.roof);

    const description = sanitizeText(unit.Description ?? unit.description) || undefined;
    const tags = [project, usage, location].filter(Boolean).slice(0, 3);
    const highlights = [
        price && { label: 'السعر', value: price },
        area && { label: 'المساحة', value: area },
        floor && { label: 'الدور', value: floor },
        usage && { label: 'النوع', value: usage },
    ].filter(Boolean) as GalleryUnit['highlights'];

    const metrics = [
        garden && { label: 'حديقة', value: garden },
        roof && { label: 'روف', value: roof },
    ].filter(Boolean);

    return {
        id: code || fallbackId,
        title,
        subtitle,
        description,
        imageUrl,
        tags,
        highlights,
        metrics,
        raw: unit,
    };
};

const createGalleryUnitsFromUrls = (
    urls: string[],
    sessionId: string,
    chunkText?: string
): GalleryUnit[] => {
    if (!Array.isArray(urls)) {
        return [];
    }
    return urls
        .map((url) => {
            const normalized = sanitizeText(url);
            if (!normalized) {
                return null;
            }
            const galleryUnit = {
                id: `chunk-${sessionId}-${uuidv4()}`,
                title: 'صورة مرجعية',
                subtitle: chunkText ? ellipsize(chunkText, 60) : 'تم استخراجها أثناء الاستجابة',
                description: chunkText,
                imageUrl: normalized,
                tags: ['مرفق بصري'],
                highlights: [],
                raw: {
                    source: 'chunk',
                    chunkText,
                    url: normalized,
                },
            } satisfies GalleryUnit;
            return galleryUnit;
        })
        .filter(Boolean) as GalleryUnit[];
};
