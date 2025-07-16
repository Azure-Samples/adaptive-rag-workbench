import { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../auth/AuthContext';
import { apiService } from '../services/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

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
  model?: string;
  cost?: number;
  error?: string;
}

interface ProcessingMetadata {
  processing_time_ms: number;
  retrieval_method: string;
  success: boolean;
}

interface ChatResponse {
  messages: Message[];
  citations: Citation[];
  queryRewrites: string[];
  tokenUsage?: TokenUsage;
  processingMetadata?: ProcessingMetadata;
  isStreaming: boolean;
  sessionId: string;
}


export function useChatStream(mode: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [queryRewrites, setQueryRewrites] = useState<string[]>([]);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | undefined>();
  const [processingMetadata, setProcessingMetadata] = useState<ProcessingMetadata | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const { getAccessToken } = useAuth();

  useEffect(() => {
    const storedSessionId = localStorage.getItem(`chat_session_${mode}`);
    if (storedSessionId) {
      setSessionId(storedSessionId);
      loadSessionHistory(storedSessionId);
    } else {
      const newSessionId = generateSessionId();
      setSessionId(newSessionId);
      localStorage.setItem(`chat_session_${mode}`, newSessionId);
    }
  }, [mode]);

  const generateSessionId = (): string => {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  };

  const loadSessionHistory = async (sessionId: string) => {
    try {
      const token = await getAccessToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiService.baseUrl}/chat/sessions/${sessionId}/history`, {
        method: 'GET',
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        const sessionMessages = data.messages || [];
        
        const convertedMessages: Message[] = sessionMessages.map((msg: any) => ({
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.timestamp)
        }));
        
        setMessages(convertedMessages);
        
        const lastAssistantMessage = sessionMessages
          .filter((msg: any) => msg.role === 'assistant')
          .pop();
        
        if (lastAssistantMessage) {
          if (lastAssistantMessage.citations) {
            setCitations(lastAssistantMessage.citations);
          }
          if (lastAssistantMessage.token_usage) {
            setTokenUsage(lastAssistantMessage.token_usage);
          }
          if (lastAssistantMessage.processing_metadata) {
            setProcessingMetadata(lastAssistantMessage.processing_metadata);
          }
        }
      }
    } catch (error) {
      console.warn('Failed to load session history:', error);
    }
  };

  const sendMessage = useCallback(async (content: string) => {
    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setIsStreaming(true);
    
    setCitations([]);
    setQueryRewrites([]);
    setTokenUsage(undefined);
    setProcessingMetadata(undefined);

    try {
      // Get access token (will be 'demo-token' in demo mode)
      const token = await getAccessToken();
      
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiService.baseUrl}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ 
          prompt: content,
          mode: mode,
          session_id: sessionId
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      let assistantMessage = '';
      let messageIndex = -1;

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = new TextDecoder().decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.error) {
                  throw new Error(data.error);
                }
                
                if (data.token) {
                  assistantMessage += data.token;
                  
                  setMessages(prev => {
                    const newMessages = [...prev];
                    
                    if (messageIndex === -1) {
                      messageIndex = newMessages.length;
                      newMessages.push({
                        role: 'assistant',
                        content: assistantMessage,
                        timestamp: new Date()
                      });
                    } else {
                      const existingMessage = newMessages[messageIndex];
                      newMessages[messageIndex] = {
                        role: existingMessage?.role || 'assistant',
                        content: assistantMessage,
                        timestamp: existingMessage?.timestamp || new Date()
                      };
                    }
                    
                    return newMessages;
                  });
                }
                
                // Handle complete answer for agentic responses
                if (data.type === 'answer_complete' && data.answer) {
                  assistantMessage = data.answer;
                  
                  setMessages(prev => {
                    const newMessages = [...prev];
                    
                    if (messageIndex === -1) {
                      messageIndex = newMessages.length;
                      newMessages.push({
                        role: 'assistant',
                        content: assistantMessage,
                        timestamp: new Date()
                      });
                    } else {
                      const existingMessage = newMessages[messageIndex];
                      newMessages[messageIndex] = {
                        role: existingMessage?.role || 'assistant',
                        content: assistantMessage,
                        timestamp: existingMessage?.timestamp || new Date()
                      };
                    }
                    
                    return newMessages;
                  });
                  
                  // Set streaming to false since we have the complete answer
                  setIsStreaming(false);
                }
                
                if (data.type === 'citations' && data.citations) {
                  setCitations(data.citations);
                }
                
                if (data.type === 'query_rewrites' && data.rewrites) {
                  setQueryRewrites(data.rewrites);
                }
                
                if (data.type === 'token_usage' && data.usage) {
                  setTokenUsage(data.usage);
                }
                
                if (data.type === 'metadata' && data.processing) {
                  setProcessingMetadata(data.processing);
                }
                
                if (data.done) {
                  setIsStreaming(false);
                  break;
                }
              } catch (parseError) {
                console.warn('Failed to parse SSE data:', parseError);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`,
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
    }
  }, [mode, getAccessToken]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setCitations([]);
    setQueryRewrites([]);
    setTokenUsage(undefined);
    setProcessingMetadata(undefined);
  }, []);

  const startNewSession = useCallback(() => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    localStorage.setItem(`chat_session_${mode}`, newSessionId);
    clearMessages();
  }, [mode, clearMessages]);

  const chatResponse: ChatResponse = {
    messages,
    citations,
    queryRewrites,
    tokenUsage,
    processingMetadata,
    isStreaming,
    sessionId
  };

  return { 
    ...chatResponse,
    isLoading, 
    sendMessage, 
    clearMessages,
    startNewSession
  };
}
