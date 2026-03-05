export default function Header() {
    return (
        <header className="flex flex-col md:flex-row justify-between items-center mb-8 border-b border-gray-800 pb-4">
            <div className="flex items-center space-x-4">
                <img
                    src="/Aether-Shield-Perceptor-Merged.png"
                    alt="Aether-ASR Logo"
                    className="h-16 w-auto object-contain drop-shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                />
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white mb-1">
                        Aether <span className="text-emerald-400">Audio Studio</span>
                    </h1>
                    <p className="text-sm text-gray-400 font-medium">All Your Audio needs in One Place.</p>
                </div>
            </div>
        </header>
    );
}
