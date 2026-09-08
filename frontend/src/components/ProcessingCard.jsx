import React from 'react';

export default function ProcessingCard() {
  return (
    <div className="w-full max-w-md mx-auto bg-white border border-gray-200 rounded-2xl p-8 text-center space-y-4 shadow-sm">
      <div className="flex justify-center">
        <div className="w-10 h-10 border-3 border-gray-200 border-t-gray-900 rounded-full animate-spin" />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-bold text-gray-900">
          Analyzing Product Label...
        </h3>
        <p className="text-xs text-gray-500">
          Extracting text, measuring font heights, and checking LMPC rules.
        </p>
      </div>
    </div>
  );
}
