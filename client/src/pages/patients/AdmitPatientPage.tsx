import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { getPatient } from '../../services/patientService';
import { getWards } from '../../services/wardService';
import { getWardAvailableBeds, admitPatient } from '../../services/admissionService';
import { Patient, Ward, Bed } from '../../types';
import {
  ArrowLeft,
  UserPlus,
  BedDouble,
  Building,
  AlertCircle,
  Layers,
  FileText,
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

export const AdmitPatientPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const patientId = Number(id);
  const activeHospitalId = user?.hospital_id || 1;

  const [patient, setPatient] = useState<Patient | null>(null);
  const [wards, setWards] = useState<Ward[]>([]);
  const [availableBeds, setAvailableBeds] = useState<Bed[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingBeds, setLoadingBeds] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [selectedWardId, setSelectedWardId] = useState<number | ''>('');
  const [selectedBedId, setSelectedBedId] = useState<number | ''>('');
  const [admissionReason, setAdmissionReason] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  // 1. Load Patient & Hospital Wards
  const loadInitialData = useCallback(async () => {
    if (!patientId) return;
    try {
      setError(null);
      const [pData, wData] = await Promise.all([
        getPatient(patientId, activeHospitalId),
        getWards({ hospital_id: activeHospitalId, limit: 100 }),
      ]);

      if (pData.current_admission) {
        setError(`Patient ${pData.first_name} ${pData.last_name} already has an active admission (${pData.current_admission.admission_number}).`);
      }

      setPatient(pData);
      setWards(wData.items || []);

      if (wData.items && wData.items.length > 0) {
        setSelectedWardId(wData.items[0].id);
      }
    } catch (err: unknown) {
      console.error('Failed to load admission prerequisites:', err);
      setError(getApiErrorMessage(err, 'Failed to fetch patient or ward details.'));
    } finally {
      setLoading(false);
    }
  }, [patientId, activeHospitalId]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // 2. Load Available Beds whenever Ward changes
  const loadBedsForWard = useCallback(async (wardId: number) => {
    setLoadingBeds(true);
    try {
      const beds = await getWardAvailableBeds(wardId);
      setAvailableBeds(beds);
      if (beds.length > 0) {
        setSelectedBedId(beds[0].id);
      } else {
        setSelectedBedId('');
      }
    } catch (err: unknown) {
      console.error('Failed to load ward available beds:', err);
      setAvailableBeds([]);
      setSelectedBedId('');
    } finally {
      setLoadingBeds(false);
    }
  }, []);

  useEffect(() => {
    if (selectedWardId) {
      loadBedsForWard(Number(selectedWardId));
    } else {
      setAvailableBeds([]);
      setSelectedBedId('');
    }
  }, [selectedWardId, loadBedsForWard]);

  const handleSubmitAdmission = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patient || !selectedWardId || !selectedBedId) {
      setError('Please select a ward and an available bed.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const adm = await admitPatient({
        patient_id: patient.id,
        ward_id: Number(selectedWardId),
        bed_id: Number(selectedBedId),
        admission_reason: admissionReason.trim() || undefined,
        hospital_id: activeHospitalId,
      });

      alert(`Admission Successful!\nAdmission Number: ${adm.admission_number}\nWard: ${adm.ward_name}\nBed: ${adm.bed_number}`);
      navigate(`/patients/${patient.id}`);
    } catch (err: unknown) {
      console.error('Admission submit error:', err);
      setError(getApiErrorMessage(err, 'Failed to process admission transaction'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-400 animate-pulse">
        <UserPlus className="w-10 h-10 mx-auto mb-3 opacity-40 animate-bounce" />
        <p className="text-sm font-semibold">Initializing admission workflow...</p>
      </div>
    );
  }

  const selectedWard = wards.find((w) => w.id === Number(selectedWardId));
  const selectedBed = availableBeds.find((b) => b.id === Number(selectedBedId));

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fadeIn pb-12">
      {/* Back Link */}
      <div>
        <Link
          to={patient ? `/patients/${patient.id}` : '/patients'}
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-indigo-600 transition-colors mb-2"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Patient Profile
        </Link>
      </div>

      {/* Main Header Container */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
        <div className="p-6 bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3">
          <div className="p-3 rounded-xl bg-indigo-600 text-white shadow-xs">
            <BedDouble className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-slate-900 dark:text-white">Admit Patient & Assign Bed</h1>
            <p className="text-xs text-slate-500">
              Select ward, inspect available bed inventory, and create an active stay admission.
            </p>
          </div>
        </div>

        {error && (
          <div className="m-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs font-semibold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
        )}

        {patient && (
          <div className="p-6 space-y-6">
            {/* Patient Overview Card */}
            <div className="p-4 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900 flex items-center justify-between">
              <div>
                <span className="font-mono text-[11px] font-bold text-indigo-700 dark:text-indigo-300">
                  {patient.patient_identifier}
                </span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  {patient.first_name} {patient.last_name}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  DOB: {patient.date_of_birth} | Gender: {patient.gender}
                </p>
              </div>
              <span className="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                ACTIVE ACCOUNT
              </span>
            </div>

            <form onSubmit={handleSubmitAdmission} className="space-y-6">
              {/* Step 1: Select Ward */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <Building className="w-4 h-4 text-indigo-500" />
                  1. Select Target Ward *
                </label>
                <select
                  value={selectedWardId}
                  onChange={(e) => setSelectedWardId(Number(e.target.value))}
                  required
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                >
                  {wards.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name} ({w.ward_type} — {w.department})
                    </option>
                  ))}
                </select>
              </div>

              {/* Step 2: Select Available Bed */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-indigo-500" />
                    2. Select Available Bed *
                  </span>
                  {loadingBeds && <span className="text-[11px] text-indigo-500 animate-pulse">Loading beds...</span>}
                </label>

                {availableBeds.length === 0 && !loadingBeds ? (
                  <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-xs font-bold flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>No available beds in this ward. Please select another ward.</span>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {availableBeds.map((bed) => {
                      const isSelected = selectedBedId === bed.id;
                      return (
                        <button
                          key={bed.id}
                          type="button"
                          onClick={() => setSelectedBedId(bed.id)}
                          className={`p-3 rounded-xl border text-left transition-all ${
                            isSelected
                              ? 'border-indigo-600 bg-indigo-50 dark:bg-indigo-950/60 ring-2 ring-indigo-500/20'
                              : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/60 hover:border-indigo-300'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-sm font-black text-slate-900 dark:text-white">
                              {bed.bed_number}
                            </span>
                            <span className="w-2 h-2 rounded-full bg-emerald-500" />
                          </div>
                          <span className="text-[10px] font-bold text-slate-400 block">{bed.bed_type}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Step 3: Admission Reason */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-indigo-500" />
                  3. Operational Reason for Admission (Optional)
                </label>
                <textarea
                  rows={3}
                  placeholder="Enter operational reason for hospital stay..."
                  value={admissionReason}
                  onChange={(e) => setAdmissionReason(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* Step 4: Confirmation Preview Card */}
              {selectedWard && selectedBed && (
                <div className="p-4 rounded-xl bg-slate-900 text-white space-y-2 text-xs animate-fadeIn">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="font-bold text-slate-400">Admission Summary Confirmation</span>
                    <span className="text-[10px] font-mono text-emerald-400">READY TO ADMIT</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 pt-1">
                    <div>
                      <span className="text-slate-400 block text-[10px]">Patient</span>
                      <span className="font-bold">{patient.first_name} {patient.last_name}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Ward</span>
                      <span className="font-bold">{selectedWard.name}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Assigned Bed</span>
                      <span className="font-bold text-emerald-400 font-mono">{selectedBed.bed_number}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Submit Buttons */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => navigate(`/patients/${patient.id}`)}
                  className="px-5 py-2.5 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !selectedBedId || !!patient.current_admission}
                  className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold transition-all shadow-md hover:shadow-lg disabled:opacity-50 flex items-center gap-1.5"
                >
                  {submitting ? 'Processing Admission...' : 'Confirm & Admit Patient'}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
