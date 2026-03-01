import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { ArrowUpTrayIcon, DocumentTextIcon, Cog8ToothIcon, PlayIcon, StopIcon } from '@heroicons/react/24/outline';
import api from '../services/api';

export default function AsrDashboard() {

    const [file, setFile] = useState<File | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [transcript, setTranscript] = useState('');

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
            const res = await api.post('/api/asr', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

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

    return (
        <div className="min-h-screen bg-[#121212] text-white p-6 md:p-12 font-sans">

            <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-emerald-400">Chatterbox ASR Server</h1>
                    <a href="/docs" className="text-sm text-gray-400 hover:text-emerald-300">API Docs</a>
                </div>
                <div className="flex space-x-4">
                    {/* Placeholder for future header actions */}
                </div>
            </header>

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
                        <h2 className="text-xl font-semibold mb-4 flex items-center">
                            <ArrowUpTrayIcon className="w-5 h-5 mr-2 text-emerald-400" /> Upload Audio
                        </h2>
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

                        <div className="flex-1 bg-[#0a0a0a] border border-gray-800 rounded-lg p-4 overflow-y-auto font-mono text-sm leading-relaxed text-gray-300">
                            {isGenerating ? (
                                <div className="flex flex-col items-center justify-center h-full text-gray-500">
                                    <div className="w-10 h-10 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
                                    Processing your audio through Faster-Whisper...
                                </div>
                            ) : transcript ? (
                                <div className="whitespace-pre-wrap">{transcript}</div>
                            ) : (
                                <div className="flex items-center justify-center h-full text-gray-600">
                                    Transcribed text will appear here.
                                </div>
                            )}
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}
