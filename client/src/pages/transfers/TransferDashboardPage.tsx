import React, { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw,
  Plus,
  Settings,
  Info,
  CheckCircle2,
  History,
  X,
  ArrowRightLeft,
  Building2,
  Clock,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import {
  PatientTransfer,
  TransferRecommendation,
  TransferOverviewStats,
  AuditLog,
  WardCapacity,
} from '../../types';
import { transferService } from '../../services/transferService';
import { getWardsOccupancy } from '../../services/occupancyService';
import { TransferRecommendationCard } from '../../components/transfers/TransferRecommendationCard';
import { TransferRecommendationDetailModal } from '../../components/transfers/TransferRecommendationDetailModal';
import { TransferRulesModal } from '../../components/transfers/TransferRulesModal';
import { NewTransferModal } from '../../components/transfers/NewTransferModal';
import { TransferActionModal } from '../../components/transfers/TransferActionModal';
import { cn } from '../../utils/cn';

export const TransferDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const hospitalId = user?.hospital_id || 1;

  // Active Tab: 'PATIENT_TRANSFERS' | 'HISTORY' | 'RECOMMENDATIONS'
  const [activeTab, setActiveTab] = useState<'PATIENT_TRANSFERS' | 'HISTORY' | 'RECOMMENDATIONS'>('PATIENT_TRANSFERS');

  // State
  const [patientTransfers, setPatientTransfers] = useState<PatientTransfer[]>([]);
  const [wardOccupancies, setWardOccupancies] = useState<WardCapacity[]>([]);
  const [recommendations, setRecommendations] = useState<TransferRecommendation[]>([]);
  const [stats, setStats] = useState<TransferOverviewStats | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [transferStatusFilter, setTransferStatusFilter] = useState<string>('ALL');

  // Modals
  const [showNewTransferModal, setShowNewTransferModal] = useState<boolean>(false);
  const [selectedTransfer, setSelectedTransfer] = useState<PatientTransfer | null>(null);
  const [selectedRecId, setSelectedRecId] = useState<number | null>(null);
  const [showRulesModal, setShowRulesModal] = useState<boolean>(false);
  const [showAuditDrawer, setShowAuditDrawer] = useState<boolean>(false);

  const fetchData = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [transfersRes, wardsRes, recsData, statsData] = await Promise.all([
        transferService.getPatientTransfers({ hospital_id: hospitalId, limit: 100 }),
        getWardsOccupancy(hospitalId),
        transferService.getRecommendations({ hospital_id: hospitalId }),
        transferService.getOverviewStats(hospitalId),
      ]);


      setPatientTransfers(transfersRes.items || []);
      setWardOccupancies(wardsRes || []);
      setRecommendations(recsData || []);
      setStats(statsData || null);
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } } };
      setError(errorObj.response?.data?.detail || 'Failed to fetch transfer dashboard data.');
    } finally {
      setLoading(false);
    }
  }, [hospitalId]);

  const fetchAuditLogs = async () => {
    try {
      const logs = await transferService.getAuditLogs(hospitalId);
      setAuditLogs(logs);
    } catch {
      // silent handle
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      fetchData();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleGenerateRecommendations = async () => {
    setGenerating(true);
    setError(null);
    try {
      await transferService.generateRecommendations(hospitalId, 1);
      await fetchData();
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } } };
      setError(errorObj.response?.data?.detail || 'Failed to generate recommendations.');
    } finally {
      setGenerating(false);
    }
  };

  const isAdmin = ['super_admin', 'admin'].includes(user?.role || '');

  // Transfer Counts
  const requestedCount = patientTransfers.filter((t) => t.status === 'REQUESTED').length;
  const approvedCount = patientTransfers.filter((t) => t.status === 'APPROVED').length;
  const completedCount = patientTransfers.filter((t) => t.status === 'COMPLETED').length;
  const rejectedCount = patientTransfers.filter((t) => t.status === 'REJECTED').length;

  // Filtered lists
  const activePatientTransfers = patientTransfers.filter((t) =>
    ['REQUESTED', 'APPROVED'].includes(t.status)
  );

  const historyPatientTransfers = patientTransfers.filter((t) =>
    ['COMPLETED', 'REJECTED', 'CANCELLED'].includes(t.status)
  );

  const displayedTransfers =
    activeTab === 'PATIENT_TRANSFERS'
      ? activePatientTransfers
      : activeTab === 'HISTORY'
      ? historyPatientTransfers
      : [];

  const filteredTransfers = displayedTransfers.filter((t) =>
    transferStatusFilter === 'ALL' ? true : t.status === transferStatusFilter
  );

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <ArrowRightLeft className="w-6 h-6 text-sky-600" />
              Inter-Ward Transfer Management
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
              Phase 7 Active
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Request, approve, reject, and execute patient bed transfers with real-time ward capacity tracking.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => {
              setShowAuditDrawer(true);
              fetchAuditLogs();
            }}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 shadow-xs transition-colors"
          >
            <History className="w-4 h-4" />
            Audit Logs
          </button>

          <button
            onClick={() => setShowRulesModal(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 shadow-xs transition-colors"
          >
            <Settings className="w-4 h-4 text-sky-600" />
            Rules {isAdmin ? '(Admin)' : ''}
          </button>

          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800 shadow-xs transition-colors"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
            Refresh
          </button>

          <button
            onClick={() => setShowNewTransferModal(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 dark:bg-sky-500 dark:hover:bg-sky-600 rounded-xl shadow-xs transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Transfer Request
          </button>
        </div>
      </div>

      {/* Notice Bar */}
      <div className="p-3.5 rounded-xl bg-sky-50/80 dark:bg-sky-950/40 border border-sky-200/80 dark:border-sky-900/40 flex items-start gap-3 text-xs text-sky-900 dark:text-sky-200">
        <Info className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <strong className="font-semibold">Inter-Ward Transfer Workflow:</strong>
          <p className="text-sky-800 dark:text-sky-300 leading-relaxed">
            Transfers must be requested by medical staff, approved by an authorized doctor or administrator, and completed to execute the bed status updates in PostgreSQL. Destination bed availability is verified at each step.
          </p>
        </div>
      </div>

      {/* Pressure Alert from stats */}
      {stats && (stats.critical_pressure_wards > 0 || stats.high_pressure_wards > 0) && (
        <div className="px-4 py-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 flex items-center justify-between text-xs text-amber-900 dark:text-amber-200">
          <span className="font-medium">
            Active ward capacity pressure detected: <strong>{stats.critical_pressure_wards}</strong> critical, <strong>{stats.high_pressure_wards}</strong> high pressure wards ({stats.active_recommendations} recommendations active).
          </span>
        </div>
      )}

      {/* Overview Metric Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs space-y-1">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total Requests</div>
          <div className="text-2xl font-extrabold text-slate-900 dark:text-slate-100">{patientTransfers.length}</div>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-amber-200 dark:border-amber-900/60 shadow-xs space-y-1">
          <div className="text-[11px] font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider">Requested</div>
          <div className="text-2xl font-extrabold text-amber-900 dark:text-amber-100">{requestedCount}</div>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-sky-200 dark:border-sky-900/60 shadow-xs space-y-1">
          <div className="text-[11px] font-bold text-sky-600 dark:text-sky-400 uppercase tracking-wider">Approved</div>
          <div className="text-2xl font-extrabold text-sky-900 dark:text-sky-100">{approvedCount}</div>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-emerald-200 dark:border-emerald-900/60 shadow-xs space-y-1">
          <div className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">Completed</div>
          <div className="text-2xl font-extrabold text-emerald-900 dark:text-emerald-100">{completedCount}</div>
        </div>

        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-rose-200 dark:border-rose-900/60 shadow-xs space-y-1">
          <div className="text-[11px] font-bold text-rose-600 dark:text-rose-400 uppercase tracking-wider">Rejected</div>
          <div className="text-2xl font-extrabold text-rose-900 dark:text-rose-100">{rejectedCount}</div>
        </div>
      </div>

      {/* Real-time Ward Capacity Quick Bar */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-sky-600" />
            <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Ward Capacity & Bed Headroom Overview
            </h3>
          </div>
          <span className="text-[11px] text-slate-400 font-medium">Real-time Phase 6 Calculation</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {wardOccupancies.map((w) => (
            <div
              key={w.ward_id}
              className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs"
            >
              <div className="space-y-0.5">
                <div className="font-bold text-slate-900 dark:text-slate-100">{w.ward_name}</div>
                <div className="text-slate-500 text-[11px]">
                  Beds: {w.occupied_beds}/{w.total_beds} ({w.available_beds} Available)
                </div>
              </div>
              <div className="text-right">
                <div
                  className={`font-extrabold text-sm ${
                    w.occupancy_percentage >= 85
                      ? 'text-rose-600'
                      : w.occupancy_percentage >= 70
                      ? 'text-amber-600'
                      : 'text-emerald-600'
                  }`}
                >
                  {(w.occupancy_percentage || 0).toFixed(1)}%
                </div>

                <span className="text-[10px] text-slate-400">Occupancy</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs Control */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
        <div className="flex items-center gap-4 text-xs font-bold">
          <button
            onClick={() => {
              setActiveTab('PATIENT_TRANSFERS');
              setTransferStatusFilter('ALL');
            }}
            className={cn(
              'pb-2 transition-colors relative',
              activeTab === 'PATIENT_TRANSFERS'
                ? 'text-sky-600 dark:text-sky-400 border-b-2 border-sky-600'
                : 'text-slate-500 hover:text-slate-900 dark:text-slate-400'
            )}
          >
            Active Transfers ({activePatientTransfers.length})
          </button>

          <button
            onClick={() => {
              setActiveTab('HISTORY');
              setTransferStatusFilter('ALL');
            }}
            className={cn(
              'pb-2 transition-colors relative',
              activeTab === 'HISTORY'
                ? 'text-sky-600 dark:text-sky-400 border-b-2 border-sky-600'
                : 'text-slate-500 hover:text-slate-900 dark:text-slate-400'
            )}
          >
            Transfer History ({historyPatientTransfers.length})
          </button>

          <button
            onClick={() => setActiveTab('RECOMMENDATIONS')}
            className={cn(
              'pb-2 transition-colors relative',
              activeTab === 'RECOMMENDATIONS'
                ? 'text-sky-600 dark:text-sky-400 border-b-2 border-sky-600'
                : 'text-slate-500 hover:text-slate-900 dark:text-slate-400'
            )}
          >
            Capacity Decision Support ({recommendations.length})
          </button>
        </div>

        {activeTab !== 'RECOMMENDATIONS' && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 font-medium">Status Filter:</span>
            <select
              value={transferStatusFilter}
              onChange={(e) => setTransferStatusFilter(e.target.value)}
              className="px-2.5 py-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium"
            >
              <option value="ALL">All Statuses</option>
              {activeTab === 'PATIENT_TRANSFERS' && (
                <>
                  <option value="REQUESTED">REQUESTED</option>
                  <option value="APPROVED">APPROVED</option>
                </>
              )}
              {activeTab === 'HISTORY' && (
                <>
                  <option value="COMPLETED">COMPLETED</option>
                  <option value="REJECTED">REJECTED</option>
                  <option value="CANCELLED">CANCELLED</option>
                </>
              )}
            </select>
          </div>
        )}
      </div>

      {/* Main Content Render */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-300 text-xs">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-44 bg-slate-100 dark:bg-slate-800/50 rounded-2xl animate-pulse"></div>
          ))}
        </div>
      ) : activeTab === 'RECOMMENDATIONS' ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Stage 4 Automated Ward Capacity Recommendations
            </h3>
            <button
              onClick={handleGenerateRecommendations}
              disabled={generating}
              className="px-3 py-1.5 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg shadow-xs transition-colors disabled:opacity-50"
            >
              {generating ? 'Analyzing...' : 'Run Decision Engine'}
            </button>
          </div>
          {recommendations.length === 0 ? (
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-8 text-center text-xs text-slate-500">
              No active ward capacity recommendations at present.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {recommendations.map((rec) => (
                <TransferRecommendationCard
                  key={rec.id}
                  recommendation={rec}
                  onSelect={(r) => setSelectedRecId(r.id)}
                />
              ))}
            </div>
          )}
        </div>
      ) : filteredTransfers.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            No {activeTab === 'PATIENT_TRANSFERS' ? 'Active' : 'Historical'} Patient Transfer Records
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {activeTab === 'PATIENT_TRANSFERS'
              ? 'There are currently no active patient transfer requests pending approval or completion.'
              : 'No completed, rejected, or cancelled transfer records match the selected filter.'}
          </p>
          {activeTab === 'PATIENT_TRANSFERS' && (
            <button
              onClick={() => setShowNewTransferModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-xl shadow-xs transition-colors"
            >
              <Plus className="w-4 h-4" />
              Create First Transfer Request
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredTransfers.map((t) => (
            <div
              key={t.id}
              className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs space-y-4 hover:border-sky-300 dark:hover:border-sky-800 transition-all"
            >
              {/* Transfer Card Header */}
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                <div>
                  <div className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                    Patient: {t.patient_name || `ID #${t.patient_id}`}
                    <span className="text-[11px] font-normal text-slate-400">
                      ({t.patient_identifier})
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    Requested {new Date(t.requested_at).toLocaleString()}
                  </div>
                </div>

                <span
                  className={`px-2.5 py-1 text-[11px] font-bold rounded-full border ${
                    t.status === 'REQUESTED'
                      ? 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900'
                      : t.status === 'APPROVED'
                      ? 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-900'
                      : t.status === 'COMPLETED'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900'
                      : 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900'
                  }`}
                >
                  {t.status}
                </span>
              </div>

              {/* Source & Destination Location Flow */}
              <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl text-xs">
                <div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase">From Source</div>
                  <div className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5">
                    {t.source_ward_name || `Ward #${t.source_ward_id}`}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Bed: {t.source_bed_number || `#${t.source_bed_id}`}
                  </div>
                </div>

                <div>
                  <div className="text-[10px] font-bold text-sky-600 uppercase">To Destination</div>
                  <div className="font-semibold text-sky-900 dark:text-sky-300 mt-0.5">
                    {t.destination_ward_name || `Ward #${t.destination_ward_id}`}
                  </div>
                  <div className="text-[11px] text-sky-700 dark:text-sky-400">
                    Bed: {t.destination_bed_number || `#${t.destination_bed_id}`}
                  </div>
                </div>
              </div>

              {t.reason && (
                <p className="text-xs text-slate-600 dark:text-slate-300 italic">
                  "{t.reason}"
                </p>
              )}

              {/* Footer Details & Action Button */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400">
                <div>
                  By: <strong>{t.requested_by_name || `User #${t.requested_by}`}</strong>
                </div>

                <button
                  onClick={() => setSelectedTransfer(t)}
                  className="px-3.5 py-1.5 text-xs font-semibold text-sky-600 hover:text-sky-700 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/50 hover:bg-sky-100 rounded-lg transition-colors"
                >
                  Manage / Details &rarr;
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      {showNewTransferModal && (
        <NewTransferModal
          hospitalId={hospitalId}
          onClose={() => setShowNewTransferModal(false)}
          onSuccess={fetchData}
        />
      )}

      {selectedTransfer && (
        <TransferActionModal
          transfer={selectedTransfer}
          userRole={user?.role}
          onClose={() => setSelectedTransfer(null)}
          onSuccess={fetchData}
        />
      )}

      {selectedRecId && (
        <TransferRecommendationDetailModal
          recommendationId={selectedRecId}
          userRole={user?.role}
          onClose={() => setSelectedRecId(null)}
          onSuccess={fetchData}
        />
      )}

      {showRulesModal && (
        <TransferRulesModal
          hospitalId={hospitalId}
          userRole={user?.role}
          onClose={() => setShowRulesModal(false)}
        />
      )}

      {/* Audit Logs Drawer */}
      {showAuditDrawer && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/60 backdrop-blur-xs flex justify-end">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 h-full shadow-2xl flex flex-col border-l border-slate-200 dark:border-slate-800">
            <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-sky-600" />
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Transfer System Audit Logs
                </h3>
              </div>
              <button
                onClick={() => setShowAuditDrawer(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 flex-1 overflow-y-auto space-y-3">
              {auditLogs.length === 0 ? (
                <div className="text-center py-8 text-xs text-slate-500">No audit logs recorded yet.</div>
              ) : (
                auditLogs.map((log) => (
                  <div
                    key={log.id}
                    className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between font-bold text-slate-900 dark:text-slate-100">
                      <span className="text-sky-600 dark:text-sky-400">{log.action}</span>
                      <span className="text-[10px] text-slate-400 font-normal">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="text-slate-600 dark:text-slate-400 text-[11px]">
                      User: <strong>{log.user_name || log.user_email || `ID ${log.user_id}`}</strong>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
