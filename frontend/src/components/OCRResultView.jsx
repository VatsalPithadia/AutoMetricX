import React, { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function OCRResultView({ result, imagePreviewUrl, sidePreviewUrls, onResetScan }) {
  const [copied, setCopied] = useState(false);
  const [showBoxes, setShowBoxes] = useState(true);
  const [selectedBlock, setSelectedBlock] = useState(null);
  const [activeTab, setActiveTab] = useState('compliance'); // 'compliance' | 'ingredients' | 'overlay' | 'raw'
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [activeSideIdx, setActiveSideIdx] = useState(0); // For multi-side overlay tab
  const [inspectingCode, setInspectingCode] = useState(null); // Modal state for QR / Barcode inspection
  const [qrCopied, setQrCopied] = useState(false);

  // Ingredient Safety State
  const [ingredientSafety, setIngredientSafety] = useState(result?.ingredient_safety || null);
  const [customIngredientsInput, setCustomIngredientsInput] = useState(result?.ingredient_safety?.raw_ingredients_text || '');
  const [isReChecking, setIsReChecking] = useState(false);
  const [selectedChipHazard, setSelectedChipHazard] = useState(null);

  useEffect(() => {
    setIngredientSafety(result?.ingredient_safety || null);
    setCustomIngredientsInput(result?.ingredient_safety?.raw_ingredients_text || '');
    setSelectedChipHazard(null);
  }, [result]);

  const handleReCheckIngredients = async () => {
    if (!customIngredientsInput.trim()) return;
    setIsReChecking(true);
    try {
      const res = await fetch(`${API_BASE_URL}/check-ingredients`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ingredients_text: customIngredientsInput.trim(),
          product_name: result.product_name || 'Scanned Product'
        })
      });
      if (!res.ok) throw new Error('Ingredient re-check failed');
      const data = await res.json();
      setIngredientSafety(data);
      setSelectedChipHazard(null);
    } catch (err) {
      console.error('Ingredient re-check error:', err);
      alert('Could not re-evaluate ingredients: ' + err.message);
    } finally {
      setIsReChecking(false);
    }
  };

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
  const barcodeAnalysis = result.barcode_qr_analysis || {};

  // Determine which image + blocks to show in overlay tab
  const activeOverlaySide = isMultiSide && sideImages.length > activeSideIdx
    ? sideImages[activeSideIdx]
    : null;
  const overlayImageUrl = isMultiSide && activeOverlaySide
    ? (sidePreviewUrls?.[activeSideIdx] || `${API_BASE_URL}/uploads/${activeOverlaySide.saved_file || activeOverlaySide.filename}`)
    : (imagePreviewUrl || (result.saved_file ? `${API_BASE_URL}/uploads/${result.saved_file}` : (result.image_filename ? `${API_BASE_URL}/uploads/${result.image_filename}` : (result.filename ? `${API_BASE_URL}/uploads/${result.filename}` : null))));
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


  const legibility = report.font_legibility_analysis;
  const rule9 = legibility?.rule_9_1_mrp_prominence;

  const declaredWeightStr = legibility?.declared_net_quantity ||
    classified.net_quantity?.formatted_value ||
    classified.net_quantity?.raw_text ||
    (classified.net_quantity?.numeric_value ? `${classified.net_quantity.numeric_value} ${classified.net_quantity.unit || 'g'}` : 'Not Isolated');

  const detectedCategoryStr = legibility?.product_category ||
    (classified.commodity_name?.clean_name || classified.commodity_name?.raw_text || 'Packaged Commodity');


  const getFieldLabel = (field) => {
    switch (field) {
      case 'net_quantity': return 'Net Quantity';
      case 'mrp': return 'Maximum Retail Price (MRP)';
      case 'mfg_date': return 'Mfg / Packing Date';
      case 'expiry_date': return 'Expiry / Best Before';
      case 'commodity_name': return 'Commodity Name';
      case 'manufacturer_details': return 'Manufacturer / Packer';
      case 'consumer_care': return 'Consumer Care Contact';
      default: return field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    }
  };

  const renderFontHeightBox = () => {
    if (!legibility) return null;

    const minReq = legibility.min_required_letter_height_mm || 1.0;
    const evaluations = legibility.rule_7_3_field_evaluations || [];
    const allPass = evaluations.length > 0 && evaluations.every((e) => e.status === 'PASS');

    return (
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm">
        {/* Section Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-800 font-bold text-xs">
              Rule 7 & 9
            </span>
            <h3 className="text-sm font-bold text-gray-900">Font Height (mm) Verification</h3>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs px-2.5 py-1 rounded-md bg-gray-100 text-gray-700 font-medium">
              Min Required: <strong className="text-gray-900">{minReq} mm</strong> ({declaredWeightStr})
            </span>
            <span className={`text-xs font-bold px-2.5 py-1 rounded-md ${allPass ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'
              }`}>
              {allPass ? '✓ ALL PASS' : '⚠️ REVIEW HEIGHTS'}
            </span>
          </div>
        </div>

        {/* Clean, Simple Table (No Icons, Plain & Direct) */}
        {evaluations.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Field</th>
                  <th className="py-2.5 px-3">Measured Size</th>
                  <th className="py-2.5 px-3">Statutory Min</th>
                  <th className="py-2.5 px-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-800">
                {evaluations.map((item, i) => {
                  const measured = item.font_height_mm;
                  const req = item.min_required_mm || minReq;
                  const isPass = item.status === 'PASS';

                  return (
                    <tr key={i} className="hover:bg-gray-50/50 transition-colors">
                      <td className="py-2.5 px-3 font-medium text-gray-900">
                        {getFieldLabel(item.field)}
                      </td>
                      <td className="py-2.5 px-3 font-mono font-bold text-gray-900 text-xs">
                        {measured != null ? `${measured} mm` : '—'}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-gray-600 text-xs">
                        {req} mm
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${isPass ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}>
                          {isPass ? 'PASS' : 'BELOW MIN'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Rule 9(1) MRP Prominence Note */}
        {rule9 && (
          <div className="p-3 rounded-lg border border-gray-200 bg-gray-50/80 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
            <div className="text-gray-700">
              <span className="font-bold text-gray-900">Rule 9(1) MRP Prominence: </span>
              <span>
                MRP height ({rule9.mrp_font_height_mm != null ? `${rule9.mrp_font_height_mm} mm` : '—'}) vs surrounding text ({rule9.avg_body_font_height_mm != null ? `${rule9.avg_body_font_height_mm} mm` : '—'}) • Ratio: <strong>{rule9.prominence_ratio || 1.0}x</strong> (Required: ≥ 1.20x)
              </span>
            </div>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase shrink-0 ${rule9.status === 'PASS' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'
              }`}>
              {rule9.status === 'PASS' ? 'PROMINENT' : 'LOW PROMINENCE'}
            </span>
          </div>
        )}
      </div>
    );
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
              {ingredientSafety && (
                <span
                  onClick={() => setActiveTab('ingredients')}
                  className={`text-xs px-2.5 py-0.5 rounded font-bold uppercase cursor-pointer transition-opacity hover:opacity-90 flex items-center gap-1.5 shadow-2xs ${
                    ingredientSafety.safety_verdict === 'SAFE'
                      ? 'bg-emerald-600 text-white'
                      : ingredientSafety.safety_verdict === 'CAUTION'
                      ? 'bg-amber-600 text-white'
                      : ingredientSafety.safety_verdict === 'HARMFUL'
                      ? 'bg-rose-600 text-white'
                      : 'bg-gray-200 text-gray-700'
                  }`}
                  title="Click to view Ingredient Safety report"
                >
                  {ingredientSafety.safety_verdict === 'SAFE' && '✓ SAFE TO CONSUME'}
                  {ingredientSafety.safety_verdict === 'CAUTION' && '⚠️ INGREDIENT CAUTION'}
                  {ingredientSafety.safety_verdict === 'HARMFUL' && '⚠️ HARMFUL INGREDIENTS'}
                  {ingredientSafety.safety_verdict === 'NOT_DETECTED' && 'Ingredients: Not Detected'}
                  {ingredientSafety.safety_score != null && ingredientSafety.safety_verdict !== 'NOT_DETECTED' && (
                    <span className="opacity-90 font-mono text-[11px]">({ingredientSafety.safety_score}/100)</span>
                  )}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 font-mono mt-0.5">
              {isMultiSide
                ? `${result.total_sides} package sides scanned`
                : `File: ${result.filename}`
              }
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

        {/* Multi-Side Consistency Info */}
        {isMultiSide && result.product_consistency && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800">
            <span className="font-bold shrink-0">✓ Same-Product Verified:</span>
            <span>{result.product_consistency.message}</span>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-gray-100 pb-1 flex-wrap">
          <button
            onClick={() => setActiveTab('compliance')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition-colors cursor-pointer ${activeTab === 'compliance' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
          >
            Compliance Declarations
          </button>
          <button
            onClick={() => setActiveTab('ingredients')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition-colors cursor-pointer flex items-center gap-1.5 ${activeTab === 'ingredients' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
          >
            <span>Ingredient Safety & Health</span>
            {ingredientSafety?.safety_verdict === 'HARMFUL' && (
              <span className="text-[10px] px-1.5 py-0.2 rounded font-bold bg-rose-500 text-white animate-pulse">
                HARMFUL
              </span>
            )}
            {ingredientSafety?.safety_verdict === 'CAUTION' && (
              <span className="text-[10px] px-1.5 py-0.2 rounded font-bold bg-amber-500 text-white">
                CAUTION
              </span>
            )}
            {ingredientSafety?.safety_verdict === 'SAFE' && (
              <span className="text-[10px] px-1.5 py-0.2 rounded font-bold bg-emerald-600 text-white">
                SAFE
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('overlay')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition-colors cursor-pointer ${activeTab === 'overlay' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
          >
            {isMultiSide ? `Label Image (${result.total_sides} Sides)` : 'Label Image'}
          </button>
          <button
            onClick={() => setActiveTab('raw')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-md transition-colors cursor-pointer ${activeTab === 'raw' ? 'bg-gray-900 text-white' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
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
              <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-full ${classified.fssai_number?.license_number || classified.fssai_number?.raw_text
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

          {/* Rules Box: Mandatory Declarations Compliance (Rule 6) */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-gray-900 text-white font-bold text-xs uppercase tracking-wider">
                  RULE 6
                </span>
                <div>
                  <h3 className="text-sm font-bold text-gray-900">Mandatory Declarations Compliance</h3>
                  <p className="text-xs text-gray-500">Verification of required label declarations under Legal Metrology Rules</p>
                </div>
              </div>
              {declarations.length > 0 && (
                <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-gray-100 text-gray-700">
                  {declarations.filter(d => !d.clause?.includes('Rule 7') && !d.clause?.includes('Rule 9') && (d.status === 'COMPLIANT' || d.status === 'PASS')).length} / {declarations.filter(d => !d.clause?.includes('Rule 7') && !d.clause?.includes('Rule 9')).length || declarations.length} Compliant
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(declarations.filter(d => !d.clause?.includes('Rule 7') && !d.clause?.includes('Rule 9')).length > 0
                ? declarations.filter(d => !d.clause?.includes('Rule 7') && !d.clause?.includes('Rule 9'))
                : declarations
              ).map((decl, idx) => {
                const st = getStatusBadge(decl.status);
                return (
                  <div key={idx} className="p-3.5 rounded-lg border border-gray-200 bg-gray-50/50 space-y-2 hover:bg-white transition-colors">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-gray-200 text-gray-700 shrink-0">
                          {decl.clause}
                        </span>
                        <h4 className="text-xs font-bold text-gray-900 truncate" title={decl.name}>{decl.name}</h4>
                      </div>
                      <span className={`text-[9px] font-extrabold px-2 py-0.5 rounded uppercase shrink-0 ${st.badge}`}>
                        {decl.status}
                      </span>
                    </div>

                    <div className="p-2 rounded bg-white border border-gray-200/80">
                      <div className="text-[9px] font-medium text-gray-400 uppercase">Detected Value</div>
                      <div className="text-xs font-mono font-semibold text-gray-800 truncate" title={decl.found_value}>
                        {decl.found_value || <span className="text-gray-400 font-normal italic">Not Found</span>}
                      </div>
                    </div>

                    <p className="text-[11px] text-gray-600 leading-relaxed">{decl.explanation}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Height (mm) Box: Font Size Legibility & Prominence (Rule 7 & 9) */}
          {renderFontHeightBox()}

        </div>
      )}

      {/* --- TAB 2: Ingredient Safety & Harm Analysis --- */}
      {activeTab === 'ingredients' && (
        <div className="space-y-6">

          {/* Hero Safety Verdict Card */}
          <div className={`p-5 rounded-xl border shadow-sm transition-all ${
            ingredientSafety?.safety_verdict === 'HARMFUL'
              ? 'bg-rose-50/70 border-rose-200'
              : ingredientSafety?.safety_verdict === 'CAUTION'
              ? 'bg-amber-50/70 border-amber-200'
              : ingredientSafety?.safety_verdict === 'SAFE'
              ? 'bg-emerald-50/70 border-emerald-200'
              : 'bg-gray-50 border-gray-200'
          }`}>
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-black/5">
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-2.5 py-1 rounded-md text-xs font-extrabold uppercase tracking-wide text-white ${
                    ingredientSafety?.safety_verdict === 'HARMFUL'
                      ? 'bg-rose-600'
                      : ingredientSafety?.safety_verdict === 'CAUTION'
                      ? 'bg-amber-600'
                      : ingredientSafety?.safety_verdict === 'SAFE'
                      ? 'bg-emerald-600'
                      : 'bg-gray-500'
                  }`}>
                    {ingredientSafety?.safety_verdict === 'HARMFUL' && '⚠️ HARMFUL PRODUCT DETECTED'}
                    {ingredientSafety?.safety_verdict === 'CAUTION' && '⚠️ MODERATE INGREDIENT CAUTION'}
                    {ingredientSafety?.safety_verdict === 'SAFE' && '✓ SAFE TO CONSUME'}
                    {ingredientSafety?.safety_verdict === 'NOT_DETECTED' && 'Ingredients Not Isolated'}
                  </span>
                  {ingredientSafety?.is_harmful && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-300">
                      High Health Hazard
                    </span>
                  )}
                </div>
                <h3 className="text-base font-bold text-gray-900">
                  Toxicological & Dietary Ingredient Health Check
                </h3>
                <p className="text-xs text-gray-700 leading-relaxed max-w-2xl">
                  {ingredientSafety?.summary || 'No ingredients detected on the label photo.'}
                </p>
              </div>

              {/* Score Meter */}
              <div className="flex items-center gap-3 bg-white/90 px-4 py-3 rounded-xl border border-black/5 shadow-2xs shrink-0">
                <div className="text-center">
                  <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Safety Score</div>
                  <div className={`text-2xl font-black font-mono leading-none mt-0.5 ${
                    ingredientSafety?.safety_score >= 75
                      ? 'text-emerald-600'
                      : ingredientSafety?.safety_score >= 50
                      ? 'text-amber-600'
                      : 'text-rose-600'
                  }`}>
                    {ingredientSafety?.safety_score ?? '—'}<span className="text-xs font-normal text-gray-400">/100</span>
                  </div>
                </div>
                <div className="w-12 h-2 bg-gray-200 rounded-full overflow-hidden shrink-0">
                  <div
                    className={`h-full rounded-full ${
                      ingredientSafety?.safety_score >= 75
                        ? 'bg-emerald-500'
                        : ingredientSafety?.safety_score >= 50
                        ? 'bg-amber-500'
                        : 'bg-rose-500'
                    }`}
                    style={{ width: `${Math.max(5, ingredientSafety?.safety_score || 0)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-4 text-xs">
              <div className="p-2.5 rounded-lg bg-white/80 border border-black/5">
                <div className="text-[10px] text-gray-500 font-semibold uppercase">Total Ingredients</div>
                <div className="text-base font-bold text-gray-900 mt-0.5">{ingredientSafety?.total_ingredients_count || 0}</div>
              </div>
              <div className="p-2.5 rounded-lg bg-white/80 border border-black/5">
                <div className="text-[10px] text-rose-600 font-semibold uppercase">High-Risk Harmful</div>
                <div className="text-base font-bold text-rose-700 mt-0.5">{ingredientSafety?.harmful_count || 0}</div>
              </div>
              <div className="p-2.5 rounded-lg bg-white/80 border border-black/5">
                <div className="text-[10px] text-amber-600 font-semibold uppercase">Moderate Caution</div>
                <div className="text-base font-bold text-amber-700 mt-0.5">{ingredientSafety?.caution_count || 0}</div>
              </div>
              <div className="p-2.5 rounded-lg bg-white/80 border border-black/5">
                <div className="text-[10px] text-emerald-600 font-semibold uppercase">Clean / Wholesome</div>
                <div className="text-base font-bold text-emerald-700 mt-0.5">{ingredientSafety?.safe_count || 0}</div>
              </div>
            </div>
          </div>

          {/* Flagged Harmful & Hazardous Ingredients Breakdown */}
          {ingredientSafety?.flagged_ingredients && ingredientSafety.flagged_ingredients.length > 0 && (
            <div className="bg-white border border-rose-200 rounded-xl p-5 space-y-4 shadow-sm">
              <div className="flex items-center justify-between pb-3 border-b border-gray-100">
                <div className="flex items-center gap-2">
                  <span className="p-1.5 rounded-lg bg-rose-600 text-white font-bold text-xs uppercase tracking-wider">
                    HAZARDS
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">
                      Identified Harmful Additives & Substances ({ingredientSafety.flagged_ingredients.length})
                    </h3>
                    <p className="text-xs text-gray-500">
                      Scientific toxicology risk assessment and regulatory bans/restrictions
                    </p>
                  </div>
                </div>
                <span className="text-xs font-bold px-2.5 py-1 rounded-md bg-rose-50 text-rose-700 border border-rose-200">
                  ⚠️ Action Required
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {ingredientSafety.flagged_ingredients.map((item, idx) => {
                  const isHigh = item.severity === 'HIGH';
                  return (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border transition-all space-y-2.5 ${
                        isHigh
                          ? 'bg-rose-50/40 border-rose-200 hover:border-rose-300'
                          : 'bg-amber-50/40 border-amber-200 hover:border-amber-300'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h4 className="text-sm font-bold text-gray-900">{item.name}</h4>
                          <span className="text-[11px] font-mono text-gray-500 font-semibold">{item.ins_code}</span>
                        </div>
                        <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded uppercase tracking-wider ${
                          isHigh ? 'bg-rose-600 text-white' : 'bg-amber-500 text-white'
                        }`}>
                          {item.severity === 'HIGH' ? 'HIGH RISK' : 'MODERATE RISK'}
                        </span>
                      </div>

                      <div className="space-y-1.5 text-xs">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Hazard:</span>
                          <span className="font-semibold text-gray-800">{item.hazard_type}</span>
                        </div>

                        <div className="p-2 rounded-lg bg-white border border-gray-200/80 text-[11px] text-gray-700 leading-relaxed">
                          {item.risk_explanation}
                        </div>

                        <div className="flex items-center gap-1 text-[11px] text-rose-700 font-medium pt-0.5">
                          <span className="font-bold">Regulatory Alert:</span>
                          <span>{item.regulatory_status}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Clean Ingredients Notice if No Hazards */}
          {ingredientSafety?.has_ingredients && (!ingredientSafety.flagged_ingredients || ingredientSafety.flagged_ingredients.length === 0) && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-sm shrink-0">
                ✓
              </div>
              <div className="text-xs">
                <h4 className="font-bold text-emerald-900">Clean Ingredient Profile</h4>
                <p className="text-emerald-800 mt-0.5">
                  No toxic additives, industrial trans fats, banned carcinogens, or synthetic azo dyes were detected in the ingredients list.
                </p>
              </div>
            </div>
          )}

          {/* Recognized Food Allergens Notice */}
          {ingredientSafety?.allergens_detected && ingredientSafety.allergens_detected.length > 0 && (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-amber-600 text-white font-bold text-[10px] uppercase">
                    ALLERGEN ALERT
                  </span>
                  <h4 className="text-xs font-bold text-amber-950">
                    Recognized Food Allergens Detected ({ingredientSafety.allergens_detected.length})
                  </h4>
                </div>
                <span className="text-[11px] text-amber-800 font-medium">FSSAI Schedule II Declaration</span>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                {ingredientSafety.allergens_detected.map((a, i) => (
                  <div key={i} className="px-3 py-1.5 rounded-lg bg-white border border-amber-200 text-xs shadow-2xs space-y-0.5">
                    <span className="font-bold text-amber-900">{a.allergen}</span>
                    <span className="block text-[10px] text-gray-500">{a.risk}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Health & Consumer Recommendations */}
          {ingredientSafety?.health_recommendations && ingredientSafety.health_recommendations.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3 shadow-sm">
              <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                Clinical Health Guidance & Consumer Advice
              </h4>
              <ul className="space-y-2 text-xs text-gray-700">
                {ingredientSafety.health_recommendations.map((rec, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-emerald-600 font-bold mt-0.5">•</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* All Detected Ingredients (Interactive Color-Coded Chips) */}
          {ingredientSafety?.all_ingredients && ingredientSafety.all_ingredients.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3 shadow-sm">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                  Extracted Ingredients Breakdown ({ingredientSafety.all_ingredients.length})
                </h4>
                <div className="flex items-center gap-3 text-[10px] font-semibold text-gray-500">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-500" /> Harmful</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Caution</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Safe</span>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {ingredientSafety.all_ingredients.map((item, idx) => {
                  const isHarmful = item.status === 'HARMFUL';
                  const isCaution = item.status === 'CAUTION';
                  const isSelected = selectedChipHazard === item.ingredient;

                  return (
                    <button
                      key={idx}
                      onClick={() => setSelectedChipHazard(isSelected ? null : item.ingredient)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border ${
                        isHarmful
                          ? 'bg-rose-50 text-rose-800 border-rose-300 hover:bg-rose-100 font-semibold'
                          : isCaution
                          ? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100 font-semibold'
                          : 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100'
                      } ${isSelected ? 'ring-2 ring-gray-900 shadow-sm' : ''}`}
                    >
                      <span>{item.ingredient}</span>
                      {isHarmful && <span className="ml-1 text-[10px]">⚠️</span>}
                      {isCaution && <span className="ml-1 text-[10px]">⚠️</span>}
                      {!isHarmful && !isCaution && <span className="ml-1 text-[10px]">✓</span>}
                    </button>
                  );
                })}
              </div>

              {/* Selected Chip Details Popdown */}
              {selectedChipHazard && (
                <div className="p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs mt-2 animate-in fade-in duration-100">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-gray-900">Selected: {selectedChipHazard}</span>
                    <button onClick={() => setSelectedChipHazard(null)} className="text-gray-400 hover:text-gray-600 text-xs">✕</button>
                  </div>
                  {(() => {
                    const matched = ingredientSafety.all_ingredients.find(i => i.ingredient === selectedChipHazard);
                    if (matched?.hazard) {
                      return (
                        <div className="space-y-1 text-gray-700">
                          <div><strong className="text-rose-700">Hazard:</strong> {matched.hazard.hazard_type} ({matched.hazard.severity} Risk)</div>
                          <div><strong className="text-gray-800">Health Impact:</strong> {matched.hazard.risk_explanation}</div>
                          <div><strong className="text-gray-800">Regulatory Status:</strong> {matched.hazard.regulatory_status}</div>
                        </div>
                      );
                    }
                    return <div className="text-emerald-700">Wholesome / Natural ingredient with no recognized toxic additives or synthetic dyes.</div>;
                  })()}
                </div>
              )}
            </div>
          )}

          {/* Live Ingredient Re-Check & Custom Verifier Box */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-gray-100">
              <div>
                <h4 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                  Interactive Ingredient Verifier & Custom Tester
                </h4>
                <p className="text-[11px] text-gray-500">
                  Edit detected text or paste ingredients from any package label to test in real-time
                </p>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => setCustomIngredientsInput('Refined Wheat Flour, Palm Oil, TBHQ (INS 319), Tartrazine (INS 102), MSG (INS 621), Partially Hydrogenated Vegetable Oil, Salt')}
                  className="text-[10px] text-rose-700 bg-rose-50 hover:bg-rose-100 px-2 py-1 rounded font-semibold transition-colors cursor-pointer"
                >
                  Preset: Harmful Snack (TBHQ + Palm Oil)
                </button>
                <button
                  type="button"
                  onClick={() => setCustomIngredientsInput('100% Organic Rolled Oats, Raw Honey, Roasted Almonds, Whole Chia Seeds, Natural Vanilla Extract')}
                  className="text-[10px] text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-2 py-1 rounded font-semibold transition-colors cursor-pointer"
                >
                  Preset: 100% Clean Organic
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <textarea
                value={customIngredientsInput}
                onChange={(e) => setCustomIngredientsInput(e.target.value)}
                placeholder="e.g. Wheat Flour (54%), Palm Oil, Artificial Color (INS 102), Antioxidant (TBHQ), Salt..."
                rows={3}
                className="w-full p-3 rounded-lg border border-gray-300 font-mono text-xs text-gray-900 focus:outline-none focus:border-gray-900 leading-relaxed"
              />

              <div className="flex items-center justify-between gap-3 flex-wrap">
                <span className="text-[11px] text-gray-400">
                  Evaluates against 150+ chemical food additives, INS codes, trans fats, and allergens.
                </span>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setCustomIngredientsInput(result?.ingredient_safety?.raw_ingredients_text || '')}
                    className="px-3 py-1.5 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 text-xs font-medium cursor-pointer"
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    onClick={handleReCheckIngredients}
                    disabled={isReChecking || !customIngredientsInput.trim()}
                    className="px-4 py-1.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-white text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isReChecking ? 'Evaluating...' : 'Re-Evaluate Ingredients'}
                  </button>
                </div>
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
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${activeSideIdx === idx
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
                        return (
                          <g key={block.id} className="pointer-events-auto cursor-pointer" onClick={() => setSelectedBlock(block.id)}>
                            <rect
                              x={r.x}
                              y={r.y}
                              width={r.width}
                              height={r.height}
                              fill={isSelected ? 'rgba(37, 99, 235, 0.25)' : 'rgba(16, 185, 129, 0.15)'}
                              stroke={isSelected ? '#2563eb' : '#10b981'}
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
                        <td className="py-1.5 px-3 text-gray-900 truncate max-w-[240px]">{block.text}</td>
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
