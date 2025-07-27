import { useState, useEffect } from 'react';
import { ChatLayout } from '../components/ChatLayout';
import { MicrosoftAnswerDisplay } from '../components/MicrosoftAnswerDisplay';
import { MicrosoftInput } from '../components/MicrosoftInput';
import { useChatStream } from '../hooks/useChatStream';
import { Sparkles } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

type RAGMode = 'fast-rag' | 'agentic-rag' | 'deep-research-rag' | 'mcp-rag';

export function QAWithVerification() {
  const { theme } = useTheme();
  
  const [query, setQuery] = useState('');
  const [selectedMode, setSelectedMode] = useState<RAGMode>('deep-research-rag'); // Use deep-research-rag for QA verification
  const { 
    messages, 
    citations, 
    queryRewrites, 
    tokenUsage, 
    processingMetadata, 
    isLoading, 
    isStreaming,
    sendMessage,
    clearMessages
  } = useChatStream(selectedMode, false); // Disable sessions for QA mode

  // Clear any existing messages when component mounts or mode changes
  useEffect(() => {
    if (clearMessages) {
      clearMessages();
    }
  }, [clearMessages, selectedMode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      await sendMessage(query);
      setQuery('');
    }
  };

  const currentMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const hasResults = currentMessage && currentMessage.role === 'assistant';

  return (
    <ChatLayout>
      <div className={`flex-1 overflow-y-auto ${
        theme === 'dark' 
          ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900' 
          : theme === 'customer' 
            ? 'bg-gradient-to-br from-customer-50 via-customer-25 to-customer-50' 
            : 'bg-gradient-to-br from-gray-50 via-white to-primary/5'
      }`}>
        {/* Content Area */}
        <div className="p-6">
          <div className="max-w-5xl mx-auto">
            {!hasResults && !isLoading && (
              <div className="space-y-8">
                {/* Welcome Message */}
                <div className="text-center py-16">
                  <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6 ${
                    theme === 'dark' 
                      ? 'bg-gradient-to-br from-gray-600 to-gray-700' 
                      : theme === 'customer' 
                        ? 'bg-gradient-to-br from-customer-500 to-customer-600' 
                        : 'bg-gradient-to-br from-primary to-primary/80'
                  }`}>
                    <Sparkles className="h-8 w-8 text-white" />
                  </div>
                  <h2 className={`text-3xl font-bold mb-3 ${
                    theme === 'dark' 
                      ? 'text-white' 
                      : theme === 'customer' 
                        ? 'text-customer-900' 
                        : 'text-gray-900'
                  }`}>
                    QA with Verification
                  </h2>
                  <p className={`text-lg mb-12 max-w-2xl mx-auto ${
                    theme === 'dark' 
                      ? 'text-gray-300' 
                      : theme === 'customer' 
                        ? 'text-customer-700' 
                        : 'text-gray-600'
                  }`}>
                    Get intelligent, verified answers with comprehensive source citations
                  </p>
                </div>

                {/* Microsoft Input */}
                <MicrosoftInput
                  query={query}
                  setQuery={setQuery}
                  selectedMode={selectedMode}
                  setSelectedMode={setSelectedMode}
                  onSubmit={handleSubmit}
                  isLoading={isLoading}
                  showSourceSelector={true}
                  placeholder="Ask anything about Microsoft..."
                  hideExampleQuestions={false}
                />
              </div>
            )}

            {/* Results */}
            {(hasResults || isLoading) && (
              <div className="space-y-6">
                <div className="bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    <p className="text-sm text-blue-800 dark:text-blue-200">
                      <strong>QA Mode:</strong> Each question starts a fresh conversation. History is not saved or carried forward.
                    </p>
                  </div>
                </div>
                
                <MicrosoftInput
                  query={query}
                  setQuery={setQuery}
                  selectedMode={selectedMode}
                  setSelectedMode={setSelectedMode}
                  onSubmit={handleSubmit}
                  isLoading={isLoading}
                  showSourceSelector={true}
                  placeholder="Ask anything about Microsoft..."
                  hideExampleQuestions={true}
                />
                
                <MicrosoftAnswerDisplay
                  messages={messages}
                  citations={citations}
                  queryRewrites={queryRewrites}
                  tokenUsage={tokenUsage}
                  processingMetadata={processingMetadata}
                  isStreaming={isStreaming}
                  ragMode={selectedMode}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </ChatLayout>
  );
}
