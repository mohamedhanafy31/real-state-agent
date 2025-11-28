'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { useWebSocket } from '@/hooks/useWebSocket';
import { AudioCapture } from '@/lib/audio/AudioCapture';
import { AudioPlayback } from '@/lib/audio/AudioPlayback';
import SlideBar from '@/components/SlideBar';
import BlobCanvas from '@/components/AnimatedBlob';
import MicrophoneButton from '@/components/MicrophoneButton';
import ImagePanel from '@/components/ImagePanel';
import type { BlobState } from '@/types';
import styles from './page.module.css';

const statusMessages: Record<BlobState, string> = {
  silent: 'اضغط للتحدث مع الذكاء الاصطناعي',
  listening: 'جاري الاستماع...',
  thinking: 'جاري المعالجة...',
  speaking: 'الذكاء الاصطناعي يتحدث...',
};

const getTimestamp = () => Date.now();

const MAX_RECORDING_DURATION_MS = 20000;

export default function Home() {
  const {
    connection,
    blob,
    content,
    ui,
    setBlobState,
    setIsRecording,
    setIsPlaying,
    setAudioLevel,
    setFrequencyData,
    incrementSessionTimer,
    setErrorMessage,
  } = useAppStore();

  const { connect, sendAudioChunk, endStream } = useWebSocket({
    onTTSAudio: (base64Audio) => {
      const receiveTime = getTimestamp();
      console.log('[OrchestratorAPI] 🎵 TTS audio received in page component:', {
        audioSize: base64Audio.length,
        audioSizeKB: (base64Audio.length / 1024).toFixed(2),
        hasAudioPlayback: !!audioPlaybackRef.current,
        timestamp: receiveTime
      });
      
      if (audioPlaybackRef.current) {
        audioPlaybackRef.current.queueSegment(base64Audio);
        setBlobState('speaking');
        setIsPlaying(true);
        console.log('[OrchestratorAPI] ✅ TTS audio queued for playback');
      } else {
        console.warn('[OrchestratorAPI] ⚠️ TTS audio received but audioPlayback not initialized');
      }
    },
  });
  const audioCaptureRef = useRef<AudioCapture | null>(null);
  const audioPlaybackRef = useRef<AudioPlayback | null>(null);
  const hasSentChunksRef = useRef(false);
  const [initialized, setInitialized] = useState(false);
  const silentTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const recordingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [micPermission, setMicPermission] = useState<'unknown' | PermissionState>('unknown');
  const permissionStatusRef = useRef<PermissionStatus | null>(null);
  const [permissionError, setPermissionError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const handlePermissionChange = (state: PermissionState) => {
      setMicPermission(state);
      if (state === 'granted') {
        setPermissionError(null);
      }
    };

    const watchPermission = async () => {
      if (!navigator.permissions?.query) {
        // Fall back to unknown state; user can trigger request manually
        setMicPermission('prompt');
        return;
      }

      try {
        const status = await navigator.permissions.query({
          name: 'microphone' as PermissionName
        });
        permissionStatusRef.current = status;
        handlePermissionChange(status.state);
        status.onchange = () => handlePermissionChange(status.state);
      } catch (error) {
        console.warn('[Permissions] Unable to query microphone permission:', error);
        setMicPermission('prompt');
      }
    };

    watchPermission();

    return () => {
      if (permissionStatusRef.current) {
        permissionStatusRef.current.onchange = null;
      }
    };
  }, []);

  const requestMicrophoneAccess = useCallback(async () => {
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setPermissionError('Microphone access is not supported in this browser.');
      return;
    }

    try {
      setPermissionError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission('granted');
    } catch (error) {
      console.error('[Permissions] Failed to acquire microphone access:', error);
      setPermissionError('Microphone permission is blocked. Please enable it in your browser settings and retry.');
      setMicPermission('denied');
    }
  }, []);

  // Initialize audio systems
  useEffect(() => {
    const initAudio = async () => {
      audioCaptureRef.current = new AudioCapture();
      audioPlaybackRef.current = new AudioPlayback();

      const captureOk = await audioCaptureRef.current.initialize();
      const playbackOk = await audioPlaybackRef.current.initialize();

      if (captureOk && playbackOk) {
        setInitialized(true);

        // Set up playback callbacks
        audioPlaybackRef.current.setOnPlaybackStart(() => {
          setBlobState('speaking');
          setIsPlaying(true);
        });

        audioPlaybackRef.current.setOnPlaybackEnd(() => {
          setBlobState('silent');
          setIsPlaying(false);
        });

        audioPlaybackRef.current.setOnAnalysis((bands) => {
          setFrequencyData(bands);
        });
      }
    };

    initAudio();

    return () => {
      if (audioCaptureRef.current) {
        audioCaptureRef.current.cleanup();
      }
      if (audioPlaybackRef.current) {
        audioPlaybackRef.current.cleanup();
      }
      if (recordingTimeoutRef.current) {
        clearTimeout(recordingTimeoutRef.current);
        recordingTimeoutRef.current = null;
      }
    };
  }, [setBlobState, setIsPlaying, setFrequencyData]);

  // Connect WebSocket
  const hasConnectedRef = useRef(false);
  useEffect(() => {
    if (initialized && !hasConnectedRef.current) {
      console.log('[OrchestratorAPI] 🔌 Initializing WebSocket connection');
      hasConnectedRef.current = true;
      connect();
    } else if (!initialized) {
      console.log('[OrchestratorAPI] ⏳ Waiting for audio systems to initialize before connecting');
    }
  }, [initialized, connect]);

  // Session timer
  useEffect(() => {
    if (connection.status !== 'connected') return;

    const interval = setInterval(() => {
      incrementSessionTimer();
    }, 1000);

    return () => clearInterval(interval);
  }, [connection.status, incrementSessionTimer]);

  // Track when recording started to calculate elapsed time
  const recordingStartTimeRef = useRef<number | null>(null);

  // Handle mic button press (start recording)
  const handleMicPress = async () => {
    if (!audioCaptureRef.current) {
      console.warn('[OrchestratorAPI] ⚠️ Cannot start recording - audio capture not initialized');
      return;
    }

    // If no session ID or connection is disconnected, reconnect first
    if (!connection.sessionId || connection.status === 'disconnected') {
      console.log('[OrchestratorAPI] 🔄 No active session, reconnecting before recording:', {
        hasSessionId: !!connection.sessionId,
        connectionStatus: connection.status
      });
      hasConnectedRef.current = false; // Reset to allow reconnection
      connect();
      // Wait a bit for connection to establish
      await new Promise(resolve => setTimeout(resolve, 1000));
      // Re-check connection status from store
      const currentConnection = useAppStore.getState().connection;
      if (!currentConnection.sessionId || currentConnection.status !== 'connected') {
        console.warn('[OrchestratorAPI] ⚠️ Failed to establish connection, cannot start recording:', {
          hasSessionId: !!currentConnection.sessionId,
          connectionStatus: currentConnection.status
        });
        return;
      }
    }

      const pressTime = getTimestamp();
    // Get current session ID from store (not from closure) to avoid stale values
    const currentConnection = useAppStore.getState().connection;
    console.log('[OrchestratorAPI] 🎤 Starting recording:', {
      sessionId: currentConnection.sessionId,
      connectionStatus: currentConnection.status,
      timestamp: pressTime
    });

    recordingStartTimeRef.current = pressTime;
    setBlobState('listening');
    setIsRecording(true);
    hasSentChunksRef.current = false;

    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
    }
    recordingTimeoutRef.current = setTimeout(() => {
      console.warn('[OrchestratorAPI] ⚠️ Max recording duration reached, stopping automatically');
      setErrorMessage('مدة التسجيل القصوى هي 20 ثانية. حاول التحدث بجمل أقصر.');
      handleMicRelease().catch((error) => {
        console.error('[OrchestratorAPI] ⚠️ Failed to stop recording after timeout:', error);
      });
    }, MAX_RECORDING_DURATION_MS);

    audioCaptureRef.current.start((base64Audio, level) => {
      const chunkTime = getTimestamp();
      setAudioLevel(level);
      
      // Get current session ID from store (not from closure) to avoid stale values
      const currentConnection = useAppStore.getState().connection;
      const currentSessionId = currentConnection.sessionId;
      
      if (currentSessionId) {
        const isFirstChunk = !hasSentChunksRef.current;
        
        if (isFirstChunk) {
          const timeToFirstChunk = chunkTime - (recordingStartTimeRef.current || chunkTime);
          console.log('[OrchestratorAPI] 🎤 First audio chunk captured:', {
            sessionId: currentSessionId,
            audioSize: base64Audio.length,
            audioSizeKB: (base64Audio.length / 1024).toFixed(2),
            audioLevel: level.toFixed(4),
            timeToFirstChunk: timeToFirstChunk.toFixed(2) + 'ms',
            timestamp: chunkTime
          });
        }
        
        sendAudioChunk(base64Audio, currentSessionId);
        
        if (!hasSentChunksRef.current) {
          // Cancel any pending timeout to revert to silent since chunks are being sent
          if (silentTimeoutRef.current) {
            console.log('[OrchestratorAPI] 🎤 Cancelling silent timeout - audio chunks are being sent');
            clearTimeout(silentTimeoutRef.current);
            silentTimeoutRef.current = null;
          }
        }
        hasSentChunksRef.current = true;
      } else {
        console.warn('[OrchestratorAPI] ⚠️ Audio chunk captured but no active session ID:', {
          connectionStatus: currentConnection.status,
          timestamp: chunkTime
        });
      }
    });
  };

  const showImagePanel = ui.showImages && content.gallery.length > 0;

  // Handle mic button release (stop recording)
  const handleMicRelease = async () => {
    const timestamp = getTimestamp();
    
    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }
    
    if (!audioCaptureRef.current || !connection.sessionId) {
      console.warn('[OrchestratorAPI] ⚠️ Cannot stop recording:', {
        hasAudioCapture: !!audioCaptureRef.current,
        hasSessionId: !!connection.sessionId,
        timestamp: timestamp
      });
      return;
    }

    const recordingDuration = recordingStartTimeRef.current 
      ? (timestamp - recordingStartTimeRef.current) / 1000
      : 0;

    console.log('[OrchestratorAPI] 🎤 Stopping recording:', {
      sessionId: connection.sessionId,
      recordingDuration: recordingDuration.toFixed(3) + 's',
      hasSentChunks: hasSentChunksRef.current,
      timestamp: timestamp
    });

    audioCaptureRef.current.stop();
    setIsRecording(false);

    if (hasSentChunksRef.current) {
      console.log('[OrchestratorAPI] 🎤 Audio chunks were sent, ending stream:', {
        sessionId: connection.sessionId,
        recordingDuration: recordingDuration.toFixed(3) + 's',
        timestamp: timestamp
      });
      setBlobState('thinking');
      await endStream(connection.sessionId);
    } else {
      console.log('[OrchestratorAPI] ⚠️ No audio chunks sent, not ending stream:', {
        sessionId: connection.sessionId,
        recordingDuration: recordingDuration.toFixed(3) + 's',
        timestamp: timestamp
      });
      // Add a delay before reverting to silent to allow transition to complete
      // This prevents immediate reversion if button is released quickly
      
      // Wait longer if recording was very short (user clicked/released quickly)
      // Audio chunks are generated every 500ms, so we need at least that long
      const waitTime = recordingDuration > 0 && recordingDuration < 0.6 
        ? (0.6 - recordingDuration) * 1000 // Wait until at least 600ms total (convert to ms)
        : 500; // Otherwise wait 500ms
      
      // Cancel any existing timeout first
      if (silentTimeoutRef.current) {
        clearTimeout(silentTimeoutRef.current);
      }
      
      silentTimeoutRef.current = setTimeout(() => {
        // Get current state from store (not from closure) to avoid stale values
        const storeState = useAppStore.getState();
        const currentState = storeState.blob.state;
        const currentHasSentChunks = hasSentChunksRef.current;
        
        // Double-check that we're still in listening state and no chunks were sent
        // Use current state from store, not closure value
        if (currentState === 'listening' && !currentHasSentChunks) {
          setBlobState('silent');
        }
        recordingStartTimeRef.current = null;
        silentTimeoutRef.current = null;
      }, waitTime);
    }
  };

  return (
    <div className={styles.page}>
      <SlideBar />

      {micPermission !== 'granted' && micPermission !== 'unknown' && (
        <div className={styles.permissionBanner} role="alert">
          <div>
            <p className={styles.permissionTitle}>Microphone access is required.</p>
            <p className={styles.permissionDescription}>
              Please enable your microphone so you can talk to the assistant.
            </p>
            {permissionError && (
              <p className={styles.permissionError}>
                {permissionError}
              </p>
            )}
          </div>
          <button
            type="button"
            className={styles.permissionButton}
            onClick={requestMicrophoneAccess}
          >
            Enable Microphone
          </button>
        </div>
      )}

      <main className={`${styles.main} ${showImagePanel ? styles.mainWithPanel : ''}`}>
        <div className={`${styles.interactionArea} ${showImagePanel ? styles.interactionAreaWithPanel : ''}`}>
          <div className={`${styles.blobContainer} ${showImagePanel ? styles.blobShifted : ''}`}>
            <BlobCanvas />
            <div className={`${styles.statusMessage} ${showImagePanel ? styles.statusShifted : ''}`}>
              <span
                key={blob.state}
                className={`${styles.statusText} ${styles[`status-${blob.state}`]}`}
              >
                {statusMessages[blob.state]}
              </span>
            </div>
          </div>

          <div className={`${styles.micContainer} ${showImagePanel ? styles.micShifted : ''}`}>
            <MicrophoneButton
              onPress={handleMicPress}
              onRelease={handleMicRelease}
            />
          </div>
        </div>

        {showImagePanel && (
          <div className={styles.panelWrapper}>
            <ImagePanel />
          </div>
        )}
      </main>
    </div>
  );
}
