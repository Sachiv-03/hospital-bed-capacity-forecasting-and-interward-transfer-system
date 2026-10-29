import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { useAuth } from '../../context/AuthContext';
import {
  Ward,
  WardCreateInput,
  WardStatus,
  WardType,
  WardStatistics,
  Hospital,
} from '../../types';
import {
  getWards,
  getWardStatistics,
  createWard,
  updateWard,
  deactivateWard,
} from '../../services/wardService';
import { hospitalService } from '../../services/hospitalService';
import { WardFormModal } from '../../components/wards/WardFormModal';
import { DeactivateWardModal } from '../../components/wards/DeactivateWardModal';
import {
  Building2,
  Plus,
  Search,
  Eye,
  Edit,
  Power,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Layers,
  Building,
} from 'lucide-react';

const WARD_TYPES: { label: string; value: string }[] = [
  { label: 'All Types', value: '' },
  { label: 'General', value: 'GENERAL' },
  { label: 'ICU', value: 'ICU' },
  { label: 'Emergency', value: 'EMERGENCY' },
  { label: 'Pediatric', value: 'PEDIATRIC' },
  { label: 'Maternity', value: 'MATERNITY' },
  { label: 'Surgical', value: 'SURGICAL' },
  { label: 'Isolation', value: 'ISOLATION' },
  { label: 'Other', value: 'OTHER' },
];

const WARD_STATUSES: { label: string; value: string }[] = [
  { label: 'All Statuses', value: '' },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Inactive', value: 'INACTIVE' },
];

