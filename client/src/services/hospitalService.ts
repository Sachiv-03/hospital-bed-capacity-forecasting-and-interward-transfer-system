import { apiClient } from './api';
import {
  Hospital,
  HospitalCreateInput,
  HospitalUpdateInput,
  HospitalListResponse,
} from '../types';

export const hospitalService = {
  getHospitals: async (params?: {
    page?: number;
    limit?: number;
    search?: string;
    status?: string;
  }): Promise<HospitalListResponse> => {
    const response = await apiClient.get<HospitalListResponse>('/hospitals', { params });
    return response.data;
  },

  getHospitalById: async (hospitalId: number): Promise<Hospital> => {
    const response = await apiClient.get<Hospital>(`/hospitals/${hospitalId}`);
    return response.data;
  },

  createHospital: async (data: HospitalCreateInput): Promise<Hospital> => {
    const response = await apiClient.post<Hospital>('/hospitals', data);
    return response.data;
  },

  updateHospital: async (hospitalId: number, data: HospitalUpdateInput): Promise<Hospital> => {
    const response = await apiClient.put<Hospital>(`/hospitals/${hospitalId}`, data);
    return response.data;
  },

  deactivateHospital: async (hospitalId: number): Promise<Hospital> => {
    const response = await apiClient.delete<Hospital>(`/hospitals/${hospitalId}`);
    return response.data;
  },
};
