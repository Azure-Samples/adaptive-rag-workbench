import { useState, useCallback, useEffect } from 'react';
import { useAuth } from '../auth/AuthContext';
import { apiService } from '../services/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  // Metadata for assistant messages
  citations?: Citation[];
  queryRewrites?: string[];
  tokenUsage?: TokenUsage;
  processingMetadata?: ProcessingMetadata;
  tracingInfo?: TracingInfo;
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

interface TracingInfo {
  thread_id?: string;
  run_id?: string;
  agent_id?: string;
  status?: string;
  created_at?: string;
  completed_at?: string;
}

interface ChatResponse {
  messages: Message[];
  citations: Citation[];
  queryRewrites: string[];
  tokenUsage?: TokenUsage;
  processingMetadata?: ProcessingMetadata;
  tracingInfo?: TracingInfo;
  isStreaming: boolean;
  sessionId: string;
}


export function useChatStream(mode: string, enableSessions: boolean = true, onModeChange?: (mode: string) => void) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [queryRewrites, setQueryRewrites] = useState<string[]>([]);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | undefined>();
  const [processingMetadata, setProcessingMetadata] = useState<ProcessingMetadata | undefined>();
  const [tracingInfo, setTracingInfo] = useState<TracingInfo | undefined>();
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const { getAccessToken } = useAuth();

  // Add debugging for sessionId changes
  useEffect(() => {
    console.log(`SessionId state changed to: "${sessionId}"`);
  }, [sessionId]);

  useEffect(() => {
    console.log(`useChatStream useEffect - mode: ${mode}, enableSessions: ${enableSessions}`);
    if (enableSessions) {
      const storedSessionId = localStorage.getItem(`chat_session_${mode}`);
      console.log(`Stored session ID for mode ${mode}:`, storedSessionId);
      if (storedSessionId) {
        console.log(`Setting session ID from storage: ${storedSessionId}`);
        setSessionId(storedSessionId);
        loadSessionHistory(storedSessionId);
      } else {
        const newSessionId = generateSessionId();
        console.log(`Generated new session ID: ${newSessionId}`);
        setSessionId(newSessionId);
        localStorage.setItem(`chat_session_${mode}`, newSessionId);
      }
    } else {
      // For non-session mode, use a temporary session ID but don't persist or load history
      const tempSessionId = `temp_${Date.now()}`;
      console.log(`Using temporary session ID: ${tempSessionId}`);
      setSessionId(tempSessionId);
      setMessages([]);
    }
  }, [mode, enableSessions]);

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
        const sessionMode = data.mode || 'fast-rag';
        
        console.log('Loading session history:', sessionMessages.length, 'messages', 'mode:', sessionMode);
        
        // Update the mode if callback is provided and mode is different
        if (onModeChange && sessionMode !== mode) {
          console.log('Switching mode from', mode, 'to', sessionMode);
          onModeChange(sessionMode);
        }
        
        const convertedMessages: Message[] = sessionMessages.map((msg: any) => ({
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.timestamp),
          // Include metadata for assistant messages
          citations: msg.citations || undefined,
          queryRewrites: msg.query_rewrites || undefined,
          tokenUsage: msg.token_usage || undefined,
          processingMetadata: msg.processing_metadata || undefined,
          tracingInfo: msg.tracing_info || undefined
        }));
        
        console.log('Converted messages:', convertedMessages);
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
          if (lastAssistantMessage.tracing_info) {
            setTracingInfo(lastAssistantMessage.tracing_info);
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
    setTracingInfo(undefined);

    try {
      // Get access token (will be 'demo-token' in demo mode)
      const token = await getAccessToken();
      
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const requestBody = { 
        prompt: content,
        mode: mode,
        session_id: sessionId,
        conversation_history: messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      };
      
      console.log(`Submitting message with sessionId: "${sessionId}", enableSessions: ${enableSessions}, mode: ${mode}`);
      console.log('Request body:', requestBody);

      const response = await fetch(`${apiService.baseUrl}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      let assistantMessage = '';
      let messageIndex = -1;
      let currentCitations: Citation[] = [];
      let currentQueryRewrites: string[] = [];
      let currentTokenUsage: TokenUsage | undefined;
      let currentProcessingMetadata: ProcessingMetadata | undefined;
      let currentTracingInfo: TracingInfo | undefined;

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
                        timestamp: new Date(),
                        citations: currentCitations,
                        queryRewrites: currentQueryRewrites,
                        tokenUsage: currentTokenUsage,
                        processingMetadata: currentProcessingMetadata,
                        tracingInfo: currentTracingInfo
                      });
                    } else {
                      const existingMessage = newMessages[messageIndex];
                      newMessages[messageIndex] = {
                        role: existingMessage?.role || 'assistant',
                        content: assistantMessage,
                        timestamp: existingMessage?.timestamp || new Date(),
                        citations: currentCitations,
                        queryRewrites: currentQueryRewrites,
                        tokenUsage: currentTokenUsage,
                        processingMetadata: currentProcessingMetadata,
                        tracingInfo: currentTracingInfo
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
                        timestamp: new Date(),
                        citations: currentCitations,
                        queryRewrites: currentQueryRewrites,
                        tokenUsage: currentTokenUsage,
                        processingMetadata: currentProcessingMetadata,
                        tracingInfo: currentTracingInfo
                      });
                    } else {
                      const existingMessage = newMessages[messageIndex];
                      newMessages[messageIndex] = {
                        role: existingMessage?.role || 'assistant',
                        content: assistantMessage,
                        timestamp: existingMessage?.timestamp || new Date(),
                        citations: currentCitations,
                        queryRewrites: currentQueryRewrites,
                        tokenUsage: currentTokenUsage,
                        processingMetadata: currentProcessingMetadata,
                        tracingInfo: currentTracingInfo
                      };
                    }
                    
                    return newMessages;
                  });
                  
                  // Set streaming to false since we have the complete answer
                  setIsStreaming(false);
                }
                
                if (data.type === 'citations' && data.citations) {
                  currentCitations = data.citations;
                  setCitations(data.citations);
                }
                
                if (data.type === 'query_rewrites' && data.rewrites) {
                  currentQueryRewrites = data.rewrites;
                  setQueryRewrites(data.rewrites);
                }
                
                if (data.type === 'token_usage' && data.usage) {
                  currentTokenUsage = data.usage;
                  setTokenUsage(data.usage);
                }
                
                if (data.type === 'metadata') {
                  // Handle session_id updates from backend
                  if (data.session_id && data.session_id !== sessionId) {
                    setSessionId(data.session_id);
                    // Update localStorage if sessions are enabled
                    if (enableSessions) {
                      localStorage.setItem(`chat_session_${mode}`, data.session_id);
                    }
                  }
                  
                  // Handle processing metadata
                  if (data.processing) {
                    currentProcessingMetadata = data.processing;
                    setProcessingMetadata(data.processing);
                  }
                }
                
                if (data.type === 'tracing_info' && data.tracing) {
                  currentTracingInfo = data.tracing;
                  setTracingInfo(data.tracing);
                }
                
                if (data.done) {
                  setIsStreaming(false);
                  // Final update with all metadata
                  setMessages(prev => {
                    const newMessages = [...prev];
                    if (messageIndex >= 0 && newMessages[messageIndex]) {
                      const existingMessage = newMessages[messageIndex];
                      newMessages[messageIndex] = {
                        ...existingMessage,
                        citations: currentCitations,
                        queryRewrites: currentQueryRewrites,
                        tokenUsage: currentTokenUsage,
                        processingMetadata: currentProcessingMetadata,
                        tracingInfo: currentTracingInfo
                      };
                    }
                    return newMessages;
                  });
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
  }, [mode, getAccessToken, sessionId, enableSessions, messages]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setCitations([]);
    setQueryRewrites([]);
    setTokenUsage(undefined);
    setProcessingMetadata(undefined);
    setTracingInfo(undefined);
  }, []);

  const startNewSession = useCallback(() => {
    if (!enableSessions) return;
    
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    localStorage.setItem(`chat_session_${mode}`, newSessionId);
    clearMessages();
  }, [mode, clearMessages, enableSessions]);

  const chatResponse: ChatResponse = {
    messages,
    citations,
    queryRewrites,
    tokenUsage,
    processingMetadata,
    tracingInfo,
    isStreaming,
    sessionId: enableSessions ? sessionId : '' // Don't expose session ID if sessions disabled
  };

  const switchSession = async (newSessionId: string) => {
    if (!enableSessions) return;
    
    setSessionId(newSessionId);
    localStorage.setItem(`chat_session_${mode}`, newSessionId);
    await loadSessionHistory(newSessionId);
  };

  return { 
    ...chatResponse,
    isLoading, 
    sendMessage, 
    clearMessages,
    startNewSession: enableSessions ? startNewSession : undefined,
    switchSession: enableSessions ? switchSession : undefined
  };
}
