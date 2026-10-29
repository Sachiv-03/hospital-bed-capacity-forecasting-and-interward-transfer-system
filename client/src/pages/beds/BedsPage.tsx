import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { bedService } from '../../services/bedService';
import { getWards } from '../../services/wardService';
import { ingestEvent } from '../../services/ingestionService';
import { Bed, BedStatus, BedType, Ward, OccupancyEventType } from '../../types';
import {
  BedDouble,
  Search,
  Filter,
  Plus,
  RefreshCw,
  Activity,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Wrench,
  Bookmark,
  UserPlus,
  UserMinus,
  Trash2,
  Building,
  Layers,
  X,
} from 'lucide-react';

const STATUS_COLORS: Record<BedStatus, { bg: string; text: string; border: string; dot: string }> = {
  AVAILABLE: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/40',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-200 dark:border-emerald-800',
    dot: 'bg-emerald-500',
  },
  OCCUPIED: {
    bg: 'bg-rose-50 dark:bg-rose-950/40',
    text: 'text-rose-700 dark:text-rose-300',
    border: 'border-rose-200 dark:border-rose-800',
    dot: 'bg-rose-500',
  },
  CLEANING: {
    bg: 'bg-amber-50 dark:bg-amber-950/40',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-800',
    dot: 'bg-amber-500',
  },
  MAINTENANCE: {
    bg: 'bg-slate-100 dark:bg-slate-800/60',
    text: 'text-slate-700 dark:text-slate-300',
    border: 'border-slate-300 dark:border-slate-700',
    dot: 'bg-slate-500',
  },
  RESERVED: {
    bg: 'bg-purple-50 dark:bg-purple-950/40',
    text: 'text-purple-700 dark:text-purple-300',
    border: 'border-purple-200 dark:border-purple-800',
    dot: 'bg-purple-500',
  },
};

