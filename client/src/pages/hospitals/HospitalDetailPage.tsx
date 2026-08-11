import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { AxiosError } from 'axios';
import { Hospital } from '../../types';
import { hospitalService } from '../../services/hospitalService';
import {
  Building,
  ArrowLeft,
  MapPin,
  CheckCircle2,
  AlertCircle,
  Building2,
  Layers,
  Calendar,
  ShieldCheck,
} from 'lucide-react';

export const HospitalDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    hospitalService
      .getHospitalById(parseInt(id))
      .then((data) => {
        setHospital(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        const msg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Failed to fetch hospital details.';
        setError(msg);
        setLoading(false);
      });
  }, [id]);

  if (loading) {
    return (
      <div className="p-8 space-y-4">
        <div className="h-8 w-48 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
        <div className="h-64 bg-slate-100 dark:bg-slate-900 rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (error || !hospital) {
    return (
      <div className="p-12 text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-xl font-bold text-slate-800 dark:text-slate-200">Hospital Not Found</h2>
        <p className="text-sm text-slate-500">{error || 'The requested hospital facility does not exist.'}</p>
        <button
          onClick={() => navigate('/hospitals')}
          className="px-4 py-2 text-xs font-bold text-sky-600 bg-sky-50 dark:bg-sky-950 rounded-xl border border-sky-200"
        >
          Back to Hospitals Directory
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Back Button */}
      <div>
        <Link
          to="/hospitals"
          className="inline-flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-sky-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Hospitals</span>
        </Link>
      </div>

      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold text-xl">
            <Building className="w-8 h-8" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-extrabold text-slate-900 dark:text-white">{hospital.name}</h1>
              <span className="px-2.5 py-0.5 rounded bg-sky-100 dark:bg-sky-950 text-sky-800 dark:text-sky-300 font-mono text-xs font-bold border border-sky-200 dark:border-sky-800">
                {hospital.code}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5" />
              {[hospital.address, hospital.city, hospital.state, hospital.country].filter(Boolean).join(', ') || 'Address not specified'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold ${
              hospital.status === 'ACTIVE'
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200'
                : 'bg-slate-100 text-slate-600 border border-slate-200'
            }`}
          >
            {hospital.status}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Total Wards</span>
            <Building2 className="w-5 h-5 text-sky-500" />
          </div>
          <div className="mt-3 text-3xl font-black text-slate-900 dark:text-white">{hospital.ward_count ?? 0}</div>
          <p className="text-xs text-slate-500 mt-1">Configured Wards</p>
        </div>

        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Total Capacity</span>
            <Layers className="w-5 h-5 text-indigo-500" />
          </div>
          <div className="mt-3 text-3xl font-black text-slate-900 dark:text-white">{hospital.total_capacity ?? 0}</div>
          <p className="text-xs text-slate-500 mt-1">Total Active Bed Capacity</p>
        </div>

        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Isolation Security</span>
            <ShieldCheck className="w-5 h-5 text-emerald-500" />
          </div>
          <div className="mt-3 text-lg font-bold text-emerald-600 dark:text-emerald-400">Enforced</div>
          <p className="text-xs text-slate-500 mt-1">FastAPI DB Filter Active</p>
        </div>
      </div>

      {/* System Information Card */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wider">Facility Details</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-slate-400">Facility ID:</span>
            <span className="font-bold text-slate-800 dark:text-slate-200 ml-2">{hospital.id}</span>
          </div>
          <div>
            <span className="text-slate-400">Hospital Code:</span>
            <span className="font-bold text-slate-800 dark:text-slate-200 ml-2">{hospital.code}</span>
          </div>
          <div>
            <span className="text-slate-400">Created At:</span>
            <span className="font-bold text-slate-800 dark:text-slate-200 ml-2">
              {new Date(hospital.created_at).toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Last Updated:</span>
            <span className="font-bold text-slate-800 dark:text-slate-200 ml-2">
              {new Date(hospital.updated_at).toLocaleString()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
