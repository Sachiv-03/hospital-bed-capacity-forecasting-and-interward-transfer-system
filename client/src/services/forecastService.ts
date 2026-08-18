import { apiClient } from './api';

export interface ForecastItem {
  date: string;
  predicted_occupied_beds: number;
  predicted_occupancy_percentage: number;
  lower_bound?: number;
  upper_bound?: number;
  lower_bound_beds?: number;
  upper_bound_beds?: number;
  risk_level: 'NORMAL' | 'MODERATE' | 'HIGH' | 'CRITICAL';
}

export interface WardForecastResponse {
  ward_id: number;
  ward_name: string;
  hospital_id: number;
  total_beds: number;
  current_occupied_beds: number;
  current_occupancy_percentage: number;
  horizon: number;
  model: string;
  model_version: string;
  generated_at: string;
  status: 'SUCCESS' | 'INSUFFICIENT_DATA' | 'MODEL_ERROR';
  message?: string;
  required_observations?: number;
  available_observations?: number;
  forecasts: ForecastItem[];
  max_predicted_occupancy: number;
  max_predicted_date?: string;
  max_risk_level: 'NORMAL' | 'MODERATE' | 'HIGH' | 'CRITICAL';
}

export interface HospitalWardForecastSummary {
  ward_id: number;
  ward_name: string;
  total_beds: number;
  current_occupancy_percentage: number;
  tomorrow_occupancy_percentage: number;
  max_7day_occupancy_percentage: number;
  max_risk_level: 'NORMAL' | 'MODERATE' | 'HIGH' | 'CRITICAL';
}

export interface HospitalDailyForecast {
  date: string;
  total_beds: number;
  predicted_occupied_beds: number;
  predicted_occupancy_percentage: number;
  risk_level: 'NORMAL' | 'MODERATE' | 'HIGH' | 'CRITICAL';
}

export interface HospitalForecastResponse {
  hospital_id: number;
  hospital_name: string;
  total_beds: number;
  horizon: number;
  generated_at: string;
  hospital_daily_forecasts: HospitalDailyForecast[];
  ward_summaries: HospitalWardForecastSummary[];
}

export interface ForecastHistoryItem {
  id: number;
  hospital_id: number;
  ward_id: number;
  forecast_date: string;
  generated_at: string;
  horizon_days: number;
  predicted_occupied_beds: number;
  predicted_occupancy_percentage: number;
  lower_bound?: number;
  upper_bound?: number;
  risk_level: string;
  model_name: string;
  model_version: string;
}

export interface ForecastHistoryResponse {
  items: ForecastHistoryItem[];
  total: number;
  page: number;
  limit: number;
}

export interface ModelPerformanceMetricItem {
  model_name: string;
  model_version: string;
  mae: number;
  rmse: number;
  mape?: number;
  training_period_start?: string;
  training_period_end?: string;
  testing_period_start?: string;
  testing_period_end?: string;
  is_best_model: boolean;
}

export interface ModelPerformanceResponse {
  hospital_id: number;
  ward_id: number;
  ward_name: string;
  evaluated_at: string;
  baseline_model: ModelPerformanceMetricItem;
  primary_model: ModelPerformanceMetricItem;
  recommended_model: string;
}

export interface ManualForecastGenerateResponse {
  status: string;
  hospitals_processed: number;
  wards_processed: number;
  forecasts_generated: number;
  models_failed: number;
  insufficient_data_count: number;
  details: Array<{ ward_id: number; ward_name: string; status: string }>;
}

export const forecastService = {
  getWardForecast: async (wardId: number, horizon: number = 7): Promise<WardForecastResponse> => {
    const response = await apiClient.get<WardForecastResponse>(`/wards/${wardId}/forecast`, {
      params: { horizon },
    });
    return response.data;
  },

  getHospitalForecast: async (hospitalId: number, horizon: number = 7): Promise<HospitalForecastResponse> => {
    const response = await apiClient.get<HospitalForecastResponse>(`/hospitals/${hospitalId}/forecast`, {
      params: { horizon },
    });
    return response.data;
  },

  getForecastHistory: async (wardId: number, page: number = 1, limit: number = 50): Promise<ForecastHistoryResponse> => {
    const response = await apiClient.get<ForecastHistoryResponse>(`/wards/${wardId}/forecast/history`, {
      params: { page, limit },
    });
    return response.data;
  },

  getModelPerformance: async (wardId: number): Promise<ModelPerformanceResponse> => {
    const response = await apiClient.get<ModelPerformanceResponse>('/forecasting/performance', {
      params: { ward_id: wardId },
    });
    return response.data;
  },

  generateManualForecast: async (hospitalId?: number, horizon: number = 7): Promise<ManualForecastGenerateResponse> => {
    const response = await apiClient.post<ManualForecastGenerateResponse>('/forecasting/generate', null, {
      params: { hospital_id: hospitalId, horizon },
    });
    return response.data;
  },
};
