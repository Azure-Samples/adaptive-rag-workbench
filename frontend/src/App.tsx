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
import { ThemeToggle } from './components/ThemeToggle';
import { Card } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Brain, MessageSquare, Database, User } from 'lucide-react';
import { ThemeProvider } from './contexts/ThemeContext';
import { useTheme } from './contexts/ThemeContext';
import './App.css';

function Navigation() {
  const location = useLocation();
  const { theme } = useTheme();

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
    <nav className={`border-b shadow-lg transition-all duration-300 ${
      theme === 'dark'
        ? 'bg-gray-800 border-gray-700 shadow-gray-900/50'
        : theme === 'customer'
        ? 'bg-white border-primary/20 shadow-primary/10'
        : 'bg-white border-gray-200 shadow-gray-500/10'
    }`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top header with logo and actions */}
        <div className="flex justify-between items-center h-20">
          <div className="flex items-center space-x-4">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-lg overflow-hidden transition-all duration-300 ${
              theme === 'dark'
                ? 'bg-gray-700 shadow-gray-900/50'
                : theme === 'customer'
                ? 'bg-primary/10 shadow-primary/20'
                : 'bg-white shadow-gray-500/20'
            }`}>
              <img src="https://raw.githubusercontent.com/Azure-Samples/adaptive-rag-workbench/main/.github/assets/arag-logo.png" alt="ARAG" className="w-8 h-8" />
            </div>
            <div>
              <h1 className={`text-2xl font-bold transition-colors duration-300 ${
                theme === 'dark'
                  ? 'text-white'
                  : theme === 'customer'
                  ? 'text-primary'
                  : 'text-microsoft-gray'
              }`}>
                Adaptive RAG Workbench
              </h1>
              <Badge variant="secondary" className={`text-xs font-medium transition-all duration-300 ${
                theme === 'dark'
                  ? 'bg-gray-700/50 text-gray-200 border-gray-600/30'
                  : theme === 'customer'
                  ? 'bg-primary/10 text-primary border-primary/20'
                  : 'bg-microsoft-blue/10 text-microsoft-blue border-microsoft-blue/20'
              }`}>
                Solution Accelerator
              </Badge>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <ThemeToggle />
            <Link to="/profile" className={`p-2 rounded-lg transition-all duration-300 ${
              theme === 'dark'
                ? 'hover:bg-gray-700 text-gray-300 hover:text-white'
                : theme === 'customer'
                ? 'hover:bg-primary/10 text-primary hover:text-primary/90'
                : 'hover:bg-gray-100 text-gray-600 hover:text-gray-800'
            }`}>
              <User className="h-5 w-5" />
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
                      ? theme === 'dark'
                        ? 'border-gray-500 bg-gradient-to-br from-gray-500/10 to-gray-600/15 shadow-lg shadow-gray-500/25'
                        : theme === 'customer'
                        ? 'border-primary bg-gradient-to-br from-primary/10 to-primary/15 shadow-md shadow-primary/20'
                        : 'border-microsoft-blue bg-gradient-to-br from-microsoft-blue/5 to-microsoft-blue/10 shadow-md'
                      : theme === 'dark'
                      ? 'border-gray-600 bg-gray-700/50 hover:border-gray-500/60 hover:bg-gray-600/60'
                      : theme === 'customer'
                      ? 'border-primary/20 bg-white hover:border-primary/40 hover:bg-primary/5'
                      : 'border-gray-200 hover:border-microsoft-blue/40 hover:bg-gray-50/50'
                  }`}>
                    <div className="flex items-center space-x-3">
                      <div className={`p-2.5 rounded-lg transition-all duration-300 ${
                        active 
                          ? `bg-gradient-to-br ${item.color} text-white shadow-md` 
                          : theme === 'dark'
                          ? 'bg-gray-700 text-gray-300 group-hover:bg-gray-600/50 group-hover:text-gray-200'
                          : theme === 'customer'
                          ? 'bg-primary/10 text-primary group-hover:bg-primary/15 group-hover:text-primary/90'
                          : 'bg-gray-100 text-gray-600 group-hover:bg-microsoft-blue/10 group-hover:text-microsoft-blue'
                      }`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className={`font-semibold text-base mb-0.5 transition-colors ${
                          active 
                            ? theme === 'dark'
                              ? 'text-gray-300'
                              : theme === 'customer'
                              ? 'text-primary'
                              : 'text-microsoft-blue'
                            : theme === 'dark'
                            ? 'text-white group-hover:text-gray-300'
                            : theme === 'customer'
                            ? 'text-primary group-hover:text-primary/90'
                            : 'text-gray-900 group-hover:text-microsoft-blue'
                        }`}>
                          {item.label}
                        </h3>
                        <p className={`text-xs transition-colors ${
                          theme === 'dark'
                            ? 'text-gray-400 group-hover:text-gray-300'
                            : theme === 'customer'
                            ? 'text-primary group-hover:text-primary/90'
                            : 'text-gray-600 group-hover:text-gray-700'
                        }`}>
                          {item.description}
                        </p>
                      </div>
                      <div className={`transition-all duration-300 ${
                        active ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                      }`}>
                        <div className={`w-2 h-2 rounded-full ${
                          theme === 'dark'
                            ? 'bg-gray-400'
                            : theme === 'customer'
                            ? 'bg-primary'
                            : 'bg-microsoft-blue'
                        }`}></div>
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

function AppContent() {
  const { theme } = useTheme();
  
  return (
    <div className={`min-h-screen transition-colors duration-300 ${
      theme === 'dark'
        ? 'bg-gradient-to-br from-gray-900 to-gray-800'
        : theme === 'customer'
        ? 'bg-gradient-to-br from-primary/5 to-primary/10'
        : 'bg-gradient-to-br from-gray-50 to-primary/5'
    }`}>
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
  );
}

function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <AuthProvider>
        <ThemeProvider>
          <Router>
            <AppContent />
          </Router>
        </ThemeProvider>
      </AuthProvider>
    </MsalProvider>
  );
}

export default App;
