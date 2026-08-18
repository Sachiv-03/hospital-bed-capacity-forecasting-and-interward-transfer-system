import React from 'react';
import {
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  Info,
  TrendingUp,
} from 'lucide-react';
import { TransferRecommendation } from '../../types';
import { cn } from '../../utils/cn';

interface TransferRecommendationCardProps {
  recommendation: TransferRecommendation;
  onSelect: (recommendation: TransferRecommendation) => void;
}

export const TransferRecommendationCard: React.FC<TransferRecommendationCardProps> = ({
  recommendation,
  onSelect,
}) => {
  const {
    source_ward,
    destination_ward,
    source_current_occupancy,
    source_predicted_occupancy,
    destination_current_occupancy,
    destination_predicted_occupancy,
    safe_transfer_capacity,
    priority_score,
    priority_level,
    status,
    reason,
    warnings,
  } = recommendation;

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority) {
      case 'CRITICAL':
        return 'bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border-rose-300 dark:border-rose-800';
      case 'HIGH':
        return 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border-amber-300 dark:border-amber-800';
      case 'MEDIUM':
        return 'bg-sky-100 text-sky-800 dark:bg-sky-950/80 dark:text-sky-300 border-sky-300 dark:border-sky-800';
      default:
        return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-300 dark:border-slate-700';
    }
  };

  const getStatusBadgeClass = (st: string) => {
    switch (st) {
      case 'APPROVED':
        return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800';
      case 'REJECTED':
        return 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800';
      case 'STALE':
      case 'EXPIRED':
        return 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800';
      default:
        return 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-800';
    }
  };

  return (
    <div
      className={cn(
        'group relative bg-white dark:bg-slate-900 rounded-xl border p-5 transition-all duration-200 hover:shadow-lg',
        priority_level === 'CRITICAL'
          ? 'border-rose-200 dark:border-rose-900/60 shadow-xs'
          : 'border-slate-200 dark:border-slate-800'
      )}
    >
      {/* Header Bar */}
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={cn(
              'px-2.5 py-1 rounded-full text-xs font-semibold border flex items-center gap-1',
              getPriorityBadgeClass(priority_level)
            )}
          >
            {priority_level === 'CRITICAL' && <ShieldAlert className="w-3.5 h-3.5" />}
            {priority_level} PRIORITY
          </span>
          <span
            className={cn(
              'px-2.5 py-1 rounded-full text-xs font-medium border',
              getStatusBadgeClass(status)
            )}
          >
            {status}
          </span>
        </div>

        {/* Score Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-100 dark:bg-slate-800/80 rounded-lg">
          <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">Match Score:</span>
          <span className="text-sm font-bold text-sky-600 dark:text-sky-400">
            {priority_score.toFixed(0)}/100
          </span>
        </div>
      </div>

      {/* Source -> Destination Transfer Flow */}
      <div className="grid grid-cols-1 md:grid-cols-11 gap-3 items-center mb-4 p-3.5 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-100 dark:border-slate-800">
        {/* Source Ward */}
        <div className="md:col-span-5 space-y-1">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Source Ward (Capacity Relief)
          </div>
          <div className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            {source_ward?.name || `Ward #${recommendation.source_ward_id}`}
            <span className="px-2 py-0.5 text-[10px] uppercase font-bold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded">
              {source_ward?.ward_type || 'WARD'}
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-600 dark:text-slate-400 pt-1">
            <span>
              Current: <strong className="text-slate-900 dark:text-slate-200">{source_current_occupancy}%</strong>
            </span>
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <span className="flex items-center gap-1 text-rose-600 dark:text-rose-400 font-medium">
              <TrendingUp className="w-3.5 h-3.5" />
              Forecast: {source_predicted_occupancy}%
            </span>
          </div>
        </div>

        {/* Transfer Indicator Arrow */}
        <div className="md:col-span-1 flex items-center justify-center py-1 md:py-0">
          <div className="w-8 h-8 rounded-full bg-sky-100 dark:bg-sky-950/80 text-sky-600 dark:text-sky-400 flex items-center justify-center shadow-xs">
            <ArrowRight className="w-4 h-4" />
          </div>
        </div>

        {/* Destination Ward */}
        <div className="md:col-span-5 space-y-1">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Recommended Destination
          </div>
          <div className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            {destination_ward?.name || `Ward #${recommendation.destination_ward_id}`}
            <span className="px-2 py-0.5 text-[10px] uppercase font-bold bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300 rounded">
              {destination_ward?.ward_type || 'WARD'}
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-600 dark:text-slate-400 pt-1">
            <span>
              Current: <strong className="text-slate-900 dark:text-slate-200">{destination_current_occupancy}%</strong>
            </span>
            <span className="text-slate-300 dark:text-slate-700">•</span>
            <span>
              Forecast: <strong className="text-slate-900 dark:text-slate-200">{destination_predicted_occupancy}%</strong>
            </span>
          </div>
        </div>
      </div>

      {/* Safe Capacity Banner */}
      <div className="flex items-center justify-between bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-900/40 rounded-lg px-3.5 py-2.5 mb-4">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="text-xs text-emerald-900 dark:text-emerald-200">
            Available safe transfer capacity:
          </span>
        </div>
        <span className="text-sm font-bold text-emerald-700 dark:text-emerald-300">
          Up to {safe_transfer_capacity} {safe_transfer_capacity === 1 ? 'bed' : 'beds'}
        </span>
      </div>

      {/* Reason Preview */}
      <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2 mb-4 leading-relaxed">
        {reason}
      </p>

      {/* Warning Badges if present */}
      {warnings && warnings.length > 0 && (
        <div className="mb-4 flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 px-3 py-1.5 rounded-lg border border-amber-200/60 dark:border-amber-900/40">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span className="truncate">{warnings[0]}</span>
        </div>
      )}

      {/* Action Footer */}
      <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <div className="text-[11px] text-slate-400 dark:text-slate-500 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Generated {new Date(recommendation.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
        <button
          onClick={() => onSelect(recommendation)}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-sky-700 bg-sky-50 hover:bg-sky-100 dark:text-sky-300 dark:bg-sky-950/70 dark:hover:bg-sky-900 transition-colors"
        >
          View Details & Review
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
