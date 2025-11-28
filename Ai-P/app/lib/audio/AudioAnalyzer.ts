import type { FrequencyBands, AudioAnalysisResult } from '@/types';

export class AudioAnalyzer {
    private analyserNode: AnalyserNode | null = null;
    private dataArray: Uint8Array<ArrayBuffer> | null = null;

    constructor(audioContext: AudioContext) {
        this.analyserNode = audioContext.createAnalyser();
        this.analyserNode.fftSize = 256;
        this.dataArray = new Uint8Array(this.analyserNode.frequencyBinCount);
    }

    connectSource(source: AudioNode): void {
        if (this.analyserNode) {
            source.connect(this.analyserNode);
        }
    }

    connectDestination(destination: AudioNode): void {
        if (this.analyserNode) {
            this.analyserNode.connect(destination);
        }
    }

    // Analyze frequency data and split into 5 bands
    analyze(): AudioAnalysisResult {
        if (!this.analyserNode || !this.dataArray) {
            return {
                bands: { low: 0, lowMid: 0, mid: 0, midHigh: 0, high: 0 },
                overall: 0,
                timestamp: Date.now(),
            };
        }

        this.analyserNode.getByteFrequencyData(this.dataArray);

        // Split into frequency bands (bins 0-255)
        const bands: FrequencyBands = {
            low: this.getAverageBand(0, 10),        // 0-200Hz
            lowMid: this.getAverageBand(10, 30),    // 200-600Hz
            mid: this.getAverageBand(30, 100),      // 600-2000Hz
            midHigh: this.getAverageBand(100, 200), // 2000-6000Hz
            high: this.getAverageBand(200, 256),    // 6000Hz+
        };

        // Calculate overall amplitude
        const overall = (bands.low + bands.lowMid + bands.mid + bands.midHigh + bands.high) / 5;

        return {
            bands,
            overall,
            timestamp: Date.now(),
        };
    }

    private getAverageBand(startBin: number, endBin: number): number {
        if (!this.dataArray) return 0;

        let sum = 0;
        const count = endBin - startBin;

        for (let i = startBin; i < endBin && i < this.dataArray.length; i++) {
            sum += this.dataArray[i];
        }

        // Normalize to 0.0 - 1.0
        return (sum / count) / 255;
    }

    getNode(): AnalyserNode | null {
        return this.analyserNode;
    }

    disconnect(): void {
        if (this.analyserNode) {
            this.analyserNode.disconnect();
        }
    }
}
