import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { getPatients, updatePatientStatus } from '../../services/patientService';
import { dischargePatient } from '../../services/admissionService';
import { Patient } from '../../types';
import {
  Users,
  UserPlus,
  Search,
  Filter,
  RefreshCw,
  BedDouble,
  Activity,
  CheckCircle2,
  AlertCircle,
  UserCheck,
  UserX,
  X,
  Phone,
  Mail,
} from 'lucide-react';

const getApiErrorMessage = (err: unknown, fallback: string): string => {
  if (axios.isAxiosError(err)) {
    return err.response?.data?.detail || fallback;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return fallback;
};

export const PatientsPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [patients, setPatients] = useState<Patient[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [admissionFilter, setAdmissionFilter] = useState<string>('ALL');

  // Discharge modal state
  const [selectedPatientForDischarge, setSelectedPatientForDischarge] = useState<Patient | null>(null);
  const [dischargeNotes, setDischargeNotes] = useState<string>('');
  const [discharging, setDischarging] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const activeHospitalId = user?.hospital_id || 1;

  const loadPatients = useCallback(async () => {
    try {
      setError(null);
      const res = await getPatients({
        hospital_id: activeHospitalId,
        search: search.trim() || undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        page,
        limit: 50,
      });
      setPatients(res.items || []);
      setTotal(res.total || 0);
      setTotalPages(res.pages || 1);
    } catch (err: unknown) {
      console.error('Failed to load patients:', err);
      setError(getApiErrorMessage(err, 'Failed to fetch patients registry from server.'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeHospitalId, search, statusFilter, page]);

  useEffect(() => {
    loadPatients();
  }, [loadPatients]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadPatients();
  };

  const handleToggleStatus = async (patient: Patient) => {
    const nextStatus = patient.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    if (!window.confirm(`Are you sure you want to change ${patient.first_name} ${patient.last_name}'s status to ${nextStatus}?`)) return;

    try {
      await updatePatientStatus(patient.id, nextStatus);
      setSuccessMsg(`Patient status updated to ${nextStatus}.`);
      setTimeout(() => setSuccessMsg(null), 3000);
      loadPatients();
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Failed to update status'));
    }
  };

  const handleDischargeConfirm = async () => {
    if (!selectedPatientForDischarge || !selectedPatientForDischarge.current_admission) return;
    setDischarging(true);
    try {
      await dischargePatient(selectedPatientForDischarge.current_admission.admission_id, {
        discharge_notes: dischargeNotes.trim() || undefined,
      });
      setSelectedPatientForDischarge(null);
      setDischargeNotes('');
      setSuccessMsg(`Patient discharged successfully and bed ${selectedPatientForDischarge.current_admission.bed_number} released.`);
      setTimeout(() => setSuccessMsg(null), 4000);
      loadPatients();
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Failed to discharge patient'));
    } finally {
      setDischarging(false);
    }
  };

  // Client-side admission state filtering if requested
  const displayedPatients = patients.filter((p) => {
    if (admissionFilter === 'ADMITTED') return !!p.current_admission;
    if (admissionFilter === 'NOT_ADMITTED') return !p.current_admission;
    return true;
  });

  const totalAdmitted = patients.filter((p) => !!p.current_admission).length;
  const totalActive = patients.filter((p) => p.status === 'ACTIVE').length;

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
              <Users className="w-3.5 h-3.5" />
              Patient & Admission Registry
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Patients Management
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Register patients, track active hospital stay admissions, assign available beds, and manage discharges.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:border-indigo-500 transition-all shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <button
            onClick={() => navigate('/patients/new')}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-md hover:shadow-lg"
          >
            <UserPlus className="w-4 h-4" />
            Register New Patient
          </button>
        </div>
      </div>

      {/* Success Banner */}
      {successMsg && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs font-medium animate-fadeIn">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Total Patients</p>
            <p className="text-2xl font-black text-slate-900 dark:text-white mt-1">{total}</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Hospital master registry</p>
          </div>
          <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
            <Users className="w-6 h-6" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Currently Admitted</p>
            <p className="text-2xl font-black text-rose-600 dark:text-rose-400 mt-1">{totalAdmitted}</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Occupying hospital beds</p>
          </div>
          <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950 text-rose-600 dark:text-rose-400">
            <BedDouble className="w-6 h-6" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Active Patient Accounts</p>
            <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1">{totalActive}</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Eligible for admission</p>
          </div>
          <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400">
            <UserCheck className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by Patient ID, Name, Phone, or Email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 flex items-center gap-1 shrink-0">
              <Filter className="w-3.5 h-3.5 text-indigo-500" />
              Admission Status:
            </label>
            <select
              value={admissionFilter}
              onChange={(e) => setAdmissionFilter(e.target.value)}
              className="px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-800 dark:text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Admission States</option>
              <option value="ADMITTED">Currently Admitted Only</option>
              <option value="NOT_ADMITTED">Not Admitted Only</option>
            </select>
          </div>
        </div>

        {/* Status Filter Pills */}
        <div className="flex items-center gap-2 pt-2 border-t border-slate-100 dark:border-slate-800/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mr-1">Account Filter:</span>
          {['ALL', 'ACTIVE', 'INACTIVE'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                statusFilter === st
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Patient Directory Table */}
      {loading ? (
        <div className="py-20 text-center text-slate-400 animate-pulse">
          <Users className="w-10 h-10 mx-auto mb-3 opacity-40 animate-bounce" />
          <p className="text-sm font-semibold">Loading patients registry...</p>
        </div>
      ) : error ? (
        <div className="p-8 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-center text-rose-700 dark:text-rose-300">
          <AlertCircle className="w-8 h-8 mx-auto mb-2" />
          <p className="font-bold text-sm">{error}</p>
        </div>
      ) : displayedPatients.length === 0 ? (
        <div className="py-16 text-center text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
          <Users className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm font-bold text-slate-700 dark:text-slate-300">No patients found</p>
          <p className="text-xs text-slate-400 mt-1">Try refining search or registration filter</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 uppercase tracking-wider font-bold border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3.5 px-4">Patient Identifier</th>
                  <th className="py-3.5 px-4">Patient Name</th>
                  <th className="py-3.5 px-4">DOB / Gender</th>
                  <th className="py-3.5 px-4">Contact Information</th>
                  <th className="py-3.5 px-4">Current Admission</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                {displayedPatients.map((patient) => (
                  <tr key={patient.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-bold text-indigo-600 dark:text-indigo-400">
                      {patient.patient_identifier}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-slate-900 dark:text-white">
                      <Link to={`/patients/${patient.id}`} className="hover:underline flex items-center gap-1.5">
                        {patient.first_name} {patient.last_name}
                      </Link>
                    </td>
                    <td className="py-3.5 px-4">
                      <div>{patient.date_of_birth}</div>
                      <div className="text-[10px] text-slate-400 uppercase font-semibold">{patient.gender}</div>
                    </td>
                    <td className="py-3.5 px-4 space-y-0.5">
                      {patient.phone && (
                        <div className="flex items-center gap-1 text-[11px]">
                          <Phone className="w-3 h-3 text-slate-400" />
                          <span>{patient.phone}</span>
                        </div>
                      )}
                      {patient.email && (
                        <div className="flex items-center gap-1 text-[11px] text-slate-400">
                          <Mail className="w-3 h-3" />
                          <span className="truncate max-w-[150px]">{patient.email}</span>
                        </div>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      {patient.current_admission ? (
                        <div className="inline-flex flex-col">
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-bold bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                            <BedDouble className="w-3.5 h-3.5 text-rose-500" />
                            {patient.current_admission.ward_name} ({patient.current_admission.bed_number})
                          </span>
                          <span className="text-[10px] text-slate-400 mt-0.5 font-mono">
                            {patient.current_admission.admission_number}
                          </span>
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500">
                          Not Admitted
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        onClick={() => handleToggleStatus(patient)}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase transition-all ${
                          patient.status === 'ACTIVE'
                            ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700'
                        }`}
                      >
                        {patient.status === 'ACTIVE' ? <UserCheck className="w-3 h-3" /> : <UserX className="w-3 h-3" />}
                        {patient.status}
                      </button>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/patients/${patient.id}`}
                          className="px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold transition-all"
                        >
                          View Profile
                        </Link>

                        {patient.current_admission ? (
                          <button
                            onClick={() => setSelectedPatientForDischarge(patient)}
                            className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-all shadow-xs"
                          >
                            Discharge
                          </button>
                        ) : (
                          patient.status === 'ACTIVE' && (
                            <Link
                              to={`/patients/${patient.id}/admit`}
                              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-xs"
                            >
                              Admit Patient
                            </Link>
                          )
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
              <span className="text-xs text-slate-500">
                Page <span className="font-semibold text-slate-700 dark:text-slate-300">{page}</span> of{' '}
                <span className="font-semibold text-slate-700 dark:text-slate-300">{totalPages}</span> ({total} patients)
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Discharge Confirmation Modal */}
      {selectedPatientForDischarge && selectedPatientForDischarge.current_admission && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl w-full max-w-md p-6 relative">
            <button
              onClick={() => setSelectedPatientForDischarge(null)}
              className="absolute right-4 top-4 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2.5 mb-4">
              <div className="p-2.5 rounded-xl bg-rose-100 dark:bg-rose-950 text-rose-600 dark:text-rose-400">
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Confirm Patient Discharge</h3>
                <p className="text-xs text-slate-500">Release assigned bed and complete admission stay</p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-2 mb-4 text-xs">
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Patient:</span>
                <span className="font-bold text-slate-900 dark:text-white">
                  {selectedPatientForDischarge.first_name} {selectedPatientForDischarge.last_name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Admission No:</span>
                <span className="font-mono">{selectedPatientForDischarge.current_admission.admission_number}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Ward & Bed:</span>
                <span className="font-bold text-rose-600">
                  {selectedPatientForDischarge.current_admission.ward_name} - {selectedPatientForDischarge.current_admission.bed_number}
                </span>
              </div>
            </div>

            <div className="space-y-2 mb-4">
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300">
                Operational Discharge Notes (Optional)
              </label>
              <textarea
                rows={3}
                placeholder="Enter minimal discharge operational notes..."
                value={dischargeNotes}
                onChange={(e) => setDischargeNotes(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-rose-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setSelectedPatientForDischarge(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleDischargeConfirm}
                disabled={discharging}
                className="px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-all shadow-md disabled:opacity-50"
              >
                {discharging ? 'Discharging...' : 'Confirm Discharge & Release Bed'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
