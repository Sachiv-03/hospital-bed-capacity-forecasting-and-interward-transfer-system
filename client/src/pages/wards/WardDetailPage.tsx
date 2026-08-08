import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Ward, WardOccupancy, WardCreateInput } from '../../types';
import { getWard, getWardOccupancy, updateWard } from '../../services/wardService';
import { WardFormModal } from '../../components/wards/WardFormModal';
import {
  Building2,
  ArrowLeft,
  Calendar,
  BedDouble,
  Info,
  Edit,
  AlertCircle,
  Loader2,
} from 'lucide-react';

export const WardDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [ward, setWard] = useState<Ward | null>(null);
  const [occupancy, setOccupancy] = useState<WardOccupancy | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Edit Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [modalApiError, setModalApiError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const wardId = parseInt(id, 10);
    if (isNaN(wardId)) {
      setError('Invalid ward ID');
      setLoading(false);
      return;
    }

    setLoading(true);
    Promise.all([getWard(wardId), getWardOccupancy(wardId)])
      .then(([wardData, occupancyData]) => {
        setWard(wardData);
        setOccupancy(occupancyData);
        setLoading(false);
      })
      .catch((err: unknown) => {
        console.error('Failed to fetch ward details:', err);
        const errorMsg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Ward not found or server error.';
        setError(errorMsg);
        setLoading(false);
      });
  }, [id]);

  const handleEditSubmit = async (formData: WardCreateInput) => {
    if (!ward) return;
    setIsSubmitting(true);
    setModalApiError(null);
    try {
      const updated = await updateWard(ward.id, formData);
      setWard(updated);
      setIsEditModalOpen(false);
    } catch (err: unknown) {
      const errorMsg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Failed to update ward.';
      setModalApiError(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px] text-slate-500 gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-sky-600" />
        <span className="text-sm font-semibold">Loading ward details...</span>
      </div>
    );
  }

  if (error || !ward) {
    return (
      <div className="p-8 text-center space-y-4 max-w-md mx-auto my-12 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">Ward Not Found</h2>
        <p className="text-xs text-slate-500">{error || 'The requested ward does not exist.'}</p>
        <button
          onClick={() => navigate('/wards')}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-bold text-sky-600 bg-sky-50 dark:bg-sky-950 rounded-xl border border-sky-200 dark:border-sky-800"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Ward List</span>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Back Navigation Bar */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/wards')}
          className="inline-flex items-center gap-2 text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-sky-600 dark:hover:text-sky-400 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Wards Management</span>
        </button>

        {isAdmin && (
          <button
            onClick={() => {
              setModalApiError(null);
              setIsEditModalOpen(true);
            }}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-bold text-white bg-sky-600 hover:bg-sky-500 rounded-xl shadow-md transition-all"
          >
            <Edit className="w-4 h-4" />
            <span>Edit Ward</span>
          </button>
        )}
      </div>

      {/* Ward Main Overview Card */}
      <div className="p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-6">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-sky-600 to-indigo-600 text-white flex items-center justify-center shadow-lg shadow-sky-500/20 shrink-0">
              <Building2 className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-black text-slate-900 dark:text-white">
                  {ward.name}
                </h1>
                <span className="px-3 py-1 text-xs font-bold uppercase rounded-full bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
                  {ward.ward_type}
                </span>
                <span
                  className={`px-3 py-1 text-xs font-bold uppercase rounded-full border ${
                    ward.status === 'ACTIVE'
                      ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
                  }`}
                >
                  {ward.status}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Department: <span className="font-semibold text-slate-800 dark:text-slate-200">{ward.department}</span> • Location: <span className="font-semibold text-slate-800 dark:text-slate-200">{ward.floor}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Specifications Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-bold uppercase text-slate-400">Total Bed Capacity</span>
            <p className="text-2xl font-black text-slate-900 dark:text-white mt-1">{ward.capacity} Beds</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-bold uppercase text-slate-400">Department</span>
            <p className="text-base font-bold text-slate-900 dark:text-white mt-1">{ward.department}</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-bold uppercase text-slate-400">Floor Location</span>
            <p className="text-base font-bold text-slate-900 dark:text-white mt-1">{ward.floor}</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-bold uppercase text-slate-400">System Record ID</span>
            <p className="text-base font-bold text-slate-900 dark:text-white mt-1">WARD-#{ward.id}</p>
          </div>
        </div>

        {/* Description Section */}
        {ward.description && (
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-800">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Ward Description & Specialty Notes</h3>
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{ward.description}</p>
          </div>
        )}

        {/* Timestamps */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800 gap-2">
          <div className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5" />
            <span>Created: {new Date(ward.created_at).toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5" />
            <span>Last Updated: {new Date(ward.updated_at).toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Bed Occupancy Topology Card (Phase 3 -> Phase 4 Bridge) */}
      <div className="p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold">
              <BedDouble className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-slate-900 dark:text-white">
                Bed Capacity & Occupancy Status
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Real-time bed tracking topology and allocation statistics.
              </p>
            </div>
          </div>
        </div>

        {/* Phase 4 Information Banner */}
        <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 flex items-start gap-3 text-xs text-amber-800 dark:text-amber-300">
          <Info className="w-5 h-5 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
          <div>
            <p className="font-bold text-sm">Phase 4 Bed Management Integration Ready</p>
            <p className="mt-0.5 leading-relaxed">
              {occupancy?.message || 'Detailed bed occupancy tracking will be enabled in Phase 4 Bed Management.'}
            </p>
          </div>
        </div>

        {/* Occupancy Metrics Display */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 text-center">
            <span className="text-xs font-bold text-slate-400 uppercase">Total Capacity</span>
            <p className="text-2xl font-black text-slate-900 dark:text-white mt-1">{occupancy?.capacity ?? ward.capacity}</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 text-center">
            <span className="text-xs font-bold text-slate-400 uppercase">Occupied Beds</span>
            <p className="text-2xl font-black text-amber-600 dark:text-amber-400 mt-1">{occupancy?.occupied_beds ?? 0}</p>
            <span className="text-[10px] text-slate-400">Phase 4 Module</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 text-center">
            <span className="text-xs font-bold text-slate-400 uppercase">Available Beds</span>
            <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1">{occupancy?.available_beds ?? ward.capacity}</p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 text-center">
            <span className="text-xs font-bold text-slate-400 uppercase">Occupancy Rate</span>
            <p className="text-2xl font-black text-sky-600 dark:text-sky-400 mt-1">{occupancy?.occupancy_rate ?? 0.0}%</p>
          </div>
        </div>
      </div>

      {/* Edit Form Modal */}
      <WardFormModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSubmit={handleEditSubmit}
        initialData={ward}
        isSubmitting={isSubmitting}
        apiError={modalApiError}
      />
    </div>
  );
};