const getApiErrorMessage = (err: unknown, fallback: string): string => {
  if (axios.isAxiosError(err)) {
    return err.response?.data?.detail || fallback;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return fallback;
};

export const BedsPage: React.FC = () => {
  const { user } = useAuth();
  const [beds, setBeds] = useState<Bed[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [selectedWardId, setSelectedWardId] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [selectedBedType, setSelectedBedType] = useState<string>('ALL');

  // Modals
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [showEventModal, setShowEventModal] = useState<boolean>(false);
  const [selectedBedForEvent, setSelectedBedForEvent] = useState<Bed | null>(null);
  const [targetEventType, setTargetEventType] = useState<OccupancyEventType>('ADMISSION');

  // Add Bed Form
  const [newBedWardId, setNewBedWardId] = useState<number>(0);
  const [newBedNumber, setNewBedNumber] = useState<string>('');
  const [newBedType, setNewBedType] = useState<BedType>('STANDARD');
  const [newBedStatus, setNewBedStatus] = useState<BedStatus>('AVAILABLE');
  const [submittingAdd, setSubmittingAdd] = useState<boolean>(false);

  // Action submission
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  const activeHospitalId = user?.hospital_id || 1;
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  // ── Load Wards & Beds ─────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    try {
      setError(null);
      const [bedData, wardData] = await Promise.all([
        bedService.getBeds({
          hospital_id: activeHospitalId,
          limit: 200,
        }),
        getWards({ hospital_id: activeHospitalId, limit: 100 }),
      ]);
      setBeds(bedData.items || []);
      setWards(wardData.items || []);
      if (wardData.items && wardData.items.length > 0 && !newBedWardId) {
        setNewBedWardId(wardData.items[0].id);
      }
    } catch (err: unknown) {
      console.error('Failed to load bed telemetry:', err);
      setError(getApiErrorMessage(err, 'Failed to fetch bed data from server.'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeHospitalId, newBedWardId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  // ── Create Bed Handler ────────────────────────────────────────────────────
  const handleCreateBed = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBedWardId || !newBedNumber.trim()) return;

    setSubmittingAdd(true);
    try {
      await bedService.createBed({
        hospital_id: activeHospitalId,
        ward_id: Number(newBedWardId),
        bed_number: newBedNumber.trim().toUpperCase(),
        bed_type: newBedType,
        status: newBedStatus,
      });
      setShowAddModal(false);
      setNewBedNumber('');
      setActionSuccessMsg(`Bed "${newBedNumber.trim().toUpperCase()}" created successfully.`);
      setTimeout(() => setActionSuccessMsg(null), 4000);
      loadData();
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Failed to create bed'));
    } finally {
      setSubmittingAdd(false);
    }
  };

  // ── Delete Bed Handler ────────────────────────────────────────────────────
  const handleDeleteBed = async (bedId: number, bedNumber: string) => {
    if (!window.confirm(`Are you sure you want to delete bed ${bedNumber}?`)) return;
    try {
      await bedService.deleteBed(bedId);
      setActionSuccessMsg(`Bed ${bedNumber} deleted.`);
      setTimeout(() => setActionSuccessMsg(null), 3000);
      loadData();
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Failed to delete bed'));
    }
  };

  // ── Open Event Modal Handler ──────────────────────────────────────────────
  const openEventModal = (bed: Bed, eventType: OccupancyEventType) => {
    setSelectedBedForEvent(bed);
    setTargetEventType(eventType);
    setShowEventModal(true);
  };

  // ── Submit Event Handler ──────────────────────────────────────────────────
  const handleSubmitEvent = async () => {
    if (!selectedBedForEvent) return;

    setActionLoading(true);
    try {
      const eventId = `EVT-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      await ingestEvent({
        event_id: eventId,
        hospital_id: selectedBedForEvent.hospital_id,
        ward_id: selectedBedForEvent.ward_id,
        bed_id: selectedBedForEvent.id,
        event_type: targetEventType,
        event_time: new Date().toISOString(),
        source: 'MANUAL',
      });
      setShowEventModal(false);
      setActionSuccessMsg(`Event ${targetEventType} processed for bed ${selectedBedForEvent.bed_number}.`);
      setTimeout(() => setActionSuccessMsg(null), 4000);
      loadData();
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Failed to process event transition'));
    } finally {
      setActionLoading(false);
    }
  };

  // ── Filter Calculations ───────────────────────────────────────────────────
  const filteredBeds = beds.filter((b) => {
    const matchSearch =
      b.bed_number.toLowerCase().includes(search.toLowerCase()) ||
      (b.ward_name && b.ward_name.toLowerCase().includes(search.toLowerCase()));

    const matchWard = selectedWardId === 'ALL' || b.ward_id === Number(selectedWardId);
    const matchStatus = selectedStatus === 'ALL' || b.status === selectedStatus;
    const matchType = selectedBedType === 'ALL' || b.bed_type === selectedBedType;

    return matchSearch && matchWard && matchStatus && matchType;
  });

  const counts = {
    total: beds.length,
    available: beds.filter((b) => b.status === 'AVAILABLE').length,
    occupied: beds.filter((b) => b.status === 'OCCUPIED').length,
    cleaning: beds.filter((b) => b.status === 'CLEANING').length,
    maintenance: beds.filter((b) => b.status === 'MAINTENANCE').length,
    reserved: beds.filter((b) => b.status === 'RESERVED').length,
  };

  const occupancyRate = counts.total > 0 ? ((counts.occupied / counts.total) * 100).toFixed(1) : '0';

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
              <BedDouble className="w-3.5 h-3.5" />
              Real-Time Bed Telemetry & Management
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Hospital Bed Management
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Live availability tracking, patient admission/discharge events, and maintenance status transitions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:border-sky-500 transition-all shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          {isAdmin && (
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold transition-all shadow-md hover:shadow-lg"
            >
              <Plus className="w-4 h-4" />
              Add New Bed
            </button>
          )}
        </div>
      </div>

      {/* Success Notification Banner */}
      {actionSuccessMsg && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs font-medium animate-fadeIn">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionSuccessMsg}</span>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Total Beds</span>
            <BedDouble className="w-4 h-4 text-sky-500" />
          </div>
          <p className="text-2xl font-black text-slate-900 dark:text-white mt-2">{counts.total}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">{wards.length} active wards</p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Occupied</span>
            <Activity className="w-4 h-4 text-rose-500" />
          </div>
          <p className="text-2xl font-black text-rose-600 dark:text-rose-400 mt-2">{counts.occupied}</p>
          <p className="text-[11px] font-bold text-rose-500 mt-0.5">{occupancyRate}% rate</p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Available</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-2">{counts.available}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Ready for admission</p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Cleaning</span>
            <Sparkles className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-2xl font-black text-amber-600 dark:text-amber-400 mt-2">{counts.cleaning}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Turnaround pending</p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Reserved</span>
            <Bookmark className="w-4 h-4 text-purple-500" />
          </div>
          <p className="text-2xl font-black text-purple-600 dark:text-purple-400 mt-2">{counts.reserved}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Hold active</p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 uppercase tracking-wider">
            <span>Maintenance</span>
            <Wrench className="w-4 h-4 text-slate-500" />
          </div>
          <p className="text-2xl font-black text-slate-700 dark:text-slate-300 mt-2">{counts.maintenance}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Out of service</p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by bed number or ward name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-sky-500"
            />
          </div>

          {/* Ward Select */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 flex items-center gap-1 shrink-0">
              <Building className="w-3.5 h-3.5 text-sky-500" />
              Ward:
            </label>
            <select
              value={selectedWardId}
              onChange={(e) => setSelectedWardId(e.target.value)}
              className="px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 focus:outline-none focus:border-sky-500"
            >
              <option value="ALL">All Wards ({wards.length})</option>
              {wards.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.ward_type})
                </option>
              ))}
            </select>
          </div>

          {/* Bed Type Select */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 flex items-center gap-1 shrink-0">
              <Layers className="w-3.5 h-3.5 text-sky-500" />
              Type:
            </label>
            <select
              value={selectedBedType}
              onChange={(e) => setSelectedBedType(e.target.value)}
              className="px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 focus:outline-none focus:border-sky-500"
            >
              <option value="ALL">All Bed Types</option>
              <option value="STANDARD">Standard</option>
              <option value="ICU">ICU</option>
              <option value="ISOLATION">Isolation</option>
              <option value="EMERGENCY">Emergency</option>
            </select>
          </div>
        </div>

        {/* Status Filter Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pt-2 border-t border-slate-100 dark:border-slate-800/80 scrollbar-none">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mr-1 flex items-center gap-1">
            <Filter className="w-3 h-3" /> Status:
          </span>
          {[
            { id: 'ALL', label: `ALL (${counts.total})` },
            { id: 'AVAILABLE', label: `Available (${counts.available})` },
            { id: 'OCCUPIED', label: `Occupied (${counts.occupied})` },
            { id: 'CLEANING', label: `Cleaning (${counts.cleaning})` },
            { id: 'RESERVED', label: `Reserved (${counts.reserved})` },
            { id: 'MAINTENANCE', label: `Maintenance (${counts.maintenance})` },
          ].map((pill) => (
            <button
              key={pill.id}
              onClick={() => setSelectedStatus(pill.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                selectedStatus === pill.id
                  ? 'bg-sky-600 text-white shadow-xs'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {pill.label}
            </button>
          ))}
        </div>
      </div>

      {/* Bed Grid Display */}
      {loading ? (
        <div className="py-20 text-center text-slate-400 animate-pulse">
          <BedDouble className="w-10 h-10 mx-auto mb-3 opacity-40 animate-bounce" />
          <p className="text-sm font-semibold">Loading real-time bed grid telemetry...</p>
        </div>
      ) : error ? (
        <div className="p-8 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-center text-rose-700 dark:text-rose-300">
          <AlertCircle className="w-8 h-8 mx-auto mb-2" />
          <p className="font-bold text-sm">{error}</p>
        </div>
      ) : filteredBeds.length === 0 ? (
        <div className="py-16 text-center text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
          <BedDouble className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm font-bold text-slate-700 dark:text-slate-300">No beds match your current filter selection</p>
          <p className="text-xs text-slate-400 mt-1">Try resetting search or status filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {filteredBeds.map((bed) => {
            const colors = STATUS_COLORS[bed.status] || STATUS_COLORS.AVAILABLE;
            return (
              <div
                key={bed.id}
                className={`p-4 rounded-2xl border ${colors.border} ${colors.bg} shadow-xs hover:shadow-md transition-all flex flex-col justify-between group`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-base font-black tracking-tight text-slate-900 dark:text-white group-hover:text-sky-600 transition-colors">
                      {bed.bed_number}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase border ${colors.border} ${colors.text} bg-white dark:bg-slate-900`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
                      {bed.status}
                    </span>
                  </div>

                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                    <Building className="w-3.5 h-3.5 text-slate-400" />
                    {bed.ward_name || `Ward #${bed.ward_id}`}
                  </p>

                  <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="font-mono bg-white/60 dark:bg-slate-900/60 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-800">
                      {bed.bed_type}
                    </span>
                    {isAdmin && (
                      <button
                        onClick={() => handleDeleteBed(bed.id, bed.bed_number)}
                        className="text-slate-400 hover:text-rose-600 transition-colors p-1"
                        title="Delete Bed"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Event State Transition Quick Actions */}
                <div className="mt-4 pt-3 border-t border-slate-200/60 dark:border-slate-800/60 flex items-center gap-1.5 flex-wrap">
                  {bed.status === 'AVAILABLE' && (
                    <button
                      onClick={() => openEventModal(bed, 'ADMISSION')}
                      className="w-full flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold transition-all shadow-xs"
                    >
                      <UserPlus className="w-3.5 h-3.5" />
                      Admit Patient
                    </button>
                  )}

                  {bed.status === 'OCCUPIED' && (
                    <>
                      <button
                        onClick={() => openEventModal(bed, 'DISCHARGE')}
                        className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-[11px] font-bold transition-all shadow-xs"
                      >
                        <UserMinus className="w-3.5 h-3.5" />
                        Discharge
                      </button>
                      <button
                        onClick={() => openEventModal(bed, 'BED_CLEANING')}
                        className="p-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-[11px] font-bold transition-all"
                        title="Send for Cleaning"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}

                  {bed.status === 'CLEANING' && (
                    <button
                      onClick={() => openEventModal(bed, 'BED_AVAILABLE')}
                      className="w-full flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-700 text-white text-[11px] font-bold transition-all shadow-xs"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Mark Clean & Ready
                    </button>
                  )}

                  {(bed.status === 'MAINTENANCE' || bed.status === 'RESERVED') && (
                    <button
                      onClick={() => openEventModal(bed, 'BED_AVAILABLE')}
                      className="w-full flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-800 text-white text-[11px] font-bold transition-all shadow-xs"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Release to Available
                    </button>
                  )}

                  {bed.status !== 'MAINTENANCE' && bed.status !== 'OCCUPIED' && (
                    <button
                      onClick={() => openEventModal(bed, 'BED_MAINTENANCE')}
                      className="text-[10px] text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 underline mt-1"
                    >
                      Maintenance
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Bed Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl w-full max-w-md p-6 relative">
            <button
              onClick={() => setShowAddModal(false)}
              className="absolute right-4 top-4 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2.5 mb-4">
              <div className="p-2.5 rounded-xl bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400">
                <BedDouble className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Add New Hospital Bed</h3>
                <p className="text-xs text-slate-500">Create a new bed entry in ward capacity registry</p>
              </div>
            </div>

            <form onSubmit={handleCreateBed} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Target Ward *
                </label>
                <select
                  value={newBedWardId}
                  onChange={(e) => setNewBedWardId(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-900 dark:text-white focus:outline-none focus:border-sky-500"
                >
                  {wards.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name} ({w.ward_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                  Bed Number / ID *
                </label>
                <input
                  type="text"
                  placeholder="e.g. ICU-01, GEN-12"
                  value={newBedNumber}
                  onChange={(e) => setNewBedNumber(e.target.value)}
                  required
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-sky-500 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Bed Type
                  </label>
                  <select
                    value={newBedType}
                    onChange={(e) => setNewBedType(e.target.value as BedType)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-900 dark:text-white focus:outline-none focus:border-sky-500"
                  >
                    <option value="STANDARD">STANDARD</option>
                    <option value="ICU">ICU</option>
                    <option value="ISOLATION">ISOLATION</option>
                    <option value="EMERGENCY">EMERGENCY</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Initial Status
                  </label>
                  <select
                    value={newBedStatus}
                    onChange={(e) => setNewBedStatus(e.target.value as BedStatus)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-900 dark:text-white focus:outline-none focus:border-sky-500"
                  >
                    <option value="AVAILABLE">AVAILABLE</option>
                    <option value="OCCUPIED">OCCUPIED</option>
                    <option value="CLEANING">CLEANING</option>
                    <option value="MAINTENANCE">MAINTENANCE</option>
                    <option value="RESERVED">RESERVED</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingAdd}
                  className="px-5 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold transition-all shadow-md disabled:opacity-50"
                >
                  {submittingAdd ? 'Creating...' : 'Create Bed'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Bed Event Status Transition Modal */}
      {showEventModal && selectedBedForEvent && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl w-full max-w-md p-6 relative">
            <button
              onClick={() => setShowEventModal(false)}
              className="absolute right-4 top-4 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2.5 mb-4">
              <div className="p-2.5 rounded-xl bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400">
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  Process Bed Event: {targetEventType}
                </h3>
                <p className="text-xs text-slate-500">
                  Bed: <span className="font-bold text-sky-600">{selectedBedForEvent.bed_number}</span> (Current status: {selectedBedForEvent.status})
                </p>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 space-y-2 mb-4 text-xs text-slate-600 dark:text-slate-300">
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Ward:</span>
                <span>{selectedBedForEvent.ward_name || `Ward #${selectedBedForEvent.ward_id}`}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Bed Type:</span>
                <span>{selectedBedForEvent.bed_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Source:</span>
                <span className="font-semibold text-sky-600">Manual Staff Telemetry</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowEventModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitEvent}
                disabled={actionLoading}
                className="px-5 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold transition-all shadow-md disabled:opacity-50"
              >
                {actionLoading ? 'Processing...' : `Confirm ${targetEventType}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
