import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Shield, LogIn, Play } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { MicrosoftLogo } from '../components/MicrosoftLogo';
import { useTheme } from '../contexts/ThemeContext';

export function Login() {
  const { login, loginDemo } = useAuth();
  const { theme } = useTheme();

  return (
    <div className={`min-h-screen flex items-center justify-center p-4 ${
      theme === 'dark' 
        ? 'bg-gradient-to-br from-gray-900 to-gray-800' 
        : theme === 'customer' 
          ? 'bg-gradient-to-br from-customer-50 to-customer-100' 
          : 'bg-gradient-to-br from-gray-50 to-primary/5'
    }`}>
      <Card className={`p-8 max-w-md mx-auto text-center backdrop-blur-sm border shadow-lg ${
        theme === 'dark' 
          ? 'bg-gray-800/90 border-gray-700' 
          : theme === 'customer' 
            ? 'bg-customer-50/90 border-customer-200' 
            : 'bg-white/80 border-gray-200'
      }`}>
        <div className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 ${
          theme === 'dark' 
            ? 'bg-gray-600' 
            : theme === 'customer' 
              ? 'bg-customer-600' 
              : 'bg-primary'
        }`}>
          <Shield className="h-8 w-8 text-white" />
        </div>
        <h1 className={`text-2xl font-bold mb-2 ${
          theme === 'dark' 
            ? 'text-white' 
            : theme === 'customer' 
              ? 'text-customer-900' 
              : 'text-gray-800'
        }`}>
          Adaptive RAG Workbench
        </h1>
        <Badge variant="secondary" className={`text-xs font-medium mb-6 ${
          theme === 'dark' 
            ? 'bg-gray-700 text-gray-200' 
            : theme === 'customer' 
              ? 'bg-customer-100 text-customer-600' 
              : 'bg-primary/10 text-primary'
        }`}>
          Solution Accelerator
        </Badge>
        <p className={`mb-6 ${
          theme === 'dark' 
            ? 'text-gray-300' 
            : theme === 'customer' 
              ? 'text-customer-700' 
              : 'text-gray-600'
        }`}>
          Sign in with your Microsoft account to access the workbench. Only @microsoft.com accounts are allowed.
        </p>
        <Button
          onClick={login}
          className={`w-full text-white py-3 mb-4 ${
            theme === 'dark' 
              ? 'bg-gray-600 hover:bg-gray-700' 
              : theme === 'customer' 
                ? 'bg-customer-600 hover:bg-customer-700' 
                : 'bg-primary hover:bg-primary/90'
          }`}
        >
          <LogIn className="h-4 w-4 mr-2" />
          Sign in with Microsoft
        </Button>
        
        {/* Demo bypass option */}
        <div className="border-t border-gray-200 pt-4 mt-4">
          <p className="text-xs text-gray-500 mb-3">
            For demo purposes only
          </p>
          <button
            onClick={loginDemo}
            className="text-sm text-primary hover:text-primary/90 underline decoration-dotted flex items-center justify-center gap-1 mx-auto transition-colors"
          >
            <Play className="h-3 w-3" />
            Continue as Demo User
          </button>
        </div>
        
        <div className="flex items-center justify-center mt-6">
          <MicrosoftLogo />
        </div>
      </Card>
    </div>
  );
}
