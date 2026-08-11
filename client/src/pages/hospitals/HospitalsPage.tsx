import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { Hospital, HospitalCreateInput, HospitalStatus } from '../../types';
import { hospitalService } from '../../services/hospitalService';
import {
  Building,
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
  MapPin,
  X,
  Loader2,
} from 'lucide-react';

export const HospitalsPage: React.FC = () => {
  const navigate = useNavigate();

  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [limit] = useState<number>(10);

  const [searchInput, setSearchInput] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingHospital, setEditingHospital] = useState<Hospital | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [modalApiError, setModalApiError] = useState<string | null>(null);

  const [formData, setFormData] = useState<HospitalCreateInput>({
    name: '',
    code: '',
    address: '',
    city: '',
    state: '',
    country: '',
  });

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchInput);
      setPage(1);
    }, 400);
    return () => clearTimeout(handler);
  }, [searchInput]);

  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  const loadHospitals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await hospitalService.getHospitals({
        page,
        limit,
        search: debouncedSearch || undefined,
        status: selectedStatus || undefined,
      });
      setHospitals(res.items);
      setTotalItems(res.total);
      setTotalPages(res.pages);
    } catch (err: unknown) {
      const msg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Failed to fetch hospitals list.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [page, limit, debouncedSearch, selectedStatus]);

  useEffect(() => {
    loadHospitals();
  }, [loadHospitals]);

  const handleOpenCreateModal = () => {
    setEditingHospital(null);
    setFormData({
      name: '',
      code: `H00${totalItems + 1}`,
      address: '',
      city: '',
      state: '',
      country: 'USA',
    });
    setModalApiError(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (h: Hospital) => {
    setEditingHospital(h);
    setFormData({
      name: h.name,
      code: h.code,
      address: h.address || '',
      city: h.city || '',
      state: h.state || '',
      country: h.country || '',
    });
    setModalApiError(null);
    setIsModalOpen(true);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.code.trim()) {
      setModalApiError('Hospital Name and Unique Code are required.');
      return;
    }
    setIsSubmitting(true);
    setModalApiError(null);
    try {
      if (editingHospital) {
        await hospitalService.updateHospital(editingHospital.id, formData);
        setToastMessage({ type: 'success', text: `Hospital '${formData.name}' updated successfully.` });
      } else {
        await hospitalService.createHospital(formData);
        setToastMessage({ type: 'success', text: `Hospital '${formData.name}' created successfully.` });
      }
      setIsModalOpen(false);
      loadHospitals();
    } catch (err: unknown) {
      const msg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Failed to save hospital.';
      setModalApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeactivate = async (h: Hospital) => {
    if (!window.confirm(`Are you sure you want to deactivate hospital '${h.name}'?`)) return;
    try {
      await hospitalService.deactivateHospital(h.id);
      setToastMessage({ type: 'success', text: `Hospital '${h.name}' has been deactivated.` });
      loadHospitals();
    } catch (err: unknown) {
      const msg = (err as AxiosError<{ detail?: string }>).response?.data?.detail || 'Failed to deactivate hospital.';
      setToastMessage({ type: 'error', text: msg });
    }
  };

  const getStatusBadge = (status: HospitalStatus) => {
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

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Toast Notification Banner */}
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
          <button onClick={() => setToastMessage(null)} className="text-xs font-bold uppercase tracking-wider">
            Dismiss
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white flex items-center gap-3">
            <Building className="w-8 h-8 text-sky-600 dark:text-sky-400" />
            Multi-Hospital System Directory
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Super Admin Portal • Configure healthcare facilities, hospital codes, and ward topologies.
          </p>
        </div>

        <button
          onClick={handleOpenCreateModal}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm text-white bg-sky-600 hover:bg-sky-500 shadow-md shadow-sky-600/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
        >
          <Plus className="w-4 h-4 stroke-[3]" />
          <span>Add Hospital</span>
        </button>
      </div>

      {/* Filter and Search Controls */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Search Box */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search hospital name, code, city..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all placeholder:text-slate-400"
            />
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setPage(1);
              }}
              className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all"
            >
              <option value="">All Statuses</option>
              <option value="ACTIVE">Active Only</option>
              <option value="INACTIVE">Inactive Only</option>
            </select>
          </div>

          {/* Clear Filters */}
          <div className="flex items-center gap-2">
            {(searchInput || selectedStatus) && (
              <button
                onClick={() => {
                  setSearchInput('');
                  setDebouncedSearch('');
                  setSelectedStatus('');
                  setPage(1);
                }}
                className="w-full py-2 px-3 text-xs font-bold uppercase tracking-wider text-slate-600 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 bg-slate-100 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 transition-colors flex items-center justify-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Clear Filters
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Hospital Table Card */}
      <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-8 space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-slate-100 dark:bg-slate-800/60 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <div className="p-12 text-center space-y-3">
            <AlertCircle className="w-10 h-10 text-rose-500 mx-auto" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">Unable to load hospitals</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">{error}</p>
          </div>
        ) : hospitals.length === 0 ? (
          <div className="p-12 text-center space-y-4">
            <Building className="w-12 h-12 text-slate-400 mx-auto" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">No hospitals found</h3>
            <p className="text-xs text-slate-500">Add a hospital facility to enable multi-tenant management.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <th className="py-3.5 px-4 sm:px-6">Hospital Name</th>
                  <th className="py-3.5 px-4">Code</th>
                  <th className="py-3.5 px-4">City / Region</th>
                  <th className="py-3.5 px-4">Wards Count</th>
                  <th className="py-3.5 px-4">Total Bed Capacity</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 sm:px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {hospitals.map((h) => (
                  <tr key={h.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors group">
                    <td className="py-4 px-4 sm:px-6">
                      <div className="font-bold text-slate-900 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                        {h.name}
                      </div>
                      {h.address && <div className="text-xs text-slate-500 line-clamp-1">{h.address}</div>}
                    </td>
                    <td className="py-4 px-4">
                      <span className="px-2.5 py-1 rounded bg-sky-100 dark:bg-sky-950 text-sky-800 dark:text-sky-300 font-mono text-xs font-bold border border-sky-200 dark:border-sky-800">
                        {h.code}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-slate-600 dark:text-slate-300 text-xs font-medium">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-slate-400" />
                        <span>{[h.city, h.state, h.country].filter(Boolean).join(', ') || 'N/A'}</span>
                      </div>
                    </td>
                    <td className="py-4 px-4 font-bold text-slate-800 dark:text-slate-200">
                      {h.ward_count ?? 0} <span className="text-xs font-normal text-slate-400">wards</span>
                    </td>
                    <td className="py-4 px-4 font-black text-slate-900 dark:text-white">
                      {h.total_capacity ?? 0} <span className="text-xs font-normal text-slate-400">beds</span>
                    </td>
                    <td className="py-4 px-4">{getStatusBadge(h.status)}</td>
                    <td className="py-4 px-4 sm:px-6 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => navigate(`/hospitals/${h.id}`)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/60 transition-colors"
                          title="View Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleOpenEditModal(h)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/60 transition-colors"
                          title="Edit Hospital"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        {h.status === 'ACTIVE' && (
                          <button
                            onClick={() => handleDeactivate(h)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/60 transition-colors"
                            title="Deactivate Hospital"
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
        {!loading && !error && hospitals.length > 0 && (
          <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
            <div>
              Showing <span className="font-bold text-slate-800 dark:text-slate-200">{(page - 1) * limit + 1}</span> to{' '}
              <span className="font-bold text-slate-800 dark:text-slate-200">{Math.min(page * limit, totalItems)}</span>{' '}
              of <span className="font-bold text-slate-800 dark:text-slate-200">{totalItems}</span> hospitals
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 disabled:opacity-40 hover:bg-slate-100 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-bold text-slate-800 dark:text-slate-200 px-2">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-600 disabled:opacity-40 hover:bg-slate-100 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Add / Edit Hospital Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/50">
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                  {editingHospital ? 'Edit Hospital Details' : 'Add New Hospital Facility'}
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Configure hospital code and location attributes for tenant isolation.
                </p>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                disabled={isSubmitting}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleFormSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">
              {modalApiError && (
                <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 flex items-start gap-3 text-xs text-rose-700 dark:text-rose-300">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{modalApiError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Hospital Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. City General Hospital"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Unique Hospital Code <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. H002"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all font-mono font-bold"
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">City</label>
                  <input
                    type="text"
                    placeholder="e.g. Metropolis"
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">State</label>
                  <input
                    type="text"
                    placeholder="e.g. New York"
                    value={formData.state}
                    onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                    className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Address</label>
                <textarea
                  rows={2}
                  placeholder="e.g. 100 Health Sciences Parkway"
                  value={formData.address}
                  onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  className="w-full px-3.5 py-2 text-sm bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/30 focus:border-sky-500 transition-all resize-none"
                />
              </div>

              <div className="pt-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  disabled={isSubmitting}
                  className="px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800 dark:text-slate-400 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-500 rounded-xl shadow-md flex items-center gap-2"
                >
                  {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  <span>{editingHospital ? 'Update Hospital' : 'Create Hospital'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
