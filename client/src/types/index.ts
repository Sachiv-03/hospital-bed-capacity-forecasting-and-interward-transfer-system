export type UserRole = 'super_admin' | 'admin' | 'doctor' | 'nurse' | 'receptionist';

export interface User {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  hospital_id?: number | null;
  hospital_name?: string | null;
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

export type HospitalStatus = 'ACTIVE' | 'INACTIVE';

export interface Hospital {
  id: number;
  name: string;
  code: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  status: HospitalStatus;
  created_at: string;
  updated_at: string;
  ward_count?: number;
  total_capacity?: number;
}

export interface HospitalCreateInput {
  name: string;
  code: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
}

export interface HospitalUpdateInput {
  name?: string;
  code?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  status?: HospitalStatus;
}

export interface HospitalListResponse {
  items: Hospital[];
  total: number;
  page: number;
  limit: number;
  pages: number;
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
  hospital_id: number;
  hospital_name?: string | null;
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
  hospital_id?: number | null;
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

// ─── Phase 6 — Bed & Occupancy Types ───────────────────────────────────────

export type BedStatus = 'AVAILABLE' | 'OCCUPIED' | 'CLEANING' | 'MAINTENANCE' | 'RESERVED';
export type BedType = 'STANDARD' | 'ICU' | 'ISOLATION' | 'EMERGENCY';

export interface Bed {
  id: number;
  hospital_id: number;
  ward_id: number;
  bed_number: string;
  status: BedStatus;
  bed_type: BedType;
  ward_name?: string | null;
  hospital_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BedCreateInput {
  ward_id: number;
  hospital_id?: number | null;
  bed_number: string;
  bed_type: BedType;
  status: BedStatus;
}

export interface BedListResponse {
  items: Bed[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export type OccupancyEventType =
  | 'ADMISSION'
  | 'DISCHARGE'
  | 'TRANSFER_IN'
  | 'TRANSFER_OUT'
  | 'BED_AVAILABLE'
  | 'BED_CLEANING'
  | 'BED_MAINTENANCE'
  | 'BED_RESERVED'
  | 'BED_RELEASED';

export type EventSource = 'SIMULATOR' | 'MANUAL' | 'API';

export interface OccupancyEvent {
  id: number;
  event_id: string;
  hospital_id: number;
  ward_id: number;
  bed_id: number;
  event_type: OccupancyEventType;
  event_time: string;
  source: EventSource;
  processed: boolean;
  created_at: string;
  ward_name?: string | null;
  bed_number?: string | null;
}

export interface OccupancyEventListResponse {
  items: OccupancyEvent[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export type CapacityStatus = 'NORMAL' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export interface WardCapacity {
  ward_id: number;
  ward_name: string;
  hospital_id: number;
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  cleaning_beds: number;
  reserved_beds: number;
  maintenance_beds: number;
  occupancy_percentage: number;
  status: CapacityStatus;
}

export interface HospitalCapacity {
  hospital_id: number;
  hospital_name: string;
  total_wards: number;
  total_beds: number;
  occupied_beds: number;
  available_beds: number;
  cleaning_beds: number;
  reserved_beds: number;
  maintenance_beds: number;
  occupancy_percentage: number;
  status: CapacityStatus;
  ward_capacities: WardCapacity[];
}
