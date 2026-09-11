import React, { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function HistoryView({ onSelectScan }) {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState(null);

  const fetchScans = async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `${API_BASE_URL}/scans`;
      const params = new URLSearchParams();
      if (searchQuery.trim()) params.append('search', searchQuery.trim());
      if (statusFilter) params.append('status', statusFilter);
      if (params.toString()) url += `?${params.toString()}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to fetch past scans');
      const data = await res.json();
      setScans(data);
    } catch (err) {
      console.error('Fetch scans error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScans();
  }, [searchQuery, statusFilter]);

  const handleRowClick = async (scanId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/scans/${scanId}`);
      if (!res.ok) throw new Error('Failed to fetch scan detail');
      const detailData = await res.json();
      onSelectScan(detailData);
    } catch (err) {
      alert('Error loading scan details: ' + err.message);
    }
  };

  const handleDeleteScan = async (scanId, productName) => {
    if (!window.confirm(`Are you sure you want to delete scan #${scanId} (${productName || 'Unknown'}) and remove its uploaded image?`)) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/scans/${scanId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete scan');
      fetchScans();
    } catch (err) {
      alert('Error deleting scan: ' + err.message);
    }
  };

  const handleClearAllHistory = async () => {
    if (!window.confirm('Are you sure you want to delete ALL past scans and remove all uploaded images? This action cannot be undone.')) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/scans`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to clear history');
      fetchScans();
    } catch (err) {
      alert('Error clearing history: ' + err.message);
    }
  };

  const getStatusBadge = (status) => {
    if (status === 'COMPLIANT') {
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    } else if (status === 'PARTIALLY_COMPLIANT') {
      return 'bg-amber-100 text-amber-800 border-amber-200';
    } else {
      return 'bg-rose-100 text-rose-800 border-rose-200';
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      
      {/* Header & Controls */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Past Audit History</h2>
            <p className="text-xs text-gray-500">
              Repository of scanned labels and LMPC compliance reports. Local images stored in <code className="bg-gray-100 px-1 py-0.5 rounded text-gray-800 font-mono">backend/uploads</code>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchScans}
              className="px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold cursor-pointer"
            >
              Refresh
            </button>
            {scans.length > 0 && (
              <button
                onClick={handleClearAllHistory}
                className="px-3 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-xs font-semibold cursor-pointer"
              >
                Clear All History
              </button>
            )}
          </div>
        </div>

        {/* Search & Status Filter Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 pt-2">
          <div className="sm:col-span-8">
            <input
              type="text"
              placeholder="Search by product name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg border border-gray-300 text-xs text-gray-900 focus:outline-none focus:border-gray-900"
            />
          </div>

          <div className="sm:col-span-4">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3.5 py-2 rounded-lg border border-gray-300 text-xs text-gray-900 bg-white focus:outline-none focus:border-gray-900"
            >
              <option value="">All Statuses</option>
              <option value="COMPLIANT">COMPLIANT</option>
              <option value="PARTIALLY_COMPLIANT">PARTIALLY_COMPLIANT</option>
              <option value="NON_COMPLIANT">NON_COMPLIANT</option>
            </select>
          </div>
        </div>
      </div>

      {/* Scans List Table */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
        {loading ? (
          <div className="p-8 text-center text-xs text-gray-500">Loading audit history...</div>
        ) : error ? (
          <div className="p-8 text-center text-xs text-red-600 font-medium">{error}</div>
        ) : scans.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No past scans found matching your search.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-semibold">
                <tr>
                  <th className="py-2.5 px-4"># ID</th>
                  <th className="py-2.5 px-4">Product Name</th>
                  <th className="py-2.5 px-4">Date / Time</th>
                  <th className="py-2.5 px-4">LMPC Status</th>
                  <th className="py-2.5 px-4">Ingredients Safety</th>
                  <th className="py-2.5 px-4">Score</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-900">
                {scans.map((scan) => (
                  <tr
                    key={scan.id}
                    onClick={() => handleRowClick(scan.id)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4 font-mono font-bold text-gray-400">#{scan.id}</td>
                    <td className="py-3 px-4 font-semibold text-gray-900 max-w-xs truncate">
                      {scan.product_name || 'Unknown Product'}
                    </td>
                    <td className="py-3 px-4 text-gray-500 font-mono text-[11px]">
                      {scan.timestamp
                        ? new Date(scan.timestamp).toLocaleString('en-IN', {
                            day: '2-digit', month: 'short', year: 'numeric',
                            hour: '2-digit', minute: '2-digit', hour12: true
                          })
                        : '-'}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${getStatusBadge(scan.overall_status)}`}>
                        {scan.overall_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {scan.ingredient_verdict && scan.ingredient_verdict !== 'NOT_CHECKED' ? (
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${
                          scan.ingredient_verdict === 'SAFE'
                            ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                            : scan.ingredient_verdict === 'CAUTION'
                            ? 'bg-amber-100 text-amber-800 border-amber-200'
                            : 'bg-rose-100 text-rose-800 border-rose-200'
                        }`}>
                          {scan.ingredient_verdict === 'SAFE' && '✓ SAFE'}
                          {scan.ingredient_verdict === 'CAUTION' && '⚠️ CAUTION'}
                          {scan.ingredient_verdict === 'HARMFUL' && '⚠️ HARMFUL'}
                          {scan.ingredient_score != null && ` (${scan.ingredient_score})`}
                        </span>
                      ) : (
                        <span className="text-[11px] text-gray-400 italic">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono font-bold text-gray-800">
                      {scan.compliance_score}%
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleRowClick(scan.id)}
                          className="px-2.5 py-1 rounded bg-gray-900 hover:bg-gray-800 text-white font-medium text-[11px] cursor-pointer"
                        >
                          View Report
                        </button>
                        <button
                          onClick={() => handleDeleteScan(scan.id, scan.product_name)}
                          className="px-2 py-1 rounded bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 font-medium text-[11px] cursor-pointer"
                          title="Delete scan and uploaded image"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
