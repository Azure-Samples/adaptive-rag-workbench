import { Sun, Moon, Palette } from 'lucide-react';
import { Button } from './ui/button';
import { useTheme } from '../contexts/ThemeContext';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const getThemeIcon = () => {
    switch (theme) {
      case 'dark':
        return <Moon className="h-4 w-4" />;
      case 'customer':
        return <Palette className="h-4 w-4" />;
      default:
        return <Sun className="h-4 w-4" />;
    }
  };

  const getThemeLabel = () => {
    switch (theme) {
      case 'dark':
        return 'Dark';
      case 'customer':
        return 'Customer';
      default:
        return 'Light';
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="outline" 
          size="sm" 
          className={`gap-2 transition-all duration-300 ${
            theme === 'dark'
              ? 'bg-gray-700 border-gray-600 text-white hover:bg-gray-600 hover:border-gray-500 shadow-lg shadow-gray-900/25'
              : theme === 'customer'
              ? 'bg-primary/5 border-primary/20 text-primary hover:bg-primary/10 hover:border-primary/30 shadow-md shadow-primary/10'
              : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50 hover:border-gray-400 shadow-md'
          }`}
        >
          {getThemeIcon()}
          <span className="hidden sm:inline font-medium">{getThemeLabel()}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent 
        align="end" 
        className={`transition-all duration-300 ${
          theme === 'dark'
            ? 'bg-gray-800 border-gray-700 shadow-2xl shadow-gray-900/50'
            : theme === 'customer'
            ? 'bg-white border-primary/20 shadow-xl shadow-primary/10'
            : 'bg-white border-gray-200 shadow-lg'
        }`}
      >
        <DropdownMenuItem 
          onClick={() => setTheme('light')}
          className={`transition-all duration-200 ${
            theme === 'light'
              ? 'bg-gray-100 text-gray-900 font-medium'
              : theme === 'dark'
              ? 'text-gray-300 hover:text-white hover:bg-gray-700'
              : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
          }`}
        >
          <Sun className="mr-2 h-4 w-4" />
          <span>Light</span>
        </DropdownMenuItem>
        <DropdownMenuItem 
          onClick={() => setTheme('dark')}
          className={`transition-all duration-200 ${
            theme === 'dark'
              ? 'bg-gray-700 text-white font-medium'
              : theme === 'customer'
              ? 'text-primary hover:text-primary/90 hover:bg-primary/10'
              : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
          }`}
        >
          <Moon className="mr-2 h-4 w-4" />
          <span>Dark</span>
        </DropdownMenuItem>
        <DropdownMenuItem 
          onClick={() => setTheme('customer')}
          className={`transition-all duration-200 ${
            theme === 'customer'
              ? 'bg-primary/15 text-primary font-medium'
              : theme === 'dark'
              ? 'text-gray-300 hover:text-primary/80 hover:bg-gray-700'
              : 'text-gray-700 hover:text-primary hover:bg-gray-100'
          }`}
        >
          <Palette className="mr-2 h-4 w-4" />
          <span>Customer</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
