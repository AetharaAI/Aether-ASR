import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { SpeakerWaveIcon, PlayIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import ttsApi, { TtsVoice } from '../services/ttsApi';
import WaveformVisualizer from './WaveformVisualizer';

interface TtsPanelProps {
    initialText?: string;
}

export default function TtsPanel({ initialText = '' }: TtsPanelProps) {
    const [text, setText] = useState(initialText);
    const [voices, setVoices] = useState<TtsVoice[]>([]);
    const [selectedVoice, setSelectedVoice] = useState('');
    const [outputFormat, setOutputFormat] = useState<'wav' | 'mp3' | 'opus'>('wav');
    const [temperature, setTemperature] = useState(0.7);
    const [exaggeration, setExaggeration] = useState(0.5);
    const [speedFactor, setSpeedFactor] = useState(1.0);
    const [isGenerating, setIsGenerating] = useState(false);
    const [audioUrl, setAudioUrl] = useState<string | null>(null);
    const [showAdvanced, setShowAdvanced] = useState(false);

    useEffect(() => {
        ttsApi.getPredefinedVoices().then(v => {
            setVoices(v);
            if (v.length > 0) setSelectedVoice(v[0].filename);
        });
    }, []);

    useEffect(() => {
        if (initialText) setText(initialText);
    }, [initialText]);

    const handleGenerate = async () => {
        if (!text.trim()) {
            toast.error("Please enter text to synthesize.");
            return;
        }
        setIsGenerating(true);
        setAudioUrl(null);
        toast('Synthesizing speech...', { icon: '🎙️' });

        try {
            const blob = await ttsApi.generateTTS({
                text: text.trim(),
                voice_mode: 'predefined',
                predefined_voice_id: selectedVoice,
                output_format: outputFormat,
                temperature,
                exaggeration,
                speed_factor: speedFactor,
            });

            const url = URL.createObjectURL(blob);
            setAudioUrl(url);
            toast.success(`Voice ready • ${selectedVoice.replace('.wav', '')}`);
        } catch (error) {
            console.error(error);
            toast.error("TTS generation failed.");
        } finally {
            setIsGenerating(false);
        }
    };

    const handleDownload = () => {
        if (!audioUrl) return;
        const a = document.createElement('a');
        a.href = audioUrl;
        a.download = `tts_output.${outputFormat}`;
        a.click();
    };

    return (
        <div className="space-y-6">
            {/* Text Input */}
            <div className="bg-[#1e1e1e] rounded-xl p-6 border border-gray-800 shadow-lg">
                <h2 className="text-xl font-semibold mb-4 flex items-center">
                    <SpeakerWaveIcon className="w-5 h-5 mr-2 text-blue-400" /> Text to Speech
                </h2>

                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Enter text to synthesize into speech..."
                    rows={6}
                    className="w-full bg-[#0a0a0a] border border-gray-700 rounded-lg p-4 text-gray-200 text-sm font-mono resize-none focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder-gray-600"
                />

                <div className="mt-4 text-xs text-gray-500 text-right">
                    {text.length} characters
                </div>
            </div>

            {/* Voice & Settings */}
            <div className="bg-[#1e1e1e] rounded-xl p-6 border border-gray-800 shadow-lg">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-1">Voice</label>
                        <select
                            value={selectedVoice}
                            onChange={(e) => setSelectedVoice(e.target.value)}
                            className="w-full bg-[#2a2a2a] border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                            {voices.length > 0 ? (
                                voices.map(v => (
                                    <option key={v.filename} value={v.filename}>
                                        {v.name.replace('.wav', '')}
                                    </option>
                                ))
                            ) : (
                                <option value="">Loading voices...</option>
                            )}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-1">Output Format</label>
                        <select
                            value={outputFormat}
                            onChange={(e) => setOutputFormat(e.target.value as 'wav' | 'mp3' | 'opus')}
                            className="w-full bg-[#2a2a2a] border border-gray-700 rounded-md py-2 px-3 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                            <option value="wav">WAV (Highest Quality)</option>
                            <option value="mp3">MP3 (Compressed)</option>
                            <option value="opus">Opus (Efficient)</option>
                        </select>
                    </div>
                </div>

                {/* Advanced Settings Toggle */}
                <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="mt-4 text-sm text-gray-500 hover:text-gray-300 transition-colors"
                >
                    {showAdvanced ? '▼ Hide' : '▶ Show'} Advanced Settings
                </button>

                {showAdvanced && (
                    <div className="mt-4 space-y-4 pt-4 border-t border-gray-800">
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-1">
                                Temperature: {temperature.toFixed(2)}
                            </label>
                            <input
                                type="range" min="0" max="1.5" step="0.05"
                                value={temperature}
                                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                                className="w-full accent-blue-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-1">
                                Exaggeration: {exaggeration.toFixed(2)}
                            </label>
                            <input
                                type="range" min="0" max="2" step="0.05"
                                value={exaggeration}
                                onChange={(e) => setExaggeration(parseFloat(e.target.value))}
                                className="w-full accent-blue-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-400 mb-1">
                                Speed: {speedFactor.toFixed(2)}x
                            </label>
                            <input
                                type="range" min="0.5" max="2" step="0.05"
                                value={speedFactor}
                                onChange={(e) => setSpeedFactor(parseFloat(e.target.value))}
                                className="w-full accent-blue-500"
                            />
                        </div>
                    </div>
                )}

                {/* Waveform during synthesis */}
                {isGenerating && (
                    <div className="mt-6 p-4 bg-[#0a0a0a] border border-gray-800 rounded-lg">
                        <WaveformVisualizer
                            color="blue"
                            barCount={20}
                            statusMessages={[
                                `Generating ${selectedVoice.replace('.wav', '')}...`,
                                'Synthesizing speech patterns...',
                                'Encoding audio waveform...',
                            ]}
                        />
                    </div>
                )}

                {/* Generate Button */}
                <button
                    onClick={handleGenerate}
                    disabled={isGenerating || !text.trim()}
                    className={`w-full mt-6 py-3 rounded-lg font-bold flex items-center justify-center transition-all ${isGenerating || !text.trim()
                        ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                        : 'bg-blue-600 hover:bg-blue-500 text-white shadow-[0_0_15px_rgba(59,130,246,0.4)] hover:shadow-[0_0_25px_rgba(59,130,246,0.6)]'
                        }`}
                >
                    {isGenerating ? (
                        <><SpeakerWaveIcon className="w-5 h-5 mr-2 animate-pulse" /> Synthesizing...</>
                    ) : (
                        <><PlayIcon className="w-5 h-5 mr-2" /> Generate Speech</>
                    )}
                </button>
            </div>

            {/* Audio Player */}
            {audioUrl && (
                <div className="bg-[#1e1e1e] rounded-xl p-6 border border-gray-800 shadow-lg animate-fade-in-up">
                    <h3 className="text-lg font-semibold mb-4 flex items-center text-blue-400">
                        <SpeakerWaveIcon className="w-5 h-5 mr-2" /> Generated Audio
                    </h3>
                    <audio controls src={audioUrl} className="w-full mb-4" />
                    <button
                        onClick={handleDownload}
                        className="flex items-center text-sm text-gray-400 hover:text-white transition-colors"
                    >
                        <ArrowDownTrayIcon className="w-4 h-4 mr-1" /> Download {outputFormat.toUpperCase()}
                    </button>
                </div>
            )}
        </div>
    );
}
