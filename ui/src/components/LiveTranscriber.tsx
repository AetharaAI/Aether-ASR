import { useState, useRef, useEffect, useCallback } from 'react';
import { MicrophoneIcon, StopCircleIcon } from '@heroicons/react/24/solid';

interface LiveTranscriberProps {
    onTranscriptUpdate: (text: string) => void;
    apiBaseUrl?: string;
}

/**
 * LiveTranscriber — streams mic audio via WebSocket to Voxtral Realtime
 * and renders transcript as it arrives.
 */
export default function LiveTranscriber({ onTranscriptUpdate, apiBaseUrl = '' }: LiveTranscriberProps) {
    const [isListening, setIsListening] = useState(false);
    const [liveText, setLiveText] = useState('');
    const [elapsed, setElapsed] = useState(0);
    const [permissionGranted, setPermissionGranted] = useState<boolean | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const workletNodeRef = useRef<AudioWorkletNode | ScriptProcessorNode | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const timerRef = useRef<number | null>(null);
    const fullTextRef = useRef('');

    const TARGET_SR = 16000;

    const startListening = useCallback(async () => {
        // Get mic permission
        let stream: MediaStream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                audio: { sampleRate: TARGET_SR, channelCount: 1, echoCancellation: true, noiseSuppression: true }
            });
            setPermissionGranted(true);
            streamRef.current = stream;
        } catch {
            setPermissionGranted(false);
            return;
        }

        // Open WebSocket
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = apiBaseUrl || `${wsProtocol}//${window.location.host}`;
        const wsUrl = `${wsHost.replace(/^http/, 'ws')}/api/voxtral/realtime`;

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            // Wait for session.created, it arrives as the first message
            // We handle it in onmessage below
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'session.created') {
                    // Now send session.update with model (flat format per current vLLM docs)
                    ws.send(JSON.stringify({
                        type: 'session.update',
                        model: 'mistralai/Voxtral-Mini-4B-Realtime-2602',
                    }));
                    // Start audio pipeline after session is configured
                    setupAudioPipeline(stream, ws);
                } else if (data.type === 'transcription.delta') {
                    fullTextRef.current += data.delta || '';
                    setLiveText(fullTextRef.current);
                    onTranscriptUpdate(fullTextRef.current);
                } else if (data.type === 'transcription.done') {
                    const finalText = data.text || fullTextRef.current;
                    fullTextRef.current = finalText;
                    setLiveText(finalText);
                    onTranscriptUpdate(finalText);
                } else if (data.type === 'error') {
                    console.error('Voxtral WS error:', data.error);
                }
            } catch {
                // Non-JSON message, ignore
            }
        };

        ws.onerror = () => {
            console.error('WebSocket error');
            stopListening();
        };

        ws.onclose = () => {
            // Connection closed
        };

        setIsListening(true);
        setElapsed(0);
        fullTextRef.current = '';
        setLiveText('');

        // Timer
        timerRef.current = window.setInterval(() => {
            setElapsed(prev => prev + 1);
        }, 1000);
    }, [onTranscriptUpdate, apiBaseUrl]);

    const setupAudioPipeline = (stream: MediaStream, ws: WebSocket) => {
        const audioCtx = new AudioContext({ sampleRate: TARGET_SR });
        audioContextRef.current = audioCtx;

        const source = audioCtx.createMediaStreamSource(stream);

        // Use ScriptProcessorNode (widely supported) to capture PCM
        const bufferSize = 4096;
        const processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
        workletNodeRef.current = processor;

        processor.onaudioprocess = (e) => {
            if (ws.readyState !== WebSocket.OPEN) return;

            const inputData = e.inputBuffer.getChannelData(0);

            // Convert float32 → int16
            const pcm16 = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            // Base64 encode
            const bytes = new Uint8Array(pcm16.buffer);
            let binary = '';
            for (let i = 0; i < bytes.length; i++) {
                binary += String.fromCharCode(bytes[i]);
            }
            const b64 = btoa(binary);

            ws.send(JSON.stringify({
                type: 'input_audio_buffer.append',
                audio: b64,
            }));
        };

        source.connect(processor);
        processor.connect(audioCtx.destination); // Required for ScriptProcessor to fire
    };

    const stopListening = useCallback(() => {
        // Send commit before closing
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'input_audio_buffer.commit' }));
            // Give a moment for final results then close
            setTimeout(() => {
                wsRef.current?.close();
            }, 2000);
        }

        // Stop audio
        if (workletNodeRef.current) {
            workletNodeRef.current.disconnect();
        }
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
            audioContextRef.current.close();
        }
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(t => t.stop());
        }

        if (timerRef.current) {
            clearInterval(timerRef.current);
        }

        setIsListening(false);
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (wsRef.current) wsRef.current.close();
            if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
            if (audioContextRef.current?.state !== 'closed') audioContextRef.current?.close();
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, []);

    const formatTime = (s: number) => {
        const m = Math.floor(s / 60).toString().padStart(2, '0');
        const sec = (s % 60).toString().padStart(2, '0');
        return `${m}:${sec}`;
    };

    return (
        <div className="flex flex-col items-center justify-center p-6 bg-[#2a2a2a] border border-gray-700 rounded-xl relative overflow-hidden">
            {permissionGranted === false && (
                <div className="absolute top-0 inset-x-0 bg-red-900/80 text-red-200 text-xs text-center py-2 z-10">
                    Microphone permission denied. Please allow it in your browser.
                </div>
            )}

            {/* Live indicator */}
            {isListening && (
                <div className="absolute top-3 right-3 flex items-center space-x-2 z-10">
                    <span className="live-dot" />
                    <span className="text-xs text-red-400 font-mono font-bold tracking-wider">LIVE</span>
                </div>
            )}

            <div className="z-10 flex flex-col items-center w-full">
                {!isListening ? (
                    <button
                        type="button"
                        onClick={startListening}
                        className="w-16 h-16 rounded-full bg-purple-600 hover:bg-purple-500 shadow-[0_0_15px_rgba(147,51,234,0.3)] hover:shadow-[0_0_25px_rgba(147,51,234,0.5)] flex items-center justify-center transition-all group"
                    >
                        <MicrophoneIcon className="w-8 h-8 text-white group-hover:scale-110 transition-transform" />
                    </button>
                ) : (
                    <button
                        type="button"
                        onClick={stopListening}
                        className="w-16 h-16 rounded-full bg-red-600 hover:bg-red-500 shadow-[0_0_15px_rgba(220,38,38,0.5)] flex items-center justify-center transition-all"
                        style={{ animation: 'pulse-glow 2s ease-in-out infinite' }}
                    >
                        <StopCircleIcon className="w-10 h-10 text-white" />
                    </button>
                )}

                <div className="mt-4 text-center">
                    {isListening ? (
                        <div className="text-purple-400 font-mono text-xl tracking-wider font-bold">
                            {formatTime(elapsed)}
                        </div>
                    ) : (
                        <div className="text-gray-400 text-sm font-medium">
                            {liveText ? 'Session ended' : 'Start Live Transcription'}
                        </div>
                    )}
                </div>

                {/* Live transcript preview */}
                {isListening && liveText && (
                    <div className="mt-4 w-full max-h-24 overflow-y-auto bg-[#1a1a1a] rounded-lg p-3 border border-purple-800/30">
                        <p className="text-sm text-gray-300 font-mono leading-relaxed">
                            {liveText}
                            <span className="typewriter-cursor" />
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
