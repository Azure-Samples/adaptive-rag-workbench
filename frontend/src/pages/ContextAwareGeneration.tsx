import { useState } from 'react';
import { ChatLayout } from '../components/ChatLayout';
import { MicrosoftAnswerDisplay } from '../components/MicrosoftAnswerDisplay';
import { MicrosoftInput } from '../components/MicrosoftInput';
import { useChatStream } from '../hooks/useChatStream';
import { useTheme } from '../contexts/ThemeContext';
import { Sparkles } from 'lucide-react';

type RAGMode = 'fast-rag' | 'agentic-rag' | 'deep-research-rag' | 'mcp-rag';

export function ContextAwareGeneration() {
  const { theme } = useTheme();
  const [query, setQuery] = useState('');
  const [selectedMode, setSelectedMode] = useState<RAGMode>('fast-rag');
  const { 
    messages, 
    citations, 
    queryRewrites, 
    tokenUsage, 
    processingMetadata, 
    isLoading, 
    isStreaming,
    sendMessage,
    sessionId,
    startNewSession
  } = useChatStream(selectedMode);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      await sendMessage(query);
      setQuery('');
    }
  };

  const handleFollowUpMessage = async (message: string) => {
    if (!isLoading) {
      await sendMessage(message);
    }
  };

  const handleNewChat = () => {
    startNewSession();
    setQuery('');
  };

  const currentMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const hasResults = currentMessage && currentMessage.role === 'assistant';

  return (
    <ChatLayout>
      <div className={`flex-1 overflow-y-auto ${
        theme === 'dark' 
          ? 'bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800' 
          : theme === 'customer' 
            ? 'bg-gradient-to-br from-customer-50 via-customer-50 to-customer-100' 
            : 'bg-gradient-to-br from-background via-background to-primary/5'
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
                      ? 'bg-gradient-to-br from-gray-700 to-gray-600' 
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
                        : 'text-foreground'
                  }`}>
                    Context-Aware Generation
                  </h2>
                  <p className={`text-lg mb-12 max-w-2xl mx-auto ${
                    theme === 'dark' 
                      ? 'text-gray-300' 
                      : theme === 'customer' 
                        ? 'text-customer-700' 
                        : 'text-muted-foreground'
                  }`}>
                    Generate contextually relevant content with intelligent document analysis
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
                  showSourceSelector={false}
                  placeholder="Ask about financial data from 10-K filings..."
                  hideExampleQuestions={false}
                />
              </div>
            )}

            {/* Results */}
            {(hasResults || isLoading) && (
              <div className="space-y-6">
                <MicrosoftInput
                  query={query}
                  setQuery={setQuery}
                  selectedMode={selectedMode}
                  setSelectedMode={setSelectedMode}
                  onSubmit={handleSubmit}
                  isLoading={isLoading}
                  showSourceSelector={false}
                  placeholder="Ask about financial data from 10-K filings..."
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
                  sessionId={sessionId}
                  onSendMessage={handleFollowUpMessage}
                  onStartNewSession={handleNewChat}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </ChatLayout>
  );
}
