import { CardFooter } from './ui/card';
import { Button } from './ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { BarChart3, Eye, Clock } from 'lucide-react';

interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  model?: string;
  cost?: number;
  error?: string;
}

interface ProcessingMetadata {
  processing_time_ms: number;
  retrieval_method: string;
  success: boolean;
}

interface TokenUsageFooterProps {
  tokenUsage?: TokenUsage;
  processingMetadata?: ProcessingMetadata;
  onViewRunInfo: () => void;
  theme: string;
}

export function TokenUsageFooter({ tokenUsage, processingMetadata, onViewRunInfo, theme }: TokenUsageFooterProps) {
  if (!tokenUsage) return null;

  return (
    <CardFooter className={`justify-between border-t ${
      theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
    }`}>
      <div className="flex items-center gap-4">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <BarChart3 className="h-4 w-4" />
                <span>{tokenUsage.total_tokens}t</span>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <div className="text-xs space-y-1">
                <div>Input tokens: {tokenUsage.prompt_tokens}</div>
                <div>Output tokens: {tokenUsage.completion_tokens}</div>
                <div>Total tokens: {tokenUsage.total_tokens}</div>
                {tokenUsage.cost && <div>Cost: ${tokenUsage.cost.toFixed(4)}</div>}
                {tokenUsage.model && <div>Model: {tokenUsage.model}</div>}
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        
        {processingMetadata && (
          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <Clock className="h-4 w-4" />
            <span>{processingMetadata.processing_time_ms}ms</span>
          </div>
        )}
      </div>
      
      <Button variant="outline" size="sm" onClick={onViewRunInfo}>
        <Eye className="h-4 w-4 mr-2" />
        View Run Info
      </Button>
    </CardFooter>
  );
}
