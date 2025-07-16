import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { MessageSquare, BarChart3, List, ExternalLink, Eye, Plus, RefreshCw } from 'lucide-react';
import { Button } from './ui/button';
import { useAuth } from '../auth/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { apiService } from '../services/api';

interface Citation {
  id: string;
  title: string;
  content: string;
  source: string;
  url?: string;
  score?: number;
  verification?: boolean;
}

interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

interface ProcessingMetadata {
  processing_time_ms: number;
  retrieval_method: string;
  success: boolean;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface PerplexityAnswerDisplayProps {
  messages: Message[];
  citations: Citation[];
  queryRewrites: string[];
  tokenUsage?: TokenUsage;
  processingMetadata?: ProcessingMetadata;
  isStreaming: boolean;
  ragMode: string;
  sessionId?: string;
  onSendMessage?: (message: string) => void;
  onStartNewSession?: () => void;
}

export function MicrosoftAnswerDisplay({
  messages,
  citations,
  queryRewrites,
  tokenUsage,
  processingMetadata,
  isStreaming,
  ragMode,
  sessionId,
  onSendMessage,
  onStartNewSession
}: PerplexityAnswerDisplayProps) {
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [showCitationModal, setShowCitationModal] = useState(false);
  const [followUpQuestions, setFollowUpQuestions] = useState<string[]>([]);
  const [isLoadingFollowUp, setIsLoadingFollowUp] = useState(false);
  const { getAccessToken } = useAuth();
  const { theme } = useTheme();

  const handleViewCitation = (citation: Citation) => {
    setSelectedCitation(citation);
    setShowCitationModal(true);
  };

  const assistantMessage = messages.find(msg => msg.role === 'assistant');
  const userMessage = messages.find(msg => msg.role === 'user');
  const answer = assistantMessage?.content || '';

  const generateFollowUpQuestions = async () => {
    if (!answer || !userMessage?.content || !sessionId) return;
    
    setIsLoadingFollowUp(true);
    try {
      const token = await getAccessToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiService.baseUrl}/chat/follow-up-questions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          original_question: userMessage.content,
          answer: answer,
          session_id: sessionId
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setFollowUpQuestions(data.follow_up_questions || []);
      }
    } catch (error) {
      console.error('Failed to generate follow-up questions:', error);
    } finally {
      setIsLoadingFollowUp(false);
    }
  };

  useEffect(() => {
    if (answer && !isStreaming && userMessage?.content) {
      generateFollowUpQuestions();
    }
  }, [answer, isStreaming, userMessage?.content, sessionId]);

  const handleFollowUpClick = (question: string) => {
    if (onSendMessage) {
      onSendMessage(question);
    }
  };

  const handleNewChat = () => {
    if (onStartNewSession) {
      onStartNewSession();
    }
  };


  return (
    <div className={`${
      theme === 'dark' 
        ? 'bg-gray-900 text-white' 
        : theme === 'customer' 
          ? 'bg-customer-50 text-customer-900' 
          : 'bg-white text-gray-900'
    }`}>
    <Tabs defaultValue="answer" className="w-full">
      <TabsList className={`grid w-full grid-cols-4 ${
        theme === 'dark' 
          ? 'bg-gray-800 border-gray-700' 
          : theme === 'customer' 
            ? 'bg-customer-100 border-customer-200' 
            : 'bg-gray-50 border-gray-200'
      }`}>
        <TabsTrigger value="answer" className={`flex items-center gap-2 ${
          theme === 'dark' 
            ? 'text-gray-300 hover:text-white data-[state=active]:bg-gray-700 data-[state=active]:text-white' 
            : theme === 'customer' 
              ? 'text-customer-700 hover:text-customer-900 data-[state=active]:bg-customer-500 data-[state=active]:text-white' 
              : 'text-gray-700 hover:text-gray-900 data-[state=active]:bg-white data-[state=active]:text-gray-900'
        }`}>
          <MessageSquare className="h-4 w-4" />
          Answer
        </TabsTrigger>
        <TabsTrigger value="sources" className={`flex items-center gap-2 ${
          theme === 'dark' 
            ? 'text-gray-300 hover:text-white data-[state=active]:bg-gray-700 data-[state=active]:text-white' 
            : theme === 'customer' 
              ? 'text-customer-700 hover:text-customer-900 data-[state=active]:bg-customer-500 data-[state=active]:text-white' 
              : 'text-gray-700 hover:text-gray-900 data-[state=active]:bg-white data-[state=active]:text-gray-900'
        }`}>
          <ExternalLink className="h-4 w-4" />
          Sources {citations && citations.length > 0 && `• ${citations.length}`}
        </TabsTrigger>
        <TabsTrigger value="steps" className={`flex items-center gap-2 ${
          theme === 'dark' 
            ? 'text-gray-300 hover:text-white data-[state=active]:bg-gray-700 data-[state=active]:text-white' 
            : theme === 'customer' 
              ? 'text-customer-700 hover:text-customer-900 data-[state=active]:bg-customer-500 data-[state=active]:text-white' 
              : 'text-gray-700 hover:text-gray-900 data-[state=active]:bg-white data-[state=active]:text-gray-900'
        }`}>
          <List className="h-4 w-4" />
          Steps
        </TabsTrigger>
        <TabsTrigger value="tokens" className={`flex items-center gap-2 ${
          theme === 'dark' 
            ? 'text-gray-300 hover:text-white data-[state=active]:bg-gray-700 data-[state=active]:text-white' 
            : theme === 'customer' 
              ? 'text-customer-700 hover:text-customer-900 data-[state=active]:bg-customer-500 data-[state=active]:text-white' 
              : 'text-gray-700 hover:text-gray-900 data-[state=active]:bg-white data-[state=active]:text-gray-900'
        }`}>
          <BarChart3 className="h-4 w-4" />
          Token Usage
        </TabsTrigger>
      </TabsList>

      <TabsContent value="answer" className="mt-6">
        <Card className={`p-6 ${
          theme === 'dark' 
            ? 'bg-gray-800 border-gray-700' 
            : theme === 'customer' 
              ? 'bg-customer-50 border-customer-200' 
              : 'bg-white border-gray-200'
        }`}>
          {isStreaming && !answer && (
            <div className="flex items-center space-x-3">
              <div className={`animate-spin rounded-full h-4 w-4 border-2 border-t-transparent ${
                theme === 'dark' 
                  ? 'border-gray-400' 
                  : theme === 'customer' 
                    ? 'border-customer-500' 
                    : 'border-gray-500'
              }`}></div>
              <span className={`text-sm ${
                theme === 'dark' 
                  ? 'text-gray-300' 
                  : theme === 'customer' 
                    ? 'text-customer-700' 
                    : 'text-gray-600'
              }`}>Generating response...</span>
            </div>
          )}
          {answer && (
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {answer}
              </ReactMarkdown>
              {isStreaming && (
                <div className="mt-4 flex items-center space-x-3">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-gray-500 border-t-transparent"></div>
                  <span className="text-sm text-gray-600">Processing...</span>
                </div>
              )}
            </div>
          )}
          
          {/* Follow-up Questions Section */}
          {answer && !isStreaming && (
            <div className="mt-6 pt-6 border-t border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">Continue the conversation</h3>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNewChat}
                  className="flex items-center gap-2"
                >
                  <Plus className="h-4 w-4" />
                  New Chat
                </Button>
              </div>
              
              {isLoadingFollowUp ? (
                <div className="flex items-center space-x-3 py-4">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-gray-500 border-t-transparent"></div>
                  <span className="text-sm text-gray-600">Generating follow-up questions...</span>
                </div>
              ) : followUpQuestions.length > 0 ? (
                <div className="space-y-3">
                  <p className="text-sm text-gray-600 mb-3">Here are some follow-up questions you might find interesting:</p>
                  {followUpQuestions.map((question, index) => (
                    <Button
                      key={index}
                      variant="outline"
                      className="w-full text-left justify-start h-auto p-4 text-wrap"
                      onClick={() => handleFollowUpClick(question)}
                    >
                      <MessageSquare className="h-4 w-4 mr-3 flex-shrink-0 mt-0.5" />
                      <span className="text-sm leading-relaxed">{question}</span>
                    </Button>
                  ))}
                  <div className="flex justify-center pt-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={generateFollowUpQuestions}
                      className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
                    >
                      <RefreshCw className="h-4 w-4" />
                      Generate new suggestions
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-sm text-gray-500 mb-3">No follow-up questions available</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={generateFollowUpQuestions}
                    className="flex items-center gap-2"
                  >
                    <RefreshCw className="h-4 w-4" />
                    Try generating suggestions
                  </Button>
                </div>
              )}
            </div>
          )}
        </Card>
      </TabsContent>

      <TabsContent value="sources" className="mt-6">
        <div className="space-y-4">
          {!citations || citations.length === 0 ? (
            <Card className="p-6 text-center text-gray-500">
              No sources available yet
            </Card>
          ) : (
            citations?.map((citation, idx) => (
              <Card key={citation.id} className="p-4">
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center text-xs font-medium">
                    {idx + 1}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-medium text-gray-900 mb-1">{citation.title}</h3>
                    <p className="text-sm text-gray-600 mb-2 line-clamp-3">{citation.content}</p>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <span>{citation.source}</span>
                      {citation.score && (
                        <Badge variant="outline" className="text-xs">
                          Score: {citation.score.toFixed(2)}
                        </Badge>
                      )}
                      {citation.verification && (
                        <Badge className="bg-green-100 text-green-800 text-xs">
                          Verified
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="text-xs h-7"
                        onClick={() => handleViewCitation(citation)}
                      >
                        <Eye className="h-3 w-3 mr-1" />
                        View Full Citation
                      </Button>
                      {citation.url && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs h-7"
                          onClick={() => window.open(citation.url, '_blank')}
                        >
                          <ExternalLink className="h-3 w-3 mr-1" />
                          Source Link
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      </TabsContent>

      <TabsContent value="steps" className="mt-6">
        <Card className="p-6">
          {queryRewrites.length === 0 ? (
            <div className="text-center text-gray-500">
              No query rewrites available
            </div>
          ) : (
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
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="font-medium text-gray-700">Processing Time:</span>
                      <span className="ml-2 text-gray-600">{processingMetadata.processing_time_ms}ms</span>
                    </div>
                    <div>
                      <span className="font-medium text-gray-700">Method:</span>
                      <span className="ml-2 text-gray-600">{processingMetadata.retrieval_method}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      </TabsContent>

      <TabsContent value="tokens" className="mt-6">
        <Card className="p-6">
          {!tokenUsage ? (
            <div className="text-center text-gray-500">
              No token usage data available
            </div>
          ) : (
            <div className="space-y-4">
              <h3 className="font-medium text-gray-900">Token Usage Statistics</h3>
              
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-primary/10 rounded-lg">
                  <div className="text-2xl font-bold text-primary">{tokenUsage.prompt_tokens}</div>
                  <div className="text-sm text-gray-600">Prompt Tokens</div>
                </div>
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">{tokenUsage.completion_tokens}</div>
                  <div className="text-sm text-gray-600">Completion Tokens</div>
                </div>
                <div className="text-center p-4 bg-purple-50 rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">{tokenUsage.total_tokens}</div>
                  <div className="text-sm text-gray-600">Total Tokens</div>
                </div>
              </div>

              <div className="mt-6 space-y-3">
                <h4 className="font-medium text-gray-900">Cost Breakdown</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Input Cost:</span>
                    <span className="font-medium">${(tokenUsage.prompt_tokens * 0.0001).toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Output Cost:</span>
                    <span className="font-medium">${(tokenUsage.completion_tokens * 0.0002).toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between border-t pt-2">
                    <span className="font-medium text-gray-900">Total Cost:</span>
                    <span className="font-bold">${((tokenUsage.prompt_tokens * 0.0001) + (tokenUsage.completion_tokens * 0.0002)).toFixed(4)}</span>
                  </div>
                </div>
              </div>

              {processingMetadata && (
                <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Performance Metrics</h4>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-600">Tokens/Second:</span>
                      <span className="ml-2 font-medium">
                        {processingMetadata.processing_time_ms > 0 
                          ? Math.round((tokenUsage.total_tokens / processingMetadata.processing_time_ms) * 1000)
                          : 'N/A'
                        }
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Efficiency:</span>
                      <span className="ml-2 font-medium">
                        {processingMetadata.success ? 'Optimal' : 'Degraded'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      </TabsContent>
    </Tabs>

      {/* Citation Details Modal */}
      {showCitationModal && selectedCitation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl max-h-[80vh] w-full flex flex-col">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-xl font-semibold text-gray-900">Citation Details</h2>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowCitationModal(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </Button>
            </div>
            
            <div className="flex-1 overflow-auto p-6 space-y-4">
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <h3 className="font-semibold text-lg text-left text-gray-900">{selectedCitation?.title}</h3>
                  {selectedCitation?.score && (
                    <Badge variant="outline" className="text-xs">
                      Score: {selectedCitation.score.toFixed(2)}
                    </Badge>
                  )}
                  {selectedCitation?.verification && (
                    <Badge className="bg-green-100 text-green-800 text-xs">
                      Verified
                    </Badge>
                  )}
                </div>
                
                <div className="flex items-center space-x-4 text-sm text-gray-600">
                  <span>Source: {selectedCitation?.source}</span>
                </div>
              </div>
              
              <hr className="border-gray-200" />
              
              <div className="space-y-2">
                <h4 className="font-medium text-sm text-gray-900">Full Citation Content:</h4>
                <div className="bg-gray-50 p-4 rounded-lg text-sm leading-relaxed text-left text-gray-900 max-h-96 overflow-y-auto">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      em: ({ children }) => <em className="italic">{children}</em>,
                    }}
                  >
                    {selectedCitation?.content || ''}
                  </ReactMarkdown>
                </div>
              </div>
              
              {selectedCitation?.url && (
                <div className="pt-2">
                  <Button
                    variant="outline"
                    onClick={() => window.open(selectedCitation.url, '_blank')}
                    className="w-full"
                  >
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open Original Source
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
