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

interface TracingInfo {
  thread_id?: string;
  run_id?: string;
  agent_id?: string;
  status?: string;
  created_at?: string;
  completed_at?: string;
}

interface SessionState {
  messages: Message[];
  citations: Citation[];
  queryRewrites: string[];
  tokenUsage?: TokenUsage;
  processingMetadata?: ProcessingMetadata;
  tracingInfo?: TracingInfo;
  isStreaming: boolean;
  sessionId: string;
}

export function useSessionManager(mode: string) {
  const [sessionStates, setSessionStates] = useState<Record<string, SessionState>>({});
  const [currentSessionId, setCurrentSessionId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const { getAccessToken } = useAuth();

  const generateSessionId = (): string => {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  };

  // Initialize current session
  useEffect(() => {
    const storedSessionId = localStorage.getItem(`chat_session_${mode}`);
    if (storedSessionId) {
      setCurrentSessionId(storedSessionId);
      loadSessionHistory(storedSessionId);
    } else {
      const newSessionId = generateSessionId();
      setCurrentSessionId(newSessionId);
      localStorage.setItem(`chat_session_${mode}`, newSessionId);
      // Initialize empty session state
      setSessionStates(prev => ({
        ...prev,
        [newSessionId]: {
          messages: [],
          citations: [],
          queryRewrites: [],
          isStreaming: false,
          sessionId: newSessionId
        }
      }));
    }
  }, [mode]);

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
        
        const lastAssistantMessage = sessionMessages
          .filter((msg: any) => msg.role === 'assistant')
          .pop();
        
        const sessionState: SessionState = {
          messages: convertedMessages,
          citations: lastAssistantMessage?.citations || [],
          queryRewrites: [],
          tokenUsage: lastAssistantMessage?.token_usage,
          processingMetadata: lastAssistantMessage?.processing_metadata,
          tracingInfo: lastAssistantMessage?.tracing_info,
          isStreaming: false,
          sessionId
        };

        setSessionStates(prev => ({
          ...prev,
          [sessionId]: sessionState
        }));
      }
    } catch (error) {
      console.warn('Failed to load session history:', error);
    }
  };

  const switchToSession = useCallback((sessionId: string) => {
    if (sessionId === currentSessionId) return;
    
    setCurrentSessionId(sessionId);
    localStorage.setItem(`chat_session_${mode}`, sessionId);
    
    // Load session if not already loaded
    if (!sessionStates[sessionId]) {
      loadSessionHistory(sessionId);
    }
  }, [currentSessionId, mode, sessionStates]);

  const startNewSession = useCallback(() => {
    const newSessionId = generateSessionId();
    setCurrentSessionId(newSessionId);
    localStorage.setItem(`chat_session_${mode}`, newSessionId);
    
    // Initialize empty session state
    setSessionStates(prev => ({
      ...prev,
      [newSessionId]: {
        messages: [],
        citations: [],
        queryRewrites: [],
        isStreaming: false,
        sessionId: newSessionId
      }
    }));
  }, [mode]);

  const updateCurrentSession = useCallback((updates: Partial<SessionState>) => {
    if (!currentSessionId) return;
    
    setSessionStates(prev => ({
      ...prev,
      [currentSessionId]: {
        ...prev[currentSessionId],
        ...updates
      }
    }));
  }, [currentSessionId]);

  const sendMessage = useCallback(async (content: string) => {
    if (!currentSessionId) return;

    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: new Date()
    };

    // Add user message immediately
    updateCurrentSession({
      messages: [...(sessionStates[currentSessionId]?.messages || []), userMessage]
    });

    setIsLoading(true);
    updateCurrentSession({ isStreaming: true });
    
    // Clear previous response data
    updateCurrentSession({
      citations: [],
      queryRewrites: [],
      tokenUsage: undefined,
      processingMetadata: undefined,
      tracingInfo: undefined
    });

    try {
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
          session_id: currentSessionId
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
                  
                  const currentState = sessionStates[currentSessionId];
                  const currentMessages = currentState?.messages || [];
                  
                  if (messageIndex === -1) {
                    messageIndex = currentMessages.length;
                    const newMessages = [...currentMessages, {
                      role: 'assistant' as const,
                      content: assistantMessage,
                      timestamp: new Date()
                    }];
                    updateCurrentSession({ messages: newMessages });
                  } else {
                    const newMessages = [...currentMessages];
                    newMessages[messageIndex] = {
                      role: 'assistant' as const,
                      content: assistantMessage,
                      timestamp: newMessages[messageIndex]?.timestamp || new Date()
                    };
                    updateCurrentSession({ messages: newMessages });
                  }
                }
                
                // Handle complete answer for agentic responses
                if (data.type === 'answer_complete' && data.answer) {
                  assistantMessage = data.answer;
                  
                  const currentState = sessionStates[currentSessionId];
                  const currentMessages = currentState?.messages || [];
                  
                  if (messageIndex === -1) {
                    messageIndex = currentMessages.length;
                    const newMessages = [...currentMessages, {
                      role: 'assistant' as const,
                      content: assistantMessage,
                      timestamp: new Date()
                    }];
                    updateCurrentSession({ messages: newMessages });
                  } else {
                    const newMessages = [...currentMessages];
                    newMessages[messageIndex] = {
                      role: 'assistant' as const,
                      content: assistantMessage,
                      timestamp: newMessages[messageIndex]?.timestamp || new Date()
                    };
                    updateCurrentSession({ messages: newMessages });
                  }
                  
                  updateCurrentSession({ isStreaming: false });
                }
                
                if (data.type === 'citations' && data.citations) {
                  updateCurrentSession({ citations: data.citations });
                }
                
                if (data.type === 'query_rewrites' && data.rewrites) {
                  updateCurrentSession({ queryRewrites: data.rewrites });
                }
                
                if (data.type === 'token_usage' && data.usage) {
                  updateCurrentSession({ tokenUsage: data.usage });
                }
                
                if (data.type === 'metadata' && data.processing) {
                  updateCurrentSession({ processingMetadata: data.processing });
                }
                
                if (data.type === 'tracing_info' && data.tracing) {
                  updateCurrentSession({ tracingInfo: data.tracing });
                }
                
                if (data.done) {
                  updateCurrentSession({ isStreaming: false });
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
      const currentState = sessionStates[currentSessionId];
      const currentMessages = currentState?.messages || [];
      const errorMessage: Message = {
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error occurred'}`,
        timestamp: new Date()
      };
      updateCurrentSession({ 
        messages: [...currentMessages, errorMessage],
        isStreaming: false
      });
    } finally {
      setIsLoading(false);
      updateCurrentSession({ isStreaming: false });
    }
  }, [mode, getAccessToken, currentSessionId, sessionStates, updateCurrentSession]);

  const clearCurrentSession = useCallback(() => {
    if (!currentSessionId) return;
    
    updateCurrentSession({
      messages: [],
      citations: [],
      queryRewrites: [],
      tokenUsage: undefined,
      processingMetadata: undefined,
      tracingInfo: undefined
    });
  }, [currentSessionId, updateCurrentSession]);

  // Get current session state
  const currentSession = currentSessionId ? sessionStates[currentSessionId] : null;

  return {
    // Session management
    currentSessionId,
    switchToSession,
    startNewSession,
    
    // Current session data
    messages: currentSession?.messages || [],
    citations: currentSession?.citations || [],
    queryRewrites: currentSession?.queryRewrites || [],
    tokenUsage: currentSession?.tokenUsage,
    processingMetadata: currentSession?.processingMetadata,
    tracingInfo: currentSession?.tracingInfo,
    isStreaming: currentSession?.isStreaming || false,
    
    // Actions
    isLoading,
    sendMessage,
    clearCurrentSession
  };
}
