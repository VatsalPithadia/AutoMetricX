import React, { useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function OCRResultView({ result, imagePreviewUrl, sidePreviewUrls, onResetScan }) {
  const [copied, setCopied] = useState(false);
  const [showBoxes, setShowBoxes] = useState(true);
  const [selectedBlock, setSelectedBlock] = useState(null);
  const [activeTab, setActiveTab] = useState('compliance'); // 'compliance' | 'search' | 'overlay' | 'raw'
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [activeSideIdx, setActiveSideIdx] = useState(0); // For multi-side overlay tab
  const [inspectingCode, setInspectingCode] = useState(null); // Modal state for QR / Barcode inspection
  const [qrCopied, setQrCopied] = useState(false);

  if (!result) return null;

  const isMultiSide = result.is_multiside === true && result.total_sides > 1;
  const sideImages = result.side_images || [];

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const res = await fetch(`${API_BASE_URL}/export-pdf`, {
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

  const handleCopyQr = (text) => {
    navigator.clipboard.writeText(text);
    setQrCopied(true);
    setTimeout(() => setQrCopied(false), 2000);
  };

  const report = result.compliance_report || {};
  const classified = result.classified_fields || {};
  const declarations = report.declarations || [];
  const deepSearch = classified.deep_search_details || {};
  const detectedLangs = result.detected_languages || classified.detected_languages || ['English'];
  const hasVertical = result.has_vertical_text || false;
  const barcodeAnalysis = result.barcode_qr_analysis || {};
  const decodedCodes = barcodeAnalysis.decoded_codes || [];

  // Determine which image + blocks to show in overlay tab
  const activeOverlaySide = isMultiSide && sideImages.length > activeSideIdx
    ? sideImages[activeSideIdx]
    : null;
  const overlayImageUrl = isMultiSide && activeOverlaySide
    ? (sidePreviewUrls?.[activeSideIdx] || `${API_BASE_URL}/uploads/${activeOverlaySide.saved_file}`)
    : imagePreviewUrl;
  const overlayBlocks = isMultiSide && activeOverlaySide
    ? activeOverlaySide.ocr_blocks || []
    : (result.ocr_blocks || []);
  const overlayMeta = isMultiSide && activeOverlaySide
    ? activeOverlaySide.image_metadata || result.image_metadata || { width: 600, height: 400 }
    : result.image_metadata || { width: 600, height: 400 };

  const getStatusBadge = (status) => {
    if (status === 'COMPLIANT' || status === 'PASS') {
      return { bg: 'bg-emerald-50 text-emerald-700 border-emerald-200', badge: 'bg-emerald-600 text-white', label: 'PASS' };
    } else if (status === 'WARNING' || status === 'PARTIALLY_COMPLIANT' || status === 'LOW_CONFIDENCE') {
      return { bg: 'bg-amber-50 text-amber-700 border-amber-200', badge: 'bg-amber-600 text-white', label: 'WARNING' };
    } else {
      return { bg: 'bg-rose-50 text-rose-700 border-rose-200', badge: 'bg-rose-600 text-white', label: 'FAIL' };
    }
  };

  const formatLangName = (l) => {
    if (l === 'gu' || l === 'Gujarati') return 'Gujarati (ગુજરાતી)';
    if (l === 'hi' || l === 'Hindi') return 'Hindi (हिन्दी)';
    return 'English';
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      
      {/* Top Header Card */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm">
        
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xl font-bold text-gray-900">Inspection Report</h2>
              <span className={`text-xs px-2.5 py-0.5 rounded font-bold uppercase ${getStatusBadge(report.overall_status).badge}`}>
                {report.overall_status || 'NON_COMPLIANT'}
              </span>
              {isMultiSide && (
                <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 border border-blue-200">
                  ◈ {result.total_sides}-Side Audit
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 font-mono mt-0.5">
              {isMultiSide
                ? `${result.total_sides} package sides scanned • Score: ${report.compliance_score || 0}% (${report.passed_rules_count || 0}/${report.total_rules_checked || 8} Rules Passed)`
                : `File: ${result.filename} • Score: ${report.compliance_score || 0}% (${report.passed_rules_count || 0}/${report.total_rules_checked || 8} Rules Passed)`
              }
            </p>

            {/* Language & Orientation Tags */}
            <div className="flex items-center gap-1.5 flex-wrap mt-2">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Detected:</span>
              {detectedLangs.map((lang) => (
                <span key={lang} className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                  🌐 {formatLangName(lang)}
                </span>
              ))}
              {hasVertical && (
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-purple-50 text-purple-700 border border-purple-200">
                  ↕ Vertical Format Captured
                </span>
              )}
            </div>
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

        {/* Multi-Side Consistency Info */}
        {isMultiSide && result.product_consistency && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800">
            <span className="font-bold shrink-0">✓ Same-Product Verified:</span>
            <span>{result.product_consistency.message}</span>
          </div>
        )}

        {/* Navigation Tabs */}
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
            onClick={() => setActiveTab('search')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
              activeTab === 'search' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            Deep Extraction Search
          </button>
          <button
            onClick={() => setActiveTab('overlay')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer ${
              activeTab === 'overlay' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            {isMultiSide ? `Label Images (${result.total_sides} Sides)` : 'Label Image & Overlay'}
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
          
          {/* FSSAI License & Barcode / QR Code Box */}
          <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/50 space-y-3 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-emerald-600 text-white font-bold text-xs uppercase tracking-wider">
                  FSSAI & QR
                </span>
                <div>
                  <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">FSSAI License & Smart QR Code Verification</h3>
                  <p className="text-[11px] text-gray-500">Food Safety Authority (FSSAI) & GS1 Digital Label Cross-Check</p>
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
              {/* FSSAI Card */}
              <div className="p-3 rounded-lg bg-white border border-emerald-100 shadow-2xs space-y-1">
                <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">FSSAI License No.</div>
                <div className="font-mono font-bold text-emerald-700 text-sm truncate">
                  {classified.fssai_number?.license_number || classified.fssai_number?.raw_text || (
                    <span className="text-amber-600 text-xs italic font-normal">Not Detected</span>
                  )}
                </div>
                {classified.fssai_number?.license_number && (
                  <div className="text-[9px] text-emerald-600 font-medium">✓ 14-Digit Standard Format</div>
                )}
              </div>

              {/* 1D Barcode GTIN */}
              <div className="p-3 rounded-lg bg-white border border-emerald-100 shadow-2xs space-y-1">
                <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">1D Barcode GTIN</div>
                <div className="font-mono font-semibold text-gray-800 text-xs truncate">
                  {barcodeAnalysis.gtin_barcodes?.join(', ') || 'None Detected'}
                </div>
                <div className="text-[9px] text-gray-400">EAN-13 / UPC Retail Code</div>
              </div>

              {/* QR Code Link & Action */}
              <div className="p-3 rounded-lg bg-white border border-emerald-100 shadow-2xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Original QR Code Link</div>
                  {barcodeAnalysis.primary_qr_code?.recovery_method && (
                    <span className="text-[8px] bg-blue-50 text-blue-600 px-1 py-0.5 rounded font-mono">
                      {barcodeAnalysis.primary_qr_code.recovery_method.split(' ')[0]}
                    </span>
                  )}
                </div>

                {barcodeAnalysis.qr_urls && barcodeAnalysis.qr_urls.length > 0 ? (
                  <div className="space-y-1">
                    <a
                      href={barcodeAnalysis.qr_urls[0]}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-semibold text-blue-600 hover:text-blue-800 underline flex items-center gap-1 truncate"
                      title={barcodeAnalysis.qr_urls[0]}
                    >
                      <span>Open Link</span>
                      <span className="text-[10px]">↗</span>
                    </a>
                    <button
                      onClick={() => setInspectingCode(barcodeAnalysis.primary_qr_code || { data: barcodeAnalysis.qr_urls[0], type: 'QRCODE', is_url: true, original_url: barcodeAnalysis.qr_urls[0] })}
                      className="text-[10px] text-gray-500 hover:text-gray-900 underline cursor-pointer block"
                    >
                      Inspect Full Content
                    </button>
                  </div>
                ) : barcodeAnalysis.primary_qr_code ? (
                  <div className="space-y-1">
                    <div className="font-mono text-gray-800 text-xs truncate">
                      {barcodeAnalysis.primary_qr_code.data?.slice(0, 24)}...
                    </div>
                    <button
                      onClick={() => setInspectingCode(barcodeAnalysis.primary_qr_code)}
                      className="text-[10px] text-blue-600 hover:text-blue-800 underline font-semibold cursor-pointer block"
                    >
                      View QR Content
                    </button>
                  </div>
                ) : (
                  <div className="text-gray-400 text-xs italic">None Detected</div>
                )}
              </div>

              {/* Cross-Check Status */}
              <div className="p-3 rounded-lg bg-white border border-emerald-100 shadow-2xs space-y-1">
                <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Cross-Check Status</div>
                <div className="text-xs text-gray-700 font-medium leading-tight">
                  {barcodeAnalysis.fssai_cross_check?.explanation || 'FSSAI License & product declarations verified.'}
                </div>
              </div>
            </div>
          </div>

          {/* Extracted Fields Summary — direct classified field values */}
          <div className="p-4 rounded-xl border border-gray-200 bg-white space-y-3 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">Extracted Declaration Values</h3>
              {classified.unit_sale_price && (
                <span className="text-[11px] font-mono font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  USP: {classified.unit_sale_price}
                </span>
              )}
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 text-xs">
              {[
                { key: 'commodity_name', label: 'Commodity Name', getValue: (f) => f?.clean_name || f?.raw_text },
                { key: 'net_quantity', label: 'Net Quantity', getValue: (f) => f?.formatted_value || f?.raw_text },
                { key: 'mrp', label: 'MRP', getValue: (f) => f?.formatted_value || f?.raw_text },
                { key: 'mfg_date', label: 'Mfg / Packing Date', getValue: (f) => f?.extracted_date || f?.raw_text },
                { key: 'expiry_date', label: 'Expiry / Best Before', getValue: (f) => f?.extracted_date || f?.raw_text },
                { key: 'manufacturer_details', label: 'Manufacturer / Packer', getValue: (f) => f?.raw_text },
                { key: 'consumer_care', label: 'Consumer Care', getValue: (f) => f?.raw_text },
                { key: 'fssai_number', label: 'FSSAI License', getValue: (f) => f?.license_number || f?.raw_text },
              ].map(({ key, label, getValue }) => {
                const fieldObj = classified[key];
                const value = fieldObj ? getValue(fieldObj) : null;
                return (
                  <div key={key} className="p-2.5 rounded-lg border border-gray-100 bg-gray-50 space-y-1">
                    <div className="text-[10px] font-bold uppercase text-gray-400 tracking-wider">{label}</div>
                    <div className={`text-xs font-semibold leading-snug ${value ? 'text-gray-900' : 'text-gray-400 italic font-normal'}`}>
                      {value
                        ? (value.length > 80 ? value.slice(0, 80) + '…' : value)
                        : 'Not Detected'}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Legal Metrology Rules Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {declarations.map((decl, idx) => {
              const st = getStatusBadge(decl.status);
              return (
                <div key={idx} className="p-4 rounded-xl border border-gray-200 bg-white space-y-2 shadow-2xs">
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
                    <div className="text-[10px] font-medium text-gray-400 uppercase">Detected Value</div>
                    <div className="text-xs font-mono font-semibold text-gray-800 truncate">
                      {decl.found_value || <span className="text-gray-400 font-normal italic">Not Found</span>}
                    </div>
                  </div>

                  <p className="text-xs text-gray-600 leading-snug">{decl.explanation}</p>
                </div>
              );
            })}
          </div>

        </div>
      )}

      {/* --- TAB 2: Deep Extraction Search Breakdown --- */}
      {activeTab === 'search' && (
        <div className="space-y-4">
          <div className="p-4 bg-white border border-gray-200 rounded-xl space-y-2">
            <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
              Deep Contextual Extraction Search Breakdown
            </h3>
            <p className="text-xs text-gray-500">
              Specialized search extractors covering Consumer Care, Manufacturer GIDC details, FSSAI licenses,
              multilingual labels (Gujarati & Hindi), and variable date/batch strips.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            
            {/* 1. Consumer Care Search Card */}
            <div className="p-4 bg-white border border-gray-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="p-1 rounded bg-blue-50 text-blue-600 font-bold text-xs">📞</span>
                  <h4 className="text-xs font-bold text-gray-900 uppercase">Consumer Care Extraction Search</h4>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${classified.consumer_care ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                  {classified.consumer_care ? 'FOUND' : 'MISSING'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div><span className="font-semibold text-gray-500">Toll-Free / Phone:</span> <span className="font-mono">{deepSearch.consumer_care?.toll_free || deepSearch.consumer_care?.phone || 'Not isolated'}</span></div>
                <div><span className="font-semibold text-gray-500">Email Contact:</span> <span className="font-mono">{deepSearch.consumer_care?.email || 'Not isolated'}</span></div>
                <div><span className="font-semibold text-gray-500">Executive / Cell:</span> {deepSearch.consumer_care?.officer_title || 'Customer Care Cell'}</div>
                <div className="pt-1 text-[11px] text-gray-600 border-t border-gray-200 mt-1">
                  <span className="font-semibold">Raw Text:</span> {classified.consumer_care?.raw_text || 'None'}
                </div>
              </div>
            </div>

            {/* 2. Manufacturer Details Search Card */}
            <div className="p-4 bg-white border border-gray-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="p-1 rounded bg-amber-50 text-amber-600 font-bold text-xs">🏭</span>
                  <h4 className="text-xs font-bold text-gray-900 uppercase">Manufacturer Details Search</h4>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${classified.manufacturer_details ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                  {classified.manufacturer_details ? 'FOUND' : 'MISSING'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div><span className="font-semibold text-gray-500">Company:</span> {deepSearch.manufacturer?.company_name || 'Declared Entity'}</div>
                <div><span className="font-semibold text-gray-500">PIN Code:</span> <span className="font-mono font-bold">{deepSearch.manufacturer?.pin_code || 'None'}</span></div>
                <div className="pt-1 text-[11px] text-gray-600 border-t border-gray-200 mt-1">
                  <span className="font-semibold">Complete Address:</span> {classified.manufacturer_details?.raw_text || 'None'}
                </div>
              </div>
            </div>

            {/* 3. FSSAI License Search Card */}
            <div className="p-4 bg-white border border-gray-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="p-1 rounded bg-emerald-50 text-emerald-600 font-bold text-xs">🛡️</span>
                  <h4 className="text-xs font-bold text-gray-900 uppercase">FSSAI License Extraction Search</h4>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${classified.fssai_number?.license_number ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                  {classified.fssai_number?.license_number ? '14-DIGIT VERIFIED' : 'NOT FOUND'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div><span className="font-semibold text-gray-500">License Number:</span> <span className="font-mono font-bold text-emerald-700">{classified.fssai_number?.license_number || 'None'}</span></div>
                <div><span className="font-semibold text-gray-500">Barcode Cross-Check:</span> {barcodeAnalysis.fssai_cross_check?.status || 'NOT_CHECKED'}</div>
              </div>
            </div>

            {/* 4. Mfg & Expiry Date Search Card */}
            <div className="p-4 bg-white border border-gray-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="p-1 rounded bg-purple-50 text-purple-600 font-bold text-xs">📅</span>
                  <h4 className="text-xs font-bold text-gray-900 uppercase">Mfg & Expiry Date Search</h4>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${classified.mfg_date ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                  {classified.mfg_date ? 'FOUND' : 'MISSING'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div><span className="font-semibold text-gray-500">Mfg / Packing Date:</span> <span className="font-mono font-bold">{classified.mfg_date?.extracted_date || classified.mfg_date?.raw_text || 'None'}</span></div>
                <div><span className="font-semibold text-gray-500">Expiry / Best Before:</span> <span className="font-mono font-bold">{classified.expiry_date?.extracted_date || classified.expiry_date?.raw_text || 'None'}</span></div>
                <div><span className="font-semibold text-gray-500">Batch / Lot Code:</span> <span className="font-mono">{deepSearch.dates?.batch_number || classified.batch_number || 'None'}</span></div>
              </div>
            </div>

            {/* 5. MRP & Net Quantity Search Card */}
            <div className="p-4 bg-white border border-gray-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="p-1 rounded bg-teal-50 text-teal-600 font-bold text-xs">₹</span>
                  <h4 className="text-xs font-bold text-gray-900 uppercase">MRP & Unit Sale Price Context Search</h4>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${classified.mrp ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                  {classified.mrp ? 'FOUND' : 'MISSING'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div><span className="font-semibold text-gray-500">Maximum Retail Price:</span> <span className="font-mono font-bold text-gray-900">{classified.mrp?.formatted_value || classified.mrp?.raw_text || 'None'}</span></div>
                <div><span className="font-semibold text-gray-500">Unit Sale Price (USP):</span> <span className="font-mono font-bold text-emerald-700">{classified.unit_sale_price || deepSearch.mrp?.usp || 'None'}</span></div>
                <div><span className="font-semibold text-gray-500">Tax Clause Included:</span> {classified.mrp?.has_tax_clause ? '✓ Yes (Incl. of all taxes)' : '⚠️ Not Explicit'}</div>
              </div>
            </div>

            {/* 6. Net Quantity Context Search Card */}
            <div className="p-4 bg-white border border-gray-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="p-1 rounded bg-indigo-50 text-indigo-600 font-bold text-xs">⚖️</span>
                  <h4 className="text-xs font-bold text-gray-900 uppercase">Net Quantity Context Search</h4>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${classified.net_quantity ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                  {classified.net_quantity ? 'FOUND' : 'MISSING'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-100">
                <div><span className="font-semibold text-gray-500">Declared Quantity:</span> <span className="font-mono font-bold">{classified.net_quantity?.formatted_value || classified.net_quantity?.raw_text || 'None'}</span></div>
                <div><span className="font-semibold text-gray-500">Standard Unit:</span> {classified.net_quantity?.unit ? `✓ Standard (${classified.net_quantity.unit})` : 'None'}</div>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* --- TAB 3: Label Image & Bounding Boxes --- */}
      {activeTab === 'overlay' && (
        <div className="space-y-4">

          {/* Side Selector for Multi-Side */}
          {isMultiSide && sideImages.length > 1 && (
            <div className="flex items-center gap-2 p-3 bg-white border border-gray-200 rounded-xl">
              <span className="text-xs text-gray-500 font-medium shrink-0">View Side:</span>
              <div className="flex gap-2 flex-wrap">
                {sideImages.map((side, idx) => (
                  <button
                    key={idx}
                    onClick={() => { setActiveSideIdx(idx); setSelectedBlock(null); }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                      activeSideIdx === idx
                        ? 'bg-gray-900 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    Side {idx + 1}{side.filename ? ` (${side.filename.split('.')[0].slice(-12)})` : ''}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-6 bg-white border border-gray-200 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-gray-900 uppercase">
                  {isMultiSide ? `Side ${activeSideIdx + 1} Image Overlay` : 'Image Overlay'}
                </h3>
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
                    src={overlayImageUrl}
                    alt={isMultiSide ? `Package Side ${activeSideIdx + 1}` : 'Analyzed Label'}
                    className="max-h-[400px] object-contain rounded block"
                  />

                  {showBoxes && overlayBlocks.length > 0 && (
                    <svg
                      className="absolute inset-0 w-full h-full pointer-events-none"
                      viewBox={`0 0 ${overlayMeta.width} ${overlayMeta.height}`}
                      preserveAspectRatio="xMidYMid meet"
                    >
                      {overlayBlocks.map((block) => {
                        const isSelected = selectedBlock === block.id;
                        const r = block.rect || { x: 0, y: 0, width: 50, height: 20 };
                        const isVert = block.is_vertical;
                        return (
                          <g key={block.id} className="pointer-events-auto cursor-pointer" onClick={() => setSelectedBlock(block.id)}>
                            <rect
                              x={r.x}
                              y={r.y}
                              width={r.width}
                              height={r.height}
                              fill={isSelected ? 'rgba(37, 99, 235, 0.25)' : (isVert ? 'rgba(168, 85, 247, 0.2)' : 'rgba(16, 185, 129, 0.15)')}
                              stroke={isSelected ? '#2563eb' : (isVert ? '#a855f7' : '#10b981')}
                              strokeWidth={Math.max(2, Math.round(overlayMeta.width / 400))}
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
              <h3 className="text-xs font-bold text-gray-900 uppercase">
                Detected Text Regions ({overlayBlocks.length})
              </h3>

              <div className="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden max-h-[400px] overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white border-b border-gray-200 text-gray-500 font-semibold sticky top-0">
                    <tr>
                      <th className="py-2 px-3">#</th>
                      <th className="py-2 px-3">Text</th>
                      <th className="py-2 px-3">Tag</th>
                      <th className="py-2 px-3 text-right">Conf</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {overlayBlocks.map((block) => (
                      <tr
                        key={block.id}
                        onClick={() => setSelectedBlock(block.id)}
                        className={`cursor-pointer ${selectedBlock === block.id ? 'bg-blue-50 font-semibold text-blue-900' : 'hover:bg-white'}`}
                      >
                        <td className="py-1.5 px-3 font-mono text-gray-400">#{block.id}</td>
                        <td className="py-1.5 px-3 text-gray-900 truncate max-w-[180px]">{block.text}</td>
                        <td className="py-1.5 px-3">
                          {block.is_vertical && (
                            <span className="text-[9px] bg-purple-100 text-purple-800 px-1 rounded font-bold mr-1">
                              ↕ VERT
                            </span>
                          )}
                          {block.lang && block.lang !== 'en' && (
                            <span className="text-[9px] bg-indigo-100 text-indigo-800 px-1 rounded font-bold uppercase">
                              {block.lang}
                            </span>
                          )}
                        </td>
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
        </div>
      )}

      {/* --- TAB 4: Raw Text --- */}
      {activeTab === 'raw' && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-gray-900 uppercase">
              Raw Extracted OCR Text{isMultiSide ? ` (All ${result.total_sides} Sides Combined)` : ''}
            </h3>
            <button onClick={handleCopyText} className="text-xs text-gray-600 hover:text-gray-900 underline">
              {copied ? 'Copied' : 'Copy Text'}
            </button>
          </div>

          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 font-mono text-xs text-gray-800 whitespace-pre-wrap leading-relaxed">
            {result.raw_text || <span className="text-gray-400 italic">No text extracted.</span>}
          </div>
        </div>
      )}

      {/* --- QR Code & Barcode Content Inspection Modal --- */}
      {inspectingCode && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-xl border border-gray-100 animate-in fade-in duration-150">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div className="flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-emerald-600 text-white font-bold text-xs">QR</span>
                <div>
                  <h3 className="text-sm font-bold text-gray-900">QR Code Content Inspector</h3>
                  <p className="text-[11px] text-gray-500">Decoded Payload & Original Link Details</p>
                </div>
              </div>
              <button
                onClick={() => setInspectingCode(null)}
                className="text-gray-400 hover:text-gray-600 text-lg leading-none cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Format & Engine</span>
                <div className="font-mono text-gray-800 mt-0.5">
                  {inspectingCode.format || inspectingCode.type} • {inspectingCode.engine || 'ZXing-C++ / PyZbar'}
                </div>
              </div>

              {inspectingCode.is_url && inspectingCode.original_url && (
                <div>
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Original Clickable Link</span>
                  <div className="mt-1 flex items-center gap-2">
                    <a
                      href={inspectingCode.original_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg font-semibold flex items-center gap-1.5 text-xs truncate max-w-sm"
                    >
                      <span>{inspectingCode.original_url}</span>
                      <span>↗</span>
                    </a>
                  </div>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Raw Payload Data</span>
                  <button
                    onClick={() => handleCopyQr(inspectingCode.data || inspectingCode.original_url)}
                    className="text-[10px] text-blue-600 hover:underline"
                  >
                    {qrCopied ? 'Copied!' : 'Copy Data'}
                  </button>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 font-mono text-xs text-gray-800 break-all max-h-40 overflow-y-auto mt-1">
                  {inspectingCode.data || inspectingCode.original_url}
                </div>
              </div>

              {inspectingCode.parsed_attributes && Object.keys(inspectingCode.parsed_attributes).length > 0 && (
                <div>
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Parsed Parameters</span>
                  <div className="p-2 bg-gray-50 rounded-lg border border-gray-200 space-y-1 font-mono text-[11px] mt-1">
                    {Object.entries(inspectingCode.parsed_attributes).map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-gray-500">{k}:</span>
                        <span className="font-bold text-gray-800">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-gray-100">
              <button
                onClick={() => setInspectingCode(null)}
                className="px-4 py-1.5 rounded-lg bg-gray-900 text-white text-xs font-semibold hover:bg-gray-800 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
