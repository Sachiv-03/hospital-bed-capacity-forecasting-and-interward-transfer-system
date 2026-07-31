export interface HealthStatus {
  status: string;
  service: string;
  version: string;
}

export interface NavItem {
  name: string;
  path: string;
  iconName: string;
  badge?: string;
}

export interface UserProfile {
  name: string;
  role: string;
  department: string;
  avatarUrl?: string;
}
