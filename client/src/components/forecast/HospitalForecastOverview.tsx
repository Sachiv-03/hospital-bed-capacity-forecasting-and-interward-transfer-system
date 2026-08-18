import React, { useState, useEffect } from 'react';
import { Building2, Layers, AlertCircle, RefreshCw, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { HospitalForecastResponse, forecastService } from '../../services/forecastService';

interface Props {
  hospitalId: number;
}

export const HospitalForecastOverview: React.FC<Props> = ({ hospitalId }) => {
  const [data, setData] = useState<HospitalForecastResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const fetchHospitalForecast = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await forecastService.getHospitalForecast(hospitalId, 7);
      setData(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load hospital forecast overview');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (hospitalId) {
      fetchHospitalForecast();
    }
  }, [hospitalId]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm animate-pulse">
        <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded w-1/3 mb-4"></div>
        <div className="h-40 bg-slate-200 dark:bg-slate-800 rounded"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-sky-500" />
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
              Hospital Capacity Forecast Overview
            </h3>
          </div>
          <button onClick={fetchHospitalForecast} className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-white">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">{error || 'Forecast data unavailable.'}</p>
      </div>
    );
  }

  const getRiskBadgeClass = (risk: string) => {
    switch (risk) {
      case 'CRITICAL':
        return 'bg-red-500/10 text-red-500 border-red-500/20';
      case 'HIGH':
        return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
      case 'MODERATE':
        return 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20';
      default:
        return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-sky-500" />
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">
              Hospital Capacity Forecast Overview
            </h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Facility-wide predicted bed pressure across wards for {data.hospital_name}
          </p>
        </div>

        <button
          onClick={fetchHospitalForecast}
          className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white transition-colors"
          title="Refresh hospital forecast"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Ward Summaries Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
          <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 uppercase font-bold text-[10px] tracking-wider border-y border-slate-200 dark:border-slate-800">
            <tr>
              <th className="py-3 px-4">Ward Name</th>
              <th className="py-3 px-4">Total Beds</th>
              <th className="py-3 px-4">Current Occupancy</th>
              <th className="py-3 px-4">Tomorrow Forecast</th>
              <th className="py-3 px-4">7-Day Peak</th>
              <th className="py-3 px-4">Predicted Risk</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-medium">
            {data.ward_summaries.map((ward) => (
              <tr key={ward.ward_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                <td className="py-3 px-4 font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-sky-500 shrink-0" />
                  {ward.ward_name}
                </td>
                <td className="py-3 px-4">{ward.total_beds} beds</td>
                <td className="py-3 px-4 font-bold">{ward.current_occupancy_percentage}%</td>
                <td className="py-3 px-4 font-bold text-sky-600 dark:text-sky-400">
                  {ward.tomorrow_occupancy_percentage}%
                </td>
                <td className="py-3 px-4 font-bold text-purple-600 dark:text-purple-400">
                  {ward.max_7day_occupancy_percentage}%
                </td>
                <td className="py-3 px-4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-black border ${getRiskBadgeClass(ward.max_risk_level)}`}>
                    {ward.max_risk_level}
                  </span>
                </td>
                <td className="py-3 px-4 text-right">
                  <button
                    onClick={() => navigate(`/wards/${ward.ward_id}`)}
                    className="inline-flex items-center text-sky-600 hover:text-sky-700 dark:text-sky-400 font-semibold gap-0.5 hover:underline"
                  >
                    View Ward <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
