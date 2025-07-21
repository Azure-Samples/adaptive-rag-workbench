import { useState, useEffect } from 'react';
import { ScrollArea } from './ui/scroll-area';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { 
  History, 
  MessageSquare, 
  Clock, 
  ChevronDown, 
  ChevronUp, 
  Plus,
  RefreshCw,
  Hash
} from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../auth/AuthContext';
import { apiService } from '../services/api';
import { 
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from './ui/collapsible';

interface SessionSummary {
  session_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  mode: string;
  last_user_message: string;
  total_tokens: number;
  session_title: string;
}

interface SessionHistoryProps {
  currentSessionId?: string;
  onSessionSelect: (sessionId: string) => void;
  onNewSession: () => void;
  mode: string;
}

export function SessionHistory({ 
  currentSessionId, 
  onSessionSelect, 
  onNewSession,
  mode 
}: SessionHistoryProps) {
  const { theme } = useTheme();
  const { getAccessToken } = useAuth();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selectedSession, setSelectedSession] = useState<string | null>(currentSessionId || null);

  const loadSessions = async () => {
    setIsLoading(true);
    try {
      const token = await getAccessToken();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${apiService.baseUrl}/chat/sessions?limit=50&mode=${mode}`, {
        method: 'GET',
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        setSessions(data.sessions || []);
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [mode]);

  useEffect(() => {
    if (currentSessionId && currentSessionId !== selectedSession) {
      setSelectedSession(currentSessionId);
    }
  }, [currentSessionId]);

  const handleSessionClick = (sessionId: string) => {
    setSelectedSession(sessionId);
    onSessionSelect(sessionId);
  };

  const handleNewSession = () => {
    setSelectedSession(null);
    onNewSession();
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
      
      if (diffInHours < 1) {
        return 'Just now';
      } else if (diffInHours < 24) {
        return `${Math.floor(diffInHours)}h ago`;
      } else if (diffInHours < 168) { // 7 days
        return `${Math.floor(diffInHours / 24)}d ago`;
      } else {
        return date.toLocaleDateString();
      }
    } catch {
      return 'Unknown';
    }
  };

  const getModeColor = (sessionMode: string) => {
    switch (sessionMode) {
      case 'fast-rag':
        return theme === 'dark' ? 'bg-emerald-900 text-emerald-100' : 'bg-emerald-100 text-emerald-800';
      case 'agentic-rag':
        return theme === 'dark' ? 'bg-blue-900 text-blue-100' : 'bg-blue-100 text-blue-800';
      case 'deep-research-rag':
        return theme === 'dark' ? 'bg-purple-900 text-purple-100' : 'bg-purple-100 text-purple-800';
      default:
        return theme === 'dark' ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600';
    }
  };

  return (
    <div className={`h-full flex flex-col ${
      theme === 'dark' 
        ? 'bg-gray-800 border-gray-700' 
        : theme === 'customer' 
          ? 'bg-customer-50 border-customer-200' 
          : 'bg-white border-gray-200'
    } border-r`}>
      {/* Header */}
      <Collapsible open={!isCollapsed} onOpenChange={setIsCollapsed}>
        <div className="p-4 border-b border-inherit">
          <div className="flex items-center justify-between">
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="p-0 h-auto">
                <div className="flex items-center gap-2">
                  <History className="h-4 w-4" />
                  <span className="font-medium">Session History</span>
                  {isCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
                </div>
              </Button>
            </CollapsibleTrigger>
            
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={loadSessions}
                disabled={isLoading}
                className="h-7 w-7 p-0"
              >
                <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                onClick={handleNewSession}
                className="h-7 w-7 p-0"
              >
                <Plus className="h-3 w-3" />
              </Button>
            </div>
          </div>
        </div>

        <CollapsibleContent>
          {/* Session List */}
          <ScrollArea className="flex-1 h-[calc(100vh-200px)]">
            <div className="p-2 space-y-2">
              {isLoading && (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                  <span className="text-sm text-gray-500">Loading sessions...</span>
                </div>
              )}

              {!isLoading && sessions.length === 0 && (
                <div className="text-center py-8">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2 text-gray-400" />
                  <p className="text-sm text-gray-500">No sessions yet</p>
                  <p className="text-xs text-gray-400 mt-1">Start a conversation to create your first session</p>
                </div>
              )}

              {sessions.map((session) => (
                <Button
                  key={session.session_id}
                  variant={selectedSession === session.session_id ? "default" : "ghost"}
                  className={`w-full p-3 h-auto text-left justify-start flex-col items-start space-y-2 ${
                    selectedSession === session.session_id
                      ? theme === 'dark'
                        ? 'bg-gray-700 border-gray-600'
                        : theme === 'customer'
                          ? 'bg-customer-100 border-customer-300'
                          : 'bg-gray-100 border-gray-300'
                      : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                  }`}
                  onClick={() => handleSessionClick(session.session_id)}
                >
                  {/* Session Title */}
                  <div className="w-full">
                    <h4 className="text-sm font-medium truncate">
                      {session.session_title}
                    </h4>
                  </div>

                  {/* Last Message Preview */}
                  <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2 w-full text-left">
                    {session.last_user_message}
                  </p>

                  {/* Metadata */}
                  <div className="flex items-center justify-between w-full text-xs">
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant="secondary" 
                        className={`text-xs px-1.5 py-0.5 ${getModeColor(session.mode)}`}
                      >
                        {session.mode.replace('-rag', '')}
                      </Badge>
                      
                      <div className="flex items-center gap-1 text-gray-500">
                        <MessageSquare className="h-3 w-3" />
                        <span>{session.message_count}</span>
                      </div>
                      
                      {session.total_tokens > 0 && (
                        <div className="flex items-center gap-1 text-gray-500">
                          <Hash className="h-3 w-3" />
                          <span>{session.total_tokens.toLocaleString()}</span>
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-1 text-gray-500">
                      <Clock className="h-3 w-3" />
                      <span>{formatDate(session.updated_at)}</span>
                    </div>
                  </div>
                </Button>
              ))}
            </div>
          </ScrollArea>

          {/* Footer */}
          {sessions.length > 0 && (
            <div className="p-3 border-t border-inherit">
              <div className="text-xs text-gray-500 text-center">
                {sessions.length} session{sessions.length !== 1 ? 's' : ''} • Mode: {mode.replace('-rag', '')}
              </div>
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
