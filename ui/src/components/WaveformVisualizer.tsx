import { useState, useEffect } from 'react';

interface WaveformVisualizerProps {
    /** Color theme: emerald for ASR, blue for TTS, purple for Voxtral */
    color?: 'emerald' | 'blue' | 'purple';
    /** Number of bars */
    barCount?: number;
    /** Status messages to cycle through */
    statusMessages?: string[];
    /** Interval between status message changes (ms) */
    messageInterval?: number;
    /** Whether the visualizer is active */
    active?: boolean;
    /** Compact mode for inline usage */
    compact?: boolean;
}

const colorMap = {
    emerald: {
        bar: 'bg-emerald-400',
        barGlow: 'shadow-[0_0_6px_rgba(52,211,153,0.5)]',
        text: 'text-emerald-400',
        textSecondary: 'text-emerald-300/60',
    },
    blue: {
        bar: 'bg-blue-400',
        barGlow: 'shadow-[0_0_6px_rgba(96,165,250,0.5)]',
        text: 'text-blue-400',
        textSecondary: 'text-blue-300/60',
    },
    purple: {
        bar: 'bg-purple-400',
        barGlow: 'shadow-[0_0_6px_rgba(192,132,252,0.5)]',
        text: 'text-purple-400',
        textSecondary: 'text-purple-300/60',
    },
};

export default function WaveformVisualizer({
    color = 'emerald',
    barCount = 24,
    statusMessages = [
        'Initializing engine...',
        'Processing audio stream...',
        'Analyzing speech patterns...',
        'Decoding language model...',
    ],
    messageInterval = 3000,
    active = true,
    compact = false,
}: WaveformVisualizerProps) {
    const [messageIndex, setMessageIndex] = useState(0);

    useEffect(() => {
        if (!active || statusMessages.length <= 1) return;
        const timer = setInterval(() => {
            setMessageIndex(prev => (prev + 1) % statusMessages.length);
        }, messageInterval);
        return () => clearInterval(timer);
    }, [active, statusMessages.length, messageInterval]);

    const colors = colorMap[color];

    if (!active) return null;

    return (
        <div className={`flex flex-col items-center justify-center ${compact ? 'py-3' : 'py-8'}`}>
            {/* Waveform bars */}
            <div className={`flex items-center justify-center ${compact ? 'h-6' : 'h-10'}`}>
                {Array.from({ length: barCount }).map((_, i) => {
                    const delay = (i * 0.08) % 1.2;
                    return (
                        <div
                            key={i}
                            className={`wave-bar ${colors.bar} ${colors.barGlow} rounded-full`}
                            style={{
                                animationDelay: `${delay}s`,
                                height: compact ? '20px' : '36px',
                                width: compact ? '2px' : '3px',
                                margin: compact ? '0 1px' : '0 2px',
                                opacity: 0.4 + (Math.sin(i * 0.5) * 0.3 + 0.3),
                            }}
                        />
                    );
                })}
            </div>

            {/* Status message */}
            <div className={`mt-${compact ? '2' : '5'} text-center`}>
                <p className={`${compact ? 'text-xs' : 'text-sm'} ${colors.text} font-medium animate-fade-in-up`}
                    key={messageIndex}>
                    {statusMessages[messageIndex]}
                </p>
            </div>
        </div>
    );
}
