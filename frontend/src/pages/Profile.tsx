import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarFallback } from '../components/ui/avatar';
import { LogOut, ArrowLeft, Play } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { Link } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';

export function Profile() {
  const { user, logout, isDemoMode } = useAuth();
  const { theme } = useTheme();

  if (!user) {
    return <div>Loading...</div>;
  }

  return (
    <div className={`min-h-screen p-4 ${
      theme === 'dark' 
        ? 'bg-gradient-to-br from-gray-900 to-gray-800' 
        : theme === 'customer' 
          ? 'bg-gradient-to-br from-customer-50 to-customer-100' 
          : 'bg-gradient-to-br from-gray-50 to-primary/5'
    }`}>
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <Link to="/" className={`inline-flex items-center hover:opacity-80 ${
            theme === 'dark' 
              ? 'text-gray-300' 
              : theme === 'customer' 
                ? 'text-customer-600' 
                : 'text-primary'
          }`}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Workbench
          </Link>
        </div>
        <Card className={`p-8 backdrop-blur-sm border shadow-lg ${
          theme === 'dark' 
            ? 'bg-gray-800/90 border-gray-700' 
            : theme === 'customer' 
              ? 'bg-customer-50/90 border-customer-200' 
              : 'bg-white/80 border-gray-200'
        }`}>
          <div className="flex items-center space-x-4 mb-6">
            <Avatar className="h-16 w-16">
               <AvatarFallback className={`text-white text-lg ${isDemoMode ? 'bg-orange-600' : 
                 theme === 'dark' 
                   ? 'bg-gray-600' 
                   : theme === 'customer' 
                     ? 'bg-customer-600' 
                     : 'bg-primary'
               }`}>
                {isDemoMode ? <Play className="h-6 w-6" /> : (String(user.name || user.username || 'U').charAt(0))}
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className={`text-2xl font-bold ${
                theme === 'dark' 
                  ? 'text-white' 
                  : theme === 'customer' 
                    ? 'text-customer-900' 
                    : 'text-gray-800'
              }`}>
                {String(user.name || 'User')}
              </h1>
              <p className={`${
                theme === 'dark' 
                  ? 'text-gray-300' 
                  : theme === 'customer' 
                    ? 'text-customer-700' 
                    : 'text-gray-600'
              }`}>{String(user.username || '')}</p>
              {isDemoMode ? (
                <Badge className="bg-orange-600 text-white mt-1">
                  <Play className="h-3 w-3 mr-1" />
                  Demo User
                </Badge>
              ) : (
                <Badge className="bg-green-600 text-white mt-1">
                  Microsoft Employee
                </Badge>
              )}
            </div>
          </div>
          
          <div className="space-y-4 mb-6">
            <div>
              <label className={`text-sm font-medium ${
                theme === 'dark' 
                  ? 'text-gray-300' 
                  : theme === 'customer' 
                    ? 'text-customer-700' 
                    : 'text-gray-700'
              }`}>Email</label>
              <p className={`${
                theme === 'dark' 
                  ? 'text-white' 
                  : theme === 'customer' 
                    ? 'text-customer-900' 
                    : 'text-gray-900'
              }`}>{String(user.username || '')}</p>
            </div>
            <div>
              <label className={`text-sm font-medium ${
                theme === 'dark' 
                  ? 'text-gray-300' 
                  : theme === 'customer' 
                    ? 'text-customer-700' 
                    : 'text-gray-700'
              }`}>Account Type</label>
              <p className={`${
                theme === 'dark' 
                  ? 'text-white' 
                  : theme === 'customer' 
                    ? 'text-customer-900' 
                    : 'text-gray-900'
              }`}>{isDemoMode ? 'Demo Account' : 'Microsoft Work Account'}</p>
            </div>
            {isDemoMode && (
              <div>
                <label className={`text-sm font-medium ${
                  theme === 'dark' 
                    ? 'text-gray-300' 
                    : theme === 'customer' 
                      ? 'text-customer-700' 
                      : 'text-gray-700'
                }`}>Demo Mode</label>
                <p className={`text-sm ${
                  theme === 'dark' 
                    ? 'text-gray-300' 
                    : theme === 'customer' 
                      ? 'text-customer-700' 
                      : 'text-gray-900'
                }`}>
                  You are using the demo version of the Adaptive RAG Workbench. 
                  This mode bypasses Microsoft authentication for demonstration purposes.
                </p>
              </div>
            )}
          </div>

          <Button
            onClick={logout}
            variant="outline"
            className={`w-full ${
              theme === 'dark' 
                ? 'border-red-400 text-red-400 hover:bg-red-900/20' 
                : theme === 'customer' 
                  ? 'border-red-300 text-red-600 hover:bg-red-50' 
                  : 'border-red-300 text-red-600 hover:bg-red-50'
            }`}
          >
            <LogOut className="h-4 w-4 mr-2" />
            {isDemoMode ? 'Exit Demo Mode' : 'Sign Out'}
          </Button>
        </Card>
      </div>
    </div>
  );
}
