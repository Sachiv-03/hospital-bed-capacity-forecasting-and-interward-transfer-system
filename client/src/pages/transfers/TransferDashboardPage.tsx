import React, { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw,
  SlidersHorizontal,
  Plus,
  Settings,
  Info,
  CheckCircle2,
  History,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import {
  TransferRecommendation,
  TransferOverviewStats,
  AuditLog,
} from '../../types';
import { transferService } from '../../services/transferService';
import { TransferRecommendationCard } from '../../components/transfers/TransferRecommendationCard';
import { TransferRecommendationDetailModal } from '../../components/transfers/TransferRecommendationDetailModal';
import { TransferRulesModal } from '../../components/transfers/TransferRulesModal';
import { cn } from '../../utils/cn';

export const TransferDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const hospitalId = user?.hospital_id || 1;

  const [recommendations, setRecommendations] = useState<TransferRecommendation[]>([]);
  const [stats, setStats] = useState<TransferOverviewStats | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('PENDING');

  // Modals
  const [selectedRecId, setSelectedRecId] = useState<number | null>(null);
  const [showRulesModal, setShowRulesModal] = useState<boolean>(false);
  const [showAuditDrawer, setShowAuditDrawer] = useState<boolean>(false);

  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const [recsData, statsData] = await Promise.all([
        transferService.getRecommendations({
          hospital_id: hospitalId,
          priority: priorityFilter !== 'ALL' ? priorityFilter : undefined,
          status: statusFilter !== 'ALL' ? statusFilter : undefined,
        }),
        transferService.getOverviewStats(hospitalId),
      ]);
      setRecommendations(recsData);
      setStats(statsData);
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } } };
      setError(errorObj.response?.data?.detail || 'Failed to fetch transfer decision support data.');
    } finally {
      setLoading(false);
    }
  }, [hospitalId, priorityFilter, statusFilter]);

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
    // Real-time polling every 30 seconds (Part 35)
    const interval = setInterval(() => {
      fetchData();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleGenerate = async () => {
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

  return (
    <div className="space-y-6 pb-12">
      {/* Page Title Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              Inter-Ward Transfer Decision Support System
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
              Stage 4 Decision Support
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Intelligent capacity relief routing, safe bed capacity calculation, and explainable recommendations.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => {
              setShowAuditDrawer(true);
              fetchAuditLogs();
            }}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 shadow-xs transition-colors"
          >
            <History className="w-4 h-4" />
            Audit Logs
          </button>

          <button
            onClick={() => setShowRulesModal(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 shadow-xs transition-colors"
          >
            <Settings className="w-4 h-4 text-sky-600" />
            Transfer Rules {isAdmin ? '(Admin)' : ''}
          </button>

          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 shadow-xs transition-colors"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
            Refresh
          </button>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 dark:bg-sky-500 dark:hover:bg-sky-600 rounded-lg shadow-xs transition-colors disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            {generating ? 'Analyzing Capacity...' : 'Generate Recommendations'}
          </button>
        </div>
      </div>

      {/* Safety Notice Disclaimer */}
      <div className="p-3.5 rounded-xl bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200/80 dark:border-blue-900/40 flex items-start gap-3 text-xs text-blue-900 dark:text-blue-200">
        <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <strong className="font-semibold">Decision Support Policy:</strong>
          <p className="text-blue-800 dark:text-blue-300 leading-relaxed">
            This system provides capacity recommendations only. It does NOT automatically transfer patients, alter patient locations, or perform clinical decisions. All final transfer decisions must be confirmed by authorized hospital staff.
          </p>
        </div>
      </div>

      {/* Overview Statistics Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-rose-200/80 dark:border-rose-900/60 shadow-xs space-y-1">
            <div className="text-xs font-semibold text-rose-700 dark:text-rose-400 uppercase tracking-wider">
              Critical Pressure Wards
            </div>
            <div className="text-2xl font-extrabold text-rose-900 dark:text-rose-100">
              {stats.critical_pressure_wards}
            </div>
            <div className="text-[11px] text-slate-500">Require immediate capacity relief</div>
          </div>

          <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-amber-200/80 dark:border-amber-900/60 shadow-xs space-y-1">
            <div className="text-xs font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wider">
              High Pressure Wards
            </div>
            <div className="text-2xl font-extrabold text-amber-900 dark:text-amber-100">
              {stats.high_pressure_wards}
            </div>
            <div className="text-[11px] text-slate-500">Occupancy &gt; 85% or high forecast</div>
          </div>

          <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-emerald-200/80 dark:border-emerald-900/60 shadow-xs space-y-1">
            <div className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider">
              Available Destinations
            </div>
            <div className="text-2xl font-extrabold text-emerald-900 dark:text-emerald-100">
              {stats.total_potential_destinations}
            </div>
            <div className="text-[11px] text-slate-500">Wards with safe capacity headroom</div>
          </div>

          <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-sky-200/80 dark:border-sky-900/60 shadow-xs space-y-1">
            <div className="text-xs font-semibold text-sky-700 dark:text-sky-400 uppercase tracking-wider">
              Pending Review
            </div>
            <div className="text-2xl font-extrabold text-sky-900 dark:text-sky-100">
              {stats.pending_recommendations}
            </div>
            <div className="text-[11px] text-slate-500">Awaiting staff authorization</div>
          </div>
        </div>
      )}

      {/* Filter Controls Bar */}
      <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-4 shadow-xs">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
            Filter Recommendations:
          </span>
        </div>

        <div className="flex items-center gap-3 flex-wrap text-xs">
          {/* Status Tabs */}
          <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
            {['PENDING', 'APPROVED', 'REJECTED', 'ALL'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={cn(
                  'px-3 py-1 rounded-md font-semibold transition-all',
                  statusFilter === st
                    ? 'bg-white dark:bg-slate-700 text-sky-700 dark:text-sky-300 shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                )}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Priority Dropdown */}
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium"
          >
            <option value="ALL">All Priorities</option>
            <option value="CRITICAL">CRITICAL Priority</option>
            <option value="HIGH">HIGH Priority</option>
            <option value="MEDIUM">MEDIUM Priority</option>
            <option value="LOW">LOW Priority</option>
          </select>
        </div>
      </div>

      {/* Main Content Area */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 dark:bg-rose-950/40 dark:border-rose-900 dark:text-rose-300 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-56 bg-slate-100 dark:bg-slate-800/50 rounded-xl animate-pulse"></div>
          ))}
        </div>
      ) : recommendations.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
            No {statusFilter !== 'ALL' ? statusFilter : ''} Recommendations Found
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            Either no ward currently satisfies the transfer trigger threshold, or all generated recommendations have been processed. Click <strong>Generate Recommendations</strong> above to run an on-demand decision support analysis.
          </p>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg shadow-xs transition-colors"
          >
            <Plus className="w-4 h-4" />
            Generate On-Demand Recommendations
          </button>
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

      {/* Detail Explanation Modal */}
      {selectedRecId && (
        <TransferRecommendationDetailModal
          recommendationId={selectedRecId}
          userRole={user?.role}
          onClose={() => setSelectedRecId(null)}
          onSuccess={fetchData}
        />
      )}

      {/* Rules Config Modal */}
      {showRulesModal && (
        <TransferRulesModal
          hospitalId={hospitalId}
          userRole={user?.role}
          onClose={() => setShowRulesModal(false)}
        />
      )}

      {/* Audit Log Drawer */}
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
                    {log.metadata_json && Object.keys(log.metadata_json).length > 0 && (
                      <div className="text-[10px] text-slate-500 font-mono bg-slate-100 dark:bg-slate-800 p-1.5 rounded overflow-x-auto">
                        {JSON.stringify(log.metadata_json)}
                      </div>
                    )}
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
