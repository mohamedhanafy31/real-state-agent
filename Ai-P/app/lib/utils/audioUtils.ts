// Audio format conversion utilities

// Convert Float32Array to PCM 16-bit signed integer format
export function float32ToPCM16(float32Array: Float32Array): Int16Array {
    const pcm16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        // Clamp to [-1, 1]
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        // Convert to 16-bit PCM
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return pcm16;
}

// Convert ArrayBuffer to Base64 string
export function arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

// Convert Base64 string to ArrayBuffer
export function base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

// Normalize audio volume
export function normalizeAudio(float32Array: Float32Array, targetRMS: number = 0.1): Float32Array {
    // Calculate RMS
    let sum = 0;
    for (let i = 0; i < float32Array.length; i++) {
        sum += float32Array[i] * float32Array[i];
    }
    const rms = Math.sqrt(sum / float32Array.length);

    // Avoid division by zero
    if (rms < 0.001) return float32Array;

    // Calculate gain
    const gain = targetRMS / rms;

    // Apply gain with limiting
    const normalized = new Float32Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        const sample = float32Array[i] * gain;
        // Hard limit to prevent clipping
        normalized[i] = Math.max(-0.99, Math.min(0.99, sample));
    }

    return normalized;
}

// Calculate audio level (0-100)
export function calculateAudioLevel(float32Array: Float32Array): number {
    let sum = 0;
    for (let i = 0; i < float32Array.length; i++) {
        sum += Math.abs(float32Array[i]);
    }
    const average = sum / float32Array.length;
    return Math.min(100, average * 100);
}
