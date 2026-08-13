import { apiClient } from './api';
import { HospitalCapacity, OccupancyEventListResponse, WardCapacity } from '../types';

// ── Capacity ────────────────────────────────────────────────────────────────

export const getHospitalCapacity = async (hospitalId: number): Promise<HospitalCapacity> => {
  const { data } = await apiClient.get<HospitalCapacity>(`/hospitals/${hospitalId}/capacity`);
  return data;
};

export const getWardCapacity = async (wardId: number): Promise<WardCapacity> => {
  const { data } = await apiClient.get<WardCapacity>(`/wards/${wardId}/capacity`);
  return data;
};

// ── Event History ───────────────────────────────────────────────────────────

export const getEventHistory = async (params: {
  hospital_id?: number;
  ward_id?: number;
  event_type?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  limit?: number;
}): Promise<OccupancyEventListResponse> => {
  const { data } = await apiClient.get<OccupancyEventListResponse>('/ingestion/events', { params });
  return data;
};

// ── Event Ingestion ─────────────────────────────────────────────────────────

export const ingestEvent = async (payload: {
  event_id: string;
  hospital_id: number;
  ward_id: number;
  bed_id: number;
  event_type: string;
  event_time: string;
  source?: string;
}) => {
  const { data } = await apiClient.post('/ingestion/events', payload);
  return data;
};

// ── Dev-Only Simulate ───────────────────────────────────────────────────────

export const triggerSimulateEvent = async (payload: {
  hospital_id: number;
  ward_id?: number;
  event_type: string;
}) => {
  const { data } = await apiClient.post('/ingestion/simulate', payload);
  return data;
};

// ── Stage 2 Historical & Alert APIs ─────────────────────────────────────────

export const getWardCapacityHistory = async (wardId: number, params?: { start_date?: string; end_date?: string; limit?: number }) => {
  const { data } = await apiClient.get(`/wards/${wardId}/capacity/history`, { params });
  return data;
};

export const getHospitalCapacityHistory = async (hospitalId: number, params?: { start_date?: string; end_date?: string; limit?: number }) => {
  const { data } = await apiClient.get(`/hospitals/${hospitalId}/capacity/history`, { params });
  return data;
};

export const getWardDailySummary = async (wardId: number, params?: { start_date?: string; end_date?: string }) => {
  const { data } = await apiClient.get(`/wards/${wardId}/daily-summary`, { params });
  return data;
};

export const getDataQualityReport = async (hospitalId?: number) => {
  const { data } = await apiClient.get('/capacity/data-quality', { params: { hospital_id: hospitalId } });
  return data;
};

export const getCapacityAlerts = async (params?: { hospital_id?: number; ward_id?: number; status?: string; severity?: string }) => {
  const { data } = await apiClient.get('/alerts', { params });
  return data;
};

export const resolveCapacityAlert = async (alertId: number) => {
  const { data } = await apiClient.post(`/alerts/${alertId}/resolve`);
  return data;
};

export const generateManualSnapshots = async () => {
  const { data } = await apiClient.post('/capacity/snapshots/generate');
  return data;
};

