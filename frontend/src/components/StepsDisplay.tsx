import { Card } from './ui/card';
import { Badge } from './ui/badge';

interface ProcessingMetadata {
  processing_time_ms: number;
  retrieval_method: string;
  success: boolean;
}

interface StepsDisplayProps {
  queryRewrites: string[];
  ragMode: string;
  processingMetadata?: ProcessingMetadata;
}

export function StepsDisplay({ queryRewrites, ragMode, processingMetadata }: StepsDisplayProps) {
  if (queryRewrites.length === 0) {
    return (
      <Card className="p-6">
        <div className="text-center text-gray-500">
          No query rewrites available
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-gray-900">Query Processing Steps</h3>
          <Badge variant="outline" className="text-xs">
            {ragMode.toUpperCase()}
          </Badge>
        </div>
        
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <div className="w-6 h-6 bg-primary/10 rounded-full flex items-center justify-center text-xs font-medium text-primary">
              1
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">Original Query</p>
              <p className="text-sm text-gray-600">{queryRewrites[0] || 'Processing...'}</p>
            </div>
          </div>

          {ragMode === 'agentic-rag' && queryRewrites.length > 1 && (
            <>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center text-xs font-medium text-purple-600">
                  2
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">Query Planning</p>
                  <p className="text-sm text-gray-600">Analyzing query complexity and planning retrieval strategy</p>
                </div>
              </div>

              {queryRewrites.slice(1).map((rewrite, idx) => (
                <div key={idx} className="flex items-start gap-3">
                  <div className="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center text-xs font-medium text-green-600">
                    {idx + 3}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">Subquery {idx + 1}</p>
                    <p className="text-sm text-gray-600">{rewrite}</p>
                  </div>
                </div>
              ))}
            </>
          )}

          {ragMode === 'fast-rag' && (
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-cyan-100 rounded-full flex items-center justify-center text-xs font-medium text-cyan-600">
                2
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">Direct Retrieval</p>
                <p className="text-sm text-gray-600">Performing fast vector search on indexed documents</p>
              </div>
            </div>
          )}

          {ragMode === 'mcp-rag' && (
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center text-xs font-medium text-blue-600">
                2
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">MCP Search</p>
                <p className="text-sm text-gray-600">Using Model Context Protocol server for enhanced search capabilities</p>
              </div>
            </div>
          )}

          {ragMode === 'deep-research-rag' && (
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 bg-orange-100 rounded-full flex items-center justify-center text-xs font-medium text-orange-600">
                {queryRewrites.length + 1}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">Verification Phase</p>
                <p className="text-sm text-gray-600">Cross-referencing sources and validating information accuracy</p>
              </div>
            </div>
          )}

          <div className="flex items-start gap-3">
            <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center text-xs font-medium text-gray-600">
              ✓
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">Response Generation</p>
              <p className="text-sm text-gray-600">Synthesizing information from retrieved sources</p>
            </div>
          </div>
        </div>

        {processingMetadata && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h4 className="font-medium text-gray-900 mb-2">Processing Metrics</h4>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium text-gray-700">Processing Time:</span>
                <span className="ml-2 text-gray-600">{processingMetadata.processing_time_ms}ms</span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Method:</span>
                <span className="ml-2 text-gray-600">{processingMetadata.retrieval_method}</span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Subqueries Executed:</span>
                <span className="ml-2 text-gray-600">{Math.max(1, queryRewrites.length - 1)}</span>
              </div>
              <div>
                <span className="font-medium text-gray-700">Semantic Ranking:</span>
                <span className="ml-2 text-gray-600">{ragMode !== 'fast-rag' && ragMode !== 'mcp-rag' ? 'Performed' : 'Skipped'}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
