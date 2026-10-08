import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { getPatient, getPatientAdmissions, updatePatient } from '../../services/patientService';
import { dischargePatient } from '../../services/admissionService';
import { Patient, Admission } from '../../types';
import {
  ArrowLeft,
  User,
  Phone,
  Mail,
  MapPin,
  Calendar,
  ShieldAlert,
  BedDouble,
  Activity,
  CheckCircle2,
  Clock,
  Edit,
  UserPlus,
  AlertCircle,
  X,
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

export const PatientDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const patientId = Number(id);
  const activeHospitalId = user?.hospital_id || 1;

  const [patient, setPatient] = useState<Patient | null>(null);
  const [admissions, setAdmissions] = useState<Admission[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Edit Patient Modal State
  const [showEditModal, setShowEditModal] = useState<boolean>(false);
  const [editFirstName, setEditFirstName] = useState<string>('');
  const [editLastName, setEditLastName] = useState<string>('');
  const [editPhone, setEditPhone] = useState<string>('');
  const [editEmail, setEditEmail] = useState<string>('');
  const [editAddress, setEditAddress] = useState<string>('');
  const [editEmergName, setEditEmergName] = useState<string>('');
  const [editEmergPhone, setEditEmergPhone] = useState<string>('');
  const [submittingEdit, setSubmittingEdit] = useState<boolean>(false);

  // Discharge Modal State
  const [showDischargeModal, setShowDischargeModal] = useState<boolean>(false);
  const [dischargeNotes, setDischargeNotes] = useState<string>('');
  const [discharging, setDischarging] = useState<boolean>(false);

  const loadData = useCallback(async () => {
    if (!patientId) return;
    try {
      setError(null);
      const [patientData, admData] = await Promise.all([
        getPatient(patientId, activeHospitalId),
        getPatientAdmissions(patientId),
      ]);
      setPatient(patientData);
      setAdmissions(admData.items || []);

      // Pre-fill edit modal
      setEditFirstName(patientData.first_name);
      setEditLastName(patientData.last_name);
      setEditPhone(patientData.phone || '');
      setEditEmail(patientData.email || '');
      setEditAddress(patientData.address || '');
      setEditEmergName(patientData.emergency_contact_name || '');
      setEditEmergPhone(patientData.emergency_contact_phone || '');
    } catch (err: unknown) {
      console.error('Failed to load patient detail:', err);
      setError(getApiErrorMessage(err, 'Failed to fetch patient details from server.'));
    } finally {
      setLoading(false);
    }
  }, [patientId, activeHospitalId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleUpdatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patient) return;
    setSubmittingEdit(true);
    try {
      await updatePatient(patient.id, {
        first_name: editFirstName.trim(),
        last_name: editLastName.trim(),
        phone: editPhone.trim() || undefined,
        email: editEmail.trim() || undefined,
        address: editAddress.trim() || undefined,
        emergency_contact_name: editEmergName.trim() || undefined,
        emergency_contact_phone: editEmergPhone.trim() || undefined,
      });
      setShowEditModal(false);
      setSuccessMsg('Patient profile updated successfully.');
      setTimeout(() => setSuccessMsg(null), 3000);
      loadData();
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Failed to update patient profile'));
    } finally {
      setSubmittingEdit(false);
    }
  };

  const handleDischargeConfirm = async () => {
    if (!patient || !patient.current_admission) return;
    setDischarging(true);
    try {
      await dischargePatient(patient.current_admission.admission_id, {
        discharge_notes: dischargeNotes.trim() || undefined,
      });
      setShowDischargeModal(false);
      setDischargeNotes('');
      setSuccessMsg('Patient discharged successfully and bed released.');
      setTimeout(() => setSuccessMsg(null), 4000);
      loadData();
    } catch (err: unknown) {
      alert(getApiErrorMessage(err, 'Failed to discharge patient'));
    } finally {
      setDischarging(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-400 animate-pulse">
        <User className="w-10 h-10 mx-auto mb-3 opacity-40 animate-bounce" />
        <p className="text-sm font-semibold">Loading patient file & stay timeline...</p>
      </div>
    );
  }

  if (error || !patient) {
    return (
      <div className="p-8 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-center text-rose-700 dark:text-rose-300 space-y-4">
        <AlertCircle className="w-8 h-8 mx-auto" />
        <p className="font-bold text-sm">{error || 'Patient record not found.'}</p>
        <button
          onClick={() => navigate('/patients')}
          className="px-4 py-2 bg-rose-600 text-white text-xs font-bold rounded-xl"
        >
          Back to Patients Directory
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* Top Navigation */}
      <div>
        <Link
          to="/patients"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-indigo-600 transition-colors mb-2"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Patients Directory
        </Link>
      </div>

      {/* Success Notification Banner */}
      {successMsg && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs font-medium animate-fadeIn">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Patient Main Banner */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="p-4 rounded-2xl bg-indigo-100 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 font-bold text-xl">
            {patient.first_name[0]}
            {patient.last_name[0]}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs font-black px-2.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                {patient.patient_identifier}
              </span>
              <span
                className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${
                  patient.status === 'ACTIVE'
                    ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
                }`}
              >
                {patient.status}
              </span>
            </div>
            <h1 className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">
              {patient.first_name} {patient.last_name}
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Registered on {new Date(patient.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowEditModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-bold text-slate-700 dark:text-slate-300 transition-all"
          >
            <Edit className="w-3.5 h-3.5" /> Edit Profile
          </button>

          {patient.current_admission ? (
            <button
              onClick={() => setShowDischargeModal(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-all shadow-md"
            >
              <Activity className="w-3.5 h-3.5" /> Discharge Patient
            </button>
          ) : (
            patient.status === 'ACTIVE' && (
              <button
                onClick={() => navigate(`/patients/${patient.id}/admit`)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-md"
              >
                <UserPlus className="w-4 h-4" /> Start Admission
              </button>
            )
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Demographics */}
        <div className="space-y-6">
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
            <h3 className="text-sm font-extrabold text-slate-900 dark:text-white uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 pb-3 flex items-center gap-2">
              <User className="w-4 h-4 text-indigo-500" /> Patient Metadata
            </h3>

            <div className="space-y-3 text-xs">
              <div className="flex items-start justify-between">
                <span className="text-slate-400 font-medium">Date of Birth:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" /> {patient.date_of_birth}
                </span>
              </div>

              <div className="flex items-start justify-between">
                <span className="text-slate-400 font-medium">Gender:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">{patient.gender}</span>
              </div>

              <div className="flex items-start justify-between">
                <span className="text-slate-400 font-medium">Phone:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1">
                  <Phone className="w-3.5 h-3.5 text-slate-400" /> {patient.phone || 'N/A'}
                </span>
              </div>

              <div className="flex items-start justify-between">
                <span className="text-slate-400 font-medium">Email:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1">
                  <Mail className="w-3.5 h-3.5 text-slate-400" /> {patient.email || 'N/A'}
                </span>
              </div>

              <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                <span className="text-slate-400 font-medium block mb-1">Residential Address:</span>
                <span className="font-medium text-slate-700 dark:text-slate-300 flex items-start gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                  {patient.address || 'No residential address recorded.'}
                </span>
              </div>
            </div>
          </div>

          {/* Emergency Contact */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
            <h3 className="text-sm font-extrabold text-slate-900 dark:text-white uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 pb-3 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-500" /> Emergency Contact
            </h3>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Contact Name:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  {patient.emergency_contact_name || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Contact Phone:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  {patient.emergency_contact_phone || 'N/A'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Admission Status & History */}
        <div className="lg:col-span-2 space-y-6">
          {/* Active Admission Card */}
          {patient.current_admission ? (
            <div className="p-6 rounded-2xl bg-gradient-to-br from-rose-500/10 via-rose-500/5 to-transparent border border-rose-200 dark:border-rose-900 shadow-xs relative overflow-hidden">
              <div className="flex items-center justify-between gap-4 mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="p-2.5 rounded-xl bg-rose-600 text-white shadow-xs">
                    <BedDouble className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-wider text-rose-600 dark:text-rose-400">
                      Active Hospital Stay
                    </span>
                    <h3 className="text-lg font-black text-slate-900 dark:text-white">
                      Admitted in {patient.current_admission.ward_name}
                    </h3>
                  </div>
                </div>
                <span className="font-mono text-xs font-bold px-3 py-1 rounded-lg bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400 shadow-xs">
                  {patient.current_admission.admission_number}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 rounded-xl bg-white/80 dark:bg-slate-900/80 backdrop-blur-xs border border-rose-100 dark:border-rose-900/50 mb-4 text-xs">
                <div>
                  <span className="text-slate-400 font-medium block">Ward</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">
                    {patient.current_admission.ward_name}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Assigned Bed</span>
                  <span className="font-bold text-rose-600 dark:text-rose-400 font-mono">
                    {patient.current_admission.bed_number}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Admission Date</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">
                    {new Date(patient.current_admission.admission_date).toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Status</span>
                  <span className="font-black text-rose-600">ADMITTED</span>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3">
                <button
                  onClick={() => setShowDischargeModal(true)}
                  className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-all shadow-md hover:shadow-lg flex items-center gap-1.5"
                >
                  <Activity className="w-4 h-4" />
                  Discharge Patient & Release Bed
                </button>
              </div>
            </div>
          ) : (
            <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs text-center py-8">
              <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              <h3 className="text-base font-bold text-slate-900 dark:text-white">Patient is Not Currently Admitted</h3>
              <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                No active hospital stay or bed occupancy. Select an available bed to admit this patient.
              </p>
              {patient.status === 'ACTIVE' && (
                <button
                  onClick={() => navigate(`/patients/${patient.id}/admit`)}
                  className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-md"
                >
                  <UserPlus className="w-4 h-4" /> Admit Patient Now
                </button>
              )}
            </div>
          )}

          {/* Admission History Table */}
          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
            <h3 className="text-sm font-extrabold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-500" /> Complete Stay & Admission History ({admissions.length})
            </h3>

            {admissions.length === 0 ? (
              <p className="text-xs text-slate-400 py-6 text-center">No historical admissions recorded for this patient.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-800/80 text-slate-500 uppercase tracking-wider font-bold border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-3 px-3">Admission #</th>
                      <th className="py-3 px-3">Ward</th>
                      <th className="py-3 px-3">Bed</th>
                      <th className="py-3 px-3">Admission Date</th>
                      <th className="py-3 px-3">Discharge Date</th>
                      <th className="py-3 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {admissions.map((adm) => (
                      <tr key={adm.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-3 font-mono font-bold text-indigo-600 dark:text-indigo-400">
                          {adm.admission_number}
                        </td>
                        <td className="py-3 px-3 font-bold">{adm.ward_name || `Ward #${adm.ward_id}`}</td>
                        <td className="py-3 px-3 font-mono font-semibold">{adm.bed_number || `Bed #${adm.bed_id}`}</td>
                        <td className="py-3 px-3 text-slate-500">{new Date(adm.admission_date).toLocaleString()}</td>
                        <td className="py-3 px-3 text-slate-500">
                          {adm.discharge_date ? new Date(adm.discharge_date).toLocaleString() : '—'}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                              adm.status === 'ADMITTED'
                                ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                                : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                            }`}
                          >
                            {adm.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Edit Profile Modal */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl w-full max-w-lg p-6 relative">
            <button
              onClick={() => setShowEditModal(false)}
              className="absolute right-4 top-4 p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Edit Patient Profile</h3>

            <form onSubmit={handleUpdatePatient} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">First Name *</label>
                  <input
                    type="text"
                    value={editFirstName}
                    onChange={(e) => setEditFirstName(e.target.value)}
                    required
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Last Name *</label>
                  <input
                    type="text"
                    value={editLastName}
                    onChange={(e) => setEditLastName(e.target.value)}
                    required
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Phone Number</label>
                  <input
                    type="text"
                    value={editPhone}
                    onChange={(e) => setEditPhone(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Email Address</label>
                  <input
                    type="email"
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Residential Address</label>
                <textarea
                  rows={2}
                  value={editAddress}
                  onChange={(e) => setEditAddress(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Emergency Contact Name</label>
                  <input
                    type="text"
                    value={editEmergName}
                    onChange={(e) => setEditEmergName(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Emergency Contact Phone</label>
                  <input
                    type="text"
                    value={editEmergPhone}
                    onChange={(e) => setEditEmergPhone(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 text-xs text-slate-500 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingEdit}
                  className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all disabled:opacity-50"
                >
                  {submittingEdit ? 'Saving...' : 'Save Profile Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Discharge Confirmation Modal */}
      {showDischargeModal && patient.current_admission && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl w-full max-w-md p-6 relative">
            <button
              onClick={() => setShowDischargeModal(false)}
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
                <p className="text-xs text-slate-500">Release assigned bed and mark stay as DISCHARGED</p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-2 mb-4 text-xs">
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Patient:</span>
                <span className="font-bold text-slate-900 dark:text-white">
                  {patient.first_name} {patient.last_name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Admission No:</span>
                <span className="font-mono">{patient.current_admission.admission_number}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-bold text-slate-500">Ward & Bed:</span>
                <span className="font-bold text-rose-600">
                  {patient.current_admission.ward_name} - {patient.current_admission.bed_number}
                </span>
              </div>
            </div>

            <div className="space-y-2 mb-4">
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300">
                Operational Discharge Notes (Optional)
              </label>
              <textarea
                rows={3}
                placeholder="Enter minimal discharge notes..."
                value={dischargeNotes}
                onChange={(e) => setDischargeNotes(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-rose-500"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowDischargeModal(false)}
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
