import { apiClient } from './api';
import { HospitalCapacity, WardCapacity } from '../types';

export interface OccupancySummary {
  hospital_id: number;
  hospital_name: string;
  total_beds: number;
  operational_beds: number;
  occupied_beds: number;
  available_beds: number;
  maintenance_beds: number;
  inactive_beds: number;
  occupancy_percentage: number;
  available_capacity_percentage: number;
  capacity_status: 'NORMAL' | 'WARNING' | 'HIGH' | 'CRITICAL';
  active_admissions: number;
  admissions_today: number;
  discharges_today: number;
  timestamp: string;
}

export interface OccupancySnapshotItem {
  id: number;
  hospital_id: number;
  ward_id: number;
  ward_name: string;
  snapshot_time: string;
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  cleaning_beds: number;
  reserved_beds: number;
  maintenance_beds: number;
  occupancy_percentage: number;
}

export interface OccupancyTrendResponse {
  items: OccupancySnapshotItem[];
  total: number;
}

export const getHospitalOccupancy = async (hospitalId?: number): Promise<HospitalCapacity> => {
  const params = hospitalId ? { hospital_id: hospitalId } : {};
  const response = await apiClient.get<HospitalCapacity>('/occupancy/hospital', { params });
  return response.data;
};

export const getOccupancySummary = async (hospitalId?: number): Promise<OccupancySummary> => {
  const params = hospitalId ? { hospital_id: hospitalId } : {};
  const response = await apiClient.get<OccupancySummary>('/occupancy/summary', { params });
  return response.data;
};

export const getWardsOccupancy = async (hospitalId?: number): Promise<WardCapacity[]> => {
  const params = hospitalId ? { hospital_id: hospitalId } : {};
  const response = await apiClient.get<WardCapacity[]>('/occupancy/wards', { params });
  return response.data;
};

export const getWardOccupancy = async (wardId: number, hospitalId?: number): Promise<WardCapacity> => {
  const params = hospitalId ? { hospital_id: hospitalId } : {};
  const response = await apiClient.get<WardCapacity>(`/occupancy/wards/${wardId}`, { params });
  return response.data;
};

export const getOccupancyTrends = async (params?: {
  hospital_id?: number;
  ward_id?: number;
  limit?: number;
}): Promise<OccupancyTrendResponse> => {
  const response = await apiClient.get<OccupancyTrendResponse>('/occupancy/trends', { params });
  return response.data;
};

export const triggerOccupancySnapshot = async (hospitalId?: number): Promise<{ snapshots_created: number }> => {
  const params = hospitalId ? { hospital_id: hospitalId } : {};
  const response = await apiClient.post<{ snapshots_created: number }>('/occupancy/snapshots', null, { params });
  return response.data;
};
