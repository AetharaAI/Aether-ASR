import React from 'react';
import { AuthProvider as OidcProvider, AuthProviderProps } from 'react-oidc-context';
import { WebStorageStateStore } from 'oidc-client-ts';

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

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    return (
        <OidcProvider {...oidcConfig}>
            {children}
        </OidcProvider>
    );
};
