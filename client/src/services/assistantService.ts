import { apiClient } from './api';
import {
  AssistantQueryRequest,
  AssistantQueryResponse,
  AssistantStatusResponse,
} from '../types/assistant';

export const queryAssistant = async (
  request: AssistantQueryRequest
): Promise<AssistantQueryResponse> => {
  const response = await apiClient.post<AssistantQueryResponse>(
    '/assistant/query',
    request
  );
  return response.data;
};

export const getAssistantStatus = async (): Promise<AssistantStatusResponse> => {
  const response = await apiClient.get<AssistantStatusResponse>(
    '/assistant/status'
  );
  return response.data;
};
