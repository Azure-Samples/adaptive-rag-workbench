import { ReactNode } from 'react';
import { Card } from './ui/card';
import { useTheme } from '../contexts/ThemeContext';

interface ChatLayoutProps {
  children: ReactNode;
}

export function ChatLayout({ children }: ChatLayoutProps) {
  const { theme } = useTheme();

  return (
    <div className={`flex flex-col min-h-screen transition-colors duration-300 ${
      theme === 'dark'
        ? 'bg-gray-900'
        : theme === 'customer'
        ? 'bg-gradient-to-br from-primary/5 to-primary/10'
        : 'bg-gray-50'
    }`}>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 flex flex-col max-w-7xl mx-auto w-full px-6 py-6">
          <Card className={`flex-1 flex flex-col h-full transition-all duration-300 ${
            theme === 'dark'
              ? 'bg-gray-800/95 backdrop-blur-md border-gray-700/50 shadow-2xl shadow-gray-900/50'
              : theme === 'customer'
              ? 'bg-white/95 backdrop-blur-md border-primary/20 shadow-xl shadow-primary/10'
              : 'bg-white/95 backdrop-blur-md border-gray-200/50 shadow-lg'
          }`}>
            {children}
          </Card>
        </div>
      </div>
    </div>
  );
}
