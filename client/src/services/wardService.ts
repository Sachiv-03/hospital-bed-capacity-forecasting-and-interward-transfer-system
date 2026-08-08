import { apiClient } from './api';
import {
  Ward,
  WardCreateInput,
  WardUpdateInput,
  WardListResponse,
  WardStatistics,
  WardOccupancy,
} from '../types';

export interface GetWardsQueryParams {
  page?: number;
  limit?: number;
  search?: string;
  ward_type?: string;
  department?: string;
  status?: string;
}

export const getWards = async (params: GetWardsQueryParams = {}): Promise<WardListResponse> => {
  const response = await apiClient.get<WardListResponse>('/wards', { params });
  return response.data;
};

export const getWard = async (id: number): Promise<Ward> => {
  const response = await apiClient.get<Ward>(`/wards/${id}`);
  return response.data;
};

export const createWard = async (data: WardCreateInput): Promise<Ward> => {
  const response = await apiClient.post<Ward>('/wards', data);
  return response.data;
};

export const updateWard = async (id: number, data: WardUpdateInput): Promise<Ward> => {
  const response = await apiClient.put<Ward>(`/wards/${id}`, data);
  return response.data;
};

export const deactivateWard = async (id: number): Promise<Ward> => {
  const response = await apiClient.delete<Ward>(`/wards/${id}`);
  return response.data;
};

export const getWardStatistics = async (): Promise<WardStatistics> => {
  const response = await apiClient.get<WardStatistics>('/wards/statistics');
  return response.data;
};

export const getWardOccupancy = async (id: number): Promise<WardOccupancy> => {
  const response = await apiClient.get<WardOccupancy>(`/wards/${id}/occupancy`);
  return response.data;
};
