export type MessageRole = 'user' | 'assistant' | 'system';

export type SourceCategory =
  | 'CURRENT_AVAILABILITY'
  | 'OCCUPANCY_TRENDS'
  | 'SARIMA_FORECAST'
  | 'CAPACITY_RISK_ALERTS'
  | 'TRANSFER_DECISION_SUPPORT'
  | 'MANAGEMENT_SUMMARY'
  | 'GENERAL_HELP';

export interface ConversationHistoryItem {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface AssistantQueryRequest {
  message: string;
  conversation_history?: ConversationHistoryItem[];
  hospital_id?: number;
  ward_id?: number;
}

export interface AssistantQueryResponse {
  answer: string;
  source_category: SourceCategory | string;
  evidence?: Record<string, any> | null;
  data_timestamp?: string | null;
  is_forecast_estimate: boolean;
  forecast_target_date?: string | null;
  warnings: string[];
  provider_status: string;
  suggested_followups: string[];
}

export interface AssistantStatusResponse {
  enabled: boolean;
  provider: string;
  model: string;
  has_api_key: boolean;
  supported_categories: string[];
  disclaimer: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  source_category?: string;
  evidence?: Record<string, any> | null;
  data_timestamp?: string | null;
  is_forecast_estimate?: boolean;
  forecast_target_date?: string | null;
  warnings?: string[];
  provider_status?: string;
  suggested_followups?: string[];
  isError?: boolean;
}
