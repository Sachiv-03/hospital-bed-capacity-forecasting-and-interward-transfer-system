import React, { useEffect, useState } from 'react';
import { fetchHealthStatus } from '../services/api';
import { getWardStatistics } from '../services/wardService';
import { HealthStatus, WardStatistics } from '../types';
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
  Server,
  Cpu,
  Layers,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [wardStats, setWardStats] = useState<WardStatistics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showArchitecture, setShowArchitecture] = useState<boolean>(false);

  useEffect(() => {
    Promise.all([fetchHealthStatus(), getWardStatistics()])
      .then(([healthData, statsData]) => {
        setHealth(healthData);
        setWardStats(statsData);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch dashboard telemetry:', err);
        setError('FastAPI Server unreachable on localhost:8000');
        setLoading(false);
      });
  }, []);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Hospital Bed Capacity Forecasting Dashboard
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Welcome back, <span className="font-bold text-sky-600 dark:text-sky-400">{user?.full_name}</span> ({user?.role?.toUpperCase()}) • Real-time Bed Occupancy & Transfer System
          </p>
        </div>

        {/* Backend & Live PostgreSQL Health Status Badge */}
        <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs text-xs font-semibold">
          {loading ? (
            <div className="flex items-center gap-2 text-slate-500">
              <span className="w-2 h-2 rounded-full bg-slate-400 animate-ping" />
              Testing PostgreSQL Connection...
            </div>
          ) : error ? (
            <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
              <AlertCircle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
              <span>FastAPI & PostgreSQL ({health?.database || 'connected'})</span>
            </div>
          )}
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total Ward Capacity Card */}
        <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Total Capacity
            </span>
            <div className="w-10 h-10 rounded-lg bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center">
              <BedDouble className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 dark:text-white">
              {wardStats?.total_capacity ?? 0}
            </span>
            <span className="text-xs text-slate-400">Total Ward Beds</span>
          </div>
          <p className="text-xs text-slate-500 mt-2">Configured in Neon PostgreSQL</p>
        </div>

        {/* Active Wards Card */}
        <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Active Wards
            </span>
            <div className="w-10 h-10 rounded-lg bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <Building2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 dark:text-white">
              {wardStats?.active_wards ?? 0}
            </span>
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
              of {wardStats?.total_wards ?? 0} Wards
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-2">Live Ward Topology</p>
        </div>


        {/* Forecast Occupancy Card */}
        <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              24h AI Occupancy Forecast
            </span>
            <div className="w-10 h-10 rounded-lg bg-amber-100 dark:bg-amber-950 text-amber-600 dark:text-amber-400 flex items-center justify-center">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 dark:text-white">-- %</span>
            <span className="text-xs text-amber-600 font-semibold">Ready for ML</span>
          </div>
          <p className="text-xs text-slate-500 mt-2">Time-series forecasting hook</p>
        </div>

        {/* Inter-Ward Transfers Card */}
        <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Inter-Ward Transfers
            </span>
            <div className="w-10 h-10 rounded-lg bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
              <ArrowRightLeft className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-black text-slate-900 dark:text-white">--</span>
            <span className="text-xs text-indigo-600 font-semibold">Queue Pipeline</span>
          </div>
          <p className="text-xs text-slate-500 mt-2">Optimization solver ready</p>
        </div>
      </div>

      {/* Optional Architecture Verification Toggle */}
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
                System Architecture & Technical Specifications
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Click to {showArchitecture ? 'hide' : 'view'} database engine status, JWT security specs, and backend details
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
                <Layers className="w-3.5 h-3.5" /> Phase 1 Foundation & Phase 2 JWT Authentication Active
              </div>

              <h2 className="text-xl sm:text-2xl font-extrabold">
                Enterprise Healthcare Platform & PostgreSQL Database Ready
              </h2>

              <p className="text-sm text-slate-300 max-w-3xl leading-relaxed">
                The database connection management engine, SQLAlchemy User ORM models, bcrypt password security, JWT token auto-refresh interceptors, role-based route guards, and health diagnostics are fully configured.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <Server className="w-5 h-5 text-sky-400" />
                  <div>
                    <p className="text-xs font-bold">FastAPI Backend</p>
                    <p className="text-[11px] text-slate-300">Swagger UI at /docs</p>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <Database className="w-5 h-5 text-emerald-400" />
                  <div>
                    <p className="text-xs font-bold">PostgreSQL Database</p>
                    <p className="text-[11px] text-slate-300">Status: {health?.database || 'connected'}</p>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center gap-3">
                  <ShieldCheck className="w-5 h-5 text-indigo-400" />
                  <div>
                    <p className="text-xs font-bold">JWT & RBAC Security</p>
                    <p className="text-[11px] text-slate-300">Active User: {user?.role}</p>
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
