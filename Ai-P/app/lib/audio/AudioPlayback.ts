import { base64ToArrayBuffer } from '../utils/audioUtils';
import { AudioAnalyzer } from './AudioAnalyzer';

export class AudioPlayback {
    private audioContext: AudioContext | null = null;
    private audioQueue: ArrayBuffer[] = [];
    private isPlaying = false;
    private currentSource: AudioBufferSourceNode | null = null;
    private analyzer: AudioAnalyzer | null = null;
    private segmentCounter = 0;
    private currentSegmentStartTime: number | null = null;
    private analysisSamples: number[][] = [];
    private currentAnalysisFrameId: number | null = null;
    private currentAnalyzingSegmentIndex: number | null = null;
    private playbackEndTimeoutId: NodeJS.Timeout | null = null;

    private onPlaybackStartCallback: (() => void) | null = null;
    private onPlaybackEndCallback: (() => void) | null = null;
    private onAnalysisCallback: ((bands: number[]) => void) | null = null;

    async initialize(): Promise<boolean> {
        try {
            this.audioContext = new AudioContext({ sampleRate: 24000 });
            this.analyzer = new AudioAnalyzer(this.audioContext);
            return true;
        } catch (error) {
            console.error('[AudioPlayback] Failed to initialize:', error);
            if (error instanceof Error) {
                console.error('[AudioPlayback] Error details:', {
                    name: error.name,
                    message: error.message,
                    stack: error.stack,
                });
            }
            return false;
        }
    }

    queueSegment(base64Audio: string): void {
        const arrayBuffer = base64ToArrayBuffer(base64Audio);
        this.audioQueue.push(arrayBuffer);
        
        const segmentIndex = this.segmentCounter;
        const queueSize = this.audioQueue.length;
        const audioSize = arrayBuffer.byteLength;

        // If we're waiting for playback to end (timeout pending), cancel it and continue playing
        if (this.playbackEndTimeoutId) {
            clearTimeout(this.playbackEndTimeoutId);
            this.playbackEndTimeoutId = null;
            // Continue playing the new segment - ensure state stays speaking
            if (!this.isPlaying) {
                this.isPlaying = true;
                // Notify that playback is continuing (to keep state as speaking)
                if (this.onPlaybackStartCallback) {
                    this.onPlaybackStartCallback();
                }
            }
            this.playNext();
        } else if (!this.isPlaying) {
            // Not currently playing, start playback
            // Auto-start if we have at least 2 segments (buffering) or if this is the first segment
            if (this.audioQueue.length >= 2 || this.audioQueue.length === 1) {
                this.isPlaying = true;
                this.playNext();
            }
        }
    }

