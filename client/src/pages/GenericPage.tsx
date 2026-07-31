import React from 'react';

interface GenericPageProps {
  title: string;
  description: string;
  moduleName: string;
}

export const GenericPage: React.FC<GenericPageProps> = ({ title, description, moduleName }) => {
  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-5">
        <h1 className="text-2xl font-extrabold text-slate-900 dark:text-white">{title}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{description}</p>
      </div>

      <div className="p-8 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-400 flex items-center justify-center mx-auto text-xl font-bold">
          {moduleName.charAt(0)}
        </div>
        <h2 className="text-lg font-bold text-slate-800 dark:text-slate-200">{moduleName} Module</h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          This module route is registered in the Phase 1 foundation layout. Business logic, tables, and interactive CRUD operations will be integrated in subsequent phases.
        </p>
        <span className="inline-block px-3 py-1 text-xs font-semibold text-sky-700 bg-sky-50 dark:bg-sky-950 dark:text-sky-300 rounded-full border border-sky-200 dark:border-sky-800">
          Phase 1 Foundation Ready
        </span>
      </div>
    </div>
  );
};
