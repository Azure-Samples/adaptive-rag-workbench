import React, { useState } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { 
  Loader2, 
  Send, 
  Zap, 
  Brain, 
  Microscope, 
  Mic, 
  Globe, 
  GraduationCap, 
  Users, 
  Building2,
  ChevronDown,
  ChevronUp,
  ChevronRight
} from 'lucide-react';

type RAGMode = 'fast-rag' | 'agentic-rag' | 'deep-research-rag';

interface MicrosoftInputProps {
  query: string;
  setQuery: (query: string) => void;
  selectedMode: RAGMode;
  setSelectedMode: (mode: RAGMode) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  showSourceSelector?: boolean;
  placeholder?: string;
  hideExampleQuestions?: boolean;
}

interface Source {
  id: string;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  enabled: boolean;
}

interface Model {
  id: string;
  name: string;
  description?: string;
}

export function MicrosoftInput({
  query,
  setQuery,
  selectedMode,
  setSelectedMode,
  onSubmit,
  isLoading,
  showSourceSelector = false,
  placeholder = "Ask anything...",
  hideExampleQuestions = false
}: MicrosoftInputProps) {
  const [selectedModel, setSelectedModel] = useState('gpt-4-1');
  const [showMoreModels, setShowMoreModels] = useState(false);
  const [sources, setSources] = useState<Source[]>([
    {
      id: 'web',
      name: 'Web',
      icon: Globe,
      description: 'Search across the entire Internet',
      enabled: true
    },
    {
      id: 'academic',
      name: 'Academic',
      icon: GraduationCap,
      description: 'Search academic papers',
      enabled: false
    },
    {
      id: 'finance',
      name: 'Finance',
      icon: Building2,
      description: 'Search SEC filings',
      enabled: true
    },
    {
      id: 'social',
      name: 'Social',
      icon: Users,
      description: 'Discussions and opinions',
      enabled: false
    }
  ]);

  const ragModes = [
    {
      id: 'fast-rag' as RAGMode,
      name: 'Fast',
      icon: Zap,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-50',
      borderColor: 'border-emerald-200'
    },
    {
      id: 'agentic-rag' as RAGMode,
      name: 'Agentic',
      icon: Brain,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200'
    },
    {
      id: 'deep-research-rag' as RAGMode,
      name: 'Deep Research',
      icon: Microscope,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
      borderColor: 'border-purple-200'
    }
  ];

  const primaryModels: Model[] = [
    { id: 'gpt-4-1', name: 'GPT-4.1', description: 'Powerful, large model for complex challenges' },
    { id: 'gpt-o3', name: 'gpt-o3', description: 'Smart, efficient model for reasoning' },
    { id: 'gpt-o4-mini', name: 'gpt-o4-mini', description: 'Fastest model for reasoning' }
  ];
  
  const additionalModels: Model[] = [
    { id: 'claude-sonnet-3-7', name: 'Claude Sonnet 3.7 on Azure Databricks' },
    { id: 'gemini-2-5-pro', name: 'Gemini-2.5-pro via APIM' }
  ];

  const getDynamicExampleQueries = (mode: RAGMode): string[] => {
    const baseQueries = {
      'fast-rag': [
        "What are Microsoft's current cloud revenue figures?",
        "How did Microsoft perform in Q3 2024 earnings?",
        "What is Microsoft's current stock price and market cap?"
      ],
      'agentic-rag': [
        "Compare Microsoft's AI strategy to Google and Amazon",
        "Analyze Microsoft's cloud transformation and competitive positioning",
        "What regulatory challenges is Microsoft facing with AI and how are they addressing them?"
      ],
      'deep-research-rag': [
        "Comprehensive analysis of Microsoft's AI investments and market positioning in 2024",
        "Deep dive into Microsoft's cloud infrastructure growth and enterprise adoption",
        "Research Microsoft's sustainability initiatives impact on long-term business strategy"
      ]
    };
    return baseQueries[mode] || baseQueries['fast-rag'];
  };

  const currentExampleQueries = getDynamicExampleQueries(selectedMode);

  const toggleSource = (sourceId: string) => {
    setSources(prev => prev.map(source => 
      source.id === sourceId 
        ? { ...source, enabled: !source.enabled }
        : source
    ));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSubmit(e);
    }
  };

  const handleExampleClick = (example: string) => {
    setQuery(example);
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-4">
      {/* Main Input Container */}
      <div className="relative bg-white rounded-2xl border border-gray-200 shadow-sm hover:shadow-md transition-all duration-200">
        <form onSubmit={handleSubmit}>
          {/* Textarea */}
          <Textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            className="w-full min-h-[120px] p-4 pb-16 resize-none border-0 focus:ring-0 rounded-2xl text-base placeholder:text-gray-500 bg-transparent"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />

          {/* Bottom Controls Bar */}
          <div className="absolute bottom-0 left-0 right-0 p-3 flex items-center justify-between border-t border-gray-100">
            {/* Left Side - RAG Mode Buttons */}
            <div className="flex items-center gap-1">
              {ragModes.map((mode) => {
                const Icon = mode.icon;
                const isSelected = selectedMode === mode.id;
                return (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => setSelectedMode(mode.id)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                      isSelected
                        ? `${mode.color} ${mode.bgColor} ${mode.borderColor} border`
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{mode.name}</span>
                  </button>
                );
              })}
            </div>

            {/* Right Side - Controls */}
            <div className="flex items-center gap-2">
              {/* Model Picker - Simplified Perplexity Style */}
              <div className="relative">
                <Select 
                  value={selectedModel} 
                  onValueChange={(value) => {
                    if (value !== 'more-models') {
                      setSelectedModel(value);
                      setShowMoreModels(false);
                    }
                  }}
                >
                  <SelectTrigger className="w-auto min-w-[140px] h-8 px-3 text-sm font-medium border border-gray-300 rounded-md transition-colors duration-200 focus:ring-1 focus:ring-gray-400 focus:ring-offset-1 bg-white">
                    <div className="flex items-center justify-between w-full">
                      <SelectValue />
                      <ChevronDown className="h-3.5 w-3.5 ml-1" />
                    </div>
                  </SelectTrigger>
                  <SelectContent className="w-64 p-0 border border-gray-300 shadow-md">
                    <div className="py-1 px-2">
                      {primaryModels.map((model) => (
                        <SelectItem key={model.id} value={model.id} className="py-1.5 px-3 hover:bg-gray-100 rounded-md cursor-pointer">
                          <div className="flex items-center justify-between w-full">
                            <span className="font-medium text-sm">{model.name}</span>
                          </div>
                        </SelectItem>
                      ))}
                      <div 
                        className="relative py-1.5 px-3 hover:bg-gray-100 rounded-md cursor-pointer border-t border-gray-200 mt-1 group"
                        onMouseEnter={() => {
                          console.log('Mouse entered More models');
                          setShowMoreModels(true);
                        }}
                        onMouseLeave={() => {
                          console.log('Mouse left More models');
                          setTimeout(() => setShowMoreModels(false), 150);
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-700">More models</span>
                          <ChevronRight className="h-3.5 w-3.5" />
                        </div>
                        
                        {/* Submenu for additional models */}
                        {showMoreModels && (
                          <div 
                            className="absolute left-full top-0 ml-1 w-64 bg-white border border-gray-300 shadow-lg rounded-md z-[60]"
                            onMouseEnter={() => {
                              console.log('Mouse entered submenu');
                              setShowMoreModels(true);
                            }}
                            onMouseLeave={() => {
                              console.log('Mouse left submenu');
                              setShowMoreModels(false);
                            }}
                          >
                            <div className="py-1 px-2">
                              {additionalModels.map((model) => (
                                <div
                                  key={model.id}
                                  className="py-1.5 px-3 hover:bg-gray-100 rounded-md cursor-pointer"
                                  onClick={() => {
                                    setSelectedModel(model.id);
                                    setShowMoreModels(false);
                                  }}
                                >
                                  <span className="font-medium text-sm">{model.name}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </SelectContent>
                </Select>
              </div>

              {/* Source Selector (only for QA with Verification) */}
              {showSourceSelector && (
                <div className="relative">
                  <Select>
                    <SelectTrigger className="w-24 h-8 text-xs border-gray-200 hover:border-gray-300">
                      <span className="text-xs">Sources</span>
                      <ChevronDown className="h-3 w-3" />
                    </SelectTrigger>
                    <SelectContent className="w-64">
                      <div className="p-2 space-y-2">
                        <div className="text-xs font-medium text-gray-700 mb-2">Set sources for search</div>
                        {sources.map((source) => {
                          const Icon = source.icon;
                          return (
                            <div
                              key={source.id}
                              className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                              onClick={() => toggleSource(source.id)}
                            >
                              <div className="flex items-center gap-2">
                                <Icon className="h-4 w-4 text-gray-600" />
                                <div>
                                  <div className="text-sm font-medium">{source.name}</div>
                                  <div className="text-xs text-gray-500">{source.description}</div>
                                </div>
                              </div>
                              <div className={`w-4 h-4 rounded-full border-2 ${
                                source.enabled 
                                  ? 'bg-blue-500 border-blue-500' 
                                  : 'border-gray-300'
                              }`}>
                                {source.enabled && (
                                  <div className="w-2 h-2 bg-white rounded-full m-0.5" />
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Voice Dictation Button */}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                title="Voice dictation (coming soon)"
              >
                <Mic className="h-4 w-4" />
              </Button>

              {/* Submit Button */}
              <Button
                type="submit"
                disabled={isLoading || !query.trim()}
                className="h-8 px-3 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" />
                )}
              </Button>
            </div>
          </div>
        </form>
      </div>

      {/* Dynamic Example Queries - Hidden during loading/generation */}
      {currentExampleQueries.length > 0 && !hideExampleQuestions && !isLoading && (
        <div className="space-y-3">
          <div className="text-sm text-gray-600">
            Try asking about Microsoft:
          </div>
          <div className="grid gap-2">
            {currentExampleQueries.map((example, idx) => (
              <button
                key={idx}
                onClick={() => handleExampleClick(example)}
                className="text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-xl border border-gray-200 transition-all duration-200 hover:shadow-sm text-sm text-gray-700 hover:text-gray-900"
              >
                <span className="flex items-start gap-2">
                  <span className="text-gray-400 mt-0.5">💡</span>
                  <span>"{example}"</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
