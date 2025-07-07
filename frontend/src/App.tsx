import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { MsalProvider } from '@azure/msal-react';
import { msalInstance } from './auth/msalConfig';
import { AuthProvider } from './auth/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ContextAwareGeneration } from './pages/ContextAwareGeneration';
import { QAWithVerification } from './pages/QAWithVerification';
import { AdaptiveKBManagement } from './pages/AdaptiveKBManagement';
import { Profile } from './pages/Profile';
import { MicrosoftLogo } from './components/MicrosoftLogo';
import { GitHubLink } from './components/GitHubLink';
import { Card } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Brain, MessageSquare, Database, User } from 'lucide-react';
import './App.css';

function Navigation() {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path || (path === '/context-aware-generation' && location.pathname === '/');

  const navItems = [
    {
      path: '/context-aware-generation',
      label: 'Context-Aware Generation',
      icon: Brain,
      description: 'AI-powered content generation',
      color: 'from-blue-500 to-blue-600'
    },
    {
      path: '/qa-verification',
      label: 'QA with Verification',
      icon: MessageSquare,
      description: 'Multi-source verification',
      color: 'from-green-500 to-green-600'
    },
    {
      path: '/adaptive-kb-management',
      label: 'Adaptive KB Management',
      icon: Database,
      description: 'Knowledge base curation',
      color: 'from-purple-500 to-purple-600'
    }
  ];

  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top header with logo and actions */}
        <div className="flex justify-between items-center h-20">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center shadow-lg overflow-hidden">
              <img src="https://raw.githubusercontent.com/Azure-Samples/adaptive-rag-workbench/main/.github/assets/arag-logo.png" alt="ARAG" className="w-8 h-8" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-microsoft-gray">Adaptive RAG Workbench</h1>
              <Badge variant="secondary" className="bg-microsoft-blue/10 text-microsoft-blue text-xs font-medium">
                Solution Accelerator
              </Badge>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <Link to="/profile" className="p-2 rounded-lg hover:bg-gray-100 transition-colors">
              <User className="h-5 w-5 text-gray-600" />
            </Link>
            <GitHubLink />
            <MicrosoftLogo />
          </div>
        </div>
        
        {/* Navigation cards */}
        <div className="pb-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.path);
              
              return (
                <Link key={item.path} to={item.path} className="block">
                  <Card className={`p-4 transition-all duration-300 cursor-pointer border-2 group hover:shadow-lg hover:-translate-y-0.5 ${
                    active 
                      ? 'border-microsoft-blue bg-gradient-to-br from-microsoft-blue/5 to-microsoft-blue/10 shadow-md' 
                      : 'border-gray-200 hover:border-microsoft-blue/40 hover:bg-gray-50/50'
                  }`}>
                    <div className="flex items-center space-x-3">
                      <div className={`p-2.5 rounded-lg transition-all duration-300 ${
                        active 
                          ? `bg-gradient-to-br ${item.color} text-white shadow-md` 
                          : 'bg-gray-100 text-gray-600 group-hover:bg-microsoft-blue/10 group-hover:text-microsoft-blue'
                      }`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className={`font-semibold text-base mb-0.5 transition-colors ${
                          active ? 'text-microsoft-blue' : 'text-gray-900 group-hover:text-microsoft-blue'
                        }`}>
                          {item.label}
                        </h3>
                        <p className="text-xs text-gray-600">
                          {item.description}
                        </p>
                      </div>
                      <div className={`transition-all duration-300 ${
                        active ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                      }`}>
                        <div className="w-2 h-2 bg-microsoft-blue rounded-full"></div>
                      </div>
                    </div>
                  </Card>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}

function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <AuthProvider>
        <Router>
          <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
            <ProtectedRoute>
              <Navigation />
              <Routes>
                <Route path="/redirect" element={<Profile />} />
                <Route path="/context-aware-generation" element={<ContextAwareGeneration />} />
                <Route path="/qa-verification" element={<QAWithVerification />} />
                <Route path="/adaptive-kb-management" element={<AdaptiveKBManagement />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/" element={<ContextAwareGeneration />} />
              </Routes>
            </ProtectedRoute>
          </div>
        </Router>
      </AuthProvider>
    </MsalProvider>
  );
}

export default App;
