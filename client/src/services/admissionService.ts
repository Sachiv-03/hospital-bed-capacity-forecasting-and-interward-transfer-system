import { apiClient } from './api';
import {
  Admission,
  AdmissionCreateInput,
  DischargeInput,
  AdmissionListResponse,
  Bed,
} from '../types';

export interface GetAdmissionsQueryParams {
  page?: number;
  limit?: number;
  ward_id?: number;
  patient_id?: number;
  status?: string;
  hospital_id?: number;
}

export const admitPatient = async (data: AdmissionCreateInput): Promise<Admission> => {
  const response = await apiClient.post<Admission>('/admissions', data);
  return response.data;
};

export const getAdmissions = async (params: GetAdmissionsQueryParams = {}): Promise<AdmissionListResponse> => {
  const response = await apiClient.get<AdmissionListResponse>('/admissions', { params });
  return response.data;
};

export const getAdmission = async (id: number): Promise<Admission> => {
  const response = await apiClient.get<Admission>(`/admissions/${id}`);
  return response.data;
};

export const dischargePatient = async (id: number, data: DischargeInput = {}): Promise<Admission> => {
  const response = await apiClient.post<Admission>(`/admissions/${id}/discharge`, data);
  return response.data;
};

export const getWardAvailableBeds = async (wardId: number): Promise<Bed[]> => {
  const response = await apiClient.get<Bed[]>(`/wards/${wardId}/available-beds`);
  return response.data;
};
