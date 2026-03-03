import React, { useEffect } from 'react';
import { AuthProvider as OidcProvider, useAuth, AuthProviderProps } from 'react-oidc-context';
import { WebStorageStateStore } from 'oidc-client-ts';
import toast from 'react-hot-toast';

const oidcConfig: AuthProviderProps = {
    authority: 'https://passport.aetherpro.us/realms/aetherpro',
    client_id: 'aether-asr',
    redirect_uri: window.location.origin + '/',
    response_type: 'code',
    scope: 'openid profile email',
    userStore: new WebStorageStateStore({ store: window.localStorage }),
    onSigninCallback: (_user: any) => {
        window.history.replaceState(
            {},
            document.title,
            window.location.pathname
        );
    },
};

const AuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const auth = useAuth();

    useEffect(() => {
        if (auth.error) {
            console.error("Auth Error:", auth.error);
            toast.error(`Authentication error: ${auth.error.message}`);
        }
    }, [auth.error]);

    if (auth.isLoading) {
        return (
            <div className="flex h-screen w-screen items-center justify-center bg-[#121212] flex-col">
                <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
                <div className="text-gray-400 font-mono text-sm animate-pulse">Initializing Identity Session...</div>
            </div>
        );
    }

    if (!auth.isAuthenticated) {
        return (
            <div className="flex h-screen w-screen items-center justify-center bg-[#121212] overflow-hidden relative">
                <div className="absolute inset-0 bg-[#0a0a0a] z-0 opacity-50 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-emerald-900/20 via-transparent to-transparent"></div>
                <div className="z-10 bg-[#1e1e1e] p-8 md:p-12 rounded-2xl border border-gray-800 shadow-2xl max-w-md w-full flex flex-col items-center">
                    <img src="/Aether-Shield-Perceptor-Merged.png" className="w-24 h-24 mb-6 drop-shadow-[0_0_15px_rgba(16,185,129,0.2)]" alt="Logo" />
                    <h1 className="text-2xl font-bold text-white mb-2 tracking-tight">Access Restricted</h1>
                    <p className="text-gray-400 text-center text-sm mb-8 leading-relaxed">
                        The Aether Audio Stack is secured via Passport-IAM. Please sign in to verify your <span className="text-emerald-400 font-mono bg-emerald-900/30 px-1 rounded">pro_audio</span> entitlement.
                    </p>
                    <button
                        onClick={() => auth.signinRedirect()}
                        className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 px-6 rounded-lg shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-all flex justify-center items-center"
                    >
                        Sign in with Passport
                    </button>
                </div>
            </div>
        );
    }

    // Pass the token setup to child components or let generic API interceptors handle it
    return <>{children}</>;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    return (
        <OidcProvider {...oidcConfig}>
            <AuthGate>{children}</AuthGate>
        </OidcProvider>
    );
};
