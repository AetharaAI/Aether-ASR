import { useState, useEffect, useRef } from 'react';
import toast from 'react-hot-toast';
import {
    ArrowUpTrayIcon, DocumentTextIcon, Cog8ToothIcon, PlayIcon,
    StopIcon, SpeakerWaveIcon, MicrophoneIcon, DocumentArrowUpIcon,
    ArrowPathIcon
} from '@heroicons/react/24/outline';
import api from '../services/api';
import ttsApi from '../services/ttsApi';
import AudioRecorder from '../components/AudioRecorder';
import Header from '../components/Header';
import TtsPanel from '../components/TtsPanel';
import WaveformVisualizer from '../components/WaveformVisualizer';
import PipelineFlow from '../components/PipelineFlow';

type StudioTab = 'asr' | 'tts' | 'workflow';

export default function AsrDashboard() {
    const [activeTab, setActiveTab] = useState<StudioTab>('asr');

    // ASR State
    const [file, setFile] = useState<File | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [displayedTranscript, setDisplayedTranscript] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const [inputMode, setInputMode] = useState<'upload' | 'record'>('upload');
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

    // TTS in-transcript
    const [ttsVoices, setTtsVoices] = useState<string[]>([]);
    const [selectedVoice, setSelectedVoice] = useState<string>('');
    const [isGeneratingTTS, setIsGeneratingTTS] = useState(false);
    const [ttsAudioUrl, setTtsAudioUrl] = useState<string | null>(null);

    useEffect(() => {
        api.get('/api/models').then(res => {
            if (res.data && res.data.models) {
                setAvailableModels(res.data.models.map((m: any) => m.id || m.name || m));
            }
        }).catch(() => { });

        api.get('/api/health').then(() => setAsrHealth('healthy')).catch(() => setAsrHealth('degraded'));

        ttsApi.getTtsHealth().then(data => {
            setTtsHealth(data.status === 'healthy' ? 'healthy' : 'degraded');
        }).catch(() => setTtsHealth('degraded'));

        ttsApi.getPredefinedVoices().then(voices => {
            if (voices && voices.length > 0) {
                const filenames = voices.map(v => v.filename);
                setTtsVoices(filenames);
                setSelectedVoice(filenames[0]);
            }
        });
    }, []);

    // Typewriter effect
    useEffect(() => {
        if (!transcript || isGenerating) {
            setDisplayedTranscript('');
            return;
        }
        setIsTyping(true);
        setDisplayedTranscript('');
        let i = 0;
        const chunkSize = Math.max(1, Math.floor(transcript.length / 100)); // show in ~100 steps
        const timer = setInterval(() => {
            i += chunkSize;
            if (i >= transcript.length) {
                setDisplayedTranscript(transcript);
                setIsTyping(false);
                clearInterval(timer);
            } else {
                setDisplayedTranscript(transcript.slice(0, i));
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
        toast('Uploading and transcribing...', { icon: '⏳' });

        try {
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
                        toast.success(`ASR complete • ${wordCount} words • ${elapsed}s • ${config.model}`);
                    } else if (statusRes.data.status === 'failed') {
                        clearInterval(pollInterval);
                        setIsGenerating(false);
                        toast.error("Transcription failed.");
                    }
                } catch {
                    clearInterval(pollInterval);
                    setIsGenerating(false);
                }
            }, 2000);
        } catch (error: any) {
            console.error(error);
            setIsGenerating(false);
            const detail = error?.response?.data?.detail || error?.response?.data?.error?.message || "Failed to submit job.";
            toast.error(typeof detail === 'string' ? detail : "Failed to submit job.");
        }
    };

    const handleGenerate = () => {
        if (!file) { toast.error("Please select an audio file first."); return; }
        submitTranscription(file);
    };

    const handleRecordingComplete = (blob: Blob) => {
        const audioFile = new File([blob], 'recording.webm', { type: blob.type });
        setFile(audioFile);
        submitTranscription(audioFile);
    };

    const handleSendToTTS = async () => {
        if (!transcript) return;
        setIsGeneratingTTS(true);
        try {
            const blob = await ttsApi.generateTTS({
                text: transcript,
                voice_mode: 'predefined',
                predefined_voice_id: selectedVoice,
                output_format: 'wav',
            });
            const url = URL.createObjectURL(blob);
            setTtsAudioUrl(url);
            toast.success("Voice synthesis complete!");
        } catch {
            toast.error("TTS generation failed.");
        } finally {
            setIsGeneratingTTS(false);
        }
    };

    const handleSendToWorkflow = () => {
        setActiveTab('tts');
    };

    const HealthBadge = ({ status, label }: { status: string; label: string }) => (
        <div className="flex items-center space-x-1.5">
            <div className={`w-2 h-2 rounded-full transition-all duration-500 ${status === 'healthy' ? 'bg-emerald-400 health-pulse' :
                    status === 'degraded' ? 'bg-yellow-400 health-pulse' :
                        'bg-gray-500 animate-pulse'
                }`}
                style={{ color: status === 'healthy' ? '#34d399' : status === 'degraded' ? '#facc15' : '#6b7280' }}
            />
            <span className="text-xs text-gray-500">{label}</span>
        </div>
    );

    const tabs: { id: StudioTab; label: string; icon: any; color: string }[] = [
        { id: 'asr', label: 'Transcribe', icon: MicrophoneIcon, color: 'emerald' },
        { id: 'tts', label: 'Synthesize', icon: SpeakerWaveIcon, color: 'blue' },
        { id: 'workflow', label: 'Pipeline', icon: ArrowPathIcon, color: 'purple' },
    ];

    return (
        <div className="min-h-screen bg-[#121212] text-white p-6 md:p-12 font-sans">
            <Header />

            {/* Service Health + Tab Navigation */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 gap-4">
                {/* Tabs */}
                <div className="flex bg-[#1e1e1e] rounded-xl p-1 border border-gray-800">
                    {tabs.map(tab => {
                        const Icon = tab.icon;
                        const isActive = activeTab === tab.id;
                        const colorMap: Record<string, string> = {
                            emerald: isActive ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/50' : '',
                            blue: isActive ? 'bg-blue-600/20 text-blue-400 border-blue-500/50' : '',
                            purple: isActive ? 'bg-purple-600/20 text-purple-400 border-purple-500/50' : '',
                        };
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`flex items-center px-5 py-2.5 rounded-lg text-sm font-medium transition-all border border-transparent ${isActive
                                    ? colorMap[tab.color]
                                    : 'text-gray-500 hover:text-gray-300 hover:bg-[#2a2a2a]'
                                    }`}
                            >
                                <Icon className="w-4 h-4 mr-2" />
                                {tab.label}
                            </button>
                        );
                    })}
                </div>

                {/* Health Badges */}
                <div className="flex items-center space-x-4">
                    <HealthBadge status={asrHealth} label="ASR Engine" />
                    <HealthBadge status={ttsHealth} label="TTS Engine" />
                </div>
            </div>

            {/* ─────────── ASR TAB ─────────── */}
            {activeTab === 'asr' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Left Column: Settings + Input */}
                    <div className="col-span-1 space-y-6">
                        <div className="bg-[#1e1e1e] rounded-xl p-6 border border-gray-800 shadow-lg">
                            <h2 className="text-xl font-semibold mb-4 flex items-center">
                                <Cog8ToothIcon className="w-5 h-5 mr-2 text-emerald-400" /> Settings
                            </h2>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-1">Model Size</label>
                                    <select
                                        className="w-full bg-[#2a2a2a] border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
                                        value={config.model}
                                        onChange={(e) => setConfig({ ...config, model: e.target.value })}
                                    >
                                        {availableModels.length > 0 ? (
                                            availableModels.map(m => <option key={m} value={m}>{m}</option>)
                                        ) : (
                                            <>
                                                <option value="tiny">tiny</option>
                                                <option value="base">base</option>
                                                <option value="large-v3">large-v3</option>
                                            </>
                                        )}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-400 mb-1">Language</label>
                                    <input
                                        type="text" value={config.language}
                                        onChange={(e) => setConfig({ ...config, language: e.target.value })}
                                        className="w-full bg-[#2a2a2a] border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
                                        placeholder="auto"
                                    />
                                </div>
                                <div className="pt-2 space-y-2">
                                    {[
                                        { key: 'vad_enabled', label: 'Voice Activity Detection (VAD)' },
                                        { key: 'word_timestamps', label: 'Word-level Timestamps' },
                                        { key: 'diarization_enabled', label: 'Speaker Diarization' },
                                    ].map(opt => (
                                        <label key={opt.key} className="flex items-center space-x-2">
                                            <input
                                                type="checkbox"
                                                checked={(config as any)[opt.key]}
                                                onChange={(e) => setConfig({ ...config, [opt.key]: e.target.checked })}
                                                className="rounded text-emerald-500 focus:ring-emerald-500 bg-[#2a2a2a] border-gray-600"
                                            />
                                            <span className="text-sm text-gray-300">{opt.label}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="bg-[#1e1e1e] rounded-xl p-6 border border-gray-800 shadow-lg">
                            <div className="flex bg-[#2a2a2a] rounded-lg p-1 mb-6 border border-gray-700">
                                <button
                                    onClick={() => setInputMode('upload')}
                                    className={`flex-1 flex items-center justify-center py-2 text-sm font-medium rounded-md transition-all ${inputMode === 'upload' ? 'bg-[#3d3d3d] text-emerald-400 shadow' : 'text-gray-400 hover:text-gray-200'}`}
                                >
                                    <DocumentArrowUpIcon className="w-4 h-4 mr-2" /> Upload File
                                </button>
                                <button
                                    onClick={() => setInputMode('record')}
                                    className={`flex-1 flex items-center justify-center py-2 text-sm font-medium rounded-md transition-all ${inputMode === 'record' ? 'bg-[#3d3d3d] text-emerald-400 shadow' : 'text-gray-400 hover:text-gray-200'}`}
                                >
                                    <MicrophoneIcon className="w-4 h-4 mr-2" /> Record Audio
                                </button>
                            </div>

                            {inputMode === 'upload' ? (
                                <>
                                    <div className="flex items-center justify-center w-full">
                                        <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-700 border-dashed rounded-lg cursor-pointer bg-[#2a2a2a] hover:bg-[#333] hover:border-emerald-600/40 transition-all">
                                            <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                                <ArrowUpTrayIcon className="w-8 h-8 mb-3 text-gray-400" />
                                                <p className="mb-2 text-sm text-gray-400"><span className="font-semibold">Click to upload</span> or drag and drop</p>
                                                <p className="text-xs text-gray-500">.wav, .mp3, .m4a, .webm, .ogg, .flac</p>
                                            </div>
                                            <input type="file" className="hidden" accept=".wav,.mp3,.m4a,.webm,.ogg,.flac,.opus" onChange={handleFileChange} />
                                        </label>
                                    </div>
                                    {file && (
                                        <div className="mt-4 p-3 bg-emerald-900/30 border border-emerald-800 rounded text-sm text-emerald-200 animate-fade-in-up">
                                            Selected: {file.name}
                                        </div>
                                    )}
                                    <button
                                        onClick={handleGenerate}
                                        disabled={isGenerating || !file}
                                        className={`w-full mt-6 py-3 rounded-lg font-bold flex items-center justify-center transition-all ${isGenerating || !file
                                            ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                                            : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)] hover:shadow-[0_0_25px_rgba(16,185,129,0.6)]'
                                            }`}
                                    >
                                        {isGenerating ? (
                                            <><StopIcon className="w-5 h-5 mr-2 animate-pulse" /> Transcribing...</>
                                        ) : (
                                            <><PlayIcon className="w-5 h-5 mr-2" /> Start Transcription</>
                                        )}
                                    </button>
                                </>
                            ) : (
                                <AudioRecorder onRecordingComplete={handleRecordingComplete} isTranscribing={isGenerating} />
                            )}
                        </div>
                    </div>

                    {/* Right Column: Output */}
                    <div className="col-span-1 lg:col-span-2">
                        <div className="bg-[#1e1e1e] rounded-xl p-6 border border-gray-800 shadow-lg h-full min-h-[500px] flex flex-col">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-xl font-semibold flex items-center">
                                    <DocumentTextIcon className="w-5 h-5 mr-2 text-emerald-400" /> Transcript Output
                                </h2>
                                {transcript && (
                                    <div className="flex space-x-2">
                                        <button
                                            onClick={() => { navigator.clipboard.writeText(transcript); toast.success("Copied!"); }}
                                            className="text-xs bg-[#2a2a2a] hover:bg-[#333] px-3 py-1 rounded border border-gray-700 transition"
                                        >
                                            Copy
                                        </button>
                                        <button
                                            onClick={handleSendToWorkflow}
                                            className="text-xs bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 px-3 py-1 rounded border border-blue-500/50 transition"
                                        >
                                            → Send to TTS
                                        </button>
                                    </div>
                                )}
                            </div>

                            <div className="flex-1 bg-[#0a0a0a] border border-gray-800 rounded-lg overflow-hidden flex flex-col">
                                <div className="flex-1 p-5 overflow-y-auto font-mono text-sm leading-relaxed text-gray-300">
                                    {isGenerating ? (
                                        <div className="flex flex-col items-center justify-center h-full min-h-[300px]">
                                            <WaveformVisualizer
                                                color="emerald"
                                                barCount={28}
                                                statusMessages={[
                                                    'Initializing ASR Engine...',
                                                    `Loading ${config.model} model...`,
                                                    'Analyzing audio waveform...',
                                                    'Detecting speech segments...',
                                                    'Decoding language patterns...',
                                                    'Processing with Faster-Whisper...',
                                                ]}
                                            />
                                        </div>
                                    ) : displayedTranscript ? (
                                        <div className="whitespace-pre-wrap animate-fade-in-up">
                                            {displayedTranscript}
                                            {isTyping && <span className="typewriter-cursor" />}
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center h-full text-gray-600 min-h-[300px]">
                                            Transcribed text will appear here.
                                        </div>
                                    )}
                                </div>

                                {/* Inline TTS Action */}
                                {transcript && ttsVoices.length > 0 && (
                                    <div className="bg-[#161616] border-t border-gray-800 p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
                                        <div className="flex items-center space-x-3 w-full sm:w-auto">
                                            <SpeakerWaveIcon className="w-5 h-5 text-gray-400" />
                                            <select
                                                value={selectedVoice}
                                                onChange={(e) => setSelectedVoice(e.target.value)}
                                                className="bg-[#2a2a2a] border border-gray-700 rounded py-1.5 px-3 text-sm text-gray-200 focus:outline-none focus:border-emerald-500 flex-1 sm:w-48"
                                            >
                                                {ttsVoices.map(voice => (
                                                    <option key={voice} value={voice}>{voice.replace('.wav', '')}</option>
                                                ))}
                                            </select>
                                        </div>
                                        <div className="flex items-center space-x-3 w-full sm:w-auto justify-end">
                                            {ttsAudioUrl && <audio controls src={ttsAudioUrl} className="h-8 max-w-[200px]" />}
                                            {isGeneratingTTS ? (
                                                <div className="flex items-center space-x-2">
                                                    <WaveformVisualizer color="blue" barCount={12} compact statusMessages={['Synthesizing voice...']} />
                                                </div>
                                            ) : (
                                                <button
                                                    onClick={handleSendToTTS}
                                                    className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-600/50 px-4 py-1.5 rounded-md text-sm font-medium transition-all hover:shadow-[0_0_10px_rgba(16,185,129,0.3)] flex items-center justify-center"
                                                >
                                                    Send to Voice
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ─────────── TTS TAB ─────────── */}
            {activeTab === 'tts' && (
                <div className="max-w-3xl mx-auto">
                    <TtsPanel initialText={transcript} />
                </div>
            )}

            {/* ─────────── WORKFLOW TAB ─────────── */}
            {activeTab === 'workflow' && (
                <div className="max-w-xl mx-auto">
                    <PipelineFlow
                        hasTranscript={!!transcript}
                        hasAudio={!!ttsAudioUrl}
                        isTranscribing={isGenerating}
                        isSynthesizing={isGeneratingTTS}
                        onGoToASR={() => setActiveTab('asr')}
                        onGoToTTS={() => setActiveTab('tts')}
                    />
                </div>
            )}
        </div>
    );
}
