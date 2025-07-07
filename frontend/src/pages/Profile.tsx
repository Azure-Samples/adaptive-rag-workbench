import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarFallback } from '../components/ui/avatar';
import { LogOut, ArrowLeft, Play } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { Link } from 'react-router-dom';

export function Profile() {
  const { user, logout, isDemoMode } = useAuth();

  if (!user) {
    return <div>Loading...</div>;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <Link to="/" className="inline-flex items-center text-blue-600 hover:text-blue-700">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Workbench
          </Link>
        </div>
        <Card className="p-8 bg-white/80 backdrop-blur-sm border-gray-200 shadow-lg">
          <div className="flex items-center space-x-4 mb-6">
            <Avatar className="h-16 w-16">
               <AvatarFallback className={`text-white text-lg ${isDemoMode ? 'bg-orange-600' : 'bg-blue-600'}`}>
                {isDemoMode ? <Play className="h-6 w-6" /> : (String(user.name || user.username || 'U').charAt(0))}
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="text-2xl font-bold text-gray-800">
                {String(user.name || 'User')}
              </h1>
              <p className="text-gray-600">{String(user.username || '')}</p>
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
              <label className="text-sm font-medium text-gray-700">Email</label>
              <p className="text-gray-900">{String(user.username || '')}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Account Type</label>
              <p className="text-gray-900">{isDemoMode ? 'Demo Account' : 'Microsoft Work Account'}</p>
            </div>
            {isDemoMode && (
              <div>
                <label className="text-sm font-medium text-gray-700">Demo Mode</label>
                <p className="text-gray-900 text-sm">
                  You are using the demo version of the Adaptive RAG Workbench. 
                  This mode bypasses Microsoft authentication for demonstration purposes.
                </p>
              </div>
            )}
          </div>

          <Button
            onClick={logout}
            variant="outline"
            className="w-full border-red-300 text-red-600 hover:bg-red-50"
          >
            <LogOut className="h-4 w-4 mr-2" />
            {isDemoMode ? 'Exit Demo Mode' : 'Sign Out'}
          </Button>
        </Card>
      </div>
    </div>
  );
}
