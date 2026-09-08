import React from 'react';

export default function Header({ backendConnected, currentNav, onNavChange }) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3.5">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        
        {/* Brand & Nav Links */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-lg font-extrabold text-gray-900 tracking-tight">MetroLens</span>
            <span className="text-xs font-medium text-gray-400">Legal Metrology</span>
          </div>

          <nav className="flex items-center gap-1 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => onNavChange('scan')}
              className={`px-3 py-1 text-xs font-semibold rounded transition-colors cursor-pointer ${
                currentNav === 'scan' ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              New Scan
            </button>
            <button
              onClick={() => onNavChange('history')}
              className={`px-3 py-1 text-xs font-semibold rounded transition-colors cursor-pointer ${
                currentNav === 'history' ? 'bg-white text-gray-900 shadow-xs' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Past Audits
            </button>
          </nav>
        </div>

        {/* Minimal System Health Indicator */}
        <div className="flex items-center gap-2 text-xs text-gray-500 font-medium">
          <span className={`w-2 h-2 rounded-full ${backendConnected ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
          <span className="hidden sm:inline">{backendConnected ? 'API Connected' : 'Connecting...'}</span>
        </div>

      </div>
    </header>
  );
}
