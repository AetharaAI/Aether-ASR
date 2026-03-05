import {
    CpuChipIcon,
    DocumentTextIcon,
    SpeakerWaveIcon,
    MusicalNoteIcon,
    CheckCircleIcon,
} from '@heroicons/react/24/outline';

type StageStatus = 'idle' | 'active' | 'done';

interface PipelineFlowProps {
    hasTranscript: boolean;
    hasAudio: boolean;
    isTranscribing: boolean;
    isSynthesizing: boolean;
    onGoToASR: () => void;
    onGoToTTS: () => void;
}

interface StageProps {
    icon: React.ElementType;
    label: string;
    sublabel: string;
    status: StageStatus;
}

function Stage({ icon: Icon, label, sublabel, status }: StageProps) {
    const styles = {
        idle: {
            ring: 'border-gray-700 bg-gray-800/50',
            icon: 'text-gray-600',
            label: 'text-gray-500',
            sub: 'text-gray-600',
        },
        active: {
            ring: 'border-emerald-500/50 bg-emerald-900/30 stage-active',
            icon: 'text-emerald-400',
            label: 'text-emerald-400',
            sub: 'text-emerald-300/60',
        },
        done: {
            ring: 'border-emerald-600/40 bg-emerald-900/20',
            icon: 'text-emerald-500',
            label: 'text-emerald-300',
            sub: 'text-emerald-400/50',
        },
    }[status];

    return (
        <div className="flex items-center space-x-4">
            <div className={`relative w-12 h-12 rounded-full border-2 flex items-center justify-center transition-all duration-500 ${styles.ring}`}>
                {status === 'done' ? (
                    <CheckCircleIcon className="w-6 h-6 text-emerald-400" />
                ) : (
                    <Icon className={`w-6 h-6 ${styles.icon} transition-colors duration-500`} />
                )}
            </div>
            <div>
                <p className={`text-sm font-bold tracking-wide uppercase ${styles.label} transition-colors duration-500`}>
                    {label}
                </p>
                <p className={`text-xs ${styles.sub} transition-colors duration-500`}>
                    {sublabel}
                </p>
            </div>
        </div>
    );
}

function FlowConnector({ active }: { active: boolean }) {
    return (
        <div className="flex flex-col items-center ml-6 h-10 relative">
            {/* Static line */}
            <div className={`w-0.5 h-full ${active ? 'bg-emerald-600/40' : 'bg-gray-700/50'} transition-colors duration-500`} />

            {/* Animated data dots */}
            {active && (
                <>
                    <div className="absolute w-1.5 h-1.5 rounded-full bg-emerald-400 data-dot" style={{ animationDelay: '0s' }} />
                    <div className="absolute w-1 h-1 rounded-full bg-emerald-400/60 data-dot" style={{ animationDelay: '0.5s' }} />
                    <div className="absolute w-1.5 h-1.5 rounded-full bg-emerald-400 data-dot" style={{ animationDelay: '1s' }} />
                </>
            )}
        </div>
    );
}

export default function PipelineFlow({
    hasTranscript,
    hasAudio,
    isTranscribing,
    isSynthesizing,
    onGoToASR,
    onGoToTTS,
}: PipelineFlowProps) {
    // Determine stage statuses
    const inputStatus: StageStatus = hasTranscript || isTranscribing ? 'done' : 'idle';
    const asrStatus: StageStatus = isTranscribing ? 'active' : hasTranscript ? 'done' : 'idle';
    const textStatus: StageStatus = hasTranscript ? (isSynthesizing ? 'done' : 'done') : isTranscribing ? 'active' : 'idle';
    const ttsStatus: StageStatus = isSynthesizing ? 'active' : hasAudio ? 'done' : 'idle';
    const outputStatus: StageStatus = hasAudio ? 'done' : isSynthesizing ? 'active' : 'idle';

    return (
        <div className="bg-[#1e1e1e] rounded-xl p-8 border border-gray-800 shadow-lg">
            <div className="text-center mb-8">
                <h2 className="text-2xl font-bold mb-2">
                    Audio <span className="text-purple-400">Pipeline</span>
                </h2>
                <p className="text-sm text-gray-500">AI Audio Factory — from raw audio to synthesized voice</p>
            </div>

            <div className="max-w-sm mx-auto space-y-0">
                <Stage icon={MusicalNoteIcon} label="Input Audio" sublabel="Upload or record" status={inputStatus} />
                <FlowConnector active={isTranscribing || hasTranscript} />

                <Stage icon={CpuChipIcon} label="ASR Engine" sublabel="Faster-Whisper large-v3" status={asrStatus} />
                <FlowConnector active={hasTranscript} />

                <Stage icon={DocumentTextIcon} label="Text Processor" sublabel="Edit & refine transcript" status={textStatus} />
                <FlowConnector active={isSynthesizing || hasAudio} />

                <Stage icon={SpeakerWaveIcon} label="Voice Synthesizer" sublabel="Chatterbox TTS" status={ttsStatus} />
                <FlowConnector active={hasAudio} />

                <Stage icon={MusicalNoteIcon} label="Output Audio" sublabel="Download or play" status={outputStatus} />
            </div>

            {/* Action buttons */}
            <div className="mt-8 flex justify-center space-x-4">
                {!hasTranscript ? (
                    <button
                        onClick={onGoToASR}
                        className="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-2.5 rounded-lg font-medium transition-all shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_25px_rgba(16,185,129,0.5)]"
                    >
                        Start with Transcription
                    </button>
                ) : (
                    <button
                        onClick={onGoToTTS}
                        className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg font-medium transition-all shadow-[0_0_15px_rgba(59,130,246,0.3)] hover:shadow-[0_0_25px_rgba(59,130,246,0.5)]"
                    >
                        Continue to Synthesize →
                    </button>
                )}
            </div>
        </div>
    );
}
