import { useState, useRef, useEffect, useCallback } from 'react';
import { MicrophoneIcon, StopCircleIcon } from '@heroicons/react/24/solid';

interface LiveTranscriberProps {
    onTranscriptUpdate: (text: string) => void;
    apiBaseUrl?: string;
}

/**
 * LiveTranscriber — TRUE real-time streaming transcription.
 *
 * Click mic → immediately connects to /api/voxtral/realtime WebSocket
 * and starts streaming PCM16 audio at 16kHz. Transcription deltas from
 * Voxtral appear in the UI the instant they arrive. Click stop → commits
 * the audio buffer, waits for the final transcript, then closes.
 *
 * Audio pipeline: MediaStream → AudioContext (16kHz) → ScriptProcessor
 *   → Float32→Int16 → base64 → input_audio_buffer.append JSON frames
 *
 * The component is resilient to different vLLM versions:
 * - If vLLM sends session.created first: we configure and then start audio
 * - If vLLM DOESN'T send session.created: audio starts immediately on WS open
 */
export default function LiveTranscriber({ onTranscriptUpdate, apiBaseUrl = '' }: LiveTranscriberProps) {
    const [isListening, setIsListening] = useState(false);
    const [status, setStatus] = useState<'idle' | 'connecting' | 'streaming' | 'finishing' | 'error'>('idle');
    const [liveText, setLiveText] = useState('');
    const [elapsed, setElapsed] = useState(0);
    const [permissionGranted, setPermissionGranted] = useState<boolean | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const timerRef = useRef<number | null>(null);
    const fullTextRef = useRef('');
    // Track whether we've started the audio pipeline (guard against double-start)
    const audioPipelineStartedRef = useRef(false);
    // If we haven't received session.created within 1.5s, start anyway
    const sessionTimeoutRef = useRef<number | null>(null);

    const TARGET_SR = 16000;
    const BUFFER_SIZE = 4096;
    const VLLM_MODEL = 'mistralai/Voxtral-Mini-4B-Realtime-2602';

    // ─── Audio pipeline setup ───────────────────────────────────────────────
    const startAudioPipeline = useCallback((ws: WebSocket, stream: MediaStream) => {
        if (audioPipelineStartedRef.current) return;
        audioPipelineStartedRef.current = true;

        const audioCtx = new AudioContext({ sampleRate: TARGET_SR });
        audioContextRef.current = audioCtx;
        const source = audioCtx.createMediaStreamSource(stream);

        const processor = audioCtx.createScriptProcessor(BUFFER_SIZE, 1, 1);
        processorRef.current = processor;

        processor.onaudioprocess = (e) => {
            if (ws.readyState !== WebSocket.OPEN) return;
            const float32 = e.inputBuffer.getChannelData(0);

            // Float32 → Int16 PCM
            const int16 = new Int16Array(float32.length);
            for (let i = 0; i < float32.length; i++) {
                const s = Math.max(-1, Math.min(1, float32[i]));
                int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            // Int16 buffer → base64
            const bytes = new Uint8Array(int16.buffer);
            let binary = '';
            for (let i = 0; i < bytes.length; i++) {
                binary += String.fromCharCode(bytes[i]);
            }

            ws.send(JSON.stringify({
                type: 'input_audio_buffer.append',
                audio: btoa(binary),
            }));
        };

        source.connect(processor);
        processor.connect(audioCtx.destination); // Required for ScriptProcessor to fire
        setStatus('streaming');
    }, []);

    // ─── Start listening ────────────────────────────────────────────────────
    const startListening = useCallback(async () => {
        // Request mic
        let stream: MediaStream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: TARGET_SR,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                }
            });
            setPermissionGranted(true);
            streamRef.current = stream;
        } catch {
            setPermissionGranted(false);
            return;
        }

        setStatus('connecting');
        setLiveText('');
        fullTextRef.current = '';
        audioPipelineStartedRef.current = false;

        // Build WebSocket URL
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const base = apiBaseUrl
            ? apiBaseUrl.replace(/^https?:/, proto.slice(0, -1) + 's:').replace(/^ws:/, 'ws:')
            : `${proto}//${window.location.host}`;
        const wsUrl = `${base}/api/voxtral/realtime`;

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        // Safety valve: if session.created never comes, start audio after 1.5s
        sessionTimeoutRef.current = window.setTimeout(() => {
            if (!audioPipelineStartedRef.current && ws.readyState === WebSocket.OPEN) {
                console.warn('[LiveTranscriber] session.created not received — starting audio anyway');
                startAudioPipeline(ws, stream);
            }
        }, 1500);

        ws.onopen = () => {
            // Send model config immediately (some vLLM versions accept this before session.created)
            ws.send(JSON.stringify({
                type: 'session.update',
                model: VLLM_MODEL,
            }));
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case 'session.created':
                    case 'session.updated':
                        // Clear the fallback timer — we have a proper handshake
                        if (sessionTimeoutRef.current) {
                            clearTimeout(sessionTimeoutRef.current);
                            sessionTimeoutRef.current = null;
                        }
                        startAudioPipeline(ws, stream);
                        break;

                    case 'transcription.delta':
                        fullTextRef.current += data.delta || '';
                        setLiveText(fullTextRef.current);
                        onTranscriptUpdate(fullTextRef.current);
                        break;

                    case 'transcription.done': {
                        const final = data.text || fullTextRef.current;
                        fullTextRef.current = final;
                        setLiveText(final);
                        onTranscriptUpdate(final);
                        break;
                    }

                    case 'error':
                        console.error('[LiveTranscriber] Voxtral error:', data.error || data);
                        setStatus('error');
                        break;
                }
            } catch {
                // Non-JSON or binary — ignore
            }
        };

        ws.onerror = (e) => {
            console.error('[LiveTranscriber] WS error', e);
            setStatus('error');
        };

        ws.onclose = () => {
            setIsListening(false);
            if (status !== 'error') setStatus('idle');
        };

        setIsListening(true);
        setElapsed(0);
        timerRef.current = window.setInterval(() => setElapsed(p => p + 1), 1000);
    }, [onTranscriptUpdate, apiBaseUrl, startAudioPipeline, status]);

    // ─── Stop listening ─────────────────────────────────────────────────────
    const stopListening = useCallback(() => {
        setStatus('finishing');

        // Clear fallback timer
        if (sessionTimeoutRef.current) {
            clearTimeout(sessionTimeoutRef.current);
            sessionTimeoutRef.current = null;
        }

        // Stop audio pipeline first
        processorRef.current?.disconnect();
        if (audioContextRef.current?.state !== 'closed') {
            audioContextRef.current?.close();
        }
        streamRef.current?.getTracks().forEach(t => t.stop());

        // Commit buffer then close WS (give 2s for final transcript)
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'input_audio_buffer.commit', final: true }));
            setTimeout(() => {
                wsRef.current?.close(1000, 'user stopped');
            }, 2000);
        }

        if (timerRef.current) clearInterval(timerRef.current);
        setIsListening(false);
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (sessionTimeoutRef.current) clearTimeout(sessionTimeoutRef.current);
            if (wsRef.current) wsRef.current.close();
            streamRef.current?.getTracks().forEach(t => t.stop());
            if (audioContextRef.current?.state !== 'closed') audioContextRef.current?.close();
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, []);

    const formatTime = (s: number) =>
        `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;

    const statusLabel = {
        idle: liveText ? 'Session ended' : 'Click to start live transcription',
        connecting: 'Connecting to Voxtral...',
        streaming: formatTime(elapsed),
        finishing: 'Finalizing...',
        error: 'Connection failed — click to retry',
    }[status];

    return (
        <div className="flex flex-col items-center justify-center p-6 bg-[#2a2a2a] border border-gray-700 rounded-xl relative overflow-hidden min-h-[140px]">
            {permissionGranted === false && (
                <div className="absolute top-0 inset-x-0 bg-red-900/80 text-red-200 text-xs text-center py-2 z-10">
                    Microphone access denied — allow it in your browser settings.
                </div>
            )}

            {/* LIVE badge */}
            {isListening && status === 'streaming' && (
                <div className="absolute top-3 right-3 flex items-center space-x-1.5 z-10">
                    <span className="live-dot" />
                    <span className="text-[10px] text-red-400 font-mono font-bold tracking-widest">LIVE</span>
                </div>
            )}

            <div className="z-10 flex flex-col items-center w-full">
                {/* Toggle button */}
                <button
                    type="button"
                    onClick={isListening ? stopListening : startListening}
                    disabled={status === 'connecting' || status === 'finishing'}
                    className={`w-16 h-16 rounded-full flex items-center justify-center transition-all disabled:opacity-60 disabled:cursor-not-allowed ${isListening
                        ? 'bg-red-600 hover:bg-red-500 shadow-[0_0_20px_rgba(220,38,38,0.6)] animate-pulse'
                        : status === 'error'
                            ? 'bg-orange-600 hover:bg-orange-500 shadow-[0_0_15px_rgba(234,88,12,0.4)]'
                            : 'bg-purple-600 hover:bg-purple-500 shadow-[0_0_15px_rgba(147,51,234,0.3)] hover:shadow-[0_0_25px_rgba(147,51,234,0.55)]'
                        }`}
                >
                    {isListening
                        ? <StopCircleIcon className="w-10 h-10 text-white" />
                        : <MicrophoneIcon className="w-8 h-8 text-white" />
                    }
                </button>

                {/* Status label */}
                <div className={`mt-3 text-center text-sm font-mono ${status === 'streaming' ? 'text-purple-400 text-lg font-bold tracking-wider' :
                    status === 'error' ? 'text-orange-400' :
                        'text-gray-400'
                    }`}>
                    {statusLabel}
                </div>

                {/* Live transcript preview (scrollable) */}
                {liveText && (
                    <div className="mt-4 w-full max-h-28 overflow-y-auto bg-[#181818] rounded-lg p-3 border border-purple-800/30">
                        <p className="text-sm text-gray-200 font-mono leading-relaxed whitespace-pre-wrap">
                            {liveText}
                            {status === 'streaming' && <span className="typewriter-cursor" />}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
