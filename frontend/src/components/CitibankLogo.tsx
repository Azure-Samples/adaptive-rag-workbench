export function CitibankLogo({ className = "h-8 w-auto" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 40"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="citibankGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#4f46e5" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
      </defs>
      
      {/* Citibank wordmark */}
      <g>
        <path
          d="M20 8C14.477 8 10 12.477 10 18C10 23.523 14.477 28 20 28C25.523 28 30 23.523 30 18C30 12.477 25.523 8 20 8Z"
          fill="url(#citibankGradient)"
        />
        <path
          d="M20 12C16.686 12 14 14.686 14 18C14 21.314 16.686 24 20 24C23.314 24 26 21.314 26 18C26 14.686 23.314 12 20 12Z"
          fill="white"
        />
        
        {/* C */}
        <path
          d="M45 28C40.029 28 36 23.971 36 19C36 14.029 40.029 10 45 10C48.314 10 51.314 11.686 53 14.5L50 16.5C49.029 14.829 47.171 14 45 14C42.238 14 40 16.238 40 19C40 21.762 42.238 24 45 24C47.171 24 49.029 23.171 50 21.5L53 23.5C51.314 26.314 48.314 28 45 28Z"
          fill="currentColor"
        />
        
        {/* i */}
        <circle cx="58" cy="12" r="2" fill="currentColor" />
        <rect x="56" y="16" width="4" height="12" fill="currentColor" />
        
        {/* t */}
        <rect x="66" y="10" width="4" height="18" fill="currentColor" />
        <rect x="62" y="16" width="8" height="3" fill="currentColor" />
        
        {/* i */}
        <circle cx="78" cy="12" r="2" fill="currentColor" />
        <rect x="76" y="16" width="4" height="12" fill="currentColor" />
        
        {/* b */}
        <rect x="86" y="10" width="4" height="18" fill="currentColor" />
        <path
          d="M90 16C90 16 94 16 96 16C98.209 16 100 17.791 100 20C100 22.209 98.209 24 96 24C94 24 90 24 90 24V16Z"
          fill="currentColor"
        />
        
        {/* a */}
        <path
          d="M110 28C106.686 28 104 25.314 104 22C104 18.686 106.686 16 110 16C113.314 16 116 18.686 116 22V24H108C108.552 25.105 109.696 26 111 26C112.105 26 113.052 25.447 113.528 24.618L115.764 26.382C114.812 27.382 113.476 28 110 28ZM110 19C108.895 19 108 19.895 108 21H112C112 19.895 111.105 19 110 19Z"
          fill="currentColor"
        />
        
        {/* n */}
        <rect x="120" y="16" width="4" height="12" fill="currentColor" />
        <path
          d="M124 16C124 16 128 16 130 16C132.209 16 134 17.791 134 20V28H130V20C130 19.448 129.552 19 129 19C128.448 19 128 19.448 128 20V28H124V16Z"
          fill="currentColor"
        />
        
        {/* k */}
        <rect x="140" y="10" width="4" height="18" fill="currentColor" />
        <path
          d="M144 22L148 16H153L148 22L153 28H148L144 22Z"
          fill="currentColor"
        />
      </g>
    </svg>
  );
}
