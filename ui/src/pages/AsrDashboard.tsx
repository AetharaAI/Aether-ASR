import { useState, useEffect, useRef, useCallback } from 'react';
import toast from 'react-hot-toast';
import {
    ArrowUpTrayIcon, Cog8ToothIcon, PlayIcon,
    SpeakerWaveIcon, MicrophoneIcon,
    BoltIcon, ChevronRightIcon, ChevronLeftIcon,
    SignalIcon, ArrowDownTrayIcon, ClipboardDocumentIcon,
    ArrowPathIcon
} from '@heroicons/react/24/outline';
import api from '../services/api';
import ttsApi from '../services/ttsApi';
import type { TtsRequestParams } from '../services/ttsApi';
import AudioRecorder from '../components/AudioRecorder';
import Header from '../components/Header';
import WaveformVisualizer from '../components/WaveformVisualizer';
import LiveTranscriber from '../components/LiveTranscriber';

type AsrEngine = 'whisper' | 'voxtral';
type InputMode = 'upload' | 'record' | 'live';
type VoiceMode = 'predefined' | 'clone';

const TAGS = ['laugh', 'chuckle', 'sigh', 'gasp', 'cough', 'clear throat', 'sniff', 'groan', 'shush'];

export default function AsrDashboard() {
    // ASR State
    const [file, setFile] = useState<File | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [displayedTranscript, setDisplayedTranscript] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const [inputMode, setInputMode] = useState<InputMode>('upload');
    const [asrEngine, setAsrEngine] = useState<AsrEngine>('whisper');
    const transcriptStartTime = useRef<number>(0);

    const [config, setConfig] = useState({
        model: 'base',
        language: 'auto',
        vad_enabled: true,
        word_timestamps: false,
        diarization_enabled: false,
    });

    const [availableModels, setAvailableModels] = useState<string[]>([]);

    // Service Health
    const [asrHealth, setAsrHealth] = useState<'healthy' | 'degraded' | 'checking'>('checking');
    const [ttsHealth, setTtsHealth] = useState<'healthy' | 'degraded' | 'checking'>('checking');
    const [voxtralHealth, setVoxtralHealth] = useState<'healthy' | 'degraded' | 'checking'>('checking');

    // TTS Panel
    const [ttsOpen, setTtsOpen] = useState(false);
    const [ttsScript, setTtsScript] = useState('');

    // TTS Full State (matching SAP TTSStudio)
    const [voiceMode, setVoiceMode] = useState<VoiceMode>('predefined');
    const [ttsVoices, setTtsVoices] = useState<{ name: string; filename: string }[]>([]);
    const [referenceFiles, setReferenceFiles] = useState<string[]>([]);
    const [selectedVoice, setSelectedVoice] = useState<string>('');
    const [selectedReference, setSelectedReference] = useState<string>('');
    const [isGeneratingTTS, setIsGeneratingTTS] = useState(false);
    const [ttsAudioUrl, setTtsAudioUrl] = useState<string | null>(null);
    const [ttsModelInfo, setTtsModelInfo] = useState<any>(null);

    // TTS Generation Params (Chatterbox full parity)
    const [ttsParams, setTtsParams] = useState({
        temperature: 0.6,
        exaggeration: 0.5,
        cfg_weight: 3.0,
        speed_factor: 1.0,
        seed: null as number | null,
        output_format: 'wav' as 'wav' | 'mp3' | 'opus',
        split_text: true,
        chunk_size: 120,
    });

    // TTS Settings panel toggle
    const [showTtsSettings, setShowTtsSettings] = useState(false);

    // Audio playback
    const audioRef = useRef<HTMLAudioElement>(null);

    useEffect(() => {
        api.get('/api/models').then(res => {
            if (res.data && res.data.models) {
                setAvailableModels(res.data.models.map((m: any) => m.id || m.name || m));
            }
        }).catch(() => { });

        api.get('/api/health').then(() => setAsrHealth('healthy')).catch(() => setAsrHealth('degraded'));

        api.get('/api/voxtral/health').then(res => {
            setVoxtralHealth(res.data.status === 'healthy' ? 'healthy' : 'degraded');
        }).catch(() => setVoxtralHealth('degraded'));

        ttsApi.getTtsHealth().then(data => {
            setTtsHealth(data.status === 'healthy' ? 'healthy' : 'degraded');
        }).catch(() => setTtsHealth('degraded'));

        // Load TTS voices and reference files
        ttsApi.getPredefinedVoices().then(voices => {
            if (voices && voices.length > 0) {
                setTtsVoices(voices);
                setSelectedVoice(voices[0].filename);
            }
        });

        ttsApi.getReferenceFiles().then(files => {
            if (files && files.length > 0) {
                setReferenceFiles(files);
                setSelectedReference(files[0]);
            }
        });

        // Load model info for tag support detection
        ttsApi.getTtsModelInfo().then(info => {
            if (info) setTtsModelInfo(info);
        });
    }, []);

    // Typewriter effect
    useEffect(() => {
        if (!transcript || isGenerating) {
            setDisplayedTranscript('');
            setIsTyping(false);
            return;
        }
        setDisplayedTranscript('');
        setIsTyping(true);
        let idx = 0;
        const timer = setInterval(() => {
            idx++;
            setDisplayedTranscript(transcript.slice(0, idx));
            if (idx >= transcript.length) {
                clearInterval(timer);
                setIsTyping(false);
            }
        }, 20);
        return () => clearInterval(timer);
    }, [transcript, isGenerating]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const submitTranscription = async (audioFile: File) => {
        setIsGenerating(true);
        setTranscript('');
        setDisplayedTranscript('');
        setTtsAudioUrl(null);
        transcriptStartTime.current = Date.now();
        const engineLabel = asrEngine === 'voxtral' ? 'Voxtral Realtime' : 'Faster-Whisper';
        toast(`Uploading to ${engineLabel}...`, { icon: '⏳' });

        try {
            if (asrEngine === 'voxtral') {
                const formData = new FormData();
                formData.append('file', audioFile);
                formData.append('language', config.language === 'auto' ? '' : config.language);
                formData.append('temperature', '0.0');

                const res = await api.post('/api/voxtral/transcribe', formData);
                setIsGenerating(false);
                const text = res.data.text || '';
                setTranscript(text);
                const elapsed = ((Date.now() - transcriptStartTime.current) / 1000).toFixed(1);
                const wordCount = text.split(/\s+/).length;
                toast.success(`Voxtral done • ${wordCount} words • ${elapsed}s`);
                return;
            }

            // Whisper path — async job via Celery
            const formData = new FormData();
            formData.append('file', audioFile);
            formData.append('model', config.model);
            formData.append('language', config.language);
            formData.append('vad_enabled', config.vad_enabled.toString());
            formData.append('word_timestamps', config.word_timestamps.toString());
            formData.append('diarization_enabled', config.diarization_enabled.toString());

            const res = await api.post('/v1/audio/transcriptions', formData);

            if (res.data.text && !res.data.job_id) {
                setIsGenerating(false);
                setTranscript(res.data.text);
                const elapsed = ((Date.now() - transcriptStartTime.current) / 1000).toFixed(1);
                const wordCount = res.data.text.split(/\s+/).length;
                toast.success(`Transcription complete • ${wordCount} words • ${elapsed}s`);
                return;
            }

            const jobId = res.data.job_id || res.data.id;
            const pollInterval = setInterval(async () => {
                try {
                    const statusRes = await api.get(`/api/transcriptions/${jobId}`);
                    if (statusRes.data.status === 'completed') {
                        clearInterval(pollInterval);
                        setIsGenerating(false);
                        const text = statusRes.data.result?.text || statusRes.data.text || '';
                        setTranscript(text);
                        const elapsed = ((Date.now() - transcriptStartTime.current) / 1000).toFixed(1);
                        const wordCount = text.split(/\s+/).length;
                        toast.success(`Transcription complete • ${wordCount} words • ${elapsed}s • ${config.model}`);
                    } else if (statusRes.data.status === 'failed') {
                        clearInterval(pollInterval);
                        setIsGenerating(false);
                        const errMsg = statusRes.data.error?.message || statusRes.data.error || 'Unknown error';
                        toast.error('Transcription failed: ' + errMsg);
                    }
                } catch (err) {
                    clearInterval(pollInterval);
                    setIsGenerating(false);
                    toast.error('Error checking transcription status.');
                }
            }, 5000); // poll every 5s — avoids rate limiter

        } catch (error: any) {
            setIsGenerating(false);
            const detail = error.response?.data?.detail;
            const msg = typeof detail === 'string' ? detail : typeof detail === 'object' ? JSON.stringify(detail) : 'Transcription failed.';
            toast.error(msg);
        }
    };

    const handleGenerate = () => {
        if (!file) { toast.error("Please select an audio file first."); return; }
        submitTranscription(file);
    };

    const handleRecordingComplete = (blob: Blob) => {
        const audioFile = new File([blob], 'recording.webm', { type: blob.type });
        setFile(audioFile);
        // Always use Whisper pipeline for recorded audio
        if (asrEngine !== 'whisper') setAsrEngine('whisper');
        submitTranscription(audioFile);
    };

    const handleLiveTranscriptUpdate = useCallback((text: string) => {
        setTranscript(text);
        setDisplayedTranscript(text);
    }, []);

    // TTS Generation with ALL Chatterbox params
    const handleGenerateTTS = async () => {
        const textToSynth = ttsScript.trim();
        if (!textToSynth) return;

        setIsGeneratingTTS(true);
        const genStart = Date.now();

        const params: TtsRequestParams = {
            text: textToSynth,
            voice_mode: voiceMode,
            output_format: ttsParams.output_format,
            split_text: ttsParams.split_text,
            chunk_size: ttsParams.chunk_size,
            temperature: ttsParams.temperature,
            exaggeration: ttsParams.exaggeration,
            cfg_weight: ttsParams.cfg_weight,
            speed_factor: ttsParams.speed_factor,
        };

        if (ttsParams.seed !== null) params.seed = ttsParams.seed;

        if (voiceMode === 'predefined' && selectedVoice) {
            params.predefined_voice_id = selectedVoice;
        } else if (voiceMode === 'clone' && selectedReference) {
            params.reference_audio_filename = selectedReference;
        }

        try {
            const blob = await ttsApi.generateTTS(params);
            const url = URL.createObjectURL(blob);
            setTtsAudioUrl(url);
            const elapsed = ((Date.now() - genStart) / 1000).toFixed(1);
            toast.success(`Voice synthesis complete • ${elapsed}s`);
        } catch (error: any) {
            const msg = error.response?.data?.detail || error.message || 'TTS generation failed.';
            toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
        } finally {
            setIsGeneratingTTS(false);
        }
    };

    const insertTag = (tag: string) => {
        setTtsScript(prev => prev + `[${tag}] `);
    };

    // Upload reference audio for cloning
    const handleUploadReference = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || e.target.files.length === 0) return;
        const files = Array.from(e.target.files);
        try {
            await ttsApi.uploadReferenceAudio(files);
            toast.success(`Uploaded ${files.length} reference file(s)`);
            // Refresh reference files list
            const updated = await ttsApi.getReferenceFiles();
            setReferenceFiles(updated);
            if (updated.length > 0 && !selectedReference) setSelectedReference(updated[0]);
        } catch {
            toast.error('Reference audio upload failed.');
        }
    };

    const HealthBadge = ({ status, label }: { status: string; label: string }) => (
        <div className="flex items-center space-x-1.5">
            <div className={`w-2 h-2 rounded-full transition-all duration-500 ${status === 'healthy' ? 'bg-emerald-400 health-pulse' :
                status === 'degraded' ? 'bg-yellow-400 health-pulse' :
                    'bg-gray-500 animate-pulse'
                }`}
            />
            <span className="text-xs text-gray-500">{label}</span>
        </div>
    );

    const inputModes: { id: InputMode; label: string; icon: any; color: string }[] = [
        { id: 'upload', label: 'Upload', icon: ArrowUpTrayIcon, color: 'emerald' },
        { id: 'record', label: 'Record', icon: MicrophoneIcon, color: 'emerald' },
        { id: 'live', label: 'Live', icon: SignalIcon, color: 'purple' },
    ];

    const ParamSlider = ({ label, value, min, max, step, onChange, display }: {
        label: string; value: number; min: number; max: number; step: number;
        onChange: (v: number) => void; display: (v: number) => string;
    }) => (
        <div className="space-y-1.5">
            <div className="flex items-center justify-between">
                <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{label}</label>
                <span className="text-[10px] font-mono text-blue-400">{display(value)}</span>
            </div>
            <input
                type="range" min={min} max={max} step={step} value={value}
                onChange={e => onChange(parseFloat(e.target.value))}
                className="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
        </div>
    );

    return (
        <div className="min-h-screen bg-[#121212] text-white p-4 md:p-8 font-sans flex flex-col">
            <Header />
            <audio ref={audioRef} />

            {/* Top bar: Health badges + TTS toggle */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-4">
                    <HealthBadge status={asrHealth} label="Whisper" />
                    <HealthBadge status={voxtralHealth} label="Voxtral" />
                    <HealthBadge status={ttsHealth} label="TTS" />
                </div>
                <button
                    onClick={() => setTtsOpen(!ttsOpen)}
                    className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all border ${ttsOpen
                        ? 'bg-blue-600/20 text-blue-400 border-blue-500/50'
                        : 'bg-[#1e1e1e] text-gray-400 border-gray-700 hover:text-gray-200 hover:border-gray-500'
                        }`}
                >
                    <SpeakerWaveIcon className="w-4 h-4 mr-2" />
                    TTS Studio
                    {ttsOpen ? <ChevronRightIcon className="w-4 h-4 ml-2" /> : <ChevronLeftIcon className="w-4 h-4 ml-2" />}
                </button>
            </div>

            {/* ─── 3-Panel Layout ─── */}
            <div className="flex-1 flex gap-6 min-h-0">

                {/* ═══ LEFT PANEL: ASR Controls ═══ */}
                <div className="w-72 flex-shrink-0 space-y-5 overflow-y-auto">

                    {/* Engine Selector */}
                    <div className="bg-[#1e1e1e] rounded-xl p-5 border border-gray-800">
                        <h3 className="text-sm font-semibold text-gray-400 mb-3 flex items-center">
                            <Cog8ToothIcon className="w-4 h-4 mr-1.5 text-emerald-400" /> ASR Engine
                        </h3>
                        <div className="flex bg-[#2a2a2a] rounded-lg p-1 border border-gray-700">
                            <button
                                onClick={() => setAsrEngine('whisper')}
                                className={`flex-1 flex items-center justify-center py-2 text-xs font-medium rounded-md transition-all ${asrEngine === 'whisper' ? 'bg-[#3d3d3d] text-emerald-400 shadow' : 'text-gray-400 hover:text-gray-200'
                                    }`}
                            >
                                <MicrophoneIcon className="w-3.5 h-3.5 mr-1" /> Whisper
                            </button>
                            <button
                                onClick={() => { setAsrEngine('voxtral'); setInputMode('live'); }}
                                className={`flex-1 flex items-center justify-center py-2 text-xs font-medium rounded-md transition-all ${asrEngine === 'voxtral' ? 'bg-[#3d3d3d] text-purple-400 shadow' : 'text-gray-400 hover:text-gray-200'
                                    }`}
                            >
                                <BoltIcon className="w-3.5 h-3.5 mr-1" /> Voxtral
                            </button>
                        </div>
                        <p className="text-[10px] text-gray-600 mt-2">
                            {asrEngine === 'voxtral' ? 'Realtime streaming • 4B • <500ms' : 'Offline batch • VAD + diarization'}
                        </p>
                    </div>

                    {/* Input Mode */}
                    <div className="bg-[#1e1e1e] rounded-xl p-5 border border-gray-800">
                        <h3 className="text-sm font-semibold text-gray-400 mb-3">Input Mode</h3>
                        <div className="flex bg-[#2a2a2a] rounded-lg p-1 border border-gray-700">
                            {inputModes.map(mode => {
                                const Icon = mode.icon;
                                const isActive = inputMode === mode.id;
                                if (mode.id === 'live' && asrEngine !== 'voxtral') return null;
                                return (
                                    <button
                                        key={mode.id}
                                        onClick={() => setInputMode(mode.id)}
                                        className={`flex-1 flex items-center justify-center py-2 text-xs font-medium rounded-md transition-all ${isActive
                                            ? `bg-[#3d3d3d] ${mode.color === 'purple' ? 'text-purple-400' : 'text-emerald-400'} shadow`
                                            : 'text-gray-400 hover:text-gray-200'
                                            }`}
                                    >
                                        <Icon className="w-3.5 h-3.5 mr-1" /> {mode.label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Config (Whisper-specific) */}
                    {(asrEngine === 'whisper' || inputMode !== 'live') && (
                        <div className="bg-[#1e1e1e] rounded-xl p-5 border border-gray-800 space-y-3">
                            <h3 className="text-sm font-semibold text-gray-400 mb-2">Configuration</h3>

                            {asrEngine === 'whisper' && (
                                <div>
                                    <label className="block text-xs text-gray-500 mb-1">Model</label>
                                    <select
                                        value={config.model}
                                        onChange={(e) => setConfig({ ...config, model: e.target.value })}
                                        className="w-full bg-[#2a2a2a] border border-gray-700 rounded py-1.5 px-2 text-xs text-gray-200 focus:outline-none focus:border-emerald-500"
                                    >
                                        {availableModels.length > 0
                                            ? availableModels.map(m => <option key={m} value={m}>{m}</option>)
                                            : ['tiny', 'base', 'small', 'medium', 'large-v3'].map(m => <option key={m} value={m}>{m}</option>)
                                        }
                                    </select>
                                </div>
                            )}

                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Language</label>
                                <select
                                    value={config.language}
                                    onChange={(e) => setConfig({ ...config, language: e.target.value })}
                                    className="w-full bg-[#2a2a2a] border border-gray-700 rounded py-1.5 px-2 text-xs text-gray-200 focus:outline-none focus:border-emerald-500"
                                >
                                    {['auto', 'en', 'es', 'fr', 'de', 'ja', 'zh', 'ko', 'pt', 'ru', 'ar', 'it', 'nl', 'hi'].map(l => (
                                        <option key={l} value={l}>{l === 'auto' ? 'Auto Detect' : l.toUpperCase()}</option>
                                    ))}
                                </select>
                            </div>

                            {asrEngine === 'whisper' && (
                                <>
                                    <label className="flex items-center text-xs text-gray-400 space-x-2">
                                        <input type="checkbox" checked={config.vad_enabled}
                                            onChange={(e) => setConfig({ ...config, vad_enabled: e.target.checked })}
                                            className="rounded bg-[#2a2a2a] border-gray-600" />
                                        <span>VAD (Voice Activity Detection)</span>
                                    </label>
                                    <label className="flex items-center text-xs text-gray-400 space-x-2">
                                        <input type="checkbox" checked={config.diarization_enabled}
                                            onChange={(e) => setConfig({ ...config, diarization_enabled: e.target.checked })}
                                            className="rounded bg-[#2a2a2a] border-gray-600" />
                                        <span>Speaker Diarization</span>
                                    </label>
                                    <label className="flex items-center text-xs text-gray-400 space-x-2">
                                        <input type="checkbox" checked={config.word_timestamps}
                                            onChange={(e) => setConfig({ ...config, word_timestamps: e.target.checked })}
                                            className="rounded bg-[#2a2a2a] border-gray-600" />
                                        <span>Word Timestamps</span>
                                    </label>
                                </>
                            )}
                        </div>
                    )}

                    {/* Input Area */}
                    <div className="bg-[#1e1e1e] rounded-xl p-5 border border-gray-800">
                        {inputMode === 'upload' && (
                            <div className="space-y-3">
                                <h3 className="text-sm font-semibold text-gray-400">Upload Audio</h3>
                                <label className="flex flex-col items-center justify-center w-full py-6 border-2 border-dashed border-gray-700 rounded-xl cursor-pointer hover:border-emerald-600/50 transition-colors bg-[#1a1a1a]">
                                    <ArrowUpTrayIcon className="w-8 h-8 text-gray-500 mb-2" />
                                    <span className="text-xs text-gray-500">
                                        {file ? file.name : 'Drop audio or click'}
                                    </span>
                                    <input type="file" accept="audio/*" onChange={handleFileChange} className="hidden" />
                                </label>
                                <button
                                    onClick={handleGenerate}
                                    disabled={!file || isGenerating}
                                    className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:shadow-[0_0_15px_rgba(16,185,129,0.3)] flex items-center justify-center"
                                >
                                    {isGenerating ? (
                                        <><span className="animate-spin mr-2">⏳</span> Processing...</>
                                    ) : (
                                        <><PlayIcon className="w-4 h-4 mr-2" /> Transcribe</>
                                    )}
                                </button>
                            </div>
                        )}

                        {inputMode === 'record' && (
                            <div className="space-y-3">
                                <h3 className="text-sm font-semibold text-gray-400">Record Audio</h3>
                                <AudioRecorder onRecordingComplete={handleRecordingComplete} isTranscribing={isGenerating} />
                            </div>
                        )}

                        {inputMode === 'live' && (
                            <div className="space-y-3">
                                <h3 className="text-sm font-semibold text-gray-400 flex items-center">
                                    <SignalIcon className="w-4 h-4 mr-1.5 text-purple-400" /> Live Transcription
                                </h3>
                                <LiveTranscriber onTranscriptUpdate={handleLiveTranscriptUpdate} />
                            </div>
                        )}
                    </div>
                </div>

                {/* ═══ CENTER: Transcript Area ═══ */}
                <div className="flex-1 flex flex-col min-w-0 panel-transition">

                    <div className="flex-1 flex flex-col gap-4">

                        {/* ASR Transcript */}
                        <div className={`bg-[#1e1e1e] rounded-xl border border-gray-800 shadow-lg flex flex-col ${ttsOpen ? 'flex-1' : 'flex-1'}`}>
                            <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-gray-400 flex items-center">
                                    <MicrophoneIcon className="w-4 h-4 mr-1.5 text-emerald-400" />
                                    Transcription
                                    {inputMode === 'live' && transcript && (
                                        <span className="ml-2 flex items-center">
                                            <span className="live-dot mr-1" />
                                            <span className="text-[10px] text-red-400 font-mono">LIVE</span>
                                        </span>
                                    )}
                                </h3>
                                {transcript && (
                                    <div className="flex items-center space-x-2">
                                        <span className="text-[10px] text-gray-600 font-mono">
                                            {transcript.split(/\s+/).length} words
                                        </span>
                                        <button onClick={() => { navigator.clipboard.writeText(transcript); toast.success('Copied!'); }}
                                            className="text-gray-600 hover:text-gray-300 transition" title="Copy">
                                            <ClipboardDocumentIcon className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                )}
                            </div>

                            <div className="flex-1 p-5 overflow-y-auto font-mono text-sm leading-relaxed text-gray-300 min-h-[200px]">
                                {isGenerating ? (
                                    <div className="flex flex-col items-center justify-center h-full">
                                        <WaveformVisualizer
                                            color={asrEngine === 'voxtral' ? 'purple' : 'emerald'}
                                            barCount={28}
                                            statusMessages={
                                                asrEngine === 'voxtral'
                                                    ? ['Connecting to Voxtral...', 'Streaming audio...', 'Realtime decoding...']
                                                    : ['Initializing ASR Engine...', `Loading ${config.model}...`, 'Analyzing audio...', 'Decoding speech...']
                                            }
                                        />
                                    </div>
                                ) : displayedTranscript ? (
                                    <div className="whitespace-pre-wrap animate-fade-in-up">
                                        {displayedTranscript}
                                        {isTyping && <span className="typewriter-cursor" />}
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-gray-600">
                                        {inputMode === 'live'
                                            ? 'Start live transcription to see words appear in real time.'
                                            : 'Transcribed text will appear here.'}
                                    </div>
                                )}
                            </div>

                            {/* Quick actions */}
                            {transcript && !ttsOpen && (
                                <div className="px-5 py-3 border-t border-gray-800 flex items-center justify-between">
                                    <button
                                        onClick={() => { setTtsScript(transcript); setTtsOpen(true); }}
                                        className="text-xs bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 px-3 py-1.5 rounded border border-blue-500/50 transition flex items-center"
                                    >
                                        <SpeakerWaveIcon className="w-3.5 h-3.5 mr-1" /> Send to TTS
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* TTS Script Input (when TTS panel open) */}
                        {ttsOpen && (
                            <div className="bg-[#1e1e1e] rounded-xl border border-blue-800/30 shadow-lg flex flex-col flex-1 tts-panel-enter">
                                <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
                                    <h3 className="text-sm font-semibold text-gray-400 flex items-center">
                                        <SpeakerWaveIcon className="w-4 h-4 mr-1.5 text-blue-400" />
                                        TTS Script
                                    </h3>
                                    <span className="text-[10px] text-gray-600 font-mono">
                                        {ttsScript.split(/\s+/).filter(Boolean).length} words • {ttsScript.length} chars
                                    </span>
                                </div>

                                {/* Tags Row */}
                                <div className="px-5 py-2 border-b border-gray-800/50 flex items-center gap-1.5 overflow-x-auto">
                                    <span className="shrink-0 text-[10px] font-medium text-gray-600 mr-1">Tags:</span>
                                    {TAGS.map(tag => (
                                        <button key={tag}
                                            className="px-2 py-0.5 text-[10px] rounded border border-gray-700 text-gray-500 hover:text-blue-400 hover:border-blue-500/50 transition whitespace-nowrap"
                                            onClick={() => insertTag(tag)}>
                                            [{tag}]
                                        </button>
                                    ))}
                                </div>

                                <textarea
                                    value={ttsScript}
                                    onChange={(e) => setTtsScript(e.target.value)}
                                    placeholder="Enter or paste your TTS script here. Use [tags] for vocal reactions like [laugh], [sigh], etc..."
                                    className="flex-1 p-5 bg-transparent resize-none text-sm text-gray-300 font-mono leading-relaxed focus:outline-none placeholder-gray-700 min-h-[120px]"
                                />

                                {/* Split text controls */}
                                <div className="px-5 py-2 border-t border-gray-800/50 flex items-center gap-4">
                                    <label className="flex items-center text-[10px] text-gray-400 gap-1.5 cursor-pointer">
                                        <input type="checkbox" checked={ttsParams.split_text}
                                            onChange={e => setTtsParams({ ...ttsParams, split_text: e.target.checked })}
                                            className="rounded bg-[#2a2a2a] border-gray-600 w-3 h-3" />
                                        Split text
                                    </label>
                                    {ttsParams.split_text && (
                                        <div className="flex items-center gap-2 flex-1">
                                            <span className="text-[10px] text-gray-600">Chunk:</span>
                                            <input type="range" min={50} max={500} step={10}
                                                value={ttsParams.chunk_size}
                                                onChange={e => setTtsParams({ ...ttsParams, chunk_size: parseInt(e.target.value) })}
                                                className="flex-1 h-1 bg-gray-700 rounded appearance-none cursor-pointer accent-blue-500" />
                                            <span className="text-[10px] font-mono text-blue-400 w-6 text-right">{ttsParams.chunk_size}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* ═══ RIGHT PANEL: TTS Controls (Full Chatterbox Parity) ═══ */}
                {ttsOpen && (
                    <div className="w-80 flex-shrink-0 overflow-y-auto space-y-4 tts-panel-enter">

                        {/* Voice Synthesis Header */}
                        <div className="bg-[#1e1e1e] rounded-xl border border-blue-800/30 p-5 space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-blue-400 flex items-center">
                                    <SpeakerWaveIcon className="w-4 h-4 mr-1.5" /> Voice Synthesis
                                </h3>
                                {ttsModelInfo && (
                                    <span className="text-[9px] font-mono text-gray-600">
                                        {ttsModelInfo.model_name || 'Chatterbox'}
                                    </span>
                                )}
                            </div>

                            {/* Voice Mode Toggle */}
                            <div className="flex bg-[#2a2a2a] rounded-lg p-1 border border-gray-700">
                                <button
                                    onClick={() => setVoiceMode('predefined')}
                                    className={`flex-1 py-1.5 text-[10px] font-medium rounded-md transition-all ${voiceMode === 'predefined' ? 'bg-[#3d3d3d] text-blue-400 shadow' : 'text-gray-400 hover:text-gray-200'}`}
                                >
                                    Predefined
                                </button>
                                <button
                                    onClick={() => setVoiceMode('clone')}
                                    className={`flex-1 py-1.5 text-[10px] font-medium rounded-md transition-all ${voiceMode === 'clone' ? 'bg-[#3d3d3d] text-purple-400 shadow' : 'text-gray-400 hover:text-gray-200'}`}
                                >
                                    Voice Clone
                                </button>
                            </div>

                            {/* Predefined Voice Select */}
                            {voiceMode === 'predefined' && (
                                <div>
                                    <label className="block text-[10px] text-gray-500 mb-1 uppercase tracking-wider font-bold">Voice</label>
                                    <select
                                        value={selectedVoice}
                                        onChange={(e) => setSelectedVoice(e.target.value)}
                                        className="w-full bg-[#2a2a2a] border border-gray-700 rounded py-1.5 px-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500"
                                    >
                                        {ttsVoices.map(v => (
                                            <option key={v.filename} value={v.filename}>{v.name || v.filename.replace('.wav', '')}</option>
                                        ))}
                                    </select>
                                </div>
                            )}

                            {/* Clone Voice — Reference Select + Upload */}
                            {voiceMode === 'clone' && (
                                <div className="space-y-3">
                                    <div>
                                        <label className="block text-[10px] text-gray-500 mb-1 uppercase tracking-wider font-bold">Reference Audio</label>
                                        <select
                                            value={selectedReference}
                                            onChange={(e) => setSelectedReference(e.target.value)}
                                            className="w-full bg-[#2a2a2a] border border-gray-700 rounded py-1.5 px-2 text-xs text-gray-200 focus:outline-none focus:border-purple-500"
                                        >
                                            {referenceFiles.length > 0
                                                ? referenceFiles.map(f => <option key={f} value={f}>{f}</option>)
                                                : <option value="">No references uploaded</option>
                                            }
                                        </select>
                                    </div>
                                    <label className="flex items-center justify-center w-full py-3 border border-dashed border-gray-700 rounded-lg cursor-pointer hover:border-purple-600/50 transition text-xs text-gray-500 hover:text-purple-400 bg-[#1a1a1a]">
                                        <ArrowUpTrayIcon className="w-3.5 h-3.5 mr-1.5" />
                                        Upload Reference (.wav/.mp3)
                                        <input type="file" accept=".wav,.mp3" multiple onChange={handleUploadReference} className="hidden" />
                                    </label>
                                </div>
                            )}

                            {/* Output Format */}
                            <div>
                                <label className="block text-[10px] text-gray-500 mb-1 uppercase tracking-wider font-bold">Output Format</label>
                                <select
                                    value={ttsParams.output_format}
                                    onChange={(e) => setTtsParams({ ...ttsParams, output_format: e.target.value as any })}
                                    className="w-full bg-[#2a2a2a] border border-gray-700 rounded py-1.5 px-2 text-xs text-gray-200 focus:outline-none focus:border-blue-500"
                                >
                                    <option value="wav">WAV (Lossless)</option>
                                    <option value="mp3">MP3 (Compressed)</option>
                                    <option value="opus">Opus</option>
                                </select>
                            </div>

                            {/* Generate Button */}
                            <button
                                onClick={handleGenerateTTS}
                                disabled={!ttsScript.trim() || isGeneratingTTS}
                                className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:shadow-[0_0_15px_rgba(59,130,246,0.3)] flex items-center justify-center"
                            >
                                {isGeneratingTTS ? (
                                    <WaveformVisualizer color="blue" barCount={12} compact statusMessages={['Synthesizing...']} />
                                ) : (
                                    <><PlayIcon className="w-4 h-4 mr-2" /> Generate Voice</>
                                )}
                            </button>

                            {/* Audio Player */}
                            {ttsAudioUrl && (
                                <div className="bg-[#0a0a0a] rounded-lg p-3 border border-gray-800 space-y-2">
                                    <audio controls src={ttsAudioUrl} className="w-full h-8" />
                                    <div className="flex items-center justify-between">
                                        <a href={ttsAudioUrl} download={`synthesis.${ttsParams.output_format}`}
                                            className="text-xs text-blue-400 hover:text-blue-300 transition flex items-center">
                                            <ArrowDownTrayIcon className="w-3 h-3 mr-1" /> Download
                                        </a>
                                        <span className="text-[9px] text-gray-600 font-mono">
                                            {voiceMode === 'clone' ? `clone: ${selectedReference}` : selectedVoice.replace('.wav', '')}
                                        </span>
                                    </div>
                                </div>
                            )}

                            {/* Quick: Send transcript to TTS script */}
                            {transcript && !ttsScript && (
                                <button
                                    onClick={() => setTtsScript(transcript)}
                                    className="w-full text-xs text-gray-500 hover:text-gray-300 py-2 border border-gray-800 rounded-lg transition hover:border-gray-600"
                                >
                                    ← Use transcript as script
                                </button>
                            )}
                        </div>

                        {/* Generation Parameters (collapsed by default) */}
                        <div className="bg-[#1e1e1e] rounded-xl border border-gray-800 overflow-hidden">
                            <button
                                onClick={() => setShowTtsSettings(!showTtsSettings)}
                                className="w-full px-5 py-3 flex items-center justify-between text-sm font-semibold text-gray-400 hover:text-gray-200 transition"
                            >
                                <span className="flex items-center">
                                    <Cog8ToothIcon className="w-4 h-4 mr-1.5 text-blue-400" />
                                    Generation Parameters
                                </span>
                                <ChevronRightIcon className={`w-4 h-4 transition-transform ${showTtsSettings ? 'rotate-90' : ''}`} />
                            </button>

                            {showTtsSettings && (
                                <div className="px-5 pb-5 space-y-4 border-t border-gray-800">
                                    <div className="pt-3" />
                                    <ParamSlider label="Temperature" value={ttsParams.temperature}
                                        min={0.05} max={1.0} step={0.05}
                                        onChange={v => setTtsParams({ ...ttsParams, temperature: v })}
                                        display={v => v.toFixed(2)} />

                                    <ParamSlider label="Exaggeration" value={ttsParams.exaggeration}
                                        min={0} max={1.0} step={0.05}
                                        onChange={v => setTtsParams({ ...ttsParams, exaggeration: v })}
                                        display={v => v.toFixed(2)} />

                                    <ParamSlider label="CFG Weight" value={ttsParams.cfg_weight}
                                        min={0} max={10} step={0.5}
                                        onChange={v => setTtsParams({ ...ttsParams, cfg_weight: v })}
                                        display={v => v.toFixed(1)} />

                                    <ParamSlider label="Speed Factor" value={ttsParams.speed_factor}
                                        min={0.5} max={2.0} step={0.05}
                                        onChange={v => setTtsParams({ ...ttsParams, speed_factor: v })}
                                        display={v => v.toFixed(2)} />

                                    <div>
                                        <label className="block text-[10px] text-gray-400 mb-1 uppercase tracking-wider font-bold">Seed</label>
                                        <input
                                            type="number"
                                            value={ttsParams.seed ?? ''}
                                            onChange={e => setTtsParams({ ...ttsParams, seed: e.target.value ? parseInt(e.target.value) : null })}
                                            placeholder="Random"
                                            className="w-full bg-[#2a2a2a] border border-gray-700 rounded py-1.5 px-2 text-xs text-gray-200 font-mono focus:outline-none focus:border-blue-500"
                                        />
                                        <p className="text-[9px] text-gray-600 mt-1">Integer for reproducible results. Leave empty for random.</p>
                                    </div>

                                    <button
                                        onClick={() => setTtsParams({
                                            temperature: 0.6, exaggeration: 0.5, cfg_weight: 3.0,
                                            speed_factor: 1.0, seed: null, output_format: 'wav',
                                            split_text: true, chunk_size: 120,
                                        })}
                                        className="w-full text-[10px] text-gray-600 hover:text-gray-300 py-1.5 border border-gray-800 rounded transition hover:border-gray-600 flex items-center justify-center"
                                    >
                                        <ArrowPathIcon className="w-3 h-3 mr-1" /> Reset to Defaults
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Tips */}
                        <div className="bg-[#1e1e1e] rounded-xl border border-gray-800 p-4">
                            <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Tips</h4>
                            <ul className="text-[10px] text-gray-600 space-y-1">
                                <li>• Use <span className="text-blue-400">[tags]</span> for vocal reactions</li>
                                <li>• Enable <span className="text-blue-400">split text</span> for long content</li>
                                <li>• <span className="text-blue-400">Clone mode</span> needs reference audio</li>
                                <li>• Speed ≠ 1.0 is experimental</li>
                            </ul>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
