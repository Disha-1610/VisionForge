import React from 'react';

export const SkeletonLoader = ({ className = '', count = 1 }) => {
  return (
    <div className="space-y-3 w-full animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`h-6 bg-slate-800/80 rounded-xl border border-slate-700/30 ${className}`}
        />
      ))}
    </div>
  );
};
