import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Badge } from './ui/badge';

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

interface TracingInfo {
  thread_id?: string;
  run_id?: string;
  agent_id?: string;
  status?: string;
  created_at?: string;
  completed_at?: string;
}

interface TracingModalProps {
  isOpen: boolean;
  onClose: () => void;
  tracingInfo?: TracingInfo;
  tokenUsage?: TokenUsage;
  processingMetadata?: ProcessingMetadata;
  userMessage?: string;
  assistantMessage?: string;
}

export function TracingModal({ 
  isOpen, 
  onClose, 
  tracingInfo, 
  tokenUsage, 
  processingMetadata,
  userMessage,
  assistantMessage 
}: TracingModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {tracingInfo?.thread_id || 'Run Information'}
            {tracingInfo?.status && (
              <Badge variant={tracingInfo.status === 'completed' ? 'default' : 'secondary'}>
                {tracingInfo.status}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>
        
        <Tabs defaultValue="input-output" className="flex-1 overflow-hidden">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="input-output">Input & output</TabsTrigger>
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
            <TabsTrigger value="evaluations">Evaluations</TabsTrigger>
          </TabsList>
          
          <TabsContent value="input-output" className="overflow-auto max-h-[60vh]">
            <div className="space-y-4">
              <div>
                <h4 className="font-medium mb-2">Input</h4>
                <pre className="bg-gray-50 dark:bg-gray-800 p-3 rounded text-sm overflow-auto">
                  {JSON.stringify({ messages: [{ role: "user", content: userMessage }] }, null, 2)}
                </pre>
              </div>
              <div>
                <h4 className="font-medium mb-2">Output</h4>
                <pre className="bg-gray-50 dark:bg-gray-800 p-3 rounded text-sm overflow-auto">
                  {JSON.stringify({ role: "assistant", content: assistantMessage }, null, 2)}
                </pre>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="metadata" className="overflow-auto max-h-[60vh]">
            <pre className="bg-gray-50 dark:bg-gray-800 p-3 rounded text-sm overflow-auto">
              {JSON.stringify({
                thread_id: tracingInfo?.thread_id,
                run_id: tracingInfo?.run_id,
                agent_id: tracingInfo?.agent_id,
                status: tracingInfo?.status,
                created_at: tracingInfo?.created_at,
                completed_at: tracingInfo?.completed_at,
                token_usage: tokenUsage,
                processing_metadata: processingMetadata
              }, null, 2)}
            </pre>
          </TabsContent>
          
          <TabsContent value="evaluations" className="overflow-auto max-h-[60vh]">
            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
              Evaluations not available for this run
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
