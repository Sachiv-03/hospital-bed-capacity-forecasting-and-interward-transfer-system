import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, ShieldCheck, Check, Ban, AlertCircle } from 'lucide-react';
import { WardTransferRule, UserRole, WardType } from '../../types';
import { transferService } from '../../services/transferService';
import { cn } from '../../utils/cn';

interface TransferRulesModalProps {
  hospitalId?: number;
  userRole?: UserRole;
  onClose: () => void;
}

const WARD_TYPES: WardType[] = [
  'GENERAL',
  'ICU',
  'STEP_DOWN',
  'EMERGENCY',
  'PEDIATRIC',
  'MATERNITY',
  'SURGICAL',
  'ISOLATION',
  'OTHER',
];

export const TransferRulesModal: React.FC<TransferRulesModalProps> = ({
  hospitalId,
  userRole,
  onClose,
}) => {
  const [rules, setRules] = useState<WardTransferRule[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // New Rule Form
  const [showAddForm, setShowAddForm] = useState<boolean>(false);
  const [sourceType, setSourceType] = useState<WardType>('ICU');
  const [destinationType, setDestinationType] = useState<WardType>('STEP_DOWN');
  const [allowed, setAllowed] = useState<boolean>(true);
  const [priority, setPriority] = useState<number>(2);
  const [maxOccupancy, setMaxOccupancy] = useState<number>(85);
  const [minBeds, setMinBeds] = useState<number>(2);
  const [reason, setReason] = useState<string>('');

  const isAdmin = ['super_admin', 'admin'].includes(userRole || '');

  useEffect(() => {
    fetchRules();
  }, [hospitalId]);

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await transferService.getRules(hospitalId);
      setRules(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch transfer rules.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    try {
      await transferService.createRule({
        hospital_id: hospitalId,
        source_ward_type: sourceType,
        destination_ward_type: destinationType,
        allowed,
        priority,
        maximum_destination_occupancy: maxOccupancy,
        minimum_available_beds: minBeds,
        reason,
        active: true,
      });
      setShowAddForm(false);
      setReason('');
      fetchRules();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create rule.');
    }
  };

  const handleToggleRuleActive = async (rule: WardTransferRule) => {
    if (!isAdmin) return;
    try {
      await transferService.updateRule(rule.id, { active: !rule.active });
      fetchRules();
    } catch (err: any) {
      setError('Failed to update rule status.');
    }
  };

  const handleDeleteRule = async (id: number) => {
    if (!isAdmin) return;
    if (!window.confirm('Are you sure you want to delete this compatibility rule?')) return;
    try {
      await transferService.deleteRule(id);
      fetchRules();
    } catch (err: any) {
      setError('Failed to delete rule.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="relative w-full max-w-3xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-sky-600 dark:text-sky-400" />
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Hospital Inter-Ward Transfer Rules Configuration
              </h2>
              <p className="text-xs text-slate-500">
                Configurable operational compatibility matrices and safety thresholds.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {error && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Active Compatibility Rules ({rules.length})
            </span>
            {isAdmin && !showAddForm && (
              <button
                onClick={() => setShowAddForm(true)}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg shadow-xs transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Transfer Rule
              </button>
            )}
          </div>

          {/* New Rule Form */}
          {showAddForm && (
            <form onSubmit={handleCreateRule} className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 space-y-3">
              <div className="text-xs font-bold text-slate-900 dark:text-slate-100 mb-2">
                Create New Ward Transfer Rule
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block text-slate-700 dark:text-slate-300 mb-1 font-medium">
                    Source Ward Type:
                  </label>
                  <select
                    value={sourceType}
                    onChange={(e) => setSourceType(e.target.value as WardType)}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
                  >
                    {WARD_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 dark:text-slate-300 mb-1 font-medium">
                    Destination Ward Type:
                  </label>
                  <select
                    value={destinationType}
                    onChange={(e) => setDestinationType(e.target.value as WardType)}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
                  >
                    {WARD_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 dark:text-slate-300 mb-1 font-medium">
                    Transfer Allowed?
                  </label>
                  <select
                    value={allowed ? 'true' : 'false'}
                    onChange={(e) => setAllowed(e.target.value === 'true')}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
                  >
                    <option value="true">Allowed (TRUE)</option>
                    <option value="false">Forbidden (FALSE)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 dark:text-slate-300 mb-1 font-medium">
                    Max Safe Destination Occ (%):
                  </label>
                  <input
                    type="number"
                    value={maxOccupancy}
                    onChange={(e) => setMaxOccupancy(Number(e.target.value))}
                    min={50}
                    max={100}
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-700 dark:text-slate-300 mb-1 font-medium text-xs">
                  Operational Rationale / Reason:
                </label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Allowed when patient meets step-down criteria."
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
                />
              </div>

              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-3 py-1 text-xs text-slate-600 hover:bg-slate-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg"
                >
                  Save Rule
                </button>
              </div>
            </form>
          )}

          {/* Rules List */}
          {loading ? (
            <div className="text-center py-8 text-xs text-slate-500">Loading rules...</div>
          ) : rules.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500">No transfer rules configured.</div>
          ) : (
            <div className="space-y-2">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className={cn(
                    'p-3.5 rounded-xl border flex items-center justify-between gap-3 text-xs transition-colors',
                    rule.allowed
                      ? 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800'
                      : 'bg-rose-50/50 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/40'
                  )}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-slate-100">
                      <span>{rule.source_ward_type || rule.source_ward_id || 'ALL'}</span>
                      <span className="text-slate-400">→</span>
                      <span>{rule.destination_ward_type || rule.destination_ward_id || 'ALL'}</span>

                      <span
                        className={cn(
                          'px-2 py-0.5 text-[10px] rounded-md font-semibold border ml-2',
                          rule.allowed
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800'
                            : 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-800'
                        )}
                      >
                        {rule.allowed ? 'ALLOWED' : 'FORBIDDEN'}
                      </span>
                    </div>

                    <p className="text-slate-600 dark:text-slate-400 text-[11px]">
                      {rule.reason || 'No description'}
                    </p>

                    <div className="text-[10px] text-slate-400 flex items-center gap-3">
                      <span>Max Dest Occupancy: <strong>{rule.maximum_destination_occupancy}%</strong></span>
                      <span>Min Available Beds Buffer: <strong>{rule.minimum_available_beds} beds</strong></span>
                    </div>
                  </div>

                  {isAdmin && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleToggleRuleActive(rule)}
                        className={cn(
                          'px-2.5 py-1 text-[11px] rounded-lg border font-medium',
                          rule.active
                            ? 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
                            : 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300'
                        )}
                      >
                        {rule.active ? 'Active' : 'Inactive'}
                      </button>

                      <button
                        onClick={() => handleDeleteRule(rule.id)}
                        className="p-1 text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100 dark:border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
