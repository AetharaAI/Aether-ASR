import { useAuth } from 'react-oidc-context';
import { ShieldCheckIcon, MicrophoneIcon, SpeakerWaveIcon, BuildingOffice2Icon } from '@heroicons/react/24/outline';

export default function LogoutPage() {
    const auth = useAuth();

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white flex flex-col items-center justify-center p-6 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-900/20 via-[#0a0a0a] to-[#0a0a0a]">

            <div className="max-w-3xl w-full flex flex-col items-center text-center mb-16">
                <img
                    src="/Aether-Shield-Perceptor-Merged.png"
                    alt="Aether Logo"
                    className="h-24 w-auto mb-8 drop-shadow-[0_0_15px_rgba(16,185,129,0.3)] animate-pulse"
                />
                <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4 text-white">
                    You're now part of the <span className="text-emerald-400">Aether Ecosystem</span>
                </h1>
                <p className="text-xl text-gray-400 max-w-2xl leading-relaxed">
                    You have securely signed out of the Audio Studio. Aether provides a continuous, intelligent layer across all your operational needs.
                </p>

                <div className="mt-10">
                    <button
                        onClick={() => auth.signinRedirect()}
                        className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 px-8 rounded-full shadow-[0_0_20px_rgba(16,185,129,0.4)] transition-all flex items-center"
                    >
                        Sign In Again
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-5xl">

                {/* Audio Studio Card */}
                <div className="bg-[#161616] border border-gray-800 rounded-2xl p-6 hover:border-emerald-500/50 transition-colors cursor-default group relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl group-hover:bg-emerald-500/10 transition-colors"></div>
                    <MicrophoneIcon className="w-10 h-10 text-emerald-400 mb-4" />
                    <h3 className="text-xl font-bold text-white mb-2">Aether ASR Studio</h3>
                    <p className="text-gray-400 text-sm leading-relaxed">
                        Industry-leading automatic speech recognition. Transcribe hours of audio into timestamped, diarized intelligence instantly.
                    </p>
                </div>

                {/* TTS Card */}
                <div className="bg-[#161616] border border-gray-800 rounded-2xl p-6 hover:border-blue-500/50 transition-colors cursor-default group relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl group-hover:bg-blue-500/10 transition-colors"></div>
                    <SpeakerWaveIcon className="w-10 h-10 text-blue-400 mb-4" />
                    <h3 className="text-xl font-bold text-white mb-2">Chatterbox TTS</h3>
                    <p className="text-gray-400 text-sm leading-relaxed">
                        Hyper-realistic, real-time voice synthesis and instant voice cloning. Give your digital agents a voice modeled exactly to your brand.
                    </p>
                </div>

                {/* SAP Card */}
                <div className="bg-[#161616] border border-gray-800 rounded-2xl p-6 hover:border-purple-500/50 transition-colors cursor-default group relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/5 rounded-full blur-3xl group-hover:bg-purple-500/10 transition-colors"></div>
                    <BuildingOffice2Icon className="w-10 h-10 text-purple-400 mb-4" />
                    <h3 className="text-xl font-bold text-white mb-2">Sentinel Perceptor</h3>
                    <p className="text-gray-400 text-sm leading-relaxed">
                        Comprehensive physical security event ingestion. Map your entire domain with continuous real-time multi-camera awareness processing.
                    </p>
                </div>

            </div>

            <footer className="mt-16 text-center text-sm text-gray-600 flex items-center">
                <ShieldCheckIcon className="w-4 h-4 mr-1 text-emerald-500/50" />
                Secured by Passport-IAM
            </footer>

        </div>
    );
}
