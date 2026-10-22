import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  ArrowRight,
  AlertCircle,
  User,
  Send,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  BedDouble,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';
import { Admission, Ward, Bed, DestinationWardRecommendation } from '../../types';
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

  // Phase 11 Decision Support Recommendations state
  const [recommendations, setRecommendations] = useState<DestinationWardRecommendation[]>([]);
  const [loadingRecs, setLoadingRecs] = useState<boolean>(false);
  const [recsError, setRecsError] = useState<string | null>(null);

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

  // Phase 11: Fetch explainable destination recommendations when patient is selected
  const fetchRecommendations = useCallback(async (patientId: number) => {
    setLoadingRecs(true);
    setRecsError(null);
    try {
      const resp = await transferService.getPatientDestinationRecommendations({
        patient_id: patientId,
        hospital_id: hospitalId,
        horizon_days: 1,
      });
      setRecommendations(resp.recommendations || []);
    } catch (err: unknown) {
      const errObj = err as { response?: { data?: { detail?: string } } };
      setRecsError(errObj.response?.data?.detail || 'Decision support recommendations unavailable.');
      setRecommendations([]);
    } finally {
      setLoadingRecs(false);
    }
  }, [hospitalId]);

  useEffect(() => {
    if (selectedAdmission) {
      fetchRecommendations(selectedAdmission.patient_id);
    } else {
      setRecommendations([]);
      setRecsError(null);
    }
  }, [selectedAdmission, fetchRecommendations]);

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

  const handleSelectRecommendedWard = (rec: DestinationWardRecommendation) => {
    setSelectedDestinationWardId(rec.ward_id.toString());
    if (rec.available_candidate_beds && rec.available_candidate_beds.length > 0) {
      setSelectedDestinationBedId(rec.available_candidate_beds[0].id.toString());
    } else {
      setSelectedDestinationBedId('');
    }
  };

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
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between shrink-0">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                New Inter-Ward Transfer Request
              </h2>
              <span className="px-2.5 py-0.5 text-[11px] font-semibold rounded-full bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-sky-600" />
                Phase 11 Decision Support
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Explainable destination ward recommendations based on live occupancy, SARIMA forecasts, and ward compatibility.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5 overflow-y-auto flex-1">
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
                  setSelectedDestinationBedId('');
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
              <div className="font-semibold text-sky-900 dark:text-sky-300 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <User className="w-4 h-4 text-sky-600" />
                  Current Admission Context
                </div>
                <span className="text-[11px] text-sky-700 dark:text-sky-400 font-normal">
                  Admission #{selectedAdmission.admission_number || selectedAdmission.id}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-slate-600 dark:text-slate-300">
                <div>
                  <span className="text-slate-400">Current Ward:</span>{' '}
                  <strong className="text-slate-800 dark:text-slate-200">{selectedAdmission.ward_name || `Ward #${selectedAdmission.ward_id}`}</strong>
                </div>
                <div>
                  <span className="text-slate-400">Current Bed:</span>{' '}
                  <strong className="text-slate-800 dark:text-slate-200">{selectedAdmission.bed_number || `Bed #${selectedAdmission.bed_id}`}</strong>
                </div>
                <div>
                  <span className="text-slate-400">Bed Type:</span>{' '}
                  <strong className="text-slate-800 dark:text-slate-200">{selectedAdmission.bed?.bed_type || 'STANDARD'}</strong>
                </div>
              </div>
            </div>
          )}

          {/* PHASE 11: RECOMMENDATION DECISION SUPPORT PANEL */}
          {selectedAdmission && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-sky-600" />
                  <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                    Recommended Destination Wards (Decision Support)
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => fetchRecommendations(selectedAdmission.patient_id)}
                  disabled={loadingRecs}
                  className="text-[11px] text-sky-600 hover:text-sky-700 dark:text-sky-400 font-semibold flex items-center gap-1"
                >
                  <RefreshCw className={`w-3 h-3 ${loadingRecs ? 'animate-spin' : ''}`} />
                  Re-evaluate
                </button>
              </div>

              {loadingRecs ? (
                <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-800 text-center text-xs text-slate-500 space-y-2">
                  <div className="animate-spin w-5 h-5 border-2 border-sky-600 border-t-transparent rounded-full mx-auto"></div>
                  <div>Analyzing live bed occupancy, SARIMA forecasts, and compatibility rules...</div>
                </div>
              ) : recsError ? (
                <div className="p-3 bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 text-xs rounded-xl border border-amber-200 dark:border-amber-900">
                  {recsError}
                </div>
              ) : recommendations.length === 0 ? (
                <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-800 text-center text-xs text-slate-500">
                  No other active wards found in this hospital facility.
                </div>
              ) : (
                <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                  {recommendations.map((rec) => {
                    const isSelected = selectedDestinationWardId === rec.ward_id.toString();
                    return (
                      <div
                        key={rec.ward_id}
                        className={`p-3.5 rounded-xl border transition-all text-xs space-y-2 ${
                          isSelected
                            ? 'border-sky-500 bg-sky-50/50 dark:bg-sky-950/40 shadow-xs'
                            : rec.is_eligible
                            ? 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/60 hover:border-slate-300'
                            : 'border-slate-100 dark:border-slate-800/60 bg-slate-50/50 dark:bg-slate-800/20 opacity-70'
                        }`}
                      >
                        {/* Card Header */}
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                rec.rank === 1
                                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                                  : rec.rank === 2
                                  ? 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300'
                                  : 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
                              }`}
                            >
                              Rank #{rec.rank}
                            </span>
                            <span className="font-bold text-slate-900 dark:text-slate-100">
                              {rec.ward_name}
                            </span>
                            <span className="text-[10px] uppercase font-semibold text-slate-500 px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded">
                              {rec.ward_type}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <span className="text-xs font-extrabold text-sky-600 dark:text-sky-400">
                              Score: {rec.score.toFixed(0)}/100
                            </span>
                            {rec.is_eligible ? (
                              <button
                                type="button"
                                onClick={() => handleSelectRecommendedWard(rec)}
                                className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition-colors ${
                                  isSelected
                                    ? 'bg-sky-600 text-white'
                                    : 'bg-slate-100 hover:bg-sky-100 text-slate-800 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-sky-900'
                                }`}
                              >
                                {isSelected ? 'Selected ✓' : 'Select Ward'}
                              </button>
                            ) : (
                              <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-950/60 dark:text-rose-300">
                                Ineligible
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Capacity & Forecast Metric Badges */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-slate-600 dark:text-slate-300">
                          <div className="flex items-center gap-1.5">
                            <BedDouble className="w-3.5 h-3.5 text-slate-400" />
                            <span>
                              Available: <strong>{rec.current_available_beds} beds</strong>
                            </span>
                          </div>
                          <div>
                            <span>
                              Current Occ: <strong>{rec.current_occupancy_percentage}%</strong>
                            </span>
                          </div>
                          <div className="flex items-center gap-1">
                            <TrendingUp className="w-3.5 h-3.5 text-sky-500" />
                            <span>
                              Forecast Occ:{' '}
                              <strong>
                                {rec.forecasted_occupancy_percentage !== null
                                  ? `${rec.forecasted_occupancy_percentage}%`
                                  : 'N/A'}
                              </strong>
                            </span>
                          </div>
                          <div>
                            <span>
                              Safe Headroom: <strong>{rec.safe_transfer_capacity} beds</strong>
                            </span>
                          </div>
                        </div>

                        {/* Explainable Reasons & Warnings */}
                        {rec.reasons && rec.reasons.length > 0 && (
                          <div className="space-y-0.5 text-[11px] text-emerald-800 dark:text-emerald-300 bg-emerald-50/60 dark:bg-emerald-950/30 p-2 rounded-lg">
                            {rec.reasons.map((r, idx) => (
                              <div key={idx} className="flex items-start gap-1.5">
                                <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0 mt-0.5" />
                                <span>{r}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {!rec.is_eligible && rec.ineligibility_reasons.length > 0 && (
                          <div className="space-y-0.5 text-[11px] text-rose-800 dark:text-rose-300 bg-rose-50/60 dark:bg-rose-950/30 p-2 rounded-lg">
                            {rec.ineligibility_reasons.map((r, idx) => (
                              <div key={idx} className="flex items-start gap-1.5">
                                <AlertCircle className="w-3 h-3 text-rose-600 shrink-0 mt-0.5" />
                                <span>{r}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {rec.warnings && rec.warnings.length > 0 && (
                          <div className="text-[10px] text-amber-700 dark:text-amber-400 flex items-start gap-1">
                            <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0 mt-0.5" />
                            <span>{rec.warnings[0]}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Disclaimer */}
              <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex items-center gap-1.5 text-[10px] text-slate-500">
                <ShieldCheck className="w-3.5 h-3.5 text-sky-600 shrink-0" />
                <span>
                  Staff Decision Support Only: Destination recommendations must be physically verified and clinically authorized by medical staff before patient movement.
                </span>
              </div>
            </div>
          )}

          {/* Transfer Flow Indicator */}
          {selectedAdmission && (
            <div className="flex items-center justify-center gap-2 text-xs text-slate-400 font-semibold uppercase tracking-wider pt-2">
              <span>Source Location</span>
              <ArrowRight className="w-4 h-4 text-sky-500 animate-pulse" />
              <span>Selected Destination</span>
            </div>
          )}

          {/* 2. Destination Ward Selector */}
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

          {/* 3. Destination Bed Selector */}
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
                No AVAILABLE physical beds currently in this destination ward.
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
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. ICU step-down to General Ward, patient condition improved, capacity rebalancing..."
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs font-medium focus:ring-2 focus:ring-sky-500"
            ></textarea>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 dark:border-slate-800 shrink-0">
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
