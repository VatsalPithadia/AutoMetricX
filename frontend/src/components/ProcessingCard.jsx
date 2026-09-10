import React from 'react';

export default function ProcessingCard({ totalImages = 1 }) {
  const isMulti = totalImages > 1;
  return (
    <div className="w-full max-w-md mx-auto bg-white border border-gray-200 rounded-2xl p-8 text-center space-y-4 shadow-sm">
      <div className="flex justify-center">
        <div className="w-10 h-10 border-3 border-gray-200 border-t-gray-900 rounded-full animate-spin" />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-bold text-gray-900">
          {isMulti ? `Analyzing ${totalImages} Package Sides...` : 'Analyzing Product Label...'}
        </h3>
        <p className="text-xs text-gray-500">
          {isMulti
            ? `Running OCR on all ${totalImages} sides, verifying same-product consistency, and checking LMPC compliance.`
            : 'Extracting text, measuring font heights, and checking LMPC rules.'}
        </p>
      </div>
      {isMulti && (
        <div className="flex justify-center gap-1.5">
          {Array.from({ length: totalImages }).map((_, i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full bg-gray-300 animate-pulse"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
