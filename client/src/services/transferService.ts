import { apiClient } from './api';
import {
  TransferRecommendation,
  TransferRecommendationDetail,
  TransferOverviewStats,
  WardTransferRule,
  AuditLog,
} from '../types';

export const transferService = {
  // Generate recommendations
  generateRecommendations: async (hospitalId?: number, horizonDays: number = 1) => {
    const response = await apiClient.post('/transfers/recommendations/generate', {
      hospital_id: hospitalId,
      horizon_days: horizonDays,
    });
    return response.data;
  },

  // Get hospital transfer pressure overview stats
  getOverviewStats: async (hospitalId?: number): Promise<TransferOverviewStats> => {
    const response = await apiClient.get('/transfers/recommendations/overview', {
      params: { hospital_id: hospitalId },
    });
    return response.data;
  },

  // List recommendations
  getRecommendations: async (params?: {
    hospital_id?: number;
    source_ward_id?: number;
    destination_ward_id?: number;
    priority?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<TransferRecommendation[]> => {
    const response = await apiClient.get('/transfers/recommendations', { params });
    return response.data;
  },

  // Get single recommendation detail
  getRecommendationDetail: async (id: number): Promise<TransferRecommendationDetail> => {
    const response = await apiClient.get(`/transfers/recommendations/${id}`);
    return response.data;
  },

  // Approve recommendation
  approveRecommendation: async (id: number, notes?: string): Promise<TransferRecommendation> => {
    const response = await apiClient.post(`/transfers/recommendations/${id}/approve`, { notes });
    return response.data;
  },

  // Reject recommendation
  rejectRecommendation: async (id: number, rejection_reason: string): Promise<TransferRecommendation> => {
    const response = await apiClient.post(`/transfers/recommendations/${id}/reject`, { rejection_reason });
    return response.data;
  },

  // Get transfer compatibility rules
  getRules: async (hospitalId?: number): Promise<WardTransferRule[]> => {
    const response = await apiClient.get('/transfers/rules', {
      params: { hospital_id: hospitalId },
    });
    return response.data;
  },

  // Create rule
  createRule: async (rule: Partial<WardTransferRule>): Promise<WardTransferRule> => {
    const response = await apiClient.post('/transfers/rules', rule);
    return response.data;
  },

  // Update rule
  updateRule: async (id: number, rule: Partial<WardTransferRule>): Promise<WardTransferRule> => {
    const response = await apiClient.put(`/transfers/rules/${id}`, rule);
    return response.data;
  },

  // Delete rule
  deleteRule: async (id: number): Promise<void> => {
    await apiClient.delete(`/transfers/rules/${id}`);
  },

  // Get audit logs
  getAuditLogs: async (hospitalId?: number, limit: number = 50): Promise<AuditLog[]> => {
    const response = await apiClient.get('/transfers/audit-logs', {
      params: { hospital_id: hospitalId, limit },
    });
    return response.data;
  },
};