    private async playNext(): Promise<void> {
        if (!this.audioContext) {
            this.isPlaying = false;
            if (this.onPlaybackEndCallback) {
                this.onPlaybackEndCallback();
            }
            return;
        }
        
        // Don't set isPlaying to false here - let onended callback handle it
        // This prevents state from reverting to silent between segments
        if (this.audioQueue.length === 0) {
            // Queue is empty, but don't call onPlaybackEnd yet
            // The onended callback will handle it after a delay
            return;
        }

        this.isPlaying = true;
        const audioData = this.audioQueue.shift();

        if (!audioData) {
            this.playNext();
            return;
        }

        try {
            const audioBuffer = await this.audioContext.decodeAudioData(audioData);
            const segmentIndex = this.segmentCounter++;
            const duration = audioBuffer.duration;
            const sampleRate = audioBuffer.sampleRate;
            const numberOfChannels = audioBuffer.numberOfChannels;
            const length = audioBuffer.length;
            this.currentSegmentStartTime = performance.now();
            this.analysisSamples = []; // Reset analysis samples for this segment

            // Notify that playback has started (for setting blob state to speaking)
            if (this.onPlaybackStartCallback) {
                this.onPlaybackStartCallback();
            }

            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            this.currentSource = source;

            // Connect to analyzer
            if (this.analyzer) {
                // Stop any previous analysis loop
                if (this.currentAnalysisFrameId !== null) {
                    cancelAnimationFrame(this.currentAnalysisFrameId);
                    this.currentAnalysisFrameId = null;
                }
                
                this.analyzer.connectSource(source);
                this.analyzer.connectDestination(this.audioContext.destination);

                // Start analysis loop for this segment
                this.currentAnalyzingSegmentIndex = segmentIndex;
                this.startAnalysis(segmentIndex, duration);
            } else {
                source.connect(this.audioContext.destination);
            }

            source.onended = () => {
                // Stop analysis loop for this segment
                if (this.currentAnalysisFrameId !== null) {
                    cancelAnimationFrame(this.currentAnalysisFrameId);
                    this.currentAnalysisFrameId = null;
                }
                
                // Only log if this is still the current segment being analyzed
                if (this.currentAnalyzingSegmentIndex === segmentIndex) {
                    // Log segment completion with summary
                    const endTime = performance.now();
                    const actualDuration = this.currentSegmentStartTime 
                        ? (endTime - this.currentSegmentStartTime) / 1000 
                        : 0;
                    
                    // Calculate average voice activity from all analysis samples
                    if (this.analysisSamples.length > 0) {
                        const avgBands = this.analysisSamples.reduce((acc, sample) => {
                            return acc.map((val, i) => val + (sample[i] || 0));
                        }, [0, 0, 0, 0, 0]).map(sum => sum / this.analysisSamples.length);
                        
                        const avgActivity = avgBands.reduce((sum, val) => sum + val, 0) / avgBands.length;
                        const maxActivity = Math.max(...avgBands);
                    const maxSampleActivity = Math.max(...this.analysisSamples.map(sample => 
                        Math.max(...sample)
                    ));
                }
                }
                
                this.currentSegmentStartTime = null;
                this.analysisSamples = [];
                this.currentAnalyzingSegmentIndex = null;
                
                // Check if there are more segments before calling playNext
                // This prevents setting state to silent between segments
                if (this.audioQueue.length > 0) {
                    // More segments queued, cancel any pending end callback and continue playing
                    if (this.playbackEndTimeoutId) {
                        clearTimeout(this.playbackEndTimeoutId);
                        this.playbackEndTimeoutId = null;
                    }
                    this.playNext();
                } else {
                    // No more segments, but wait a bit to see if more arrive
                    // Use a small delay to handle segments arriving in quick succession
                    // Cancel any existing timeout first
                    if (this.playbackEndTimeoutId) {
                        clearTimeout(this.playbackEndTimeoutId);
                    }
                    this.playbackEndTimeoutId = setTimeout(() => {
                        this.playbackEndTimeoutId = null;
                        // Check again if queue is still empty
                        if (this.audioQueue.length === 0) {
                            // No more segments arrived, playback has ended
                            this.isPlaying = false;
                            if (this.onPlaybackEndCallback) {
                                this.onPlaybackEndCallback();
                            }
                        } else {
                            // More segments arrived during the delay, continue playing
                            this.playNext();
                        }
                    }, 300); // 300ms delay to catch late-arriving segments
                }
            };

            source.start();
        } catch (error) {
            this.playNext();
        }
    }

    private startAnalysis(segmentIndex: number, segmentDuration: number): void {
        if (!this.analyzer || !this.onAnalysisCallback || !this.isPlaying) return;

        let analysisCount = 0;
        const startTime = performance.now();

        const analyze = () => {
            // Stop if this is no longer the current segment being analyzed
            if (this.currentAnalyzingSegmentIndex !== segmentIndex || !this.isPlaying || !this.analyzer) {
                this.currentAnalysisFrameId = null;
                return;
            }

            const result = this.analyzer.analyze();
            const bands = [
                result.bands.low,
                result.bands.lowMid,
                result.bands.mid,
                result.bands.midHigh,
                result.bands.high,
            ];

            // Store analysis sample for summary
            this.analysisSamples.push([...bands]);

            // Calculate activity metrics
            const avgActivity = bands.reduce((sum, val) => sum + val, 0) / bands.length;
            const maxActivity = Math.max(...bands);

            analysisCount++;

            if (this.onAnalysisCallback) {
                this.onAnalysisCallback(bands);
            }

            this.currentAnalysisFrameId = requestAnimationFrame(analyze);
        };

        this.currentAnalysisFrameId = requestAnimationFrame(analyze);
    }

    setOnPlaybackStart(callback: () => void): void {
        this.onPlaybackStartCallback = callback;
    }

    setOnPlaybackEnd(callback: () => void): void {
        this.onPlaybackEndCallback = callback;
    }

    setOnAnalysis(callback: (bands: number[]) => void): void {
        this.onAnalysisCallback = callback;
    }

    stop(): void {
        this.isPlaying = false;

        // Cancel any pending playback end timeout
        if (this.playbackEndTimeoutId) {
            clearTimeout(this.playbackEndTimeoutId);
            this.playbackEndTimeoutId = null;
        }

        // Stop analysis loop
        if (this.currentAnalysisFrameId !== null) {
            cancelAnimationFrame(this.currentAnalysisFrameId);
            this.currentAnalysisFrameId = null;
        }

        if (this.currentSource) {
            try {
                this.currentSource.stop();
            } catch (e) {
                // Source might already be stopped
            }
            this.currentSource = null;
        }

        this.audioQueue = [];
        this.currentAnalyzingSegmentIndex = null;
        this.analysisSamples = [];
    }

    cleanup(): void {
        this.stop();

        if (this.analyzer) {
            this.analyzer.disconnect();
            this.analyzer = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.onPlaybackStartCallback = null;
        this.onPlaybackEndCallback = null;
        this.onAnalysisCallback = null;
    }

    isInitialized(): boolean {
        return this.audioContext !== null;
    }
}
