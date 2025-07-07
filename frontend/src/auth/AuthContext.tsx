import React, { createContext, useContext, ReactNode, useState } from 'react';
import { useMsal, useAccount } from '@azure/msal-react';

interface AuthContextType {
  isAuthenticated: boolean;
  user: DemoUser | Record<string, unknown> | null;
  login: () => void;
  logout: () => void;
  getAccessToken: () => Promise<string | null>;
  // Demo mode functions
  loginDemo: () => void;
  isDemoMode: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface DemoUser {
  username: string;
  name: string;
  localAccountId: string;
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { instance, accounts } = useMsal();
  const account = useAccount(accounts[0] || {});
  const [demoUser, setDemoUser] = useState<DemoUser | null>(null);

  const login = () => {
    instance.loginRedirect({
      scopes: [],
    });
  };

  const logout = () => {
    if (demoUser) {
      setDemoUser(null);
    } else {
      instance.logoutRedirect();
    }
  };

  const loginDemo = () => {
    setDemoUser({
      username: 'demo@demo.com',
      name: 'Demo User',
      localAccountId: 'demo-user-id'
    });
  };

  const getAccessToken = async (): Promise<string | null> => {
    if (demoUser) {
      // Return a demo token for demo mode
      console.log('Using demo token');
      return 'demo-token';
    }
    
    try {
      console.log('Attempting to acquire token with scope:', import.meta.env.VITE_API_SCOPE);
      console.log('Account:', accounts[0]);
      
      const response = await instance.acquireTokenSilent({
        scopes: [import.meta.env.VITE_API_SCOPE],
        account: accounts[0]
      });
      console.log('Token acquired successfully');
      return response.accessToken;
    } catch (error) {
      console.error('Failed to acquire token:', error);
      console.log('Environment variables:', {
        VITE_API_SCOPE: import.meta.env.VITE_API_SCOPE,
        VITE_AAD_CLIENT_ID: import.meta.env.VITE_AAD_CLIENT_ID,
        VITE_AAD_TENANT_ID: import.meta.env.VITE_AAD_TENANT_ID
      });
      return null;
    }
  };

  const validateDomain = (email: string) => {
    return email.endsWith('@microsoft.com');
  };

  // Determine the current user
  let currentUser = null;
  if (demoUser) {
    currentUser = demoUser;
  } else if (account && validateDomain(account.username)) {
    currentUser = account;
  }

  return (
    <AuthContext.Provider value={{ 
      isAuthenticated: !!currentUser, 
      user: currentUser, 
      login, 
      logout, 
      getAccessToken,
      loginDemo,
      isDemoMode: !!demoUser
    }}>
      {children}
    </AuthContext.Provider>
  );
};
