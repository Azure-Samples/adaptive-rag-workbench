import { useState, useCallback } from 'react';
import { ChatLayout } from '../components/ChatLayout';
import { MicrosoftAnswerDisplay } from '../components/MicrosoftAnswerDisplay';
import { MicrosoftInput } from '../components/MicrosoftInput';
import { SessionHistory } from '../components/SessionHistory';
import { useChatStream } from '../hooks/useChatStream';
import { useTheme } from '../contexts/ThemeContext';
import { Sparkles } from 'lucide-react';

type RAGMode = 'fast-rag' | 'agentic-rag' | 'deep-research-rag';

export function ContextAwareGeneration() {
  const { theme } = useTheme();
  const [query, setQuery] = useState('');
  const [selectedMode, setSelectedMode] = useState<RAGMode>('fast-rag');
  const [showSessionHistory, setShowSessionHistory] = useState(false);

  // Create a wrapper function to handle mode changes from session switching
  const handleModeChange = (mode: string) => {
    if (mode === 'fast-rag' || mode === 'agentic-rag' || mode === 'deep-research-rag') {
      setSelectedMode(mode as RAGMode);
    }
  };

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
    startNewSession,
    switchSession
  } = useChatStream(selectedMode, true, handleModeChange);

  // Switch to a different session without reloading the page
  const handleSessionSelect = useCallback(async (sessionId: string) => {
    if (switchSession) {
      await switchSession(sessionId);
    }
  }, [switchSession]);

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
    if (startNewSession) {
      startNewSession();
    }
    setQuery('');
  };

  const currentMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const hasResults = currentMessage && currentMessage.role === 'assistant';

  return (
    <div className="flex h-screen">
      {/* Session History Sidebar */}
      {showSessionHistory && (
        <div className="w-80 border-r bg-background flex-shrink-0">
          <SessionHistory
            mode={selectedMode}
            currentSessionId={sessionId}
            onSessionSelect={(sessionId) => {
              // Use our simplified session switching
              handleSessionSelect(sessionId);
              setShowSessionHistory(false);
            }}
            onNewSession={() => {
              if (startNewSession) {
                startNewSession();
              }
              setShowSessionHistory(false);
            }}
          />
        </div>
      )}

      {/* Main Content Container */}
      <div className="flex-1 flex flex-col">
        <ChatLayout>
          <div className={`flex-1 overflow-y-auto ${
            theme === 'dark' 
              ? 'bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800' 
              : theme === 'customer' 
                ? 'bg-gradient-to-br from-customer-50 via-customer-50 to-customer-100' 
                : 'bg-gradient-to-br from-background via-background to-primary/5'
          }`}>
            {/* Header with Session History Button */}
            <div className="p-4 border-b">
              <button
                onClick={() => setShowSessionHistory(!showSessionHistory)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  theme === 'dark'
                    ? 'bg-gray-700 text-white hover:bg-gray-600'
                    : theme === 'customer'
                      ? 'bg-customer-500 text-white hover:bg-customer-600'
                      : 'bg-primary text-white hover:bg-primary/90'
                }`}
              >
                {showSessionHistory ? 'Hide' : 'Show'} Sessions
              </button>
            </div>

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
      </div>
    </div>
  );
}
