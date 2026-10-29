import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  queryAssistant,
  getAssistantStatus,
} from '../../services/assistantService';
import {
  ChatMessage,
  AssistantStatusResponse,
} from '../../types/assistant';
import {
  Bot,
  Send,
  Sparkles,
  RefreshCw,
  Trash2,
  AlertTriangle,
  TrendingUp,
  BedDouble,
  ShieldAlert,
  ArrowRightLeft,
  Clock,
  Info,
  ChevronRight,
} from 'lucide-react';
import { cn } from '../../utils/cn';

const STARTER_QUESTIONS = [
  {
    title: 'Current Bed Availability',
    question: 'How many beds are currently available?',
    icon: BedDouble,
    category: 'CURRENT_AVAILABILITY',
    color: 'from-sky-500/10 to-blue-500/10 border-sky-200 dark:border-sky-800 text-sky-700 dark:text-sky-300',
  },
  {
    title: 'Highest Predicted Occupancy',
    question: 'Which wards have the highest predicted occupancy next week?',
    icon: TrendingUp,
    category: 'SARIMA_FORECAST',
    color: 'from-indigo-500/10 to-purple-500/10 border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300',
  },
  {
    title: 'Explain High-Risk Alerts',
    question: 'Explain the latest high-risk alerts and why they were triggered.',
    icon: ShieldAlert,
    category: 'CAPACITY_RISK_ALERTS',
    color: 'from-amber-500/10 to-orange-500/10 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300',
  },
  {
    title: '7-Day Capacity Risk',
    question: 'Summarize the next seven days of capacity risk for management.',
    icon: AlertTriangle,
    category: 'MANAGEMENT_SUMMARY',
    color: 'from-rose-500/10 to-red-500/10 border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300',
  },
  {
    title: 'Transfer Recommendations',
    question: 'Show existing transfer recommendations and suitable beds.',
    icon: ArrowRightLeft,
    category: 'TRANSFER_DECISION_SUPPORT',
    color: 'from-emerald-500/10 to-teal-500/10 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300',
  },
];

