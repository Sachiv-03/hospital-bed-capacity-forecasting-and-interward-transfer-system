import { apiClient } from './api';
import {
  Patient,
  PatientCreateInput,
  PatientUpdateInput,
  PatientListResponse,
  AdmissionListResponse,
} from '../types';

export interface GetPatientsQueryParams {
  page?: number;
  limit?: number;
  search?: string;
  status?: string;
  hospital_id?: number;
}

export const getPatients = async (params: GetPatientsQueryParams = {}): Promise<PatientListResponse> => {
  const response = await apiClient.get<PatientListResponse>('/patients', { params });
  return response.data;
};

export const getPatient = async (id: number, hospital_id?: number): Promise<Patient> => {
  const response = await apiClient.get<Patient>(`/patients/${id}`, {
    params: hospital_id ? { hospital_id } : {},
  });
  return response.data;
};

export const createPatient = async (data: PatientCreateInput): Promise<Patient> => {
  const response = await apiClient.post<Patient>('/patients', data);
  return response.data;
};

export const updatePatient = async (id: number, data: PatientUpdateInput): Promise<Patient> => {
  const response = await apiClient.put<Patient>(`/patients/${id}`, data);
  return response.data;
};

export const updatePatientStatus = async (id: number, status: 'ACTIVE' | 'INACTIVE'): Promise<Patient> => {
  const response = await apiClient.patch<Patient>(`/patients/${id}/status`, { status });
  return response.data;
};

export const getPatientAdmissions = async (patientId: number): Promise<AdmissionListResponse> => {
  const response = await apiClient.get<AdmissionListResponse>(`/patients/${patientId}/admissions`);
  return response.data;
};
