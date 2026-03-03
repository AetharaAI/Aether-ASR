import { useEffect, useState } from 'react';
import { useAuth } from 'react-oidc-context';
import { ArrowRightOnRectangleIcon, UserCircleIcon, ShieldCheckIcon } from '@heroicons/react/24/outline';
import api from '../services/api';

interface WhoamiResponse {
    authenticated: boolean;
    sub: string | null;
    roles: string[];
    tier: string;
    remaining_quota: number;
}

export default function Header() {
    const auth = useAuth();
    const [account, setAccount] = useState<WhoamiResponse | null>(null);

    useEffect(() => {
        api.get('/api/whoami').then(res => {
            setAccount(res.data);
        }).catch(err => {
            console.error("Failed to fetch account info", err);
        });
    }, [auth.isAuthenticated]);

    const handleLogout = () => {
        // Clear tokens
        auth.removeUser().then(() => {
            // Send user to our custom logout landing page cleanly
            // Sometimes signoutRedirect uses the OIDC OP to end session
            auth.signoutRedirect({ post_logout_redirect_uri: window.location.origin + '/logout' }).catch(() => {
                window.location.href = '/logout';
            });
        });
    };

    const handleLogin = () => {
        auth.signinRedirect();
    };

    return (
        <header className="flex flex-col md:flex-row justify-between items-center mb-8 border-b border-gray-800 pb-4">
            <div className="flex items-center space-x-4 mb-4 md:mb-0">
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

            <div className="flex items-center space-x-4">
                {account ? (
                    <div className="flex items-center space-x-4 bg-[#1e1e1e] border border-gray-800 px-4 py-2 rounded-lg">
                        <div className="flex flex-col items-end">
                            {auth.isAuthenticated ? (
                                <>
                                    <span className="text-sm font-semibold text-gray-200 flex items-center">
                                        {account.tier === "PRO" && <ShieldCheckIcon className="w-4 h-4 text-emerald-400 mr-1" />}
                                        {auth.user?.profile?.preferred_username || auth.user?.profile?.email || 'Aether Member'}
                                    </span>
                                    <span className="text-xs text-gray-400">
                                        Tier: <span className={account.tier === 'PRO' ? 'text-emerald-400 font-medium' : 'text-gray-300'}>{account.tier}</span>
                                        {account.tier !== "PRO" && ` | Quotes left: ${account.remaining_quota}`}
                                    </span>
                                </>
                            ) : (
                                <>
                                    <span className="text-sm font-semibold text-gray-300">Guest User</span>
                                    <span className="text-xs text-red-400">
                                        {account.remaining_quota} Free Uses Remaining
                                    </span>
                                </>
                            )}
                        </div>

                        <div className="w-px h-8 bg-gray-700 mx-2"></div>

                        {auth.isAuthenticated ? (
                            <button
                                onClick={handleLogout}
                                className="text-sm text-gray-400 hover:text-white transition-colors flex items-center"
                            >
                                <ArrowRightOnRectangleIcon className="w-5 h-5 mr-1" />
                                Logout
                            </button>
                        ) : (
                            <button
                                onClick={handleLogin}
                                className="text-sm bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-md transition-colors font-medium flex items-center shadow-[0_0_10px_rgba(16,185,129,0.2)]"
                            >
                                <UserCircleIcon className="w-5 h-5 mr-1" />
                                Sign In / Sign Up
                            </button>
                        )}
                    </div>
                ) : (
                    <div className="w-48 h-12 bg-[#1e1e1e] rounded animate-pulse"></div>
                )}
            </div>
        </header>
    );
}
