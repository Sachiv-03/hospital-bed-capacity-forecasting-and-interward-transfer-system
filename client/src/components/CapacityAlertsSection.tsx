import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle2,
  ShieldAlert,
  BrainCircuit,
  RefreshCw,
  Play,
  TrendingUp,
  Calendar,
  ChevronDown,
  ChevronUp,
  ArrowRightLeft,
  Building2,
  Clock,
} from 'lucide-react';
import { CapacityAlert, CapacityAlertSummary } from '../types';
import {
  getCapacityAlerts,
  getCapacityAlertSummary,
  resolveCapacityAlert,
  acknowledgeCapacityAlert,
  evaluateCapacityAlerts,
} from '../services/ingestionService';
import { ExplainableAlertDetailModal } from './ExplainableAlertDetailModal';

interface Props {
  hospitalId?: number;
}

export const CapacityAlertsSection: React.FC<Props> = ({ hospitalId }) => {
  const [alerts, setAlerts] = useState<CapacityAlert[]>([]);
  const [summary, setSummary] = useState<CapacityAlertSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [statusFilter, setStatusFilter] = useState<string>('ACTIVE');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [alertTypeFilter, setAlertTypeFilter] = useState<string>('ALL');
  const [selectedAlertForModal, setSelectedAlertForModal] = useState<CapacityAlert | null>(null);
  const [expandedAlertIds, setExpandedAlertIds] = useState<Set<number>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const params: { hospital_id?: number; status?: string; severity?: string; alert_type?: string } = {
        hospital_id: hospitalId,
      };
      if (statusFilter !== 'ALL') {
        params.status = statusFilter;
      }
      if (severityFilter !== 'ALL') {
        params.severity = severityFilter;
      }
      if (alertTypeFilter !== 'ALL') {
        params.alert_type = alertTypeFilter;
      }
      const [alertRes, summaryRes] = await Promise.allSettled([
        getCapacityAlerts(params),
        getCapacityAlertSummary({ hospital_id: hospitalId }),
      ]);

      if (alertRes.status === 'fulfilled') {
        setAlerts(alertRes.value.items || []);
      }
      if (summaryRes.status === 'fulfilled') {
        setSummary(summaryRes.value);
      }
    } catch (err) {
      console.error('Failed to fetch capacity alerts:', err);
    } finally {
      setLoading(false);
    }
  }, [hospitalId, statusFilter, severityFilter, alertTypeFilter]);

  const handleResolve = async (alertId: number) => {
    setActionLoading(true);
    try {
      await resolveCapacityAlert(alertId);
      setToastMessage('Alert resolved successfully.');
      setTimeout(() => setToastMessage(null), 3000);
      if (selectedAlertForModal?.id === alertId) {
        setSelectedAlertForModal(null);
      }
      fetchAlerts();
    } catch (err: any) {
      console.error('Failed to resolve alert:', err);
      const detail = err.response?.data?.detail;
      const errorStr = typeof detail === 'string' ? detail : (err.message || 'Failed to resolve alert.');
      setToastMessage(`Error: ${errorStr}`);
      setTimeout(() => setToastMessage(null), 4000);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAcknowledge = async (alertId: number) => {
    setActionLoading(true);
    try {
      await acknowledgeCapacityAlert(alertId);
      setToastMessage('Alert acknowledged.');
      setTimeout(() => setToastMessage(null), 3000);
      if (selectedAlertForModal?.id === alertId) {
        setSelectedAlertForModal((prev) => (prev ? { ...prev, status: 'ACKNOWLEDGED' } : null));
      }
      fetchAlerts();
    } catch (err: any) {
      console.error('Failed to acknowledge alert:', err);
      const detail = err.response?.data?.detail;
      const errorStr = typeof detail === 'string' ? detail : (err.message || 'Failed to acknowledge alert.');
      setToastMessage(`Error: ${errorStr}`);
      setTimeout(() => setToastMessage(null), 4000);
    } finally {
      setActionLoading(false);
    }
  };

  const handleTriggerEvaluation = async () => {
    setEvaluating(true);
    try {
      const res = await evaluateCapacityAlerts({ hospital_id: hospitalId, horizon: 7 });
      setToastMessage(`Explainable risk evaluation complete (${res.wards_evaluated} wards evaluated, ${res.alerts_count} alert(s) updated).`);
      setTimeout(() => setToastMessage(null), 4000);
      fetchAlerts();
    } catch (err) {
      console.error('Evaluation trigger failed:', err);
    } finally {
      setEvaluating(false);
    }
  };

  const toggleExpand = (id: number) => {
    setExpandedAlertIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  useEffect(() => {
    fetchAlerts();
    const timer = setInterval(fetchAlerts, 30_000);
    return () => clearInterval(timer);
  }, [fetchAlerts]);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-5">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/80 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
                Explainable AI Capacity Alerts
              </h3>
              <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 flex items-center gap-1">
                <BrainCircuit className="w-3 h-3" />
                SARIMA Decision Support
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Deterministic rule-based risk evaluation using live occupancy and predictive forecasts.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleTriggerEvaluation}
            disabled={evaluating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-xl bg-purple-600 hover:bg-purple-500 text-white shadow-xs transition-colors disabled:opacity-50"
            title="Evaluate capacity risk across wards using latest forecasts"
          >
            <Play className={`w-3.5 h-3.5 fill-white ${evaluating ? 'animate-spin' : ''}`} />
            <span>{evaluating ? 'Evaluating...' : 'Run Risk Evaluation'}</span>
          </button>

          <button
            onClick={fetchAlerts}
            className="p-1.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors text-slate-600 dark:text-slate-300"
            title="Refresh alerts"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-sky-500' : ''}`} />
          </button>
        </div>
      </div>

      {/* KPI Summary Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Total Active</span>
            <ShieldAlert className="w-4 h-4 text-slate-500" />
          </div>
          <div className="text-2xl font-black text-slate-900 dark:text-white mt-1">
            {summary ? summary.total_active : alerts.filter((a) => a.status !== 'RESOLVED').length}
          </div>
          <span className="text-[10px] text-slate-400">Active capacity events</span>
        </div>

        <div className="p-3.5 rounded-xl bg-rose-50/70 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-rose-700 dark:text-rose-300">Critical & High</span>
            <AlertCircle className="w-4 h-4 text-rose-500" />
          </div>
          <div className="text-2xl font-black text-rose-600 dark:text-rose-400 mt-1">
            {summary
              ? summary.critical_count + summary.high_count
              : alerts.filter((a) => a.status !== 'RESOLVED' && (a.severity === 'CRITICAL' || a.severity === 'WARNING')).length}
          </div>
          <span className="text-[10px] text-rose-600/80 dark:text-rose-400/80">Immediate attention needed</span>
        </div>

        <div className="p-3.5 rounded-xl bg-amber-50/70 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700 dark:text-amber-300">Unacknowledged</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-black text-amber-600 dark:text-amber-400 mt-1">
            {summary ? summary.unacknowledged_count : alerts.filter((a) => a.status === 'ACTIVE').length}
          </div>
          <span className="text-[10px] text-amber-600/80 dark:text-amber-400/80">Pending clinical review</span>
        </div>

        <div className="p-3.5 rounded-xl bg-purple-50/70 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-900">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700 dark:text-purple-300">Data Quality</span>
            <BrainCircuit className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-black text-purple-600 dark:text-purple-400 mt-1">
            {summary
              ? summary.data_quality_count
              : alerts.filter((a) => a.status !== 'RESOLVED' && (a.alert_type === 'INSUFFICIENT_DATA' || a.alert_type === 'HIGH_UNCERTAINTY')).length}
          </div>
          <span className="text-[10px] text-purple-600/80 dark:text-purple-400/80">Stale/uncertain forecasts</span>
        </div>
      </div>

      {/* Filter Tabs & Selectors */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700">
          {(['ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'ALL'] as const).map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded-lg font-bold transition-all ${
                statusFilter === st
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs'
                  : 'text-slate-500 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Type:</span>
            <select
              value={alertTypeFilter}
              onChange={(e) => setAlertTypeFilter(e.target.value)}
              className="px-2.5 py-1 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg font-semibold text-slate-700 dark:text-slate-200"
            >
              <option value="ALL">All Categories</option>
              <option value="CRITICAL_OCCUPANCY">Critical Occupancy</option>
              <option value="HIGH_OCCUPANCY">High Occupancy</option>
              <option value="LOW_AVAILABILITY">Low Availability</option>
              <option value="FORECAST_CRITICAL_OCCUPANCY">Forecast Critical</option>
              <option value="FORECAST_HIGH_OCCUPANCY">Forecast High</option>
              <option value="CAPACITY_EXCEEDANCE">Capacity Exceedance</option>
              <option value="RAPID_INCREASE">Rapid Surge</option>
              <option value="HIGH_UNCERTAINTY">High Uncertainty</option>
              <option value="INSUFFICIENT_DATA">Data Quality Notice</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Severity:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-2.5 py-1 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg font-semibold text-slate-700 dark:text-slate-200"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical Only</option>
              <option value="WARNING">Warning</option>
              <option value="INFO">Info</option>
            </select>
          </div>
        </div>
      </div>

      {/* Alert List Container */}
      {loading ? (
        <p className="text-xs text-slate-400 py-6 text-center animate-pulse">Evaluating explainable capacity alerts...</p>
      ) : alerts.length === 0 ? (
        <div className="flex items-center gap-3 p-5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-800 dark:text-emerald-300">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-500" />
          <div>
            <p className="text-xs font-bold">All Wards Normal ({statusFilter} Filter)</p>
            <p className="text-xs opacity-90 mt-0.5">
              No alerts match the current filter criteria. Ward occupancy and forecasts remain within approved operational limits.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => {
            const isCritical = alert.severity === 'CRITICAL';
            const isAcknowledged = alert.status === 'ACKNOWLEDGED';
            const isResolved = alert.status === 'RESOLVED';
            const isExpanded = expandedAlertIds.has(alert.id);
            const expl = alert.explanation;
            const ev = expl?.evidence;

            return (
              <div
                key={alert.id}
                className={`rounded-xl border transition-all duration-200 overflow-hidden ${
                  isCritical
                    ? 'bg-rose-50/70 dark:bg-rose-950/30 border-rose-200 dark:border-rose-900'
                    : alert.severity === 'WARNING'
                    ? 'bg-amber-50/70 dark:bg-amber-950/30 border-amber-200 dark:border-amber-900'
                    : 'bg-slate-50 dark:bg-slate-900/60 border-slate-200 dark:border-slate-800'
                }`}
              >
                {/* Main Alert Card Summary */}
                <div className="p-4 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <AlertCircle
                      className={`w-5 h-5 shrink-0 mt-0.5 ${
                        isCritical
                          ? 'text-rose-500'
                          : alert.severity === 'WARNING'
                          ? 'text-amber-500'
                          : 'text-sky-500'
                      }`}
                    />
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Severity Badge */}
                        <span
                          className={`px-2 py-0.5 text-[10px] font-extrabold uppercase rounded-md tracking-wider ${
                            isCritical
                              ? 'bg-rose-600 text-white'
                              : alert.severity === 'WARNING'
                              ? 'bg-amber-600 text-white'
                              : 'bg-sky-600 text-white'
                          }`}
                        >
                          {alert.severity}
                        </span>

                        {/* Status Badge */}
                        <span
                          className={`px-2 py-0.5 text-[10px] font-bold rounded-md uppercase tracking-wider ${
                            isResolved
                              ? 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                              : isAcknowledged
                              ? 'bg-sky-100 dark:bg-sky-950 text-sky-800 dark:text-sky-300 border border-sky-300 dark:border-sky-800'
                              : 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800'
                          }`}
                        >
                          {alert.status}
                        </span>

                        <span className="text-xs font-bold text-slate-900 dark:text-white">
                          {alert.ward_name}
                        </span>
                        <span className="text-xs text-slate-400">
                          &bull; {alert.alert_type.replace(/_/g, ' ')}
                        </span>
                      </div>

                      {/* Headline / Message */}
                      <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                        {expl?.headline || alert.message}
                      </p>

                      {/* Evidence Chips */}
                      <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-slate-600 dark:text-slate-300">
                        <span className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                          Trigger: <strong className="text-slate-900 dark:text-white">{alert.trigger_value.toFixed(1)}</strong> (Threshold: {alert.threshold_value})
                        </span>

                        {ev?.predicted_occupancy_percentage != null && (
                          <span className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center gap-1">
                            <TrendingUp className="w-3 h-3 text-sky-500" />
                            Forecast Peak: <strong className="text-sky-600 dark:text-sky-400">{ev.predicted_occupancy_percentage.toFixed(1)}%</strong>
                          </span>
                        )}

                        {ev?.forecast_target_date && (
                          <span className="px-2 py-0.5 rounded bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center gap-1">
                            <Calendar className="w-3 h-3 text-purple-500" />
                            Target: <strong className="text-purple-600 dark:text-purple-400">{ev.forecast_target_date}</strong>
                          </span>
                        )}

                        {ev?.lower_bound_percentage != null && ev?.upper_bound_percentage != null && (
                          <span className="px-2 py-0.5 rounded bg-sky-50 dark:bg-sky-950/50 border border-sky-200 dark:border-sky-800 text-sky-800 dark:text-sky-300 text-[10px]">
                            95% CI: {ev.lower_bound_percentage.toFixed(1)}% - {ev.upper_bound_percentage.toFixed(1)}%
                          </span>
                        )}
                      </div>

                      {/* Phase 11 Decision Support & Exploration Shortcuts */}
                      <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px] font-semibold border-t border-slate-100 dark:border-slate-800/80 mt-2">
                        <Link
                          to={`/transfers?ward_id=${alert.ward_id}`}
                          className="inline-flex items-center gap-1 text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 hover:underline"
                          title="Open Inter-Ward Transfer Decision Support for this ward"
                        >
                          <ArrowRightLeft className="w-3.5 h-3.5" />
                          <span>Transfer Support</span>
                        </Link>
                        <span className="text-slate-300 dark:text-slate-700">&bull;</span>
                        <Link
                          to={`/forecast`}
                          className="inline-flex items-center gap-1 text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 hover:underline"
                          title="View SARIMA forecasts"
                        >
                          <TrendingUp className="w-3.5 h-3.5" />
                          <span>Forecast Projections</span>
                        </Link>
                        <span className="text-slate-300 dark:text-slate-700">&bull;</span>
                        <Link
                          to={`/wards/${alert.ward_id}`}
                          className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 hover:underline"
                          title="View ward details and physical bed inventory"
                        >
                          <Building2 className="w-3.5 h-3.5" />
                          <span>Ward Details</span>
                        </Link>
                      </div>
                    </div>
                  </div>

                  {/* Action Controls */}
                  <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                    <button
                      onClick={() => toggleExpand(alert.id)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-bold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                    >
                      <BrainCircuit className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
                      <span>{isExpanded ? 'Hide Evidence' : 'Explain'}</span>
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>

                    <button
                      onClick={() => setSelectedAlertForModal(alert)}
                      className="px-2.5 py-1 text-xs font-bold rounded-lg bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-200 hover:bg-purple-200 dark:hover:bg-purple-900 transition-colors"
                      title="Inspect full explainable payload"
                    >
                      Inspect
                    </button>

                    {!isResolved && !isAcknowledged && (
                      <button
                        onClick={() => handleAcknowledge(alert.id)}
                        disabled={actionLoading}
                        className="px-2.5 py-1 text-xs font-bold rounded-lg bg-sky-600 hover:bg-sky-500 text-white transition-colors disabled:opacity-50"
                      >
                        Acknowledge
                      </button>
                    )}

                    {!isResolved && (
                      <button
                        onClick={() => handleResolve(alert.id)}
                        disabled={actionLoading}
                        className="px-2.5 py-1 text-xs font-bold rounded-lg bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
                      >
                        Resolve
                      </button>
                    )}
                  </div>
                </div>

                {/* Inline Expandable Explanation & Triggered Rules */}
                {isExpanded && (
                  <div className="border-t border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/80 p-4 space-y-3 text-xs animate-fadeIn">
                    <div>
                      <span className="font-bold uppercase tracking-wider text-slate-400 text-[10px] block mb-1">
                        Explainable Evidence & Rationale:
                      </span>
                      <p className="text-slate-700 dark:text-slate-300 leading-relaxed">
                        {expl?.human_readable_explanation || alert.message}
                      </p>
                    </div>

                    {expl?.triggered_rules && expl.triggered_rules.length > 0 && (
                      <div>
                        <span className="font-bold uppercase tracking-wider text-slate-400 text-[10px] block mb-1.5">
                          Triggered Risk Rules:
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {expl.triggered_rules.map((rule) => (
                            <div
                              key={rule.rule_id}
                              className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700"
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-bold text-slate-800 dark:text-slate-100">{rule.rule_id}</span>
                                <span className="text-[10px] font-bold text-slate-500">Value: {rule.trigger_value.toFixed(1)}</span>
                              </div>
                              <p className="text-slate-600 dark:text-slate-300 text-[11px] mt-0.5">{rule.condition_met}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {expl?.suggested_actions && expl.suggested_actions.length > 0 && (
                      <div>
                        <span className="font-bold uppercase tracking-wider text-slate-400 text-[10px] block mb-1">
                          Suggested Administrative Actions:
                        </span>
                        <ul className="list-disc list-inside space-y-0.5 text-slate-700 dark:text-slate-300 text-[11px]">
                          {expl.suggested_actions.map((act, i) => (
                            <li key={i}>{act}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Detail Modal */}
      <ExplainableAlertDetailModal
        alert={selectedAlertForModal}
        onClose={() => setSelectedAlertForModal(null)}
        onAcknowledge={handleAcknowledge}
        onResolve={handleResolve}
        isActionLoading={actionLoading}
      />
    </div>
  );
};
