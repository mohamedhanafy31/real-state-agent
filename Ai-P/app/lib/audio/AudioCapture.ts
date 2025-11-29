export class AudioCapture {
    private audioContext: AudioContext | null = null;
    private mediaStream: MediaStream | null = null;
    private mediaRecorder: MediaRecorder | null = null;
    private analyser: AnalyserNode | null = null;
    private source: MediaStreamAudioSourceNode | null = null;
    private isCapturing = false;
    private animationFrameId: number | null = null;

    private onChunkCallback: ((base64Audio: string, level: number) => void) | null = null;

    async initialize(): Promise<boolean> {
        try {
            // Request microphone access
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000,
                    // channelCount: 1, // Removed to match test_client.html
                },
            });

            // Create audio context for analysis only
            this.audioContext = new AudioContext({ sampleRate: 16000 });
            this.source = this.audioContext.createMediaStreamSource(this.mediaStream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.source.connect(this.analyser);

            // Initialize MediaRecorder
            let mimeType = 'audio/webm';
            if (!MediaRecorder.isTypeSupported(mimeType)) {
                mimeType = 'audio/webm;codecs=opus';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = ''; // Use default
                }
            }

            const options = mimeType ? { mimeType } : undefined;
            this.mediaRecorder = new MediaRecorder(this.mediaStream, options);

            this.mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0 && this.isCapturing && this.onChunkCallback) {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        const base64 = (reader.result as string).split(',')[1];
                        // We get level from the analyzer loop, but for the callback signature
                        // we can pass the current instantaneous level
                        const level = this.getCurrentLevel();
                        this.onChunkCallback!(base64, level);
                    };
                    reader.readAsDataURL(event.data);
                }
            };

            return true;
        } catch (error) {
            console.error('[AudioCapture] Failed to initialize:', error);
            if (error instanceof Error) {
                console.error('[AudioCapture] Error details:', {
                    name: error.name,
                    message: error.message,
                    stack: error.stack,
                });
            }
            return false;
        }
    }

    private getCurrentLevel(): number {
        if (!this.analyser) return 0;
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteTimeDomainData(dataArray);

        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            const value = (dataArray[i] - 128) / 128;
            sum += value * value;
        }
        return Math.sqrt(sum / dataArray.length);
    }

    start(onChunk: (base64Audio: string, level: number) => void): void {
        if (!this.mediaRecorder || !this.audioContext) {
            throw new Error('Audio capture not initialized');
        }

        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }

        this.onChunkCallback = onChunk;
        this.isCapturing = true;

        // Start recording with 500ms chunks (matching test_client.html)
        this.mediaRecorder.start(500);
    }

    stop(): void {
        this.isCapturing = false;

        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
    }

    cleanup(): void {
        this.stop();

        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.mediaRecorder = null;
        this.source = null;
        this.analyser = null;
        this.onChunkCallback = null;
    }

    isInitialized(): boolean {
        return this.mediaRecorder !== null;
    }
}
