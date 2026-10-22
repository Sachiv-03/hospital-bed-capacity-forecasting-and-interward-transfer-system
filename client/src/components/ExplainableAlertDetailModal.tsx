import React from 'react';
import { Link } from 'react-router-dom';
import {
  X,
  BrainCircuit,
  TrendingUp,
  ShieldAlert,
  CheckCircle2,
  Clock,
  Info,
  ChevronRight,
  Database,
  Calendar,
  Sparkles,
  ArrowRightLeft,
  Building2,
} from 'lucide-react';
import { CapacityAlert } from '../types';

interface Props {
  alert: CapacityAlert | null;
  onClose: () => void;
  onAcknowledge?: (alertId: number) => void;
  onResolve?: (alertId: number) => void;
  isActionLoading?: boolean;
}

export const ExplainableAlertDetailModal: React.FC<Props> = ({
  alert,
  onClose,
  onAcknowledge,
  onResolve,
  isActionLoading,
}) => {
  if (!alert) return null;

  const expl = alert.explanation;
  const ev = expl?.evidence;
  const isCritical = alert.severity === 'CRITICAL';
  const isAcknowledged = alert.status === 'ACKNOWLEDGED';
  const isResolved = alert.status === 'RESOLVED';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
      <div
        className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl p-6 sm:p-8 space-y-6"
        role="dialog"
        aria-labelledby="alert-modal-title"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div
              className={`p-2.5 rounded-xl ${
                isCritical
                  ? 'bg-rose-100 text-rose-600 dark:bg-rose-950/80 dark:text-rose-400'
                  : 'bg-amber-100 text-amber-600 dark:bg-amber-950/80 dark:text-amber-400'
              }`}
            >
              <BrainCircuit className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`px-2 py-0.5 text-[10px] font-extrabold uppercase rounded-md tracking-wider ${
                    isCritical
                      ? 'bg-rose-600 text-white'
                      : 'bg-amber-600 text-white'
                  }`}
                >
                  {alert.severity}
                </span>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  {alert.status}
                </span>
                <span className="text-xs text-slate-500 font-semibold">
                  {alert.hospital_name || 'Hospital'} &bull; {alert.ward_name}
                </span>
              </div>
              <h2 id="alert-modal-title" className="text-xl font-black text-slate-900 dark:text-white">
                {expl?.headline || `${alert.alert_type.replace(/_/g, ' ')} in ${alert.ward_name}`}
              </h2>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Explainable Decision Support Banner */}
        <div className="p-3.5 rounded-xl bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-900 text-purple-900 dark:text-purple-200 text-xs flex items-start gap-2.5">
          <Sparkles className="w-4 h-4 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-bold">Deterministic Explainable AI Decision Support</p>
            <p className="opacity-90 mt-0.5">
              Alert generated deterministically from actual historical bed snapshots, authorized ward capacity,
              and active SARIMA time-series forecasts. Operational support only — does not claim clinical causation.
            </p>
          </div>
        </div>

        {/* Dynamic Human-Readable Explanation */}
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-sky-500" />
            Synthesized Clinical & Operational Explanation
          </h3>
          <p className="text-sm leading-relaxed text-slate-800 dark:text-slate-200">
            {expl?.human_readable_explanation || alert.message}
          </p>
        </div>

        {/* Quantitative Evidence Grid */}
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1.5">
            <Database className="w-3.5 h-3.5 text-indigo-500" />
            Observed & Forecasted Supporting Evidence
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Current Occupancy</span>
              <span className="text-lg font-black text-slate-900 dark:text-white">
                {ev ? `${ev.current_occupancy_percentage.toFixed(1)}%` : `${alert.trigger_value.toFixed(1)}%`}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                {ev ? `${ev.current_occupied_beds}/${ev.ward_capacity} beds` : 'Observed live'}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Forecasted Occupancy</span>
              <span className="text-lg font-black text-sky-600 dark:text-sky-400">
                {ev?.predicted_occupancy_percentage != null ? `${ev.predicted_occupancy_percentage.toFixed(1)}%` : '--'}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                {ev?.predicted_occupied_beds != null ? `~${ev.predicted_occupied_beds.toFixed(1)} beds projected` : 'No forecast data'}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Forecast Target Date</span>
              <span className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1 mt-1">
                <Calendar className="w-3.5 h-3.5 text-purple-500" />
                {ev?.forecast_target_date || 'Live Snapshot'}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                {ev?.forecast_horizon_days ? `${ev.forecast_horizon_days}-day horizon` : 'Immediate'}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Estimated Free Beds</span>
              <span className={`text-lg font-black ${
                (ev?.predicted_available_beds ?? ev?.current_available_beds ?? 0) <= 2
                  ? 'text-rose-500'
                  : 'text-emerald-500'
              }`}>
                {ev?.predicted_available_beds != null ? ev.predicted_available_beds : (ev?.current_available_beds ?? '--')}
              </span>
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Physical capacity: {ev?.ward_capacity ?? '--'}
              </span>
            </div>
          </div>

          {/* Uncertainty & Prediction Interval */}
          {ev?.lower_bound_percentage != null && ev?.upper_bound_percentage != null && (
            <div className="mt-3 p-3 rounded-xl bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-900 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-sky-600 dark:text-sky-400" />
                <span className="font-bold text-slate-800 dark:text-slate-100">95% Forecast Prediction Interval:</span>
                <span className="font-semibold text-sky-700 dark:text-sky-300">
                  {ev.lower_bound_percentage.toFixed(1)}% — {ev.upper_bound_percentage.toFixed(1)}%
                </span>
                <span className="text-slate-500">
                  (Span: {ev.uncertainty_interval_width != null ? `${ev.uncertainty_interval_width.toFixed(1)}%` : '--'})
                </span>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-sky-200 dark:bg-sky-800 text-sky-900 dark:text-sky-100">
                Model: {ev.model_used || 'SARIMA'}
              </span>
            </div>
          )}

          {/* Time to Threshold indicator */}
          {ev?.time_to_threshold_days && (
            <div className="mt-2 p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-xs flex items-center gap-2 text-amber-800 dark:text-amber-200">
              <Clock className="w-4 h-4 text-amber-600 shrink-0" />
              <span>
                <strong>Threshold Proximity:</strong> Projected to cross capacity threshold in <strong>{ev.time_to_threshold_days} day(s)</strong> (Projected Date: {ev.time_to_threshold_date}).
              </span>
            </div>
          )}

          {/* Historical trend */}
          {ev?.historical_trend_percentage_change != null && (
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Historical Trend Velocity: <strong className={ev.historical_trend_percentage_change > 0 ? 'text-amber-600' : 'text-slate-600'}>
                {ev.historical_trend_percentage_change > 0 ? `+${ev.historical_trend_percentage_change.toFixed(1)}%` : `${ev.historical_trend_percentage_change.toFixed(1)}%`}
              </strong> over last {ev.historical_trend_days || 3} days.
            </div>
          )}
        </div>

        {/* Triggered Rules Breakdown */}
        {expl?.triggered_rules && expl.triggered_rules.length > 0 && (
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
              Triggered Risk Rules & Thresholds
            </h3>
            <div className="space-y-2">
              {expl.triggered_rules.map((rule) => (
                <div
                  key={rule.rule_id}
                  className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] font-extrabold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {rule.rule_id}
                      </span>
                      <span className="text-xs font-bold text-slate-900 dark:text-white">
                        {rule.rule_name}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
                      {rule.condition_met}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {rule.description}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                      Value: {rule.trigger_value.toFixed(1)}
                    </span>
                    <span className="text-[10px] text-slate-400 block">
                      Threshold: {rule.threshold_value}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Suggested Administrative Next Steps */}
        {expl?.suggested_actions && expl.suggested_actions.length > 0 && (
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              Suggested Administrative Actions (Non-Clinical)
            </h3>
            <ul className="space-y-2">
              {expl.suggested_actions.map((action, idx) => (
                <li
                  key={idx}
                  className="p-2.5 rounded-lg bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900 text-xs text-emerald-900 dark:text-emerald-200 flex items-start gap-2"
                >
                  <ChevronRight className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <span>{action}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Data Quality & Limitations Notice */}
        {ev?.data_quality_notes && ev.data_quality_notes.length > 0 && (
          <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs text-slate-600 dark:text-slate-400 flex items-start gap-2">
            <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
            <div>
              <strong className="text-slate-700 dark:text-slate-300">Data Quality & Limitations:</strong>
              <ul className="list-disc list-inside mt-0.5">
                {ev.data_quality_notes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Operational Shortcuts */}
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-bold text-slate-700 dark:text-slate-300">Decision Support Shortcuts:</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              to={`/transfers?ward_id=${alert.ward_id}`}
              onClick={onClose}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/70 border border-sky-200 dark:border-sky-800 text-sky-700 dark:text-sky-300 font-bold hover:bg-sky-100 dark:hover:bg-sky-900 transition-colors"
            >
              <ArrowRightLeft className="w-3.5 h-3.5" />
              <span>Inter-Ward Transfer Decision Support</span>
            </Link>

            <Link
              to={`/forecast`}
              onClick={onClose}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-50 dark:bg-purple-950/70 border border-purple-200 dark:border-purple-800 text-purple-700 dark:text-purple-300 font-bold hover:bg-purple-100 dark:hover:bg-purple-900 transition-colors"
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>SARIMA Forecasts</span>
            </Link>

            <Link
              to={`/wards/${alert.ward_id}`}
              onClick={onClose}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 font-bold hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
            >
              <Building2 className="w-3.5 h-3.5" />
              <span>Ward Details</span>
            </Link>
          </div>
        </div>

        {/* Modal Actions Footer */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
          <div className="text-[11px] text-slate-400">
            {alert.acknowledged_at && (
              <span>Acknowledged at {new Date(alert.acknowledged_at).toLocaleString()}</span>
            )}
            {alert.resolved_at && (
              <span className="ml-2">Resolved at {new Date(alert.resolved_at).toLocaleString()}</span>
            )}
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            {!isResolved && !isAcknowledged && onAcknowledge && (
              <button
                onClick={() => onAcknowledge(alert.id)}
                disabled={isActionLoading}
                className="px-4 py-2 text-xs font-bold rounded-xl bg-sky-600 hover:bg-sky-500 text-white shadow-sm transition-all disabled:opacity-50"
              >
                Acknowledge Alert
              </button>
            )}

            {!isResolved && onResolve && (
              <button
                onClick={() => onResolve(alert.id)}
                disabled={isActionLoading}
                className="px-4 py-2 text-xs font-bold rounded-xl bg-slate-800 hover:bg-slate-700 dark:bg-slate-700 dark:hover:bg-slate-600 text-white shadow-sm transition-all disabled:opacity-50"
              >
                Resolve Alert
              </button>
            )}

            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-bold rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
