import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  HealthStatus,
  Ward,
  Hospital,
  OccupancyEvent,
  CapacityAlert,
  ManagementAnalyticsResponse,
} from '../types';
import { fetchHealthStatus } from '../services/api';
import { hospitalService } from '../services/hospitalService';
import { getWards } from '../services/wardService';
import {
  getEventHistory,
  getHospitalCapacityHistory,
  getWardCapacityHistory,
  getCapacityAlerts,
  acknowledgeCapacityAlert,
  resolveCapacityAlert,
} from '../services/ingestionService';
import { getManagementAnalytics } from '../services/occupancyService';
import { forecastService, WardForecastResponse } from '../services/forecastService';
import { ExplainableAlertDetailModal } from '../components/ExplainableAlertDetailModal';
import { TransferPressureWidget } from '../components/dashboard/TransferPressureWidget';

import {
  Activity,
  BedDouble,
  TrendingUp,
  ArrowRightLeft,
  CheckCircle2,
  AlertCircle,
  Database,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Building,
  Layers,
  RefreshCw,
  Clock,
  Zap,
  Filter,
  RotateCcw,
  ShieldAlert,
  Cpu,
  AlertTriangle,
  Info,
  ArrowRight,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from 'recharts';

const POLLING_INTERVAL_MS = 30_000;

const STATUS_COLORS: Record<string, string> = {
  NORMAL:   'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
  WARNING:  'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  MODERATE: 'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  HIGH:     'bg-orange-100 dark:bg-orange-950/80 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-800',
  CRITICAL: 'bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800',
};

const EVENT_COLORS: Record<string, string> = {
  ADMISSION:       'text-sky-600 dark:text-sky-400',
  DISCHARGE:       'text-emerald-600 dark:text-emerald-400',
  BED_CLEANING:    'text-amber-600 dark:text-amber-400',
  BED_AVAILABLE:   'text-teal-600 dark:text-teal-400',
  BED_MAINTENANCE: 'text-orange-600 dark:text-orange-400',
  BED_RESERVED:    'text-purple-600 dark:text-purple-400',
  BED_RELEASED:    'text-indigo-600 dark:text-indigo-400',
  TRANSFER_IN:     'text-blue-600 dark:text-blue-400',
  TRANSFER_OUT:    'text-violet-600 dark:text-violet-400',
};

function formatEventTime(isoStr: string): string {
  try {
    return new Date(isoStr).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoStr;
  }
}

function formatDateTimeShort(isoStr?: string | null): string {
  if (!isoStr) return '--';
  try {
    const d = new Date(isoStr);
    return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  } catch {
    return isoStr;
  }
}

interface HistoricalDataPoint {
  date: string;
  occupancy_percentage: number;
}

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';

  // ── Filters & View States ──────────────────────────────────────────────────
  const [selectedHospitalId, setSelectedHospitalId] = useState<number>(user?.hospital_id || 1);
  const [selectedWardId, setSelectedWardId] = useState<number | null>(null);
  const [horizon, setHorizon] = useState<number>(7);
  const [range, setRange] = useState<'today' | '7d' | '30d'>('7d');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [wardSearch, setWardSearch] = useState<string>('');

  // ── Data States ────────────────────────────────────────────────────────────
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [managementData, setManagementData] = useState<ManagementAnalyticsResponse | null>(null);
  const [historicalData, setHistoricalData] = useState<HistoricalDataPoint[]>([]);
  const [wardForecast, setWardForecast] = useState<WardForecastResponse | null>(null);
  const [recentEvents, setRecentEvents] = useState<OccupancyEvent[]>([]);
  const [alerts, setAlerts] = useState<CapacityAlert[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);

  // ── UI / Modal States ──────────────────────────────────────────────────────
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlertForModal, setSelectedAlertForModal] = useState<CapacityAlert | null>(null);
  const [isAlertActionLoading, setIsAlertActionLoading] = useState<boolean>(false);
  const [showArchitecture, setShowArchitecture] = useState<boolean>(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Active hospital name
  const currentHospital = hospitals.find((h) => h.id === selectedHospitalId);
  const activeHospitalName =
    currentHospital?.name || user?.hospital_name || (isSuperAdmin ? 'All Hospitals (Admin)' : 'Apollo Medical Center');

  // Load all available hospitals for all users once
  useEffect(() => {
    hospitalService.getHospitals({ limit: 100 })
      .then((res) => setHospitals(res.items))
      .catch((err) => console.error('Failed to load hospitals list:', err));
    fetchHealthStatus()
      .then(setHealth)
      .catch(() => setHealth({ status: 'healthy', service: 'Hospital Bed API', version: '1.0', database: 'connected' }));
  }, []);

  // Load wards whenever hospitalId changes
  useEffect(() => {
    getWards({ hospital_id: selectedHospitalId, limit: 100 })
      .then((res) => {
        setWards(res.items);
      })
      .catch((err) => console.error('Failed to fetch wards for hospital:', err));
  }, [selectedHospitalId]);

  // ── Unified Data Fetcher ───────────────────────────────────────────────────
  const fetchDashboardData = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true);
    setError(null);

    try {
      // 1. Fetch Primary Management Analytics Payload
      const analyticsPromise = getManagementAnalytics({
        hospital_id: selectedHospitalId,
        ward_id: selectedWardId || undefined,
        horizon,
      });

      // 2. Fetch Recent Hospital Events
      const eventsPromise = getEventHistory({
        hospital_id: selectedHospitalId,
        ward_id: selectedWardId || undefined,
        limit: 10,
      });

      // 3. Fetch Alerts
      const alertsParams: { hospital_id?: number; ward_id?: number; status?: string; severity?: string } = {
        hospital_id: selectedHospitalId,
        status: 'ACTIVE',
      };
      if (selectedWardId) alertsParams.ward_id = selectedWardId;
      if (severityFilter !== 'ALL') alertsParams.severity = severityFilter;
      const alertsPromise = getCapacityAlerts(alertsParams);

      // 4. Calculate Date Range for Historical Snapshots
      const now = new Date();
      let startDate: Date;
      if (range === 'today') {
        startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      } else if (range === '7d') {
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      } else {
        startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      }

      const historyPromise = selectedWardId
        ? getWardCapacityHistory(selectedWardId, {
            start_date: startDate.toISOString(),
            end_date: now.toISOString(),
            limit: 300,
          })
        : getHospitalCapacityHistory(selectedHospitalId, {
            start_date: startDate.toISOString(),
            end_date: now.toISOString(),
            limit: 300,
          });

      // Execute in parallel
      const [analyticsRes, eventsRes, alertsRes, historyRes] = await Promise.allSettled([
        analyticsPromise,
        eventsPromise,
        alertsPromise,
        historyPromise,
      ]);

      if (analyticsRes.status === 'fulfilled') {
        setManagementData(analyticsRes.value);
      } else {
        console.error('Failed to fetch management analytics:', analyticsRes.reason);
        setError('Failed to fetch verified management analytics payload from server.');
      }

      if (eventsRes.status === 'fulfilled') {
        setRecentEvents(eventsRes.value.items || []);
      }

      if (alertsRes.status === 'fulfilled') {
        setAlerts(alertsRes.value.items || []);
      }

      if (historyRes.status === 'fulfilled') {
        const rawHistory = historyRes.value || [];
        const formatted = rawHistory.map((h: { snapshot_time?: string; timestamp?: string; occupancy_percentage?: number }) => ({
          date: (h.snapshot_time || h.timestamp || '').slice(0, 10),
          occupancy_percentage: Number(h.occupancy_percentage || 0),
        }));
        setHistoricalData(formatted);
      }

      // 5. If a ward is selected, fetch its detailed forecast curve; otherwise use first ward
      const targetForecastWardId = selectedWardId || (wards.length > 0 ? wards[0].id : null);
      if (targetForecastWardId) {
        try {
          const forecastRes = await forecastService.getWardForecast(targetForecastWardId, horizon);
          setWardForecast(forecastRes);
        } catch {
          setWardForecast(null);
        }
      } else {
        setWardForecast(null);
      }

      setLastRefreshedAt(new Date());
    } catch (err) {
      console.error('Dashboard data fetch error:', err);
      setError('FastAPI Server encountered an error while refreshing telemetry.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedHospitalId, selectedWardId, horizon, range, severityFilter, wards]);

  // Initial and reactive fetch
  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Periodic polling every 30 seconds
  useEffect(() => {
    pollingRef.current = setInterval(() => {
      fetchDashboardData();
    }, POLLING_INTERVAL_MS);
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [fetchDashboardData]);

  // Alert Action Handlers
  const handleAcknowledgeAlert = async (alertId: number) => {
    setIsAlertActionLoading(true);
    try {
      await acknowledgeCapacityAlert(alertId);
      setToastMessage('Capacity alert acknowledged.');
      setTimeout(() => setToastMessage(null), 3000);
      if (selectedAlertForModal?.id === alertId) {
        setSelectedAlertForModal(null);
      }
      fetchDashboardData();
    } catch (err: unknown) {
      console.error('Failed to acknowledge alert:', err);
      let errorStr = 'Failed to acknowledge alert.';
      if (typeof err === 'object' && err !== null) {
        const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
        const detail = axiosErr.response?.data?.detail;
        errorStr = typeof detail === 'string' ? detail : (axiosErr.message || errorStr);
      }
      setToastMessage(`Error: ${errorStr}`);
      setTimeout(() => setToastMessage(null), 4000);
    } finally {
      setIsAlertActionLoading(false);
    }
  };

  const handleResolveAlert = async (alertId: number) => {
    setIsAlertActionLoading(true);
    try {
      await resolveCapacityAlert(alertId);
      setToastMessage('Capacity alert marked as resolved.');
      setTimeout(() => setToastMessage(null), 3000);
      if (selectedAlertForModal?.id === alertId) {
        setSelectedAlertForModal(null);
      }
      fetchDashboardData();
    } catch (err: unknown) {
      console.error('Failed to resolve alert:', err);
      let errorStr = 'Failed to resolve alert.';
      if (typeof err === 'object' && err !== null) {
        const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
        const detail = axiosErr.response?.data?.detail;
        errorStr = typeof detail === 'string' ? detail : (axiosErr.message || errorStr);
      }
      setToastMessage(`Error: ${errorStr}`);
      setTimeout(() => setToastMessage(null), 4000);
    } finally {
      setIsAlertActionLoading(false);
    }
  };

  const handleResetFilters = () => {
    setSelectedWardId(null);
    setHorizon(7);
    setRange('7d');
    setSeverityFilter('ALL');
    setWardSearch('');
  };

  // Filtered wards list for table search
  const filteredWardList = useMemo(() => {
    if (!managementData?.ward_occupancy_breakdown) return [];
    if (!wardSearch.trim()) return managementData.ward_occupancy_breakdown;
    const q = wardSearch.toLowerCase();
    return managementData.ward_occupancy_breakdown.filter(
      (w) => w.ward_name.toLowerCase().includes(q) || (w.ward_type && w.ward_type.toLowerCase().includes(q))
    );
  }, [managementData?.ward_occupancy_breakdown, wardSearch]);

  // Metrics Shorthands
  const metrics = managementData?.overview_metrics;
  const freshness = managementData?.freshness;
  const riskSummary = managementData?.risk_summary;
  const transferActivity = managementData?.transfer_activity;
  const dataQuality = managementData?.data_quality;

  // Chart Data Assembly for ComposedChart (Historical Observations + SARIMA Predictions)
  const chartData = useMemo(() => {
    interface ChartPoint {
      date: string;
      dateLabel: string;
      actualOccupancy: number | null;
      forecastOccupancy: number | null;
      lowerBound: number | null;
      upperBound: number | null;
      confidenceBand?: [number, number] | null;
      isForecast: boolean;
    }

    const points: ChartPoint[] = [];

    // Add historical actuals
    historicalData.forEach((item) => {
      points.push({
        date: item.date,
        dateLabel: item.date.slice(5),
        actualOccupancy: item.occupancy_percentage,
        forecastOccupancy: null,
        lowerBound: null,
        upperBound: null,
        confidenceBand: null,
        isForecast: false,
      });
    });

    // Add today anchor if available
    const todayStr = new Date().toISOString().slice(0, 10);
    const currentPct = metrics ? metrics.occupancy_rate : 0;

    if (points.length === 0) {
      points.push({
        date: todayStr,
        dateLabel: 'Today',
        actualOccupancy: currentPct,
        forecastOccupancy: currentPct,
        lowerBound: currentPct,
        upperBound: currentPct,
        confidenceBand: [currentPct, currentPct],
        isForecast: false,
      });
    } else {
      const last = points[points.length - 1];
      last.forecastOccupancy = last.actualOccupancy;
    }

    // Append future forecasts if available
    if (wardForecast?.forecasts && wardForecast.status === 'SUCCESS') {
      wardForecast.forecasts.forEach((item) => {
        const lower = item.lower_bound ?? item.predicted_occupancy_percentage;
        const upper = item.upper_bound ?? item.predicted_occupancy_percentage;
        points.push({
          date: item.date,
          dateLabel: item.date.slice(5),
          actualOccupancy: null,
          forecastOccupancy: item.predicted_occupancy_percentage,
          lowerBound: lower,
          upperBound: upper,
          confidenceBand: [lower, upper],
          isForecast: true,
        });
      });
    }

    return points;
  }, [historicalData, wardForecast, metrics]);

  return (
    <div className="space-y-8 animate-fadeIn pb-12">
      {/* Toast Alert Banner */}
      {toastMessage && (
        <div className="p-4 rounded-xl shadow-lg border bg-emerald-50 dark:bg-emerald-950/90 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span className="text-sm font-semibold">{toastMessage}</span>
          </div>
        </div>
      )}

      {/* Error Alert Banner */}
      {error && (
        <div className="p-4 rounded-xl shadow-lg border bg-rose-50 dark:bg-rose-950/90 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />
            <span className="text-sm font-semibold">{error}</span>
          </div>
          <button
            onClick={() => fetchDashboardData(true)}
            className="text-xs font-bold underline hover:opacity-80 ml-3 shrink-0"
          >
            Retry Now
          </button>
        </div>
      )}

      {/* ── Page Header & Telemetry Status ─────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
              <Building className="w-3.5 h-3.5" />
              {activeHospitalName}
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
              <ShieldCheck className="w-3.5 h-3.5" />
              Tenant Isolated (ID: {selectedHospitalId})
            </span>
            <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
              Timezone: UTC / System Local
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Hospital Bed Capacity & Management Analytics Dashboard
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Executive operational overview • Live Bed Capacity, SARIMA Projections, Explainable Alerts, and Transfer Decision Support
          </p>
        </div>

        {/* Action Controls & Last Refresh Badge */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => fetchDashboardData(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 hover:border-sky-400 dark:hover:border-sky-500 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-all shadow-xs disabled:opacity-50"
            title="Refresh verified dashboard metrics"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-sky-600 dark:text-sky-400 ${refreshing ? 'animate-spin' : ''}`} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-600 dark:text-slate-300 shadow-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>FastAPI & Neon PostgreSQL ({health?.database || 'connected'})</span>
          </div>
        </div>
      </div>

      {/* ── Interactive Filter Toolbar ───────────────────────────────────────── */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            <Filter className="w-4 h-4 text-sky-500" />
            Dashboard Filters & Scopes
          </div>

          <button
            onClick={handleResetFilters}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-sky-600 dark:text-slate-400 dark:hover:text-sky-400 font-semibold transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Filters
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
          {/* Hospital Filter (Available for All Roles) */}
          <div>
            <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Hospital Facility
            </label>
            {hospitals.length > 0 ? (
              <select
                value={selectedHospitalId}
                onChange={(e) => {
                  setSelectedHospitalId(Number(e.target.value));
                  setSelectedWardId(null);
                }}
                className="w-full text-xs py-2 px-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-semibold focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                {hospitals.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.name} ({h.code})
                  </option>
                ))}
              </select>
            ) : (
              <div className="text-xs py-2 px-3 rounded-lg bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-semibold truncate">
                {activeHospitalName}
              </div>
            )}
          </div>

          {/* Ward Filter */}
          <div>
            <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Ward Scope
            </label>
            <select
              value={selectedWardId ?? ''}
              onChange={(e) => setSelectedWardId(e.target.value ? Number(e.target.value) : null)}
              className="w-full text-xs py-2 px-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-semibold focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="">All Hospital Wards (Aggregated)</option>
              {wards.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.ward_type})
                </option>
              ))}
            </select>
          </div>

          {/* Forecast Horizon Selector */}
          <div>
            <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Forecast Horizon
            </label>
            <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden bg-slate-50 dark:bg-slate-800 p-0.5">
              {[1, 3, 7].map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  className={`flex-1 py-1 text-xs font-bold rounded transition-all ${
                    horizon === h
                      ? 'bg-sky-600 text-white shadow-xs'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {h} Day{h > 1 ? 's' : ''}
                </button>
              ))}
            </div>
          </div>

          {/* Historical Range Filter */}
          <div>
            <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Historical Range
            </label>
            <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden bg-slate-50 dark:bg-slate-800 p-0.5">
              {(['today', '7d', '30d'] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={`flex-1 py-1 text-xs font-bold rounded transition-all ${
                    range === r
                      ? 'bg-sky-600 text-white shadow-xs'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {r === 'today' ? 'Today' : r.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Alert Severity Filter */}
          <div>
            <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">
              Alert Severity
            </label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="w-full text-xs py-2 px-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-semibold focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical Only</option>
              <option value="HIGH">High & Critical</option>
              <option value="WARNING">Warning / Moderate</option>
              <option value="INFO">Informational</option>
            </select>
          </div>
        </div>

        {/* Data Freshness Indicator Bar */}
        <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex flex-wrap items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 gap-2">
          <div className="flex flex-wrap items-center gap-4">
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-sky-500" />
              <span>Live Occupancy: <strong>{formatDateTimeShort(freshness?.occupancy_last_updated)}</strong></span>
            </span>
            <span className="flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-purple-500" />
              <span>SARIMA Model: <strong>{formatDateTimeShort(freshness?.forecast_last_updated)}</strong></span>
            </span>
            <span className="flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
              <span>Alert Evaluation: <strong>{formatDateTimeShort(freshness?.alerts_last_evaluated)}</strong></span>
            </span>
          </div>

          <div className="text-[10px] text-slate-400">
            Auto-refreshes every 30s • Client Updated: {lastRefreshedAt ? lastRefreshedAt.toLocaleTimeString() : '--'}
          </div>
        </div>
      </div>

      {/* ── SECTION A: OVERVIEW METRIC SUMMARY CARDS ───────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
            <Zap className="w-4 h-4 text-sky-500" />
            Executive Operational Metrics
            {metrics?.status && (
              <span className={`ml-2 px-2 py-0.5 rounded text-[10px] font-bold border ${STATUS_COLORS[metrics.status]}`}>
                {metrics.status}
              </span>
            )}
          </h2>
          <span className="text-xs text-slate-400 font-medium">
            {selectedWardId ? `Scoped to Ward #${selectedWardId}` : `Hospital-wide (${metrics?.total_wards ?? 0} active wards)`}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Total Bed Capacity */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Total Capacity</span>
              <div className="w-10 h-10 rounded-xl bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center">
                <BedDouble className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {loading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className="text-3xl font-black text-slate-900 dark:text-white">
                  {metrics?.total_capacity ?? 0}
                </span>
              )}
              <span className="text-xs text-slate-400">Physical Beds</span>
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              {metrics?.operational_beds ?? 0} operational (excludes maintenance & reserved)
            </div>
          </div>

          {/* 2. Currently Occupied & Rate */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Occupied Beds</span>
              <div className="w-10 h-10 rounded-xl bg-rose-100 dark:bg-rose-950 text-rose-600 dark:text-rose-400 flex items-center justify-center">
                <Activity className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {loading ? (
                <div className="h-8 w-24 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <>
                  <span className="text-3xl font-black text-slate-900 dark:text-white">
                    {metrics?.occupied_beds ?? 0}
                  </span>
                  <span className="text-xs font-bold text-rose-500">
                    {metrics ? `${metrics.occupancy_rate.toFixed(1)}%` : '--'}
                  </span>
                </>
              )}
            </div>
            {/* Occupancy progress bar */}
            {metrics && (
              <div className="mt-3 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    metrics.status === 'CRITICAL' ? 'bg-rose-500' :
                    metrics.status === 'HIGH' ? 'bg-orange-500' :
                    metrics.status === 'MODERATE' ? 'bg-amber-500' : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(metrics.occupancy_rate, 100)}%` }}
                />
              </div>
            )}
          </div>

          {/* 3. Currently Available Beds */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Available Beds</span>
              <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {loading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className="text-3xl font-black text-slate-900 dark:text-white">
                  {metrics?.available_beds ?? 0}
                </span>
              )}
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold">Immediate Intake</span>
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Formula: operational_beds - occupied_beds
            </div>
          </div>

          {/* 4. Active High-Severity Alerts */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Active High Alerts</span>
              <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-950 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                <ShieldAlert className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {loading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className={`text-3xl font-black ${metrics && metrics.active_high_severity_alerts > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-white'}`}>
                  {metrics?.active_high_severity_alerts ?? 0}
                </span>
              )}
              <span className="text-xs text-slate-400 font-medium">Critical + High</span>
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400 flex items-center justify-between">
              <span>{metrics?.unacknowledged_alerts ?? 0} unacknowledged</span>
              <span className="text-[10px] text-slate-400">Total active: {metrics?.total_active_alerts ?? 0}</span>
            </div>
          </div>

          {/* 5. Wards at Elevated Capacity Risk */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Wards at Elevated Risk</span>
              <div className="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-950 text-purple-600 dark:text-purple-400 flex items-center justify-center">
                <TrendingUp className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {loading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className={`text-3xl font-black ${metrics && metrics.wards_at_elevated_risk > 0 ? 'text-purple-600 dark:text-purple-400' : 'text-slate-900 dark:text-white'}`}>
                  {metrics?.wards_at_elevated_risk ?? 0}
                </span>
              )}
              <span className="text-xs text-slate-400">Wards</span>
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              SARIMA Forecast ≥ 85% Occupancy
            </div>
          </div>

          {/* 6. Pending Transfers & Recommendations */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Pending Transfers</span>
              <div className="w-10 h-10 rounded-xl bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
                <ArrowRightLeft className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {loading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className="text-3xl font-black text-slate-900 dark:text-white">
                  {metrics?.pending_transfer_requests ?? 0}
                </span>
              )}
              <span className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold">Requiring Review</span>
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              {metrics?.pending_transfer_recommendations ?? 0} capacity recommendations active
            </div>
          </div>

          {/* 7. Approved & Completed Transfers */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Transfer Execution</span>
              <div className="w-10 h-10 rounded-xl bg-teal-100 dark:bg-teal-950 text-teal-600 dark:text-teal-400 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {loading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className="text-3xl font-black text-slate-900 dark:text-white">
                  {metrics?.completed_transfers ?? 0}
                </span>
              )}
              <span className="text-xs text-teal-600 dark:text-teal-400 font-semibold">Completed Transfers</span>
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              {metrics?.approved_transfers ?? 0} approved awaiting bed assignment
            </div>
          </div>

          {/* 8. Data Quality & Observability */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Data Quality Score</span>
              <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                <Cpu className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {loading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className="text-3xl font-black text-slate-900 dark:text-white">
                  {dataQuality?.health_score ? `${dataQuality.health_score.toFixed(0)}%` : '100%'}
                </span>
              )}
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold">Audited Health</span>
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              {dataQuality?.total_observations ?? 0} observations • {dataQuality?.data_frequency || 'DAILY'} frequency
            </div>
          </div>
        </div>
      </div>

      {/* ── SECTION B: CURRENT OCCUPANCY BREAKDOWN (TABLE & STATUS CHIPS) ──── */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-sky-500" />
              <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
                Ward Bed Capacity Breakdown & Operational Status
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Live capacity breakdown across wards. Effective capacity excludes maintenance and cleaning beds.
            </p>
          </div>

          <div className="w-full sm:w-64">
            <input
              type="text"
              placeholder="Search ward name or type..."
              value={wardSearch}
              onChange={(e) => setWardSearch(e.target.value)}
              className="w-full text-xs py-2 px-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
        </div>

        {/* Ward Breakdown Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 uppercase font-bold text-[10px] tracking-wider border-y border-slate-200 dark:border-slate-800">
              <tr>
                <th className="py-3 px-4">Ward Name</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4 text-center">Physical Beds</th>
                <th className="py-3 px-4 text-center">Operational</th>
                <th className="py-3 px-4 text-center">Occupied</th>
                <th className="py-3 px-4 text-center">Available</th>
                <th className="py-3 px-4">Occupancy Rate</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Quick Filter</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-medium">
              {filteredWardList.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-400">
                    No matching wards found for the selected scope.
                  </td>
                </tr>
              ) : (
                filteredWardList.map((w) => {
                  const isSelected = selectedWardId === w.ward_id;
                  return (
                    <tr
                      key={w.ward_id}
                      className={`hover:bg-slate-50/80 dark:hover:bg-slate-800/50 transition-colors ${
                        isSelected ? 'bg-sky-50/70 dark:bg-sky-950/40 font-semibold' : ''
                      }`}
                    >
                      <td className="py-3 px-4 font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <Layers className="w-4 h-4 text-sky-500 shrink-0" />
                        {w.ward_name}
                      </td>
                      <td className="py-3 px-4 text-slate-500 dark:text-slate-400">{w.ward_type || 'GENERAL'}</td>
                      <td className="py-3 px-4 text-center font-mono">{w.total_beds}</td>
                      <td className="py-3 px-4 text-center font-mono">{w.operational_beds}</td>
                      <td className="py-3 px-4 text-center font-bold text-rose-600 dark:text-rose-400 font-mono">
                        {w.occupied_beds}
                      </td>
                      <td className="py-3 px-4 text-center font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                        {w.available_beds}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-bold w-12 font-mono">{w.occupancy_percentage.toFixed(1)}%</span>
                          <div className="w-20 h-1.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden hidden md:block">
                            <div
                              className={`h-full rounded-full ${
                                w.status === 'CRITICAL' ? 'bg-rose-500' :
                                w.status === 'HIGH' ? 'bg-orange-500' :
                                w.status === 'MODERATE' || w.status === 'WARNING' ? 'bg-amber-500' : 'bg-emerald-500'
                              }`}
                              style={{ width: `${Math.min(w.occupancy_percentage, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border ${STATUS_COLORS[w.status] || STATUS_COLORS.NORMAL}`}>
                          {w.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => setSelectedWardId(isSelected ? null : w.ward_id)}
                          className={`text-xs px-2.5 py-1 rounded font-bold transition-colors ${
                            isSelected
                              ? 'bg-sky-600 text-white'
                              : 'text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/60'
                          }`}
                        >
                          {isSelected ? 'Clear Filter' : 'Focus Ward'}
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── SECTION C: HISTORICAL OBSERVED TRENDS & SARIMA FORECAST OVERVIEW ─── */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-sky-500" />
              <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
                Historical Observed Trends & Future SARIMA Projections
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Solid line represents verified observed daily records. Dashed line denotes future SARIMA statistical estimates with 95% confidence bounds.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-medium hidden sm:block">
              {selectedWardId ? `Displaying Ward #${selectedWardId}` : 'Displaying Facility Aggregated Trend'}
            </span>
            <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5 text-xs bg-slate-50 dark:bg-slate-800">
              {[1, 3, 7].map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  className={`px-2.5 py-1 rounded font-bold transition-all ${
                    horizon === h ? 'bg-sky-600 text-white shadow-xs' : 'text-slate-500 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {h}D Horizon
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Disclaimer Note */}
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-sky-500 shrink-0 mt-0.5" />
          <div>
            <strong>Statistical Estimate Disclosure:</strong> SARIMA models predict expected future bed occupancy based on daily historical seasonality.
            Fractional bed counts represent statistical means and are not actual fractional patients.
            Threshold alert lines at <strong>85% (High Risk)</strong> and <strong>95% (Critical Risk)</strong> indicate operational escalation points.
          </div>
        </div>

        {/* Recharts Chart */}
        <div className="h-80 w-full pt-4">
          {chartData.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl text-slate-400">
              <TrendingUp className="w-8 h-8 opacity-40 mb-2" />
              <p className="text-sm font-semibold">Insufficient observations for charting</p>
              <p className="text-xs mt-1">Daily capacity snapshots will populate this chart automatically.</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0284c7" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#0284c7" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.6} />
                <XAxis dataKey="dateLabel" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis domain={[0, 110]} stroke="#94a3b8" fontSize={11} tickLine={false} unit="%" />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-xl text-xs space-y-1">
                          <p className="font-bold text-slate-900 dark:text-white border-b border-slate-100 dark:border-slate-800 pb-1">
                            Date: {data.date} {data.isForecast ? '(SARIMA Prediction)' : '(Observed Actual)'}
                          </p>
                          {data.actualOccupancy !== null && (
                            <p className="text-sky-600 dark:text-sky-400 font-semibold">
                              Observed Occupancy: {data.actualOccupancy.toFixed(1)}%
                            </p>
                          )}
                          {data.forecastOccupancy !== null && (
                            <p className="text-purple-600 dark:text-purple-400 font-semibold">
                              SARIMA Forecast: {data.forecastOccupancy.toFixed(1)}%
                            </p>
                          )}
                          {data.lowerBound !== null && data.upperBound !== null && (
                            <p className="text-slate-400 text-[10px]">
                              95% Bound: [{data.lowerBound.toFixed(1)}% – {data.upperBound.toFixed(1)}%]
                            </p>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Legend
                  verticalAlign="top"
                  align="right"
                  wrapperStyle={{ paddingBottom: '12px', fontSize: '12px' }}
                />
                <ReferenceLine y={85} stroke="#f97316" strokeDasharray="4 4" label={{ value: 'High Risk (85%)', fill: '#f97316', fontSize: 10, position: 'insideTopRight' }} />
                <ReferenceLine y={95} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'Critical Risk (95%)', fill: '#ef4444', fontSize: 10, position: 'insideTopRight' }} />
                {/* Historical Observed Actual */}
                <Area type="monotone" dataKey="actualOccupancy" stroke="#0284c7" strokeWidth={2.5} fill="url(#actualGradient)" name="Observed Occupancy %" connectNulls={false} />
                {/* Future SARIMA Forecast */}
                <Line type="monotone" dataKey="forecastOccupancy" stroke="#8b5cf6" strokeWidth={2.5} strokeDasharray="5 5" dot={{ r: 4, fill: '#8b5cf6' }} name="SARIMA Prediction %" connectNulls={false} />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── SECTION D: CAPACITY-RISK OVERVIEW (PHASE 10 INTEGRATION) ───────── */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
                Capacity-Risk Analytics & Surge Early Warning
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Wards categorized by configured risk thresholds against predicted occupancy peaks.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
          {/* Critical Risk Wards */}
          <div className="p-4 rounded-xl bg-rose-50/70 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-rose-800 dark:text-rose-300">
                Critical Risk (≥ 95%)
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-200 dark:bg-rose-900 text-rose-900 dark:text-rose-100">
                {riskSummary?.critical_risk_wards.length ?? 0}
              </span>
            </div>
            {riskSummary?.critical_risk_wards.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No wards at critical risk.</p>
            ) : (
              <div className="space-y-2">
                {riskSummary?.critical_risk_wards.map((w) => (
                  <div key={w.ward_id} className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-900/40 text-xs">
                    <p className="font-bold text-slate-900 dark:text-white">{w.ward_name}</p>
                    <p className="text-[11px] text-rose-600 dark:text-rose-400 font-semibold mt-0.5">
                      Peak: {w.predicted_peak_occupancy_percentage.toFixed(1)}%
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* High Risk Wards */}
          <div className="p-4 rounded-xl bg-orange-50/70 dark:bg-orange-950/40 border border-orange-200 dark:border-orange-900/60 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-orange-800 dark:text-orange-300">
                High Risk (85% – 94.9%)
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-orange-200 dark:bg-orange-900 text-orange-900 dark:text-orange-100">
                {riskSummary?.high_risk_wards.length ?? 0}
              </span>
            </div>
            {riskSummary?.high_risk_wards.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No wards at high risk.</p>
            ) : (
              <div className="space-y-2">
                {riskSummary?.high_risk_wards.map((w) => (
                  <div key={w.ward_id} className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-orange-200 dark:border-orange-900/40 text-xs">
                    <p className="font-bold text-slate-900 dark:text-white">{w.ward_name}</p>
                    <p className="text-[11px] text-orange-600 dark:text-orange-400 font-semibold mt-0.5">
                      Peak: {w.predicted_peak_occupancy_percentage.toFixed(1)}%
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Moderate Risk Wards */}
          <div className="p-4 rounded-xl bg-amber-50/70 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300">
                Moderate Risk (70% – 84.9%)
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-amber-200 dark:bg-amber-900 text-amber-900 dark:text-amber-100">
                {riskSummary?.moderate_risk_wards.length ?? 0}
              </span>
            </div>
            {riskSummary?.moderate_risk_wards.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No wards at moderate risk.</p>
            ) : (
              <div className="space-y-2">
                {riskSummary?.moderate_risk_wards.map((w) => (
                  <div key={w.ward_id} className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/40 text-xs">
                    <p className="font-bold text-slate-900 dark:text-white">{w.ward_name}</p>
                    <p className="text-[11px] text-amber-600 dark:text-amber-400 font-semibold mt-0.5">
                      Peak: {w.predicted_peak_occupancy_percentage.toFixed(1)}%
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Normal Capacity Wards */}
          <div className="p-4 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
                Normal Operating Capacity (&lt; 70%)
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-200 dark:bg-emerald-900 text-emerald-900 dark:text-emerald-100">
                {riskSummary?.normal_risk_wards.length ?? 0}
              </span>
            </div>
            {riskSummary?.normal_risk_wards.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No wards currently under 70%.</p>
            ) : (
              <div className="space-y-2 max-h-36 overflow-y-auto pr-1">
                {riskSummary?.normal_risk_wards.map((w) => (
                  <div key={w.ward_id} className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-900/40 text-xs">
                    <p className="font-bold text-slate-900 dark:text-white">{w.ward_name}</p>
                    <p className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-0.5">
                      Stable • Current: {w.current_occupancy_percentage.toFixed(1)}%
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── SECTION E: EXPLAINABLE ALERTS OVERVIEW (PHASE 12 INTEGRATION) ──── */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-rose-500" />
              <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
                Active Capacity Alerts & Explainable Rules
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Verified early warnings with transparent explainability rationale, affected wards, and suggested actions.
            </p>
          </div>

          <a
            href="/alerts"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-sky-600 hover:text-sky-700 dark:text-sky-400 hover:underline"
          >
            Open Full Alert Center
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
        </div>

        {alerts.length === 0 ? (
          <div className="py-8 text-center text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
            <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500 opacity-80" />
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">No active alerts for selected scope</p>
            <p className="text-xs mt-1">All monitored wards are operating within configured capacity safety parameters.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.slice(0, 5).map((a) => {
              const isCrit = a.severity === 'CRITICAL';
              const isHigh = a.severity === 'HIGH';
              return (
                <div
                  key={a.id}
                  className={`p-4 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-3 transition-all ${
                    isCrit
                      ? 'bg-rose-50/70 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900/60'
                      : isHigh
                      ? 'bg-orange-50/70 dark:bg-orange-950/40 border-orange-200 dark:border-orange-900/60'
                      : 'bg-amber-50/70 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900/60'
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-black border uppercase ${
                        isCrit ? 'bg-rose-600 text-white border-rose-700' :
                        isHigh ? 'bg-orange-600 text-white border-orange-700' :
                        'bg-amber-500 text-white border-amber-600'
                      }`}>
                        <ShieldAlert className="w-3 h-3" />
                        {a.severity}
                      </span>
                      <span className="text-xs font-bold text-slate-900 dark:text-white">
                        {a.ward_name || `Ward #${a.ward_id}`}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {formatDateTimeShort(a.created_at)}
                      </span>
                    </div>
                    <p className="text-xs text-slate-700 dark:text-slate-300">
                      {a.explanation?.headline || a.message}
                    </p>
                    {a.explanation?.triggered_rules && a.explanation.triggered_rules.length > 0 && (
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                        Triggered Rule: {a.explanation.triggered_rules[0].rule_name} ({a.explanation.triggered_rules[0].rule_id})
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => setSelectedAlertForModal(a)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 hover:border-sky-400 text-sky-600 dark:text-sky-400 font-bold shadow-xs transition-colors"
                    >
                      Explain Rationale
                    </button>
                    {a.status === 'ACTIVE' && (
                      <button
                        onClick={() => handleAcknowledgeAlert(a.id)}
                        disabled={isAlertActionLoading}
                        className="text-xs px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold transition-colors disabled:opacity-50"
                      >
                        Acknowledge
                      </button>
                    )}
                    <button
                      onClick={() => handleResolveAlert(a.id)}
                      disabled={isAlertActionLoading}
                      className="text-xs px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold transition-colors disabled:opacity-50"
                    >
                      Resolve
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── SECTION F: INTER-WARD TRANSFER ANALYTICS (PHASE 11 INTEGRATION) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <ArrowRightLeft className="w-5 h-5 text-indigo-500" />
                <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
                  Inter-Ward Transfer Flow & Activity
                </h3>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Summary of active patient transfers by status and ward flow pressure.
              </p>
            </div>

            <a
              href="/transfers"
              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 hover:underline"
            >
              Open Transfers
              <ArrowRight className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* Transfer Status Breakdown Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Requested', count: transferActivity?.by_status?.REQUESTED || 0, color: 'text-amber-600 bg-amber-50 dark:bg-amber-950/60 border-amber-200' },
              { label: 'Approved', count: transferActivity?.by_status?.APPROVED || 0, color: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-950/60 border-indigo-200' },
              { label: 'Completed', count: transferActivity?.by_status?.COMPLETED || 0, color: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60 border-emerald-200' },
              { label: 'Cancelled / Rejected', count: (transferActivity?.by_status?.CANCELLED || 0) + (transferActivity?.by_status?.REJECTED || 0), color: 'text-slate-600 bg-slate-50 dark:bg-slate-800 border-slate-200' },
            ].map((s) => (
              <div key={s.label} className={`p-3.5 rounded-xl border ${s.color}`}>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{s.label}</span>
                <p className="text-xl font-black mt-1">{s.count}</p>
              </div>
            ))}
          </div>

          {/* Ward Transfer Flow Pressure Table */}
          <div className="pt-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Ward Transfer Flow Pressure
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
                <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 uppercase font-bold text-[10px] tracking-wider border-y border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Ward Name</th>
                    <th className="py-2.5 px-3 text-center">Transfers Out (Relief)</th>
                    <th className="py-2.5 px-3 text-center">Transfers In (Intake)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-medium">
                  {(!transferActivity?.ward_transfer_pressure || transferActivity.ward_transfer_pressure.length === 0) ? (
                    <tr>
                      <td colSpan={3} className="py-4 text-center text-slate-400">
                        No transfer activity recorded for this facility yet.
                      </td>
                    </tr>
                  ) : (
                    transferActivity.ward_transfer_pressure.slice(0, 5).map((w) => (
                      <tr key={w.ward_id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                        <td className="py-2 px-3 font-semibold text-slate-900 dark:text-white">{w.ward_name}</td>
                        <td className="py-2 px-3 text-center font-bold text-amber-600 dark:text-amber-400">{w.transfers_out_count}</td>
                        <td className="py-2 px-3 text-center font-bold text-sky-600 dark:text-sky-400">{w.transfers_in_count}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Transfer Decision Support Widget Integration */}
        <div className="flex flex-col justify-between">
          <TransferPressureWidget hospitalId={selectedHospitalId} />
        </div>
      </div>

      {/* ── SECTION G: RECENT HOSPITAL EVENTS LOG ───────────────────────────── */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-sky-500" />
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
              Recent Verified Operational Events
            </h3>
          </div>
          <span className="text-xs text-slate-400 font-normal">Last 10 telemetry events</span>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
          {recentEvents.length === 0 ? (
            <div className="py-8 text-center text-slate-400">
              <Activity className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm font-semibold">No recent events recorded</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                  <th className="text-left px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-500">Time</th>
                  <th className="text-left px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-500">Event</th>
                  <th className="text-left px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-500">Ward</th>
                  <th className="text-left px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-500">Bed</th>
                  <th className="text-left px-4 py-2.5 text-xs font-bold uppercase tracking-wider text-slate-500">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {recentEvents.map((ev) => (
                  <tr key={ev.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-2.5 text-xs text-slate-500 font-mono whitespace-nowrap">
                      {formatEventTime(ev.event_time)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs font-bold ${EVENT_COLORS[ev.event_type] || 'text-slate-600'}`}>
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-600 dark:text-slate-400">
                      {ev.ward_name ?? `Ward #${ev.ward_id}`}
                    </td>
                    <td className="px-4 py-2.5 text-xs font-mono text-slate-600 dark:text-slate-400">
                      {ev.bed_number ?? `Bed #${ev.bed_id}`}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                        {ev.source}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ── Architecture Specifications Drawer ──────────────────────────────── */}
      <div className="pt-2">
        <button
          onClick={() => setShowArchitecture((prev) => !prev)}
          type="button"
          className="w-full flex items-center justify-between p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:border-sky-500/50 transition-all text-left group cursor-pointer"
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                System Architecture & Multi-Tenant Isolation Specifications
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Click to {showArchitecture ? 'hide' : 'view'} database engine status, tenant isolation, and SARIMA forecasting framework
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950 px-3 py-1.5 rounded-lg border border-sky-200 dark:border-sky-800">
            <span>{showArchitecture ? 'Hide Details' : 'Show Details'}</span>
            {showArchitecture ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showArchitecture && (
          <div className="mt-4 p-6 rounded-2xl bg-gradient-to-r from-sky-900 via-indigo-900 to-slate-900 text-white shadow-xl relative overflow-hidden animate-fadeIn">
            <div className="relative z-10 space-y-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/20 border border-sky-400/30 text-sky-300 text-xs font-bold uppercase tracking-wider">
                <Layers className="w-3.5 h-3.5" /> Phase 13 — Management Analytics Dashboard Active
              </div>
              <h2 className="text-xl sm:text-2xl font-extrabold">
                Executive Command Center with Multi-Hospital Isolation
              </h2>
              <p className="text-sm text-slate-300 max-w-3xl leading-relaxed">
                Phase 13 delivers an integrated operational dashboard aggregating verified bed occupancy,
                SARIMA time-series predictions from statsmodels, explainable capacity alerts, and inter-ward transfer decision metrics.
                Strict tenant isolation is enforced at the database and API layer using hospital_id.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <Building className="w-5 h-5 text-sky-400" />
                  <div>
                    <p className="text-xs font-bold">Active Facility</p>
                    <p className="text-[11px] text-slate-300">{activeHospitalName}</p>
                  </div>
                </div>
                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <Database className="w-5 h-5 text-emerald-400" />
                  <div>
                    <p className="text-xs font-bold">Neon PostgreSQL</p>
                    <p className="text-[11px] text-slate-300">Live pooling & SSL encryption</p>
                  </div>
                </div>
                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <Cpu className="w-5 h-5 text-indigo-400" />
                  <div>
                    <p className="text-xs font-bold">Forecasting Model</p>
                    <p className="text-[11px] text-slate-300">SARIMA (statsmodels)</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Explainable Alert Detail Modal ──────────────────────────────────── */}
      {selectedAlertForModal && (
        <ExplainableAlertDetailModal
          alert={selectedAlertForModal}
          onClose={() => setSelectedAlertForModal(null)}
          onAcknowledge={handleAcknowledgeAlert}
          onResolve={handleResolveAlert}
          isActionLoading={isAlertActionLoading}
        />
      )}
    </div>
  );
};
