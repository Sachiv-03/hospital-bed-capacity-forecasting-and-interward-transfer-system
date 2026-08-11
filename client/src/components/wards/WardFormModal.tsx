import React, { useState, useEffect } from 'react';
import { Ward, WardCreateInput, WardType, Hospital } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { hospitalService } from '../../services/hospitalService';
import { X, AlertCircle, Loader2, Building } from 'lucide-react';

interface WardFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: WardCreateInput) => Promise<void>;
  initialData?: Ward | null;
  isSubmitting: boolean;
  apiError?: string | null;
}

const WARD_TYPES: WardType[] = [
  'GENERAL',
  'ICU',
  'EMERGENCY',
  'PEDIATRIC',
  'MATERNITY',
  'SURGICAL',
  'ISOLATION',
  'OTHER',
];

export const WardFormModal: React.FC<WardFormModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  isSubmitting,
  apiError,
}) => {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';

  const [formData, setFormData] = useState<WardCreateInput>({
    hospital_id: initialData?.hospital_id || user?.hospital_id || 1,
    name: '',
    ward_type: 'GENERAL',
    department: '',
    floor: 'Floor 1',
    capacity: 20,
    description: '',
  });

  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loadingHospitals, setLoadingHospitals] = useState<boolean>(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (isSuperAdmin && isOpen) {
      setLoadingHospitals(true);
      hospitalService
        .getHospitals({ limit: 100 })
        .then((res) => setHospitals(res.items))
        .catch((err) => console.error('Failed to load hospitals for selection:', err))
        .finally(() => setLoadingHospitals(false));
    }
  }, [isSuperAdmin, isOpen]);

  useEffect(() => {
    if (initialData) {
      setFormData({
        hospital_id: initialData.hospital_id,
        name: initialData.name,
        ward_type: initialData.ward_type,
        department: initialData.department,
        floor: initialData.floor,
        capacity: initialData.capacity,
        description: initialData.description || '',
      });
    } else {
      setFormData({
        hospital_id: user?.hospital_id || 1,
        name: '',
        ward_type: 'GENERAL',
        department: '',
        floor: 'Floor 1',
        capacity: 20,
        description: '',
      });
    }
    setErrors({});
  }, [initialData, isOpen, user?.hospital_id]);

  if (!isOpen) return null;

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Ward name is required.';
    }
    if (!formData.department.trim()) {
      newErrors.department = 'Department is required.';
    }
    if (!formData.floor.trim()) {
      newErrors.floor = 'Floor is required.';
    }
    if (!formData.capacity || formData.capacity <= 0) {
      newErrors.capacity = 'Capacity must be a positive integer greater than 0.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    await onSubmit(formData);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/50">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">
              {initialData ? 'Edit Ward Information' : 'Create New Ward'}
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {initialData
                ? 'Update ward specifications, department, and bed capacity.'
                : 'Add a new ward to hospital capacity management.'}
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">
          {apiError && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 flex items-start gap-3 text-xs text-rose-700 dark:text-rose-300">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{apiError}</span>
            </div>
          )}

          {/* Super Admin Hospital Selector */}
          {isSuperAdmin && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                <Building className="w-3.5 h-3.5 text-sky-600" />
                Target Hospital Facility <span className="text-rose-500">*</span>
              </label>
              {loadingHospitals ? (
                <div className="h-10 bg-slate-100 dark:bg-slate-800 rounded-xl animate-pulse" />
              ) : (
                <select
                  value={formData.hospital_id || ''}
                  onChange={(e) => setFormData({ ...formData, hospital_id: parseInt(e.target.value) })}
                  className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all font-semibold"
                >
                  {hospitals.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.name} ({h.code})
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {/* Ward Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Ward Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Intensive Care Unit A"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className={`w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border rounded-xl focus:outline-none focus:ring-2 transition-all ${
                errors.name
                  ? 'border-rose-400 focus:ring-rose-500/30'
                  : 'border-slate-200 dark:border-slate-700 focus:ring-sky-500/30 focus:border-sky-500'
              }`}
            />
            {errors.name && <p className="text-xs text-rose-500 mt-1">{errors.name}</p>}
          </div>

          {/* Ward Type & Department Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Ward Type */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Ward Type <span className="text-rose-500">*</span>
              </label>
              <select
                value={formData.ward_type}
                onChange={(e) => setFormData({ ...formData, ward_type: e.target.value as WardType })}
                className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all"
              >
                {WARD_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            {/* Department */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Department <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                placeholder="e.g. Critical Care"
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                className={`w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border rounded-xl focus:outline-none focus:ring-2 transition-all ${
                  errors.department
                    ? 'border-rose-400 focus:ring-rose-500/30'
                    : 'border-slate-200 dark:border-slate-700 focus:ring-sky-500/30 focus:border-sky-500'
                }`}
              />
              {errors.department && <p className="text-xs text-rose-500 mt-1">{errors.department}</p>}
            </div>
          </div>

          {/* Floor & Capacity Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Floor */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Floor / Location <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                placeholder="e.g. Floor 2 or Wing B"
                value={formData.floor}
                onChange={(e) => setFormData({ ...formData, floor: e.target.value })}
                className={`w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border rounded-xl focus:outline-none focus:ring-2 transition-all ${
                  errors.floor
                    ? 'border-rose-400 focus:ring-rose-500/30'
                    : 'border-slate-200 dark:border-slate-700 focus:ring-sky-500/30 focus:border-sky-500'
                }`}
              />
              {errors.floor && <p className="text-xs text-rose-500 mt-1">{errors.floor}</p>}
            </div>

            {/* Capacity */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Bed Capacity <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                min="1"
                placeholder="e.g. 20"
                value={formData.capacity}
                onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value) || 0 })}
                className={`w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border rounded-xl focus:outline-none focus:ring-2 transition-all ${
                  errors.capacity
                    ? 'border-rose-400 focus:ring-rose-500/30'
                    : 'border-slate-200 dark:border-slate-700 focus:ring-sky-500/30 focus:border-sky-500'
                }`}
              />
              {errors.capacity && <p className="text-xs text-rose-500 mt-1">{errors.capacity}</p>}
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Description / Notes <span className="text-slate-400 font-normal">(Optional)</span>
            </label>
            <textarea
              rows={3}
              placeholder="Provide additional details regarding ward equipment, specialty, or staffing..."
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all resize-none"
            />
          </div>

          {/* Modal Actions */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 rounded-xl transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-500 rounded-xl shadow-md shadow-sky-600/20 flex items-center gap-2 transition-all disabled:opacity-50"
            >
              {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
              <span>{initialData ? 'Update Ward' : 'Create Ward'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