export const WardsPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const isSuperAdmin = user?.role === 'super_admin';

  // Data states
  const [wards, setWards] = useState<Ward[]>([]);
  const [statistics, setStatistics] = useState<WardStatistics | null>(null);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(10);

  // Filter & Search states
  const [searchInput, setSearchInput] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [selectedHospitalId, setSelectedHospitalId] = useState<number | undefined>(undefined);

  // UI Loading & Error states
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingStats, setLoadingStats] = useState<boolean>(true);
  const [errorList, setErrorList] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Modal states
  const [isFormModalOpen, setIsFormModalOpen] = useState<boolean>(false);
  const [editingWard, setEditingWard] = useState<Ward | null>(null);
  const [isFormSubmitting, setIsFormSubmitting] = useState<boolean>(false);
  const [modalApiError, setModalApiError] = useState<string | null>(null);

  const [deactivatingWard, setDeactivatingWard] = useState<Ward | null>(null);
  const [isDeactivating, setIsDeactivating] = useState<boolean>(false);

  const activeHospitalName =
    user?.hospital_name || (isSuperAdmin ? 'All Hospitals' : 'Apollo Medical Center');

  // Load Super Admin hospital options
  useEffect(() => {
    if (isSuperAdmin) {
      hospitalService
        .getHospitals({ limit: 100 })
        .then((res) => setHospitals(res.items))
        .catch((err) => console.error('Failed to load hospitals list:', err));
    }
  }, [isSuperAdmin]);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchInput);
      setPage(1);
    }, 400);

    return () => clearTimeout(handler);
  }, [searchInput]);

  // Toast auto-clear
  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  // Load Ward Statistics
  const loadStatistics = useCallback(async () => {
    setLoadingStats(true);
    try {
      const stats = await getWardStatistics(selectedHospitalId);
      setStatistics(stats);
    } catch (err: unknown) {
      console.error('Failed to load ward statistics:', err);
    } finally {
      setLoadingStats(false);
    }
  }, [selectedHospitalId]);

  // Load Ward List
  const loadWards = useCallback(async () => {
    setLoadingList(true);
    setErrorList(null);
    try {
      const data = await getWards({
        page,
        limit,
        search: debouncedSearch || undefined,
        ward_type: selectedType || undefined,
        status: selectedStatus || undefined,
        department: selectedDept || undefined,
        hospital_id: selectedHospitalId,
      });
      setWards(data.items);
      setTotalItems(data.total);
      setTotalPages(data.pages);
    } catch (err: unknown) {
      console.error('Failed to fetch wards list:', err);
      const errorMsg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Failed to load hospital wards.';
      setErrorList(errorMsg);
    } finally {
      setLoadingList(false);
    }
  }, [page, limit, debouncedSearch, selectedType, selectedStatus, selectedDept, selectedHospitalId]);

  useEffect(() => {
    loadStatistics();
  }, [loadStatistics]);

  useEffect(() => {
    loadWards();
  }, [loadWards]);

  // Handle Form Submission (Create or Edit)
  const handleFormSubmit = async (formData: WardCreateInput) => {
    setIsFormSubmitting(true);
    setModalApiError(null);
    try {
      if (editingWard) {
        await updateWard(editingWard.id, formData);
        setToastMessage({ type: 'success', text: `Ward '${formData.name}' updated successfully.` });
      } else {
        await createWard(formData);
        setToastMessage({ type: 'success', text: `Ward '${formData.name}' created successfully.` });
      }
      setIsFormModalOpen(false);
      setEditingWard(null);
      loadWards();
      loadStatistics();
    } catch (err: unknown) {
      const errorMsg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Failed to save ward information.';
      setModalApiError(errorMsg);
    } finally {
      setIsFormSubmitting(false);
    }
  };

  // Handle Ward Deactivation
  const handleDeactivateConfirm = async () => {
    if (!deactivatingWard) return;
    setIsDeactivating(true);
    try {
      await deactivateWard(deactivatingWard.id);
      setToastMessage({
        type: 'success',
        text: `Ward '${deactivatingWard.name}' has been safely set to INACTIVE.`,
      });
      setDeactivatingWard(null);
      loadWards();
      loadStatistics();
    } catch (err: unknown) {
      const errorMsg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Failed to deactivate ward.';
      setToastMessage({
        type: 'error',
        text: errorMsg,
      });
    } finally {
      setIsDeactivating(false);
    }
  };

  const clearFilters = () => {
    setSearchInput('');
    setDebouncedSearch('');
    setSelectedType('');
    setSelectedStatus('');
    setSelectedDept('');
    setSelectedHospitalId(undefined);
    setPage(1);
  };

  // Badge Color Helpers
  const getStatusBadge = (status: WardStatus) => {
    if (status === 'ACTIVE') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          ACTIVE
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
        INACTIVE
      </span>
    );
  };

  const getTypeBadge = (type: WardType) => {
    const colorMap: Record<WardType, string> = {
      ICU: 'bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800',
      EMERGENCY: 'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
      GENERAL: 'bg-sky-100 dark:bg-sky-950/80 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800',
      PEDIATRIC: 'bg-purple-100 dark:bg-purple-950/80 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
      MATERNITY: 'bg-pink-100 dark:bg-pink-950/80 text-pink-700 dark:text-pink-300 border-pink-200 dark:border-pink-800',
      SURGICAL: 'bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800',
      ISOLATION: 'bg-teal-100 dark:bg-teal-950/80 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800',
      OTHER: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    };

    return (
      <span className={`px-2.5 py-0.5 rounded-md text-[11px] font-bold tracking-wide uppercase border ${colorMap[type] || colorMap.OTHER}`}>
        {type}
      </span>
    );
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Toast Banner */}
      {toastMessage && (
        <div
          className={`p-4 rounded-xl shadow-lg border flex items-center justify-between transition-all ${
            toastMessage.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950/90 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200'
              : 'bg-rose-50 dark:bg-rose-950/90 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200'
          }`}
        >
          <div className="flex items-center gap-3">
            {toastMessage.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />
            )}
            <span className="text-sm font-semibold">{toastMessage.text}</span>
          </div>
          <button
            onClick={() => setToastMessage(null)}
            className="text-xs font-bold uppercase tracking-wider hover:opacity-80"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
              <Building className="w-3.5 h-3.5" />
              {activeHospitalName}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white flex items-center gap-3">
            <Building2 className="w-8 h-8 text-sky-600 dark:text-sky-400" />
            Ward Management
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Manage hospital wards, capacity, and availability for {activeHospitalName}.
          </p>
        </div>

        {isAdmin ? (
          <button
            onClick={() => {
              setEditingWard(null);
              setModalApiError(null);
              setIsFormModalOpen(true);
            }}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm text-white bg-sky-600 hover:bg-sky-500 shadow-md shadow-sky-600/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <Plus className="w-4 h-4 stroke-[3]" />
            <span>Add Ward</span>
          </button>
        ) : (
          <div className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700">
            Read-Only Staff Access
          </div>
        )}
      </div>

      {/* Statistics Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Wards */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Total Wards
            </span>
            <div className="w-10 h-10 rounded-xl bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold">
              <Building2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            {loadingStats ? (
              <div className="h-8 w-16 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
            ) : (
              <span className="text-3xl font-black text-slate-900 dark:text-white">
                {statistics?.total_wards ?? 0}
              </span>
            )}
            <span className="text-xs text-slate-400">Hospital Wards</span>
          </div>
        </div>

        {/* Active Wards */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Active Wards
            </span>
            <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            {loadingStats ? (
              <div className="h-8 w-16 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
            ) : (
              <span className="text-3xl font-black text-slate-900 dark:text-white">
                {statistics?.active_wards ?? 0}
              </span>
            )}
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold">Operational</span>
          </div>
        </div>

        {/* Total Capacity */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Total Capacity
            </span>
            <div className="w-10 h-10 rounded-xl bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            {loadingStats ? (
              <div className="h-8 w-16 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
            ) : (
              <span className="text-3xl font-black text-slate-900 dark:text-white">
                {statistics?.total_capacity ?? 0}
              </span>
            )}
            <span className="text-xs text-slate-400">Total Bed Capacity</span>
          </div>
        </div>

        {/* Inactive Wards */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Inactive Wards
            </span>
            <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-950 text-amber-600 dark:text-amber-400 flex items-center justify-center font-bold">
              <Power className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            {loadingStats ? (
              <div className="h-8 w-16 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
            ) : (
              <span className="text-3xl font-black text-slate-900 dark:text-white">
                {statistics?.inactive_wards ?? 0}
              </span>
            )}
            <span className="text-xs text-slate-400">Offline / Maintenance</span>
          </div>
        </div>
      </div>

      {/* Filter and Search Controls */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Search Box */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search ward name or department..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all placeholder:text-slate-400"
            />
          </div>

          {/* Super Admin Hospital Selector Filter */}
          {isSuperAdmin && (
            <div>
              <select
                value={selectedHospitalId || ''}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value) : undefined;
                  setSelectedHospitalId(val);
                  setPage(1);
                }}
                className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all font-semibold"
              >
                <option value="">All Hospitals (Super Admin)</option>
                {hospitals.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.name} ({h.code})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Ward Type Select */}
          <div>
            <select
              value={selectedType}
              defaultValue=""
              onChange={(e) => {
                setSelectedType(e.target.value);
                setPage(1);
              }}
              className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all"
            >
              {WARD_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Status Select */}
          <div>
            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setPage(1);
              }}
              className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all"
            >
              {WARD_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Clear Filters Button */}
          <div className="flex items-center gap-2">
            {(searchInput || selectedType || selectedStatus || selectedHospitalId) && (
              <button
                onClick={clearFilters}
                className="w-full py-2 px-3 text-xs font-bold uppercase tracking-wider text-slate-600 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 bg-slate-100 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 transition-colors flex items-center justify-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Clear Filters
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Ward Data Table Card */}
      <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
        {loadingList ? (
          <div className="p-8 space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-slate-100 dark:bg-slate-800/60 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : errorList ? (
          <div className="p-12 text-center space-y-3">
            <AlertCircle className="w-10 h-10 text-rose-500 mx-auto" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">Unable to load wards</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">{errorList}</p>
            <button
              onClick={loadWards}
              className="px-4 py-2 text-xs font-bold text-sky-600 bg-sky-50 dark:bg-sky-950 rounded-xl border border-sky-200 dark:border-sky-800 hover:bg-sky-100 transition-colors"
            >
              Retry Connection
            </button>
          </div>
        ) : wards.length === 0 ? (
          <div className="p-12 text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
              <Building2 className="w-8 h-8" />
            </div>
            {debouncedSearch || selectedType || selectedStatus || selectedHospitalId ? (
              <div>
                <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">No wards match your search</h3>
                <p className="text-xs text-slate-500 mt-1">Try adjusting your filters or search keywords.</p>
                <button
                  onClick={clearFilters}
                  className="mt-4 px-4 py-2 text-xs font-bold text-sky-600 bg-sky-50 dark:bg-sky-950 rounded-xl border border-sky-200 dark:border-sky-800"
                >
                  Clear Search & Filters
                </button>
              </div>
            ) : (
              <div>
                <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">No wards found</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Add your first ward to start managing hospital capacity and inter-ward transfers.
                </p>
                {isAdmin && (
                  <button
                    onClick={() => {
                      setEditingWard(null);
                      setModalApiError(null);
                      setIsFormModalOpen(true);
                    }}
                    className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-xs font-bold text-white bg-sky-600 hover:bg-sky-500 rounded-xl shadow-md"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Add Ward</span>
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <th className="py-3.5 px-4 sm:px-6">Ward Name</th>
                  {isSuperAdmin && <th className="py-3.5 px-4">Hospital</th>}
                  <th className="py-3.5 px-4">Ward Type</th>
                  <th className="py-3.5 px-4">Department</th>
                  <th className="py-3.5 px-4">Floor</th>
                  <th className="py-3.5 px-4">Capacity</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 sm:px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {wards.map((ward) => (
                  <tr
                    key={ward.id}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors group"
                  >
                    {/* Ward Name & Description */}
                    <td className="py-4 px-4 sm:px-6">
                      <div className="font-bold text-slate-900 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                        {ward.name}
                      </div>
                      {ward.description && (
                        <div className="text-xs text-slate-500 dark:text-slate-400 line-clamp-1 mt-0.5">
                          {ward.description}
                        </div>
                      )}
                    </td>

                    {/* Hospital Column for Super Admin */}
                    {isSuperAdmin && (
                      <td className="py-4 px-4 font-medium text-slate-600 dark:text-slate-400 text-xs">
                        <span className="px-2 py-0.5 rounded bg-sky-50 dark:bg-sky-950 text-sky-700 dark:text-sky-300 font-semibold border border-sky-200 dark:border-sky-800">
                          {ward.hospital_name || `Hospital #${ward.hospital_id}`}
                        </span>
                      </td>
                    )}

                    {/* Ward Type */}
                    <td className="py-4 px-4">{getTypeBadge(ward.ward_type)}</td>

                    {/* Department */}
                    <td className="py-4 px-4 font-semibold text-slate-700 dark:text-slate-300">
                      {ward.department}
                    </td>

                    {/* Floor */}
                    <td className="py-4 px-4 text-slate-600 dark:text-slate-400 text-xs font-medium">
                      {ward.floor}
                    </td>

                    {/* Capacity */}
                    <td className="py-4 px-4 font-black text-slate-900 dark:text-white">
                      {ward.capacity}{' '}
                      <span className="text-[11px] font-normal text-slate-400">beds</span>
                    </td>

                    {/* Status */}
                    <td className="py-4 px-4">{getStatusBadge(ward.status)}</td>

                    {/* Actions */}
                    <td className="py-4 px-4 sm:px-6 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* View Details */}
                        <button
                          onClick={() => navigate(`/wards/${ward.id}`)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-sky-600 dark:hover:text-sky-400 hover:bg-sky-50 dark:hover:bg-sky-950/60 transition-colors"
                          title="View Ward Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>

                        {/* Edit Ward (Admin / Super Admin) */}
                        {isAdmin && (
                          <button
                            onClick={() => {
                              setEditingWard(ward);
                              setModalApiError(null);
                              setIsFormModalOpen(true);
                            }}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/60 transition-colors"
                            title="Edit Ward"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                        )}

                        {/* Deactivate Ward (Admin / Super Admin) */}
                        {isAdmin && ward.status === 'ACTIVE' && (
                          <button
                            onClick={() => setDeactivatingWard(ward)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-amber-600 dark:hover:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/60 transition-colors"
                            title="Deactivate Ward"
                          >
                            <Power className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {!loadingList && !errorList && wards.length > 0 && (
          <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
            <div>
              Showing <span className="font-bold text-slate-800 dark:text-slate-200">{(page - 1) * limit + 1}</span> to{' '}
              <span className="font-bold text-slate-800 dark:text-slate-200">
                {Math.min(page * limit, totalItems)}
              </span>{' '}
              of <span className="font-bold text-slate-800 dark:text-slate-200">{totalItems}</span> wards
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-100 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-bold text-slate-800 dark:text-slate-200 px-2">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 disabled:opacity-40 hover:bg-slate-100 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Add / Edit Form Modal */}
      <WardFormModal
        isOpen={isFormModalOpen}
        onClose={() => {
          setIsFormModalOpen(false);
          setEditingWard(null);
        }}
        onSubmit={handleFormSubmit}
        initialData={editingWard}
        isSubmitting={isFormSubmitting}
        apiError={modalApiError}
      />

      {/* Deactivate Ward Confirmation Modal */}
      <DeactivateWardModal
        isOpen={!!deactivatingWard}
        onClose={() => setDeactivatingWard(null)}
        onConfirm={handleDeactivateConfirm}
        wardName={deactivatingWard?.name || ''}
        isDeactivating={isDeactivating}
      />
    </div>
  );
};
