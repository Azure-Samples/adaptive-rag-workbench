
import { useTheme } from '../contexts/ThemeContext';

export function MicrosoftLogo({ className = "" }: { className?: string }) {
  const { theme } = useTheme();
  
  const textColor = theme === 'dark' ? '#FFFFFF' : theme === 'customer' ? '#1e40af' : '#323130';
  
  return (
    <div className={`flex items-center ${className}`}>
      <svg width="108" height="24" viewBox="0 0 108 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="10" height="10" fill="#F25022"/>
        <rect x="12" width="10" height="10" fill="#7FBA00"/>
        <rect y="12" width="10" height="10" fill="#00A4EF"/>
        <rect x="12" y="12" width="10" height="10" fill="#FFB900"/>
        <text x="28" y="16" fontFamily="Segoe UI, sans-serif" fontSize="14" fontWeight="600" fill={textColor}>Microsoft</text>
      </svg>
    </div>
  );
}
