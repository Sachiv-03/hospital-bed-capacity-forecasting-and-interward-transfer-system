import React, { useState } from 'react';
import { X, CheckCircle2, XCircle, CheckSquare, Ban, AlertCircle, User } from 'lucide-react';
import { PatientTransfer } from '../../types';

import { transferService } from '../../services/transferService';

interface TransferActionModalProps {
  transfer: PatientTransfer;
  userRole?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export const TransferActionModal: React.FC<TransferActionModalProps> = ({
  transfer,
  userRole,
  onClose,
  onSuccess,
}) => {
  const [actionType, setActionType] = useState<'VIEW' | 'APPROVE' | 'REJECT' | 'COMPLETE' | 'CANCEL'>('VIEW');
  const [notes, setNotes] = useState<string>('');
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const canApproveOrReject = ['super_admin', 'admin', 'doctor'].includes(userRole || '');
  const canCompleteOrCancel = ['super_admin', 'admin', 'doctor', 'nurse'].includes(userRole || '');

  const handleApprove = async () => {
    setLoading(true);
    setError(null);
    try {
      await transferService.approvePatientTransfer(transfer.id, notes.trim() || undefined);
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const errObj = err as { response?: { data?: { detail?: string } } };
      setError(errObj.response?.data?.detail || 'Failed to approve transfer.');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      setError('Rejection reason is required.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await transferService.rejectPatientTransfer(transfer.id, rejectionReason.trim());
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const errObj = err as { response?: { data?: { detail?: string } } };
      setError(errObj.response?.data?.detail || 'Failed to reject transfer.');
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = async () => {
    setLoading(true);
    setError(null);
    try {
      await transferService.completePatientTransfer(transfer.id);
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const errObj = err as { response?: { data?: { detail?: string } } };
      setError(errObj.response?.data?.detail || 'Failed to complete transfer.');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    setLoading(true);
    setError(null);
    try {
      await transferService.cancelPatientTransfer(transfer.id);
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const errObj = err as { response?: { data?: { detail?: string } } };
      setError(errObj.response?.data?.detail || 'Failed to cancel transfer.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                Transfer Request #{transfer.id}
              </h2>
              <span
                className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border ${
                  transfer.status === 'REQUESTED'
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : transfer.status === 'APPROVED'
                    ? 'bg-sky-50 text-sky-700 border-sky-200'
                    : transfer.status === 'COMPLETED'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}
              >
                {transfer.status}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Requested on {new Date(transfer.requested_at).toLocaleString()}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Patient Overview */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-900 dark:text-slate-100">
              <User className="w-4 h-4 text-sky-600" />
              {transfer.patient_name || `Patient ID #${transfer.patient_id}`}
              <span className="text-slate-400 font-normal">
                ({transfer.patient_identifier})
              </span>
            </div>

            {/* Transfer Movement Visualization */}
            <div className="grid grid-cols-2 gap-3 pt-2 text-xs border-t border-slate-200 dark:border-slate-700/60">
              <div className="space-y-1">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Source Location</div>
                <div className="font-semibold text-slate-800 dark:text-slate-200">
                  {transfer.source_ward_name || `Ward #${transfer.source_ward_id}`}
                </div>
                <div className="text-slate-500 text-[11px]">
                  Bed: {transfer.source_bed_number || `Bed #${transfer.source_bed_id}`}
                </div>
              </div>

              <div className="space-y-1">
                <div className="text-[10px] font-bold text-sky-600 uppercase">Destination Location</div>
                <div className="font-semibold text-sky-900 dark:text-sky-300">
                  {transfer.destination_ward_name || `Ward #${transfer.destination_ward_id}`}
                </div>
                <div className="text-sky-700 dark:text-sky-400 text-[11px]">
                  Bed: {transfer.destination_bed_number || `Bed #${transfer.destination_bed_id}`}
                </div>
              </div>
            </div>

            {transfer.reason && (
              <div className="pt-2 text-xs text-slate-600 dark:text-slate-300 italic border-t border-slate-200 dark:border-slate-700/60">
                Reason: "{transfer.reason}"
              </div>
            )}
            {transfer.rejection_reason && (
              <div className="pt-2 text-xs text-rose-700 dark:text-rose-400 italic border-t border-slate-200 dark:border-slate-700/60">
                Rejection Reason: "{transfer.rejection_reason}"
              </div>
            )}
          </div>

          {/* Action Form Inputs depending on action type */}
          {actionType === 'APPROVE' && (
            <div className="space-y-3 p-4 bg-sky-50/60 dark:bg-sky-950/30 rounded-xl border border-sky-200 dark:border-sky-900">
              <label className="block text-xs font-semibold text-sky-900 dark:text-sky-200">
                Approval Notes (Optional)
              </label>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional approval notes..."
                className="w-full px-3 py-2 rounded-lg border border-sky-300 dark:border-sky-800 bg-white dark:bg-slate-900 text-xs"
              ></textarea>
              <button
                onClick={handleApprove}
                disabled={loading}
                className="w-full py-2.5 text-xs font-bold text-white bg-sky-600 hover:bg-sky-700 rounded-lg shadow-xs transition-colors"
              >
                {loading ? 'Approving...' : 'Confirm Approval'}
              </button>
            </div>
          )}

          {actionType === 'REJECT' && (
            <div className="space-y-3 p-4 bg-rose-50/60 dark:bg-rose-950/30 rounded-xl border border-rose-200 dark:border-rose-900">
              <label className="block text-xs font-semibold text-rose-900 dark:text-rose-200">
                Rejection Reason (Required) *
              </label>
              <textarea
                rows={2}
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Reason for rejecting this transfer..."
                className="w-full px-3 py-2 rounded-lg border border-rose-300 dark:border-rose-800 bg-white dark:bg-slate-900 text-xs"
              ></textarea>
              <button
                onClick={handleReject}
                disabled={loading || !rejectionReason.trim()}
                className="w-full py-2.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-xs transition-colors disabled:opacity-50"
              >
                {loading ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          )}

          {actionType === 'COMPLETE' && (
            <div className="space-y-3 p-4 bg-emerald-50/60 dark:bg-emerald-950/30 rounded-xl border border-emerald-200 dark:border-emerald-900 text-xs">
              <div className="font-bold text-emerald-900 dark:text-emerald-200">
                Execute Bed Relocation & Complete Transfer
              </div>
              <p className="text-emerald-800 dark:text-emerald-300 text-[11px] leading-relaxed">
                This will automatically set source bed <strong>{transfer.source_bed_number}</strong> to <strong>AVAILABLE</strong>, destination bed <strong>{transfer.destination_bed_number}</strong> to <strong>OCCUPIED</strong>, and update the patient's active admission record.
              </p>
              <button
                onClick={handleComplete}
                disabled={loading}
                className="w-full py-2.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs transition-colors"
              >
                {loading ? 'Executing Relocation...' : 'Execute Complete Transfer'}
              </button>
            </div>
          )}

          {actionType === 'CANCEL' && (
            <div className="space-y-3 p-4 bg-slate-100 dark:bg-slate-800 rounded-xl border border-slate-300 dark:border-slate-700 text-xs">
              <div className="font-bold text-slate-800 dark:text-slate-200">
                Cancel Transfer Request
              </div>
              <p className="text-slate-600 dark:text-slate-400 text-[11px]">
                Are you sure you want to cancel this transfer request?
              </p>
              <button
                onClick={handleCancel}
                disabled={loading}
                className="w-full py-2.5 text-xs font-bold text-slate-700 dark:text-slate-200 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 rounded-lg transition-colors"
              >
                {loading ? 'Cancelling...' : 'Confirm Cancel Request'}
              </button>
            </div>
          )}

          {/* Initial Action Buttons when actionType === 'VIEW' */}
          {actionType === 'VIEW' && (
            <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              {transfer.status === 'REQUESTED' && canApproveOrReject && (
                <>
                  <button
                    onClick={() => setActionType('REJECT')}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-rose-700 dark:text-rose-300 bg-rose-50 hover:bg-rose-100 dark:bg-rose-950 dark:hover:bg-rose-900 border border-rose-200 dark:border-rose-800 rounded-xl transition-colors"
                  >
                    <XCircle className="w-4 h-4" />
                    Reject
                  </button>
                  <button
                    onClick={() => setActionType('APPROVE')}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-xl shadow-xs transition-colors"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Approve
                  </button>
                </>
              )}

              {(transfer.status === 'APPROVED' || transfer.status === 'REQUESTED') && canCompleteOrCancel && (
                <button
                  onClick={() => setActionType('COMPLETE')}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs transition-colors"
                >
                  <CheckSquare className="w-4 h-4" />
                  Complete Transfer
                </button>
              )}

              {(transfer.status === 'REQUESTED' || transfer.status === 'APPROVED') && canCompleteOrCancel && (
                <button
                  onClick={() => setActionType('CANCEL')}
                  className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900"
                >
                  <Ban className="w-4 h-4" />
                  Cancel
                </button>
              )}
            </div>
          )}

          {actionType !== 'VIEW' && (
            <button
              onClick={() => setActionType('VIEW')}
              className="text-xs text-slate-500 hover:underline block text-center mx-auto"
            >
              Back to overview
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
