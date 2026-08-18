import React, { useState, useEffect } from 'react';
import { Cpu, CheckCircle2, Award, RefreshCw } from 'lucide-react';
import { ModelPerformanceResponse, forecastService } from '../../services/forecastService';

interface Props {
  wardId: number;
}

export const ModelPerformanceCard: React.FC<Props> = ({ wardId }) => {
  const [performance, setPerformance] = useState<ModelPerformanceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPerformance = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await forecastService.getModelPerformance(wardId);
      setPerformance(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load model performance metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (wardId) {
      fetchPerformance();
    }
  }, [wardId]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm animate-pulse">
        <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded w-1/3 mb-4"></div>
        <div className="h-32 bg-slate-200 dark:bg-slate-800 rounded"></div>
      </div>
    );
  }

  if (error || !performance) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-purple-500" />
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
              Model Performance & Accuracy Metrics
            </h3>
          </div>
          <button
            onClick={fetchPerformance}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {error || 'Model performance metrics currently unavailable.'}
        </p>
      </div>
    );
  }

  const { baseline_model: baseline, primary_model: primary, recommended_model: bestModel } = performance;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-purple-500" />
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
              Model Evaluation & Accuracy Benchmark
            </h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Comparing Naive Moving Average Baseline vs Primary SARIMA Time-Series Model
          </p>
        </div>

        <button
          onClick={fetchPerformance}
          className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white transition-colors"
          title="Refresh metrics"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* Baseline Model Box */}
        <div
          className={`p-4 rounded-xl border transition-all ${
            bestModel === baseline.model_name
              ? 'bg-purple-500/5 border-purple-500/30 ring-1 ring-purple-500/20'
              : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm text-slate-900 dark:text-white">
                {baseline.model_name}
              </span>
              <span className="text-xs text-slate-500">v{baseline.model_version}</span>
            </div>
            {bestModel === baseline.model_name && (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full">
                <Award className="w-3.5 h-3.5" /> Best Performer
              </span>
            )}
          </div>

          <div className="grid grid-cols-3 gap-2 text-center py-2 border-y border-slate-200 dark:border-slate-800">
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">MAE</div>
              <div className="text-lg font-black text-slate-900 dark:text-white">{baseline.mae} beds</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">RMSE</div>
              <div className="text-lg font-black text-slate-900 dark:text-white">{baseline.rmse} beds</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">MAPE</div>
              <div className="text-lg font-black text-slate-900 dark:text-white">
                {baseline.mape != null ? `${baseline.mape}%` : 'N/A'}
              </div>
            </div>
          </div>

          <div className="text-xs text-slate-500 dark:text-slate-400 mt-3">
            Moving average baseline predicting next observations using rolling window.
          </div>
        </div>

        {/* Primary SARIMA Model Box */}
        <div
          className={`p-4 rounded-xl border transition-all ${
            bestModel === primary.model_name
              ? 'bg-purple-500/5 border-purple-500/30 ring-1 ring-purple-500/20'
              : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm text-slate-900 dark:text-white">
                {primary.model_name}
              </span>
              <span className="text-xs text-slate-500">v{primary.model_version}</span>
            </div>
            {bestModel === primary.model_name && (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" /> Recommended
              </span>
            )}
          </div>

          <div className="grid grid-cols-3 gap-2 text-center py-2 border-y border-slate-200 dark:border-slate-800">
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">MAE</div>
              <div className="text-lg font-black text-slate-900 dark:text-white">{primary.mae} beds</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">RMSE</div>
              <div className="text-lg font-black text-slate-900 dark:text-white">{primary.rmse} beds</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 dark:text-slate-400">MAPE</div>
              <div className="text-lg font-black text-slate-900 dark:text-white">
                {primary.mape != null ? `${primary.mape}%` : 'N/A'}
              </div>
            </div>
          </div>

          <div className="text-xs text-slate-500 dark:text-slate-400 mt-3">
            SARIMAX state-space model capturing seasonal weekly dynamics and auto-regression.
          </div>
        </div>
      </div>
    </div>
  );
};
