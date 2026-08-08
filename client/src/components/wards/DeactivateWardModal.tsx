import React from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';

interface DeactivateWardModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  wardName: string;
  isDeactivating: boolean;
}

export const DeactivateWardModal: React.FC<DeactivateWardModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  wardName,
  isDeactivating,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl w-full max-w-md p-6 overflow-hidden">
        <div className="flex items-start gap-4">
          <div className="w-11 h-11 rounded-xl bg-amber-100 dark:bg-amber-950/80 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0 border border-amber-200 dark:border-amber-900">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">
              Deactivate Ward?
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
              Are you sure you want to deactivate <span className="font-semibold text-slate-800 dark:text-slate-200">{wardName}</span>?
            </p>
            <p className="text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 p-2.5 rounded-lg border border-amber-200 dark:border-amber-900/50 mt-3">
              This ward status will be changed to <strong>INACTIVE</strong>. Existing relationships will be preserved and historical records will remain intact.
            </p>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeactivating}
            className="px-4 py-2 text-sm font-semibold text-slate-600 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 rounded-xl transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeactivating}
            className="px-4 py-2 text-sm font-semibold text-white bg-amber-600 hover:bg-amber-500 rounded-xl shadow-md shadow-amber-600/20 flex items-center gap-2 transition-all disabled:opacity-50"
          >
            {isDeactivating && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>Deactivate Ward</span>
          </button>
        </div>
      </div>
    </div>
  );
};