export const AssistantPage: React.FC = () => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const saved = sessionStorage.getItem('assistant_chat_history');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          return parsed.map((m: Partial<ChatMessage> & { content?: unknown }) => {
            let safeContent = '';
            if (typeof m.content === 'string') {
              safeContent = m.content;
            } else if (Array.isArray(m.content)) {
              safeContent = (m.content as unknown[])
                .map((item) =>
                  typeof item === 'object' && item !== null && 'msg' in item
                    ? String((item as { msg: unknown }).msg)
                    : typeof item === 'object' && item !== null
                    ? JSON.stringify(item)
                    : String(item)
                )
                .join('; ');
            } else if (typeof m.content === 'object' && m.content !== null) {
              safeContent =
                'msg' in m.content
                  ? String((m.content as { msg: unknown }).msg)
                  : JSON.stringify(m.content);
            } else {
              safeContent = String(m.content ?? '');
            }
            return {
              ...m,
              content: safeContent,
            } as ChatMessage;
          });
        }
      } catch {
        return [];
      }
    }
    return [];
  });
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [statusInfo, setStatusInfo] = useState<AssistantStatusResponse | null>(null);
  const activeHospitalId = user?.hospital_id || 1;

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    sessionStorage.setItem('assistant_chat_history', JSON.stringify(messages));
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const status = await getAssistantStatus();
        setStatusInfo(status);
      } catch {
        // Fallback status
        setStatusInfo({
          enabled: true,
          provider: 'deterministic',
          model: 'rule-based synthesizer',
          has_api_key: false,
          supported_categories: [],
          disclaimer: 'Decision support tool only.',
        });
      }
    };
    fetchStatus();
  }, []);

  const handleSendMessage = async (textToSend?: string) => {
    const queryText = (textToSend || inputMessage).trim();
    if (!queryText || isLoading) return;

    const userMsgId = `user-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: queryText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    // Build bounded conversation history (exclude error messages, truncate length to safe limit)
    const historyPayload = messages
      .filter((m) => !m.isError && (m.role === 'user' || m.role === 'assistant'))
      .slice(-6)
      .map((m) => ({
        role: m.role,
        content: m.content.slice(0, 2000),
        timestamp: new Date().toISOString(),
      }));

    try {
      const response = await queryAssistant({
        message: queryText,
        conversation_history: historyPayload,
        hospital_id: activeHospitalId,
      });

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        source_category: response.source_category,
        evidence: response.evidence,
        data_timestamp: response.data_timestamp,
        is_forecast_estimate: response.is_forecast_estimate,
        forecast_target_date: response.forecast_target_date,
        warnings: response.warnings,
        provider_status: response.provider_status,
        suggested_followups: response.suggested_followups,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      let errorText = 'A system error occurred while retrieving hospital data. Please check your network connection or try again.';
      if (err && typeof err === 'object') {
        const axiosErr = err as { response?: { data?: unknown }; message?: string };
        const responseData = axiosErr.response?.data;
        if (responseData && typeof responseData === 'object') {
          const resObj = responseData as Record<string, unknown>;
          const detail = resObj.detail ?? resObj.message ?? responseData;
          if (typeof detail === 'string') {
            errorText = detail;
          } else if (Array.isArray(detail)) {
            errorText = detail
              .map((item) =>
                typeof item === 'object' && item !== null && 'msg' in item
                  ? String((item as { msg: unknown }).msg)
                  : typeof item === 'object' && item !== null
                  ? JSON.stringify(item)
                  : String(item)
              )
              .join('; ');
          } else if (typeof detail === 'object' && detail !== null) {
            errorText =
              'msg' in detail
                ? String((detail as { msg: unknown }).msg)
                : JSON.stringify(detail);
          }
        } else if (typeof responseData === 'string') {
          errorText = responseData;
        } else if (axiosErr.message) {
          errorText = String(axiosErr.message);
        }
      }

      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: errorText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    sessionStorage.removeItem('assistant_chat_history');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatCategoryBadge = (category?: string) => {
    switch (category) {
      case 'CURRENT_AVAILABILITY':
        return { label: 'Live Bed Availability', color: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 border-sky-200 dark:border-sky-800' };
      case 'SARIMA_FORECAST':
        return { label: 'SARIMA Forecast Model', color: 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border-purple-200 dark:border-purple-800' };
      case 'CAPACITY_RISK_ALERTS':
        return { label: 'Explainable Capacity Alert', color: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-200 dark:border-amber-800' };
      case 'OCCUPANCY_TRENDS':
        return { label: 'Historical Trend Analysis', color: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800' };
      case 'TRANSFER_DECISION_SUPPORT':
        return { label: 'Transfer Decision Support', color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800' };
      case 'MANAGEMENT_SUMMARY':
        return { label: 'Executive Management Summary', color: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border-blue-200 dark:border-blue-800' };
      default:
        return { label: 'Decision Support', color: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700' };
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] max-w-6xl mx-auto px-4 py-3">
      {/* Top Header Card */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 mb-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-600 via-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-md shadow-sky-500/20">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-slate-900 dark:text-white">
                AI Hospital Management Assistant
              </h1>
              <span className="px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded-full bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 border border-sky-300 dark:border-sky-800">
                Phase 17
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Conversational decision support grounded in live bed availability, historical trends, and SARIMA forecasts.
            </p>
          </div>
        </div>

        {/* Status Indicators & Controls */}
        <div className="flex items-center gap-2">
          {statusInfo && (
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 text-xs rounded-xl bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-medium">
                {statusInfo.has_api_key ? `Live ${statusInfo.provider.toUpperCase()}` : 'Deterministic Decision Support'}
              </span>
              <span className="text-[10px] opacity-75">({statusInfo.model})</span>
            </div>
          )}

          {messages.length > 0 && (
            <button
              onClick={handleClearChat}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-300 hover:text-rose-600 dark:hover:text-rose-400 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
              title="Clear conversation history"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear Chat</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Conversation Stream */}
      <div className="flex-1 overflow-y-auto px-1 py-2 space-y-4">
        {messages.length === 0 ? (
          /* Empty State / Welcome Screen */
          <div className="py-6 px-4 flex flex-col items-center text-center">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-white mb-4 shadow-lg shadow-sky-500/25">
              <Bot className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-1">
              How can I assist hospital operations today?
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-lg mb-6">
              Ask natural-language questions about ward occupancy, available beds, 7-day SARIMA forecasts,
              explainable capacity risks, or transfer decision support.
            </p>

            {/* Starter Suggestion Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 w-full max-w-3xl">
              {STARTER_QUESTIONS.map((item, idx) => {
                const IconComponent = item.icon;
                return (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(item.question)}
                    className={cn(
                      'flex flex-col text-left p-3.5 rounded-xl border bg-gradient-to-br transition-all duration-150 hover:scale-[1.02] hover:shadow-md group',
                      item.color
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <IconComponent className="w-5 h-5 transition-transform group-hover:scale-110" />
                      <ChevronRight className="w-4 h-4 opacity-40 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <span className="text-xs font-semibold text-slate-900 dark:text-white mb-1">
                      {item.title}
                    </span>
                    <span className="text-xs text-slate-600 dark:text-slate-300">
                      "{item.question}"
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          /* Message List */
          messages.map((msg) => {
            const isUser = msg.role === 'user';
            const badge = !isUser ? formatCategoryBadge(msg.source_category) : null;

            return (
              <div
                key={msg.id}
                className={cn('flex flex-col', isUser ? 'items-end' : 'items-start')}
              >
                {/* Role header & timestamp */}
                <div className="flex items-center gap-2 mb-1 px-1 text-[11px] text-slate-400">
                  <span className="font-semibold text-slate-600 dark:text-slate-300">
                    {isUser ? user?.full_name || 'Authorized Staff' : 'CareFlow AI Assistant'}
                  </span>
                  <span>•</span>
                  <span>{msg.timestamp}</span>
                </div>

                {/* Message Bubble Card */}
                <div
                  className={cn(
                    'max-w-[85%] sm:max-w-[78%] rounded-2xl px-4 py-3 shadow-xs text-sm',
                    isUser
                      ? 'bg-gradient-to-r from-sky-600 to-indigo-600 text-white rounded-tr-none'
                      : msg.isError
                      ? 'bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200 rounded-tl-none'
                      : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200 rounded-tl-none'
                  )}
                >
                  {/* Assistant Category Badge & Forecast Alert Banner */}
                  {!isUser && badge && (
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span
                        className={cn(
                          'px-2 py-0.5 text-[11px] font-semibold rounded-md border',
                          badge.color
                        )}
                      >
                        {badge.label}
                      </span>

                      {msg.is_forecast_estimate && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-md bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                          <TrendingUp className="w-3 h-3" />
                          <span>
                            Statistical Forecast Projection
                            {msg.forecast_target_date ? ` (${msg.forecast_target_date})` : ''}
                          </span>
                        </span>
                      )}
                    </div>
                  )}

                  {/* Main Message Text */}
                  <div className="whitespace-pre-line leading-relaxed font-normal">
                    {typeof msg.content === 'string'
                      ? msg.content
                      : typeof msg.content === 'object' && msg.content !== null && 'msg' in msg.content
                      ? String((msg.content as { msg: unknown }).msg)
                      : typeof msg.content === 'object' && msg.content !== null
                      ? JSON.stringify(msg.content)
                      : String(msg.content ?? '')}
                  </div>

                  {/* Structured Evidence Card (if provided) */}
                  {!isUser && msg.evidence && (
                    <div className="mt-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 text-xs">
                      <div className="flex items-center justify-between mb-2 pb-1 border-b border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400">
                        <span className="font-semibold uppercase tracking-wider text-[10px]">
                          Verified Backend Evidence
                        </span>
                        {msg.data_timestamp && (
                          <span className="flex items-center gap-1 text-[10px]">
                            <Clock className="w-3 h-3" />
                            {new Date(msg.data_timestamp).toLocaleString()}
                          </span>
                        )}
                      </div>

                      {/* Hospital Summary Breakdown */}
                      {msg.evidence.hospital_summary && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
                          <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                            <span className="block text-[10px] text-slate-400">Total Capacity</span>
                            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
                              {msg.evidence.hospital_summary.total_beds} beds
                            </span>
                          </div>
                          <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                            <span className="block text-[10px] text-slate-400">Occupied</span>
                            <span className="text-sm font-bold text-amber-600 dark:text-amber-400">
                              {msg.evidence.hospital_summary.occupied_beds} ({msg.evidence.hospital_summary.occupancy_percentage}%)
                            </span>
                          </div>
                          <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                            <span className="block text-[10px] text-slate-400">Available</span>
                            <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                              {msg.evidence.hospital_summary.available_beds} beds
                            </span>
                          </div>
                          <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                            <span className="block text-[10px] text-slate-400">Status</span>
                            <span className="text-sm font-bold text-sky-600 dark:text-sky-400">
                              {msg.evidence.hospital_summary.status}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Ward Summary Breakdown */}
                      {msg.evidence.ward && (
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                          <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                            <span className="block text-[10px] text-slate-400">Operational Beds</span>
                            <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
                              {msg.evidence.ward.operational_beds}
                            </span>
                          </div>
                          <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                            <span className="block text-[10px] text-slate-400">Occupancy Rate</span>
                            <span className="text-sm font-bold text-amber-600 dark:text-amber-400">
                              {msg.evidence.ward.occupancy_percentage}%
                            </span>
                          </div>
                          <div className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                            <span className="block text-[10px] text-slate-400">Available Beds</span>
                            <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                              {msg.evidence.ward.available_beds}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Warnings or Caveats Banner */}
                  {!isUser && (() => {
                    const filteredWarnings = (msg.warnings || []).filter(
                      (w) => typeof w !== 'string' || !w.toLowerCase().includes('deterministic decision-support mode')
                    );
                    if (filteredWarnings.length === 0) return null;
                    return (
                      <div className="mt-2.5 px-3 py-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-amber-800 dark:text-amber-300 text-xs">
                        {filteredWarnings.map((w, wIdx) => (
                          <div key={wIdx} className="flex items-start gap-1.5">
                            <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                            <span>{typeof w === 'string' ? w : JSON.stringify(w)}</span>
                          </div>
                        ))}
                      </div>
                    );
                  })()}

                  {/* Contextual Suggested Follow-up Chips */}
                  {!isUser && msg.suggested_followups && msg.suggested_followups.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-800/80">
                      <span className="block text-[11px] font-semibold text-slate-400 mb-1.5">
                        Suggested Follow-ups:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.suggested_followups.map((chip, chipIdx) => (
                          <button
                            key={chipIdx}
                            onClick={() => handleSendMessage(chip)}
                            className="px-2.5 py-1 text-xs rounded-full bg-slate-100 dark:bg-slate-800 hover:bg-sky-50 dark:hover:bg-sky-950/60 text-slate-700 dark:text-slate-300 hover:text-sky-700 dark:hover:text-sky-300 border border-slate-200 dark:border-slate-700 transition-colors"
                          >
                            {chip}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex items-center gap-2 p-3 text-xs text-slate-500 dark:text-slate-400">
            <RefreshCw className="w-4 h-4 animate-spin text-sky-600 dark:text-sky-400" />
            <span>Analyzing hospital occupancy telemetry and forecasting models...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box & Bottom Disclaimer */}
      <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-800">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="relative flex items-center gap-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-2xl p-2 shadow-sm focus-within:ring-2 focus-within:ring-sky-500/30 focus-within:border-sky-500 transition-all"
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={1000}
            placeholder="Ask about hospital occupancy, forecasts, risks, alerts, or transfers..."
            className="flex-1 max-h-32 bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 resize-none outline-none px-2 py-1"
          />

          <div className="flex items-center gap-2 shrink-0 pr-1">
            <span className="text-[10px] text-slate-400 hidden sm:inline">
              {inputMessage.length}/1000
            </span>
            <button
              type="submit"
              disabled={!inputMessage.trim() || isLoading}
              className={cn(
                'p-2 rounded-xl text-white transition-all duration-150',
                inputMessage.trim() && !isLoading
                  ? 'bg-sky-600 hover:bg-sky-700 shadow-md shadow-sky-500/25 cursor-pointer scale-100'
                  : 'bg-slate-300 dark:bg-slate-800 text-slate-400 cursor-not-allowed opacity-60'
              )}
              aria-label="Send query"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>

        <p className="text-[11px] text-center text-slate-400 dark:text-slate-500 mt-2">
          CareFlow AI Assistant provides clinical decision support grounded in hospital records. It does not replace clinical judgment or execute patient transfers autonomously.
        </p>
      </div>
    </div>
  );
};

export default AssistantPage;
