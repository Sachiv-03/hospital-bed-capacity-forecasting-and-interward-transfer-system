import React, { useState, useEffect } from 'react';
import {
  X,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Info,
  Clock,
  ThumbsUp,
  ThumbsDown,
  Lock,
  Activity,
  FileText,
} from 'lucide-react';
import { TransferRecommendationDetail, UserRole } from '../../types';
import { transferService } from '../../services/transferService';
import { cn } from '../../utils/cn';

interface TransferRecommendationDetailModalProps {
  recommendationId: number | null;
  userRole?: UserRole;
  onClose: () => void;
  onSuccess: () => void;
}

export const TransferRecommendationDetailModal: React.FC<TransferRecommendationDetailModalProps> = ({
  recommendationId,
  userRole,
  onClose,
  onSuccess,
}) => {
  const [detail, setDetail] = useState<TransferRecommendationDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Approval Modal state
  const [showApproveConfirm, setShowApproveConfirm] = useState<boolean>(false);
  const [approvalNotes, setApprovalNotes] = useState<string>('');
  const [approving, setApproving] = useState<boolean>(false);

  // Rejection Modal state
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);
  const [rejectionReasonSelect, setRejectionReasonSelect] = useState<string>('Clinical decision');
  const [rejectionReasonText, setRejectionReasonText] = useState<string>('');
  const [rejecting, setRejecting] = useState<boolean>(false);
  const [rejectionError, setRejectionError] = useState<string | null>(null);

  const canAction = ['super_admin', 'admin', 'doctor', 'nurse'].includes(userRole || '');

  useEffect(() => {
    if (!recommendationId) return;
    fetchDetail();
  }, [recommendationId]);

  const fetchDetail = async () => {
    if (!recommendationId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await transferService.getRecommendationDetail(recommendationId);
      setDetail(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load recommendation details.');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!recommendationId) return;
    setApproving(true);
    setError(null);
    try {
      await transferService.approveRecommendation(recommendationId, approvalNotes);
      setShowApproveConfirm(false);
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to approve recommendation.');
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!recommendationId) return;
    const finalReason =
      rejectionReasonSelect === 'Other'
        ? rejectionReasonText
        : `${rejectionReasonSelect}: ${rejectionReasonText}`.trim();

    if (!finalReason || finalReason.length < 3) {
      setRejectionError('Please provide a descriptive reason for rejecting this recommendation.');
      return;
    }

    setRejecting(true);
    setRejectionError(null);
    try {
      await transferService.rejectRecommendation(recommendationId, finalReason);
      setShowRejectModal(false);
      onSuccess();
      onClose();
    } catch (err: any) {
      setRejectionError(err.response?.data?.detail || 'Failed to reject recommendation.');
    } finally {
      setRejecting(false);
    }
  };

  if (!recommendationId) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="relative w-full max-w-3xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden my-8">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-sky-600 dark:text-sky-400" />
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
              Inter-Ward Transfer Decision Support Explanation
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 space-y-3">
              <div className="w-8 h-8 border-4 border-sky-600 border-t-transparent rounded-full animate-spin"></div>
              <p className="text-xs text-slate-500">Loading decision support data & revalidating...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-300 text-sm">
              {error}
            </div>
          ) : detail ? (
            <>
              {/* Revalidation Banner */}
              {detail.revalidation_status !== 'VALID' && (
                <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 flex items-center gap-2.5 text-xs text-amber-900 dark:text-amber-200">
                  <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <div>
                    <strong>Capacity Revalidation Notice:</strong> {detail.revalidation_status}
                  </div>
                </div>
              )}

              {/* Transfer Flow Header Card */}
              <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200/80 dark:border-slate-800 grid grid-cols-1 md:grid-cols-11 gap-4 items-center">
                {/* Source Ward */}
                <div className="md:col-span-5 space-y-1">
                  <div className="text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                    Source Ward
                  </div>
                  <div className="text-lg font-bold text-slate-900 dark:text-slate-100">
                    {detail.source_ward?.name || `Ward #${detail.source_ward_id}`}
                  </div>
                  <div className="text-xs text-slate-600 dark:text-slate-400 space-y-0.5">
                    <div>
                      Department: <strong>{detail.source_ward?.department || 'N/A'}</strong>
                    </div>
                    <div>
                      Current Occupancy:{' '}
                      <strong className="text-slate-900 dark:text-slate-100">
                        {detail.source_current_occupancy}%
                      </strong>
                    </div>
                    <div>
                      Tomorrow Forecast:{' '}
                      <strong className="text-rose-600 dark:text-rose-400">
                        {detail.source_predicted_occupancy}%
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Arrow */}
                <div className="md:col-span-1 flex items-center justify-center">
                  <div className="w-9 h-9 rounded-full bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold">
                    <ArrowRight className="w-5 h-5" />
                  </div>
                </div>

                {/* Destination Ward */}
                <div className="md:col-span-5 space-y-1">
                  <div className="text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                    Target Destination
                  </div>
                  <div className="text-lg font-bold text-slate-900 dark:text-slate-100">
                    {detail.destination_ward?.name || `Ward #${detail.destination_ward_id}`}
                  </div>
                  <div className="text-xs text-slate-600 dark:text-slate-400 space-y-0.5">
                    <div>
                      Department: <strong>{detail.destination_ward?.department || 'N/A'}</strong>
                    </div>
                    <div>
                      Current Occupancy:{' '}
                      <strong className="text-slate-900 dark:text-slate-100">
                        {detail.destination_current_occupancy}%
                      </strong>
                    </div>
                    <div>
                      Tomorrow Forecast:{' '}
                      <strong className="text-slate-900 dark:text-slate-100">
                        {detail.destination_predicted_occupancy}%
                      </strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Score Breakdown & Safe Capacity Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Score Card */}
                <div className="p-4 bg-sky-50/60 dark:bg-sky-950/20 rounded-xl border border-sky-100 dark:border-sky-900/40 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-sky-900 dark:text-sky-300 uppercase tracking-wider">
                      Decision Support Score
                    </span>
                    <span className="text-xl font-extrabold text-sky-600 dark:text-sky-400">
                      {detail.priority_score.toFixed(0)} / 100
                    </span>
                  </div>

                  {/* Score Breakdown Progress Bars */}
                  {detail.score_breakdown && (
                    <div className="space-y-2 text-xs">
                      <div>
                        <div className="flex justify-between text-slate-600 dark:text-slate-400 mb-0.5">
                          <span>Source Urgency (0–40)</span>
                          <span className="font-semibold">{detail.score_breakdown.source_urgency} pts</span>
                        </div>
                        <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-rose-500 h-full rounded-full"
                            style={{ width: `${(detail.score_breakdown.source_urgency / 40) * 100}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-slate-600 dark:text-slate-400 mb-0.5">
                          <span>Destination Capacity (0–25)</span>
                          <span className="font-semibold">{detail.score_breakdown.destination_capacity} pts</span>
                        </div>
                        <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-emerald-500 h-full rounded-full"
                            style={{ width: `${(detail.score_breakdown.destination_capacity / 25) * 100}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-slate-600 dark:text-slate-400 mb-0.5">
                          <span>Destination Future Capacity (0–20)</span>
                          <span className="font-semibold">{detail.score_breakdown.future_capacity} pts</span>
                        </div>
                        <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-sky-500 h-full rounded-full"
                            style={{ width: `${(detail.score_breakdown.future_capacity / 20) * 100}%` }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-slate-600 dark:text-slate-400 mb-0.5">
                          <span>Ward Compatibility (0–15)</span>
                          <span className="font-semibold">{detail.score_breakdown.compatibility} pts</span>
                        </div>
                        <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-purple-500 h-full rounded-full"
                            style={{ width: `${(detail.score_breakdown.compatibility / 15) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Safe Capacity Card */}
                <div className="p-4 bg-emerald-50/60 dark:bg-emerald-950/20 rounded-xl border border-emerald-100 dark:border-emerald-900/40 space-y-3 flex flex-col justify-between">
                  <div>
                    <div className="text-xs font-semibold text-emerald-900 dark:text-emerald-300 uppercase tracking-wider mb-1">
                      Safe Capacity Threshold
                    </div>
                    <div className="text-2xl font-extrabold text-emerald-700 dark:text-emerald-300">
                      Up to {detail.safe_transfer_capacity} Safe Beds
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mt-2 leading-relaxed">
                      Calculated using a <strong>85% maximum safe destination occupancy</strong> safety margin to prevent destination ward overflow.
                    </p>
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 pt-2 border-t border-emerald-200/50 dark:border-emerald-900/40">
                    Destination Available Beds: <strong>{detail.available_beds} beds</strong>
                  </div>
                </div>
              </div>

              {/* Human Readable Explanation Reason */}
              <div className="p-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200/80 dark:border-slate-800 space-y-2">
                <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-sky-600" />
                  Recommendation Rationale:
                </div>
                <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                  {detail.reason}
                </p>
              </div>

              {/* Passed Rules & Warnings */}
              <div className="space-y-3">
                {detail.rules_passed && detail.rules_passed.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Passed Rules & Compatibility Checks
                    </div>
                    <ul className="space-y-1 text-xs text-slate-600 dark:text-slate-400 pl-5 list-disc">
                      {detail.rules_passed.map((rule, idx) => (
                        <li key={idx}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {detail.warnings && detail.warnings.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-amber-800 dark:text-amber-300 mb-1.5 flex items-center gap-1">
                      <AlertTriangle className="w-4 h-4 text-amber-600" /> Operational Warnings & Considerations
                    </div>
                    <ul className="space-y-1 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 p-3 rounded-lg border border-amber-200/60 dark:border-amber-900/40 list-disc pl-5">
                      {detail.warnings.map((warn, idx) => (
                        <li key={idx}>{warn}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Status & Review Audit Footer */}
              {detail.status === 'APPROVED' && (
                <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-xs text-emerald-900 dark:text-emerald-200 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <div>
                    Approved by staff member at {detail.approved_at ? new Date(detail.approved_at).toLocaleString() : 'N/A'}.
                  </div>
                </div>
              )}

              {detail.status === 'REJECTED' && (
                <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-900 dark:text-rose-200 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <X className="w-4 h-4 text-rose-600" /> Recommendation Rejected by Hospital Staff
                  </div>
                  <div>Reason: {detail.rejection_reason || 'No reason specified'}</div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Modal Footer Controls */}
        <div className="px-6 py-4 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            Close
          </button>

          {detail && detail.status === 'PENDING' && canAction && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowRejectModal(true)}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 dark:text-rose-300 dark:bg-rose-950/60 dark:hover:bg-rose-900 rounded-lg border border-rose-200 dark:border-rose-800 transition-colors"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
                Reject Recommendation
              </button>

              <button
                onClick={() => setShowApproveConfirm(true)}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 dark:bg-sky-500 dark:hover:bg-sky-600 rounded-lg transition-colors shadow-xs"
              >
                <ThumbsUp className="w-3.5 h-3.5" />
                Approve Recommendation
              </button>
            </div>
          )}
        </div>

        {/* Approve Confirmation Modal */}
        {showApproveConfirm && (
          <div className="fixed inset-0 z-60 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white dark:bg-slate-900 rounded-xl p-6 max-w-md w-full border border-slate-200 dark:border-slate-800 space-y-4 shadow-2xl">
              <div className="flex items-center gap-2 text-sky-600 dark:text-sky-400">
                <ThumbsUp className="w-5 h-5" />
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Approve Transfer Recommendation?
                </h3>
              </div>

              <div className="text-xs text-slate-600 dark:text-slate-400 space-y-2 leading-relaxed bg-sky-50/50 dark:bg-sky-950/30 p-3 rounded-lg border border-sky-100 dark:border-sky-900/40">
                <p>
                  You are approving the decision support recommendation to transfer capacity from{' '}
                  <strong>{detail?.source_ward?.name}</strong> to <strong>{detail?.destination_ward?.name}</strong>.
                </p>
                <p className="font-semibold text-slate-700 dark:text-slate-300">
                  ⚠️ Note: Approving this decision support recommendation registers staff authorization; it does NOT automatically move or alter any patient record.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Optional Staff Approval Notes:
                </label>
                <textarea
                  value={approvalNotes}
                  onChange={(e) => setApprovalNotes(e.target.value)}
                  placeholder="e.g. Approved during morning clinical bed rounds."
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  rows={2}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowApproveConfirm(false)}
                  className="px-3.5 py-1.5 text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleApprove}
                  disabled={approving}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg flex items-center gap-1.5 shadow-xs"
                >
                  {approving ? 'Approving...' : 'Confirm Approval'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Rejection Reason Modal */}
        {showRejectModal && (
          <div className="fixed inset-0 z-60 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white dark:bg-slate-900 rounded-xl p-6 max-w-md w-full border border-slate-200 dark:border-slate-800 space-y-4 shadow-2xl">
              <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
                <ThumbsDown className="w-5 h-5" />
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Reject Transfer Recommendation
                </h3>
              </div>

              <p className="text-xs text-slate-600 dark:text-slate-400">
                Please provide a mandatory operational or clinical reason for rejecting this recommendation:
              </p>

              {rejectionError && (
                <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                  {rejectionError}
                </div>
              )}

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Select Reason Category:
                  </label>
                  <select
                    value={rejectionReasonSelect}
                    onChange={(e) => setRejectionReasonSelect(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
                  >
                    <option value="Clinical decision">Clinical decision (Patient not stable for transfer)</option>
                    <option value="Destination unavailable">Destination ward temporarily unavailable</option>
                    <option value="Staffing restriction">Staffing / Nurse ratio constraint</option>
                    <option value="Operational restriction">Operational restriction in destination</option>
                    <option value="Recommendation no longer appropriate">Recommendation no longer appropriate</option>
                    <option value="Other">Other (Custom explanation)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Explanation Details:
                  </label>
                  <textarea
                    value={rejectionReasonText}
                    onChange={(e) => setRejectionReasonText(e.target.value)}
                    placeholder="Provide details explaining the rejection reason..."
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    rows={3}
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowRejectModal(false)}
                  className="px-3.5 py-1.5 text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReject}
                  disabled={rejecting}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg flex items-center gap-1.5 shadow-xs"
                >
                  {rejecting ? 'Submitting Rejection...' : 'Submit Rejection'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
