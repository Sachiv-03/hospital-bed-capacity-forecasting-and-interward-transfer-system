import React, { useState, useEffect } from 'react';
import { X, ArrowRight, AlertCircle, User, Send } from 'lucide-react';
import { Admission, Ward, Bed } from '../../types';
import { getAdmissions, getWardAvailableBeds } from '../../services/admissionService';
import { getWards } from '../../services/wardService';
import { transferService } from '../../services/transferService';

interface NewTransferModalProps {
  hospitalId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export const NewTransferModal: React.FC<NewTransferModalProps> = ({
  hospitalId,
  onClose,
  onSuccess,
}) => {
  const [admissions, setAdmissions] = useState<Admission[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [availableBeds, setAvailableBeds] = useState<Bed[]>([]);

  const [selectedAdmissionId, setSelectedAdmissionId] = useState<string>('');
  const [selectedDestinationWardId, setSelectedDestinationWardId] = useState<string>('');
  const [selectedDestinationBedId, setSelectedDestinationBedId] = useState<string>('');
  const [reason, setReason] = useState<string>('');

  const [loadingAdmissions, setLoadingAdmissions] = useState<boolean>(true);
  const [loadingBeds, setLoadingBeds] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchInitialData = async () => {
      setLoadingAdmissions(true);
      try {
        const [admissionsRes, wardsRes] = await Promise.all([
          getAdmissions({ hospital_id: hospitalId, status: 'ADMITTED', limit: 100 }),
          getWards({ hospital_id: hospitalId, limit: 100 }),
        ]);
        setAdmissions(admissionsRes.items || []);
        setWards((wardsRes.items || []).filter((w: Ward) => w.status === 'ACTIVE'));
      } catch (err: unknown) {

        const errObj = err as { response?: { data?: { detail?: string } } };
        setError(errObj.response?.data?.detail || 'Failed to fetch patients or wards data.');
      } finally {
        setLoadingAdmissions(false);
      }
    };

    fetchInitialData();
  }, [hospitalId]);

  const selectedAdmission = admissions.find((a) => a.id === Number(selectedAdmissionId));

