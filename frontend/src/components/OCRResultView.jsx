import React, { useState } from 'react';

export default function OCRResultView({ result, imagePreviewUrl, onResetScan }) {
  const [copied, setCopied] = useState(false);
  const [showJson, setShowJson] = useState(false);
  const [showBoxes, setShowBoxes] = useState(true);
  const [selectedBlock, setSelectedBlock] = useState(null);
  const [activeTab, setActiveTab] = useState('compliance'); // 'compliance' | 'overlay' | 'raw'
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  if (!result) return null;

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const res = await fetch('http://localhost:8000/export-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(result)
      });
      if (!res.ok) throw new Error('PDF export failed');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `metrolens_audit_certificate_${result.filename || 'report'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF download error:', err);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleCopyText = () => {
    navigator.clipboard.writeText(result.raw_text || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const imgMeta = result.image_metadata || { width: 600, height: 400 };
  const report = result.compliance_report || {};
  const classified = result.classified_fields || {};
  const declarations = report.declarations || [];

  const getStatusBadge = (status) => {
    if (status === 'COMPLIANT' || status === 'PASS') {
      return { bg: 'bg-emerald-50 text-emerald-700 border-emerald-200', badge: 'bg-emerald-600 text-white', label: 'PASS' };
    } else if (status === 'WARNING' || status === 'PARTIALLY_COMPLIANT' || status === 'LOW_CONFIDENCE') {
      return { bg: 'bg-amber-50 text-amber-700 border-amber-200', badge: 'bg-amber-600 text-white', label: 'WARNING' };
    } else {
      return { bg: 'bg-rose-50 text-rose-700 border-rose-200', badge: 'bg-rose-600 text-white', label: 'FAIL' };
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      
      {/* Top Header Card */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm">
        
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-gray-900">Inspection Report</h2>
              <span className={`text-xs px-2.5 py-0.5 rounded font-bold uppercase ${getStatusBadge(report.overall_status).badge}`}>
                {report.overall_status || 'NON_COMPLIANT'}
              </span>
            </div>
            <p className="text-xs text-gray-500 font-mono mt-0.5">
              File: {result.filename} &bull; Score: {report.compliance_score || 0}% ({report.passed_rules_count || 0}/{report.total_rules_checked || 8} Rules Passed)
            </p>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              onClick={handleDownloadPdf}
              disabled={downloadingPdf}
              className="px-4 py-2 rounded-lg bg-gray-900 hover:bg-gray-800 text-white text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
            >
              {downloadingPdf ? 'Exporting PDF...' : 'Download PDF Report'}
            </button>

            <button
              onClick={onResetScan}
              className="px-3 py-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-medium cursor-pointer"
            >
              New Scan
            </button>
          </div>
        </div>

        {/* Minimal Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-gray-100 pb-1">
          <button
            onClick={() => setActiveTab('compliance')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
              activeTab === 'compliance' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            Compliance Declarations
          </button>
          <button
            onClick={() => setActiveTab('overlay')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
              activeTab === 'overlay' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            Label Image & Overlay
          </button>
          <button
            onClick={() => setActiveTab('raw')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
              activeTab === 'raw' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            Raw Text
          </button>
        </div>

      </div>

      {/* --- TAB 1: Compliance Declarations --- */}
      {activeTab === 'compliance' && (
        <div className="space-y-6">
          
          {/* FSSAI License & Barcode Verification Box (UPSIDE / ABOVE Metrology Rules) */}
          <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/50 space-y-3 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-emerald-600 text-white font-bold text-xs uppercase tracking-wider">
                  FSSAI
                </span>
                <div>
                  <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">FSSAI License & Barcode Verification Box</h3>
                  <p className="text-[11px] text-gray-500">Food Safety and Standards Authority of India (FSSAI) Compliance Check</p>
                </div>
              </div>
              <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-full ${
                classified.fssai_number?.license_number || classified.fssai_number?.raw_text
                  ? 'bg-emerald-600 text-white'
                  : 'bg-amber-500 text-white'
              }`}>
                {classified.fssai_number?.license_number ? '14-Digit Valid License' : 'FSSAI Status'}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5 text-xs">
              <div className="p-3 rounded-lg bg-white border border-emerald-100 shadow-2xs space-y-1">
                <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">FSSAI License No.</div>
                <div className="font-mono font-bold text-emerald-700 text-sm truncate">
                  {classified.fssai_number?.license_number || classified.fssai_number?.raw_text || (
                    <span className="text-amber-600 text-xs italic font-normal">Not Detected</span>
                  )}
                </div>
                {classified.fssai_number?.license_number && (
                  <div className="text-[9px] text-emerald-600 font-medium">✓ Verified 14-Digit Standard Format</div>
                )}
              </div>

              <div className="p-3 rounded-lg bg-white border border-emerald-100 shadow-2xs space-y-1">
                <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">1D Barcode GTIN</div>
                <div className="font-mono font-semibold text-gray-800 text-xs truncate">
                  {result.barcode_qr_analysis?.gtin_barcodes?.join(', ') || 'None Detected'}
                </div>
                <div className="text-[9px] text-gray-400">EAN-13 / UPC Code</div>
              </div>

              <div className="p-3 rounded-lg bg-white border border-emerald-100 shadow-2xs space-y-1">
                <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">QR Code Link</div>
                <div className="font-mono font-semibold text-gray-800 text-xs truncate">
                  {result.barcode_qr_analysis?.qr_urls?.join(', ') || 'None Detected'}
                </div>
                <div className="text-[9px] text-gray-400">Digital Smart Label</div>
              </div>

              <div className="p-3 rounded-lg bg-white border border-emerald-100 shadow-2xs space-y-1">
                <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Cross-Check Status</div>
                <div className="text-xs text-gray-700 font-medium leading-tight">
                  {result.barcode_qr_analysis?.fssai_cross_check?.explanation || 'FSSAI License & product declarations verified.'}
                </div>
              </div>
            </div>
          </div>

          {/* Legal Metrology Rules Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {declarations.map((decl, idx) => {
              const st = getStatusBadge(decl.status);
              return (
                <div key={idx} className="p-4 rounded-xl border border-gray-200 bg-white space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-700">
                        {decl.clause}
                      </span>
                      <h4 className="text-xs font-bold text-gray-900">{decl.name}</h4>
                    </div>
                    <span className={`text-[9px] font-extrabold px-2 py-0.5 rounded uppercase ${st.badge}`}>
                      {decl.status}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                    <div className="text-[10px] font-medium text-gray-400 uppercase">Detected Text</div>
                    <div className="text-xs font-mono font-semibold text-gray-800 truncate">
                      {decl.found_value || <span className="text-gray-400 font-normal italic">Not Found</span>}
                    </div>
                  </div>

                  <p className="text-xs text-gray-600 leading-snug">{decl.explanation}</p>
                </div>
              );
            })}
          </div>

          {/* Font Size Legibility Analysis Table */}
          {report.font_legibility_analysis && (
            <div className="p-4 rounded-xl border border-gray-200 bg-white space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">Font Size Legibility (Rule 7 & 9)</h3>
                <span className="text-xs font-mono text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
                  Scale: {report.font_legibility_analysis.scale_px_mm} px/mm
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200 text-gray-500 font-semibold">
                    <tr>
                      <th className="py-2 px-3">Field</th>
                      <th className="py-2 px-3">Measured Size (mm)</th>
                      <th className="py-2 px-3">Required Min (mm)</th>
                      <th className="py-2 px-3 text-right">Rule 7 Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-gray-800">
                    {report.font_legibility_analysis.rule_7_3_field_evaluations?.map((item, i) => (
                      <tr key={i}>
                        <td className="py-2 px-3 font-semibold capitalize">{item.field.replace('_', ' ')}</td>
                        <td className="py-2 px-3 font-mono">{item.font_height_mm} mm</td>
                        <td className="py-2 px-3 font-mono">{report.font_legibility_analysis.min_required_letter_height_mm} mm</td>
                        <td className="py-2 px-3 text-right">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                            item.status === 'PASS' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                          }`}>
                            {item.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </div>
      )}

      {/* --- TAB 2: Label Image & Bounding Boxes --- */}
      {activeTab === 'overlay' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-6 bg-white border border-gray-200 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-gray-900 uppercase">Image Overlay</h3>
              <button
                onClick={() => setShowBoxes(!showBoxes)}
                className="text-xs text-gray-600 hover:text-gray-900 underline"
              >
                {showBoxes ? 'Hide Overlays' : 'Show Overlays'}
              </button>
            </div>

            <div className="relative bg-gray-50 rounded-lg overflow-hidden border border-gray-200 flex items-center justify-center p-2">
              <div className="relative inline-block max-w-full">
                <img
                  src={imagePreviewUrl}
                  alt="Analyzed Label"
                  className="max-h-[400px] object-contain rounded block"
                />

                {showBoxes && result.ocr_blocks && (
                  <svg
                    className="absolute inset-0 w-full h-full pointer-events-none"
                    viewBox={`0 0 ${imgMeta.width} ${imgMeta.height}`}
                    preserveAspectRatio="xMidYMid meet"
                  >
                    {result.ocr_blocks.map((block) => {
                      const isSelected = selectedBlock === block.id;
                      const r = block.rect || { x: 0, y: 0, width: 50, height: 20 };
                      return (
                        <g key={block.id} className="pointer-events-auto cursor-pointer" onClick={() => setSelectedBlock(block.id)}>
                          <rect
                            x={r.x}
                            y={r.y}
                            width={r.width}
                            height={r.height}
                            fill={isSelected ? 'rgba(37, 99, 235, 0.2)' : 'rgba(16, 185, 129, 0.15)'}
                            stroke={isSelected ? '#2563eb' : '#10b981'}
                            strokeWidth={Math.max(2, Math.round(imgMeta.width / 400))}
                            rx="2"
                          />
                        </g>
                      );
                    })}
                  </svg>
                )}
              </div>
            </div>
          </div>

          <div className="lg:col-span-6 bg-white border border-gray-200 rounded-xl p-4 space-y-3">
            <h3 className="text-xs font-bold text-gray-900 uppercase">Detected Text Regions ({result.total_blocks})</h3>

            <div className="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden max-h-[400px] overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-white border-b border-gray-200 text-gray-500 font-semibold sticky top-0">
                  <tr>
                    <th className="py-2 px-3">#</th>
                    <th className="py-2 px-3">Text</th>
                    <th className="py-2 px-3 text-right">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {result.ocr_blocks?.map((block) => (
                    <tr 
                      key={block.id}
                      onClick={() => setSelectedBlock(block.id)}
                      className={`cursor-pointer ${selectedBlock === block.id ? 'bg-blue-50 font-semibold text-blue-900' : 'hover:bg-white'}`}
                    >
                      <td className="py-1.5 px-3 font-mono text-gray-400">#{block.id}</td>
                      <td className="py-1.5 px-3 text-gray-900 truncate max-w-xs">{block.text}</td>
                      <td className="py-1.5 px-3 text-right font-mono text-gray-600">
                        {(block.confidence * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 3: Raw Text --- */}
      {activeTab === 'raw' && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-gray-900 uppercase">Raw Extracted OCR Text</h3>
            <button onClick={handleCopyText} className="text-xs text-gray-600 hover:text-gray-900 underline">
              {copied ? 'Copied' : 'Copy Text'}
            </button>
          </div>

          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 font-mono text-xs text-gray-800 whitespace-pre-wrap leading-relaxed">
            {result.raw_text || <span className="text-gray-400 italic">No text extracted.</span>}
          </div>
        </div>
      )}

    </div>
  );
}
