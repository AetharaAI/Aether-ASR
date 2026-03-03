import { useState, useRef, useEffect } from 'react';
import { MicrophoneIcon, StopCircleIcon } from '@heroicons/react/24/solid';

interface AudioRecorderProps {
    onRecordingComplete: (file: File) => void;
    isTranscribing: boolean;
}

export default function AudioRecorder({ onRecordingComplete, isTranscribing }: AudioRecorderProps) {
    const [isRecording, setIsRecording] = useState(false);
    const [recordingTime, setRecordingTime] = useState(0);
    const [permissionGranted, setPermissionGranted] = useState<boolean | null>(null);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const animationFrameRef = useRef<number | null>(null);
    const chunksRef = useRef<BlobPart[]>([]);
    const timerRef = useRef<number | null>(null);

    // Check or request mic permission
    const checkPermission = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            // Stop the stream right away, just wanted to get permission
            stream.getTracks().forEach(track => track.stop());
            setPermissionGranted(true);
            return true;
        } catch (err) {
            console.error("Microphone permission denied", err);
            setPermissionGranted(false);
            return false;
        }
    };

    const startRecording = async () => {
        let hasPermission = permissionGranted;
        if (!hasPermission) {
            hasPermission = await checkPermission();
            if (!hasPermission) return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Setup Audio Context for Waveform
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
            analyserRef.current = audioContextRef.current.createAnalyser();
            const source = audioContextRef.current.createMediaStreamSource(stream);
            source.connect(analyserRef.current);

            // Configuration for waveform visualization
            analyserRef.current.fftSize = 256;
            const bufferLength = analyserRef.current.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            // Start Media Recorder
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            chunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data);
                }
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
                // Create a File object from the Blob
                const audioFile = new File([audioBlob], `recording-${new Date().getTime()}.webm`, {
                    type: 'audio/webm',
                    lastModified: new Date().getTime()
                });

                onRecordingComplete(audioFile);

                // Cleanup all tracks
                stream.getTracks().forEach(track => track.stop());

                if (audioContextRef.current?.state !== 'closed') {
                    audioContextRef.current?.close();
                }
            };

            mediaRecorder.start();
            setIsRecording(true);
            setRecordingTime(0);

            // Start timer
            timerRef.current = setInterval(() => {
                setRecordingTime(prev => prev + 1);
            }, 1000);

            // Start the canvas rendering loop
            const drawWaveform = () => {
                if (!canvasRef.current || !analyserRef.current) return;

                const canvas = canvasRef.current;
                const canvasCtx = canvas.getContext('2d');
                if (!canvasCtx) return;

                const width = canvas.width;
                const height = canvas.height;

                analyserRef.current.getByteFrequencyData(dataArray);

                // Clear canvas with a very slight fade for trailing effect
                canvasCtx.fillStyle = 'rgba(24, 24, 27, 0.4)'; // match a dark background
                canvasCtx.fillRect(0, 0, width, height);

                const barWidth = (width / bufferLength) * 2.5;
                let barHeight;
                let x = 0;

                // Peak volume calculation to pulse the center
                let sum = 0;
                for (let i = 0; i < bufferLength; i++) {
                    sum += dataArray[i];
                }
                const average = sum / bufferLength;
                const pulseRatio = Math.min(average / 128, 1);

                // Draw symmetrical waveform originating from center
                for (let i = 0; i < bufferLength; i++) {
                    barHeight = (dataArray[i] / 255) * height;

                    // Tailwind emerald-500: rgb(16, 185, 129)
                    // Dynamically adjust opacity and color brightness based on intensity
                    const r = 16 + (pulseRatio * 20);
                    const g = 185 + (pulseRatio * 70);
                    const b = 129;

                    canvasCtx.fillStyle = `rgb(${r},${g},${b})`;

                    // Draw symmetrically (from center outwards)
                    const y = (height - barHeight) / 2;

                    // Left side
                    canvasCtx.fillRect((width / 2) - x, y, barWidth - 1, barHeight);
                    // Right side
                    canvasCtx.fillRect((width / 2) + x, y, barWidth - 1, barHeight);

                    x += barWidth;
                }

                animationFrameRef.current = requestAnimationFrame(drawWaveform);
            };

            drawWaveform();

        } catch (err) {
            console.error("Failed to start recording:", err);
            // Usually signifies permission denied or no device found
            setPermissionGranted(false);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);

            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        }
    };

    useEffect(() => {
        return () => {
            // Cleanup on unmount
            if (mediaRecorderRef.current?.state === 'recording') {
                mediaRecorderRef.current.stop();
            }
            if (timerRef.current) clearInterval(timerRef.current);
            if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
            if (audioContextRef.current?.state !== 'closed') {
                audioContextRef.current?.close();
            }
        };
    }, []);

    const formatTime = (seconds: number) => {
        const m = Math.floor(seconds / 60).toString().padStart(2, '0');
        const s = (seconds % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    };

    return (
        <div className="flex flex-col items-center justify-center p-6 bg-[#2a2a2a] border border-gray-700 rounded-xl relative overflow-hidden">

            {/* Error Message for Permissions */}
            {permissionGranted === false && (
                <div className="absolute top-0 inset-x-0 bg-red-900/80 text-red-200 text-xs text-center py-2 z-10">
                    Microphone permission denied. Please allow it in your browser.
                </div>
            )}

            {/* Visualizer Canvas overlay (renders behind the buttons) */}
            <canvas
                ref={canvasRef}
                width={400}
                height={100}
                className={`absolute inset-0 w-full h-full object-cover opacity-80 transition-opacity duration-300 ${isRecording ? 'opacity-100' : 'opacity-0'}`}
                style={{ pointerEvents: 'none', background: '#2a2a2a' }}
            />

            <div className="z-10 flex flex-col items-center w-full">
                {!isRecording ? (
                    <button
                        type="button"
                        onClick={startRecording}
                        disabled={isTranscribing}
                        className="w-16 h-16 rounded-full bg-emerald-600 hover:bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_25px_rgba(16,185,129,0.5)] flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed group"
                    >
                        <MicrophoneIcon className="w-8 h-8 text-white group-hover:scale-110 transition-transform" />
                    </button>
                ) : (
                    <button
                        type="button"
                        onClick={stopRecording}
                        className="w-16 h-16 rounded-full bg-red-600 hover:bg-red-500 shadow-[0_0_15px_rgba(220,38,38,0.5)] animate-pulse flex items-center justify-center transition-all"
                    >
                        <StopCircleIcon className="w-10 h-10 text-white" />
                    </button>
                )}

                <div className="mt-4 text-center">
                    {isRecording ? (
                        <div className="text-emerald-400 font-mono text-xl tracking-wider font-bold shadow-black drop-shadow-md">
                            {formatTime(recordingTime)}
                        </div>
                    ) : (
                        <div className="text-gray-400 text-sm font-medium">
                            {isTranscribing ? "Transcribing..." : "Click to Record Voice"}
                        </div>
                    )}
                </div>
            </div>

        </div>
    );
}
