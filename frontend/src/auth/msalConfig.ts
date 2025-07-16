import { PublicClientApplication } from "@azure/msal-browser";

declare global {
  interface ImportMetaEnv {
    readonly VITE_AAD_CLIENT_ID?: string;
    readonly VITE_AAD_TENANT_ID?: string;
    readonly VITE_AAD_USER_FLOW?: string;
    readonly VITE_AAD_AUTHORITY?: string;
    readonly VITE_AAD_REDIRECT_URI?: string;
    readonly VITE_API_SCOPE?: string;
    readonly VITE_API_BASE?: string;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

export const msal = new PublicClientApplication({
  auth: {
    clientId: import.meta.env.VITE_AAD_CLIENT_ID || 'dummy-client-id',
    authority: import.meta.env.VITE_AAD_AUTHORITY || 'https://login.microsoftonline.com/common',
    redirectUri: import.meta.env.VITE_AAD_REDIRECT_URI || window.location.origin,
    knownAuthorities: import.meta.env.VITE_AAD_AUTHORITY ? [new URL(import.meta.env.VITE_AAD_AUTHORITY).host] : ['login.microsoftonline.com']
  },
  cache: { cacheLocation: "sessionStorage" }
});

export const msalInstance = msal;
