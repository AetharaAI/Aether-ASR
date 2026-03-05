import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { ArrowUpTrayIcon, DocumentTextIcon, Cog8ToothIcon, PlayIcon, StopIcon, SpeakerWaveIcon, MicrophoneIcon, DocumentArrowUpIcon } from '@heroicons/react/24/outline';
import api from '../services/api';
import ttsApi from '../services/ttsApi';
import AudioRecorder from '../components/AudioRecorder';
import Header from '../components/Header';

export default function AsrDashboard() {

    const [file, setFile] = useState<File | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [inputMode, setInputMode] = useState<'upload' | 'record'>('upload');

    // TTS States
    const [ttsVoices, setTtsVoices] = useState<string[]>([]);
    const [selectedVoice, setSelectedVoice] = useState<string>('');
    const [isGeneratingTTS, setIsGeneratingTTS] = useState(false);
    const [ttsAudioUrl, setTtsAudioUrl] = useState<string | null>(null);

    const [config, setConfig] = useState({
        model: 'base',
        language: 'auto',
        vad_enabled: true,
        word_timestamps: false,
        diarization_enabled: false,
    });

    const [availableModels, setAvailableModels] = useState<string[]>([]);

    useEffect(() => {
        // Fetch available models on load
        api.get('/api/ui/initial-data').then(res => {
            if (res.data && res.data.models) {
                setAvailableModels(res.data.models);
            }
        }).catch(err => {
            console.error("Failed to fetch initial data", err);
        });

        // Fetch TTS voices
        ttsApi.getPredefinedVoices().then(voices => {
            if (voices && voices.length > 0) {
                setTtsVoices(voices);
                setSelectedVoice(voices[0]);
            }
        });
    }, []);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleGenerate = async () => {
        if (!file) {
            toast.error("Please select an audio file first.");
            return;
        }

        setIsGenerating(true);
        setTranscript('');
        toast('Uploading and transcribing Please wait...', { icon: '⏳' });

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('model', config.model);
            formData.append('language', config.language);
            formData.append('vad_enabled', config.vad_enabled.toString());
            formData.append('word_timestamps', config.word_timestamps.toString());
            formData.append('diarization_enabled', config.diarization_enabled.toString());

            // Note: The backend is async, so we'll poll for the result.
            // Axios will automatically set the correct Content-Type with boundary for FormData
            const res = await api.post('/v1/audio/transcriptions', formData);

            const jobId = res.data.id;

            // Poll for completion
            const pollInterval = setInterval(async () => {
                try {
                    const statusRes = await api.get(`/api/transcriptions/${jobId}`);
                    if (statusRes.data.status === 'completed') {
                        clearInterval(pollInterval);
                        setIsGenerating(false);
                        setTranscript(statusRes.data.result.text);
                        toast.success("Transcription complete!");
                    } else if (statusRes.data.status === 'failed') {
                        clearInterval(pollInterval);
                        setIsGenerating(false);
                        toast.error("Transcription failed.");
                    }
                } catch (e) {
                    clearInterval(pollInterval);
                    setIsGenerating(false);
                }
            }, 2000);

        } catch (error) {
            console.error(error);
            setIsGenerating(false);
            toast.error("Failed to submit job.");
        }
    };

    const handleRecordingComplete = (recordedFile: File) => {
        setFile(recordedFile);
        // Automatically start generation when recording finishes
        // We need a slight delay to allow state to set
        setTimeout(() => {
            // Note: Since setFile is async, we modify the handler to optionally take a file directly
            handleGenerateWithFile(recordedFile);
        }, 100);
    };

    const handleGenerateWithFile = async (currentFile: File) => {
        setIsGenerating(true);
        setTranscript('');
        setTtsAudioUrl(null); // Clear previous TTS
        toast('Uploading recording and transcribing...', { icon: '⏳' });

        try {
            const formData = new FormData();
            formData.append('file', currentFile);
            formData.append('model', config.model);
            formData.append('language', config.language);
            formData.append('vad_enabled', config.vad_enabled.toString());
            formData.append('word_timestamps', config.word_timestamps.toString());
            formData.append('diarization_enabled', config.diarization_enabled.toString());

            const res = await api.post('/v1/audio/transcriptions', formData);

            const jobId = res.data.id;

            const pollInterval = setInterval(async () => {
                try {
                    const statusRes = await api.get(`/api/transcriptions/${jobId}`);
                    if (statusRes.data.status === 'completed') {
                        clearInterval(pollInterval);
                        setIsGenerating(false);
                        setTranscript(statusRes.data.result.text);
                        toast.success("Transcription complete!");
                    } else if (statusRes.data.status === 'failed') {
                        clearInterval(pollInterval);
                        setIsGenerating(false);
                        toast.error("Transcription failed.");
                    }
                } catch (e) {
                    clearInterval(pollInterval);
                    setIsGenerating(false);
                }
            }, 2000);

        } catch (error) {
            console.error(error);
            setIsGenerating(false);
            toast.error("Failed to submit job.");
        }
    };

    const handleSendToTTS = async () => {
        if (!transcript || !selectedVoice) return;

        setIsGeneratingTTS(true);
        // Clear old audio
        if (ttsAudioUrl) {
            URL.revokeObjectURL(ttsAudioUrl);
            setTtsAudioUrl(null);
        }

        const loadingToast = toast.loading(`Generating voice: ${selectedVoice}...`);

        try {
            const audioBlob = await ttsApi.generateTTS({
                text: transcript,
                voice_mode: 'predefined',
                predefined_voice_id: selectedVoice,
                output_format: 'mp3'
            });

            const url = URL.createObjectURL(audioBlob);
            setTtsAudioUrl(url);
            toast.success("Voice generation complete!", { id: loadingToast });
        } catch (err) {
            console.error("TTS generation failed", err);
            toast.error("Failed to generate voice from Chatterbox server.", { id: loadingToast });
        } finally {
            setIsGeneratingTTS(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#121212] text-white p-6 md:p-12 font-sans">
            <Header />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* Left Column: Form & Settings */}
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
                                    type="text"
                                    value={config.language}
                                    onChange={(e) => setConfig({ ...config, language: e.target.value })}
                                    className="w-full bg-[#2a2a2a] border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
                                    placeholder="auto"
                                />
                            </div>

                            <div className="pt-2 space-y-2">
                                <label className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        checked={config.vad_enabled}
                                        onChange={(e) => setConfig({ ...config, vad_enabled: e.target.checked })}
                                        className="rounded text-emerald-500 focus:ring-emerald-500 bg-[#2a2a2a] border-gray-600"
                                    />
                                    <span className="text-sm text-gray-300">Enable Voice Activity Detection (VAD)</span>
                                </label>

                                <label className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        checked={config.word_timestamps}
                                        onChange={(e) => setConfig({ ...config, word_timestamps: e.target.checked })}
                                        className="rounded text-emerald-500 focus:ring-emerald-500 bg-[#2a2a2a] border-gray-600"
                                    />
                                    <span className="text-sm text-gray-300">Word-level Timestamps</span>
                                </label>

                                <label className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        checked={config.diarization_enabled}
                                        onChange={(e) => setConfig({ ...config, diarization_enabled: e.target.checked })}
                                        className="rounded text-emerald-500 focus:ring-emerald-500 bg-[#2a2a2a] border-gray-600"
                                    />
                                    <span className="text-sm text-gray-300">Speaker Diarization</span>
                                </label>
                            </div>
                        </div>
                    </div>

                    <div className="bg-[#1e1e1e] rounded-xl p-6 border border-gray-800 shadow-lg">

                        {/* Audio Input Tabs */}
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

                        <h2 className="text-xl font-semibold mb-4 flex items-center">
                            {inputMode === 'upload' ? <ArrowUpTrayIcon className="w-5 h-5 mr-2 text-emerald-400" /> : <MicrophoneIcon className="w-5 h-5 mr-2 text-emerald-400" />}
                            {inputMode === 'upload' ? 'Upload Audio' : 'Record Audio'}
                        </h2>

                        {inputMode === 'upload' ? (
                            <>
                                <div className="flex items-center justify-center w-full">
                                    <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-700 border-dashed rounded-lg cursor-pointer bg-[#2a2a2a] hover:bg-[#333] transition-colors">
                                        <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                            <ArrowUpTrayIcon className="w-8 h-8 mb-3 text-gray-400" />
                                            <p className="mb-2 text-sm text-gray-400"><span className="font-semibold">Click to upload</span> or drag and drop</p>
                                            <p className="text-xs text-gray-500">.wav, .mp3, .m4a</p>
                                        </div>
                                        <input type="file" className="hidden" accept=".wav,.mp3,.m4a" onChange={handleFileChange} />
                                    </label>
                                </div>
                                {file && (
                                    <div className="mt-4 p-3 bg-emerald-900/30 border border-emerald-800 rounded text-sm text-emerald-200">
                                        Selected: {file.name}
                                    </div>
                                )}

                                <button
                                    onClick={handleGenerate}
                                    disabled={isGenerating || !file}
                                    className={`w-full mt-6 py-3 rounded-lg font-bold flex items-center justify-center transition-all ${isGenerating || !file
                                        ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)]'
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
                            <AudioRecorder
                                onRecordingComplete={handleRecordingComplete}
                                isTranscribing={isGenerating}
                            />
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
                                    <button className="text-xs bg-[#2a2a2a] hover:bg-[#333] px-3 py-1 rounded border border-gray-700 transition">Copy JSON</button>
                                    <button className="text-xs bg-[#2a2a2a] hover:bg-[#333] px-3 py-1 rounded border border-gray-700 transition">Export SRT</button>
                                </div>
                            )}
                        </div>

                        <div className="flex-1 bg-[#0a0a0a] border border-gray-800 rounded-lg overflow-hidden flex flex-col">

                            {/* Transcript Content Area */}
                            <div className="flex-1 p-5 overflow-y-auto font-mono text-sm leading-relaxed text-gray-300">
                                {isGenerating ? (
                                    <div className="flex flex-col items-center justify-center h-full text-gray-500 min-h-[300px]">
                                        <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
                                        Processing your audio through Faster-Whisper...
                                    </div>
                                ) : transcript ? (
                                    <div className="whitespace-pre-wrap">{transcript}</div>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-gray-600 min-h-[300px]">
                                        Transcribed text will appear here.
                                    </div>
                                )}
                            </div>

                            {/* TTS Action Drawer (Bottom of transcript) */}
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
                                        {ttsAudioUrl && (
                                            <audio controls src={ttsAudioUrl} className="h-8 max-w-[200px]" />
                                        )}
                                        <button
                                            onClick={handleSendToTTS}
                                            disabled={isGeneratingTTS}
                                            className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-600/50 px-4 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center justify-center disabled:opacity-50"
                                        >
                                            {isGeneratingTTS ? (
                                                <span className="animate-pulse">Synthesizing...</span>
                                            ) : (
                                                'Send to Voice'
                                            )}
                                        </button>
                                    </div>
                                </div>
                            )}

                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}
