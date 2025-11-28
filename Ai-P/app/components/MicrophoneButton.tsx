'use client';

import { useAppStore } from '@/store/useAppStore';
import { useState } from 'react';
import styles from './MicrophoneButton.module.css';

interface MicrophoneButtonProps {
    onPress: () => void;
    onRelease: () => void;
}

export default function MicrophoneButton({ onPress, onRelease }: MicrophoneButtonProps) {
    const { audio, ui, blob } = useAppStore();
    const [isPressed, setIsPressed] = useState(false);
    const isToggleMode = true;

    const isSpeaking = blob.state === 'speaking';
    const canInteract = blob.state === 'silent' || blob.state === 'listening';

    const handlePointerDown = () => {
        if (!ui.micButtonEnabled || isToggleMode || isSpeaking || !canInteract) {
            return;
        }
        setIsPressed(true);
        onPress();
    };

    const handlePointerUp = () => {
        if (!ui.micButtonEnabled || isToggleMode || isSpeaking || !canInteract) {
            return;
        }
        setIsPressed(false);
        onRelease();
    };

    const handleClick = () => {
        if (!ui.micButtonEnabled || !isToggleMode || isSpeaking || !canInteract) {
            return;
        }

        if (audio.isRecording) {
            setIsPressed(false);
            onRelease();
        } else {
            setIsPressed(true);
            onPress();
        }
    };

    const getButtonClass = () => {
        let className = styles.micButton;
        if ((isPressed || (isToggleMode && audio.isRecording)) && audio.isRecording) className += ` ${styles.recording}`;
        if (!ui.micButtonEnabled || isSpeaking || !canInteract) className += ` ${styles.disabled}`;
        if (ui.errorMessage) className += ` ${styles.error}`;
        return className;
    };

    const getLabel = () => {
        if (isSpeaking) return 'الذكاء الاصطناعي يتحدث...';
        if (blob.state === 'listening') return 'جاري الاستماع...';
        if (blob.state === 'thinking') return 'جاري المعالجة...';
        return isToggleMode ? 'اضغط للبدء / الإيقاف' : 'اضغط مع الاستمرار للتحدث';
    };

    return (
        <div className={styles.container}>
            <button
                className={getButtonClass()}
                onPointerDown={handlePointerDown}
                onPointerUp={handlePointerUp}
                onPointerLeave={() => {
                    if (!isToggleMode && isPressed) {
                        handlePointerUp();
                    }
                }}
                onClick={handleClick}
                disabled={!ui.micButtonEnabled || isSpeaking || !canInteract}
                aria-label={getLabel()}
                role="button"
                tabIndex={0}
            >
                <svg
                    className={styles.icon}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    {audio.isRecording && isToggleMode ? (
                        <rect x="6" y="6" width="12" height="12" rx="2" />
                    ) : (
                        <>
                            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                            <line x1="12" y1="19" x2="12" y2="23" />
                            <line x1="8" y1="23" x2="16" y2="23" />
                        </>
                    )}
                </svg>
            </button>
        </div>
    );
}
