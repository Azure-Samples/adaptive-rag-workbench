import { useState, useEffect } from 'react';
import { Star, ExternalLink } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { useTheme } from '../contexts/ThemeContext';

export function GitHubLink() {
  const [starCount, setStarCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const { theme } = useTheme();

  useEffect(() => {
    const fetchStarCount = async () => {
      try {
        const response = await fetch('https://api.github.com/repos/thegovind/adaptive-rag-workbench');
        const data = await response.json();
        setStarCount(data.stargazers_count);
      } catch (error) {
        console.error('Failed to fetch GitHub star count:', error);
        setStarCount(0);
      } finally {
        setLoading(false);
      }
    };

    fetchStarCount();
  }, []);

  return (
    <Button
      variant="outline"
      size="sm"
      className={`flex items-center gap-2 transition-all duration-300 ${
        theme === 'dark'
          ? 'bg-gray-700 hover:bg-gray-600 border-gray-600 text-white hover:border-gray-500'
          : theme === 'customer'
          ? 'bg-primary/10 hover:bg-primary/15 border-primary/20 text-primary hover:border-primary/30'
          : 'bg-white hover:bg-gray-50 border-gray-200 text-gray-700 hover:border-gray-300'
      }`}
      onClick={() => window.open('https://github.com/thegovind/adaptive-rag-workbench', '_blank')}
    >
      <Star className="h-4 w-4" />
      <span className="text-sm font-medium">Star</span>
      {loading ? (
        <div className={`w-6 h-4 animate-pulse rounded ${
          theme === 'dark'
            ? 'bg-gray-600'
            : theme === 'customer'
            ? 'bg-primary/20'
            : 'bg-gray-200'
        }`} />
      ) : (
        <Badge variant="secondary" className={`ml-1 transition-all duration-300 ${
          theme === 'dark'
            ? 'bg-gray-600 text-gray-200 border-gray-500'
            : theme === 'customer'
            ? 'bg-primary/15 text-primary border-primary/20'
            : 'bg-gray-100 text-gray-700 border-gray-300'
        }`}>
          {starCount?.toLocaleString() || '0'}
        </Badge>
      )}
      <ExternalLink className="h-3 w-3 ml-1" />
    </Button>
  );
}
