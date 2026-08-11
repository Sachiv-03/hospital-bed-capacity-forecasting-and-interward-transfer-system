import { apiClient } from './api';
import { BedListResponse, BedCreateInput } from '../types';

const BASE = '/beds';

export const bedService = {
  getBeds: async (params: {
    ward_id?: number;
    hospital_id?: number;
    status?: string;
    bed_type?: string;
    page?: number;
    limit?: number;
  }): Promise<BedListResponse> => {
    const { data } = await apiClient.get<BedListResponse>(BASE, { params });
    return data;
  },

  createBed: async (payload: BedCreateInput) => {
    const { data } = await apiClient.post(BASE, payload);
    return data;
  },

  updateBed: async (bedId: number, payload: Partial<BedCreateInput>) => {
    const { data } = await apiClient.put(`${BASE}/${bedId}`, payload);
    return data;
  },

  deleteBed: async (bedId: number) => {
    await apiClient.delete(`${BASE}/${bedId}`);
  },
};
