export type UserRole = 'admin' | 'doctor' | 'nurse' | 'receptionist';

export interface User {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  database?: string;
}

export interface NavItem {
  name: string;
  path: string;
  iconName: string;
  badge?: string;
  roles?: UserRole[];
}

export type WardType =
  | 'GENERAL'
  | 'ICU'
  | 'EMERGENCY'
  | 'PEDIATRIC'
  | 'MATERNITY'
  | 'SURGICAL'
  | 'ISOLATION'
  | 'OTHER';

export type WardStatus = 'ACTIVE' | 'INACTIVE';

export interface Ward {
  id: number;
  name: string;
  ward_type: WardType;
  department: string;
  floor: string;
  capacity: number;
  description?: string;
  status: WardStatus;
  created_at: string;
  updated_at: string;
}

export interface WardCreateInput {
  name: string;
  ward_type: WardType;
  department: string;
  floor: string;
  capacity: number;
  description?: string;
}

export interface WardUpdateInput {
  name?: string;
  ward_type?: WardType;
  department?: string;
  floor?: string;
  capacity?: number;
  description?: string;
  status?: WardStatus;
}

export interface WardListResponse {
  items: Ward[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface WardStatistics {
  total_wards: number;
  active_wards: number;
  inactive_wards: number;
  total_capacity: number;
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  occupancy_rate: number;
}

export interface WardOccupancy {
  ward_id: number;
  ward_name: string;
  capacity: number;
  occupied_beds: number;
  available_beds: number;
  occupancy_rate: number;
  message: string;
}