  // Fetch available beds when destination ward changes
  useEffect(() => {
    if (!selectedDestinationWardId) {
      setAvailableBeds([]);
      setSelectedDestinationBedId('');
      return;
    }

    const fetchBeds = async () => {
      setLoadingBeds(true);
      setError(null);
      try {
        const beds = await getWardAvailableBeds(Number(selectedDestinationWardId));
        setAvailableBeds(beds);
      } catch (err: unknown) {
        const errObj = err as { response?: { data?: { detail?: string } } };
        setError(errObj.response?.data?.detail || 'Failed to fetch available beds.');
      } finally {
        setLoadingBeds(false);
      }
    };

    fetchBeds();
  }, [selectedDestinationWardId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAdmission) {
      setError('Please select an admitted patient.');
      return;
    }
    if (!selectedDestinationWardId) {
      setError('Please select a destination ward.');
      return;
    }
    if (!selectedDestinationBedId) {
      setError('Please select an available destination bed.');
      return;
    }
    if (selectedAdmission.ward_id === Number(selectedDestinationWardId)) {
      setError('Destination ward must be different from current ward.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await transferService.createPatientTransfer({
        patient_id: selectedAdmission.patient_id,
        destination_ward_id: Number(selectedDestinationWardId),
        destination_bed_id: Number(selectedDestinationBedId),
        reason: reason.trim() || undefined,
        hospital_id: hospitalId,
      });

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const errObj = err as { response?: { data?: { detail?: string } } };
      setError(errObj.response?.data?.detail || 'Failed to create transfer request.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
              New Inter-Ward Transfer Request
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Relocate an admitted patient to another ward with an available bed.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* 1. Select Patient */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Select Admitted Patient *
            </label>
            {loadingAdmissions ? (
              <div className="h-10 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse"></div>
            ) : admissions.length === 0 ? (
              <div className="p-3 bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 text-xs rounded-lg">
                No currently admitted patients found in this hospital.
              </div>
            ) : (
              <select
                value={selectedAdmissionId}
                onChange={(e) => {
                  setSelectedAdmissionId(e.target.value);
                  setSelectedDestinationWardId('');
                }}
                required
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs font-medium focus:ring-2 focus:ring-sky-500"
              >
                <option value="">-- Choose Patient --</option>
                {admissions.map((adm) => (
                  <option key={adm.id} value={adm.id}>
                    {adm.patient?.first_name} {adm.patient?.last_name} ({adm.patient?.patient_identifier}) - Ward: {adm.ward_name || adm.ward_id}, Bed: {adm.bed_number || adm.bed_id}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Current Location Display */}
          {selectedAdmission && (
            <div className="p-3.5 rounded-xl bg-sky-50/70 dark:bg-sky-950/30 border border-sky-100 dark:border-sky-900/50 space-y-2 text-xs">
              <div className="font-semibold text-sky-900 dark:text-sky-300 flex items-center gap-1.5">
                <User className="w-4 h-4 text-sky-600" />
                Current Admission Details
              </div>
              <div className="grid grid-cols-2 gap-2 text-slate-600 dark:text-slate-300">
                <div>
                  <span className="text-slate-400">Current Ward:</span>{' '}
                  <strong className="text-slate-800 dark:text-slate-200">{selectedAdmission.ward_name || `Ward #${selectedAdmission.ward_id}`}</strong>
                </div>
                <div>
                  <span className="text-slate-400">Current Bed:</span>{' '}
                  <strong className="text-slate-800 dark:text-slate-200">{selectedAdmission.bed_number || `Bed #${selectedAdmission.bed_id}`}</strong>
                </div>
              </div>
            </div>
          )}

          {/* Transfer Arrow Indicator */}
          {selectedAdmission && (
            <div className="flex items-center justify-center gap-2 text-xs text-slate-400 font-semibold uppercase tracking-wider">
              <span>Current Location</span>
              <ArrowRight className="w-4 h-4 text-sky-500 animate-pulse" />
              <span>Destination</span>
            </div>
          )}

          {/* 2. Destination Ward */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Destination Ward *
            </label>
            <select
              value={selectedDestinationWardId}
              onChange={(e) => setSelectedDestinationWardId(e.target.value)}
              disabled={!selectedAdmission}
              required
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs font-medium focus:ring-2 focus:ring-sky-500 disabled:opacity-50"
            >
              <option value="">-- Choose Destination Ward --</option>
              {wards
                .filter((w) => selectedAdmission ? w.id !== selectedAdmission.ward_id : true)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name} ({w.ward_type} - Floor {w.floor})
                  </option>
                ))}
            </select>
          </div>

          {/* 3. Destination Bed */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Destination Bed (AVAILABLE) *
            </label>
            {loadingBeds ? (
              <div className="h-10 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse"></div>
            ) : !selectedDestinationWardId ? (
              <div className="text-xs text-slate-400 italic">Select a destination ward first.</div>
            ) : availableBeds.length === 0 ? (
              <div className="p-3 bg-rose-50 dark:bg-rose-950/30 text-rose-800 dark:text-rose-300 text-xs rounded-lg">
                No AVAILABLE beds currently in this destination ward.
              </div>
            ) : (
              <select
                value={selectedDestinationBedId}
                onChange={(e) => setSelectedDestinationBedId(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs font-medium focus:ring-2 focus:ring-sky-500"
              >
                <option value="">-- Select Available Bed --</option>
                {availableBeds.map((b) => (
                  <option key={b.id} value={b.id}>
                    Bed {b.bed_number} ({b.bed_type})
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* 4. Reason */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Reason for Transfer
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. ICU step-down to General Ward, patient condition improved, specialty care requirement..."
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs font-medium focus:ring-2 focus:ring-sky-500"
            ></textarea>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !selectedDestinationBedId}
              className="inline-flex items-center gap-1.5 px-5 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-xl shadow-xs transition-colors disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              {submitting ? 'Submitting Request...' : 'Submit Transfer Request'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
