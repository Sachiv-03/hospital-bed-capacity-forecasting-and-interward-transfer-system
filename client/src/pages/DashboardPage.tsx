import React, { useEffect, useRef, useState, useCallback } from 'react';
import { fetchHealthStatus } from '../services/api';
import { getWardStatistics } from '../services/wardService';
import { getHospitalCapacity, getEventHistory } from '../services/ingestionService';
import { HealthStatus, WardStatistics, HospitalCapacity, OccupancyEvent, CapacityStatus } from '../types';
import { useAuth } from '../context/AuthContext';
import {
  Activity,
  BedDouble,
  Building2,
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
} from 'lucide-react';

// ── Polling interval (ms) ────────────────────────────────────────────────────
const POLLING_INTERVAL_MS = 30_000;

// ── Capacity status badge ────────────────────────────────────────────────────
const STATUS_COLORS: Record<CapacityStatus, string> = {
  NORMAL:   'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
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

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [wardStats, setWardStats] = useState<WardStatistics | null>(null);
  const [capacity, setCapacity] = useState<HospitalCapacity | null>(null);
  const [recentEvents, setRecentEvents] = useState<OccupancyEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [capacityLoading, setCapacityLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showArchitecture, setShowArchitecture] = useState<boolean>(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const activeHospitalName =
    user?.hospital_name || (user?.role === 'super_admin' ? 'All Hospitals (System Admin View)' : 'Apollo Medical Center');

  // ── Load static data once ─────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([fetchHealthStatus(), getWardStatistics()])
      .then(([healthData, statsData]) => {
        setHealth(healthData);
        setWardStats(statsData);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch dashboard telemetry:', err);
        setError('FastAPI Server unreachable');
        setLoading(false);
      });
  }, []);

  // ── Load/poll real capacity data ──────────────────────────────────────────
  const loadCapacity = useCallback(async () => {
    if (!user?.hospital_id) return;
    setCapacityLoading(true);
    try {
      const [cap, events] = await Promise.all([
        getHospitalCapacity(user.hospital_id),
        getEventHistory({ hospital_id: user.hospital_id, limit: 10 }),
      ]);
      setCapacity(cap);
      setRecentEvents(events.items);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Capacity load failed:', err);
    } finally {
      setCapacityLoading(false);
    }
  }, [user?.hospital_id]);

  useEffect(() => {
    loadCapacity();
    // Set up polling — stop on unmount
    pollingRef.current = setInterval(() => {
      loadCapacity();
    }, POLLING_INTERVAL_MS);
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [loadCapacity]);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
              <Building className="w-3.5 h-3.5" />
              {activeHospitalName}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Hospital Bed Capacity & Command Dashboard
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Welcome back, <span className="font-bold text-sky-600 dark:text-sky-400">{user?.full_name}</span> ({user?.role?.toUpperCase()}) • Live Bed Occupancy Tracking
          </p>
        </div>

        {/* Status Badge */}
        <div className="flex items-center gap-2">
          {lastRefresh && (
            <span className="text-[10px] text-slate-400 hidden sm:block">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={loadCapacity}
            className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 hover:border-sky-400 transition-all"
            title="Refresh now"
          >
            <RefreshCw className={`w-4 h-4 text-slate-500 dark:text-slate-400 ${capacityLoading ? 'animate-spin' : ''}`} />
          </button>
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs text-xs font-semibold">
            {loading ? (
              <div className="flex items-center gap-2 text-slate-500">
                <span className="w-2 h-2 rounded-full bg-slate-400 animate-ping" />
                Connecting...
              </div>
            ) : error ? (
              <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
                <AlertCircle className="w-4 h-4" />
                <span>{error}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>FastAPI & Neon PostgreSQL ({health?.database || 'connected'})</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Live Capacity Overview Cards */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2">
            <Zap className="w-4 h-4 text-sky-500" />
            Live Bed Occupancy
            {capacity && (
              <span className={`ml-2 px-2 py-0.5 rounded-md text-[10px] font-bold border ${STATUS_COLORS[capacity.status as CapacityStatus]}`}>
                {capacity.status}
              </span>
            )}
          </h2>
          <span className="text-xs text-slate-400">Auto-refreshes every 30s</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {/* Total Beds */}
          <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Total Beds</span>
              <div className="w-10 h-10 rounded-lg bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center">
                <BedDouble className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {capacityLoading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className="text-3xl font-black text-slate-900 dark:text-white">
                  {capacity?.total_beds ?? wardStats?.total_capacity ?? 0}
                </span>
              )}
              <span className="text-xs text-slate-400">across {capacity?.total_wards ?? wardStats?.total_wards ?? 0} wards</span>
            </div>
          </div>

          {/* Occupied */}
          <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Occupied</span>
              <div className="w-10 h-10 rounded-lg bg-rose-100 dark:bg-rose-950 text-rose-600 dark:text-rose-400 flex items-center justify-center">
                <Activity className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {capacityLoading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <>
                  <span className="text-3xl font-black text-slate-900 dark:text-white">
                    {capacity?.occupied_beds ?? 0}
                  </span>
                  <span className="text-xs font-bold text-rose-500">
                    {capacity ? `${capacity.occupancy_percentage.toFixed(1)}%` : '--'}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Available */}
          <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Available</span>
              <div className="w-10 h-10 rounded-lg bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {capacityLoading ? (
                <div className="h-8 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <span className="text-3xl font-black text-slate-900 dark:text-white">
                  {capacity?.available_beds ?? 0}
                </span>
              )}
            </div>
          </div>

          {/* Occupancy % */}
          <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Occupancy</span>
              <div className="w-10 h-10 rounded-lg bg-amber-100 dark:bg-amber-950 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                <TrendingUp className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              {capacityLoading ? (
                <div className="h-8 w-24 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : (
                <>
                  <span className="text-3xl font-black text-slate-900 dark:text-white">
                    {capacity ? `${capacity.occupancy_percentage.toFixed(1)}%` : '0%'}
                  </span>
                  {capacity && (
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${STATUS_COLORS[capacity.status as CapacityStatus]}`}>
                      {capacity.status}
                    </span>
                  )}
                </>
              )}
            </div>
            {/* Occupancy bar */}
            {capacity && (
              <div className="mt-3 h-1.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    capacity.status === 'CRITICAL' ? 'bg-rose-500' :
                    capacity.status === 'HIGH' ? 'bg-orange-500' :
                    capacity.status === 'MODERATE' ? 'bg-amber-500' : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(capacity.occupancy_percentage, 100)}%` }}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bed Status Breakdown */}
      {capacity && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Occupied', val: capacity.occupied_beds, color: 'bg-rose-500' },
            { label: 'Available', val: capacity.available_beds, color: 'bg-emerald-500' },
            { label: 'Cleaning', val: capacity.cleaning_beds, color: 'bg-amber-500' },
            { label: 'Reserved', val: capacity.reserved_beds, color: 'bg-purple-500' },
            { label: 'Maintenance', val: capacity.maintenance_beds, color: 'bg-slate-500' },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-3 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <div className={`w-3 h-8 rounded-full ${item.color}`} />
              <div>
                <p className="text-xs text-slate-500 font-semibold">{item.label}</p>
                <p className="text-lg font-black text-slate-900 dark:text-white">{item.val}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Future Modules Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">24h AI Occupancy Forecast</span>
            <div className="w-10 h-10 rounded-lg bg-amber-100 dark:bg-amber-950 text-amber-600 dark:text-amber-400 flex items-center justify-center">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-2xl font-black text-slate-900 dark:text-white">-- %</span>
            <span className="ml-2 text-xs text-amber-600 font-semibold">ML Ready (Phase 7)</span>
          </div>
        </div>

        <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Inter-Ward Transfers</span>
            <div className="w-10 h-10 rounded-lg bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
              <ArrowRightLeft className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-2xl font-black text-slate-900 dark:text-white">--</span>
            <span className="ml-2 text-xs text-indigo-600 font-semibold">Stage 2 Pipeline</span>
          </div>
        </div>
      </div>

      {/* Recent Events Feed */}
      <div>
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-2 mb-3">
          <Clock className="w-4 h-4 text-sky-500" />
          Recent Hospital Events
          <span className="ml-auto text-xs text-slate-400 font-normal">Last 10 events</span>
        </h2>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
          {recentEvents.length === 0 ? (
            <div className="py-12 text-center text-slate-400">
              <Activity className="w-8 h-8 mx-auto mb-3 opacity-40" />
              <p className="text-sm font-medium">No events yet</p>
              <p className="text-xs mt-1">Start the simulator or trigger events to see activity here</p>
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

      {/* Architecture Toggle */}
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
                Multi-Hospital Architecture & System Specifications
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Click to {showArchitecture ? 'hide' : 'view'} database engine status, tenant isolation, and backend security
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
                <Layers className="w-3.5 h-3.5" /> Phase 6 Stage 1 — Data Pipeline Active
              </div>
              <h2 className="text-xl sm:text-2xl font-extrabold">
                Live Bed Tracking + Hospital Simulator Active
              </h2>
              <p className="text-sm text-slate-300 max-w-3xl leading-relaxed">
                Phase 6 Stage 1 adds real-time bed occupancy tracking via the ingestion pipeline.
                A hospital simulator generates ADMISSION, DISCHARGE, and maintenance events every 10 seconds.
                All data is isolated by hospital_id in Neon PostgreSQL.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <Building className="w-5 h-5 text-sky-400" />
                  <div>
                    <p className="text-xs font-bold">Active Hospital</p>
                    <p className="text-[11px] text-slate-300">{activeHospitalName}</p>
                  </div>
                </div>
                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <Database className="w-5 h-5 text-emerald-400" />
                  <div>
                    <p className="text-xs font-bold">PostgreSQL Database</p>
                    <p className="text-[11px] text-slate-300">beds + occupancy_events tables active</p>
                  </div>
                </div>
                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <ShieldCheck className="w-5 h-5 text-indigo-400" />
                  <div>
                    <p className="text-xs font-bold">Tenant Data Isolation</p>
                    <p className="text-[11px] text-slate-300">Enforced by FastAPI + hospital_id</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
