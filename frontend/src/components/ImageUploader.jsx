import React, { useState, useRef } from 'react';

export default function ImageUploader({ selectedImages = [], onImagesSelected, onStartScan, isScanning }) {
  const [isDragging, setIsDragging] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const fileInputRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processFiles(Array.from(e.target.files));
      e.target.value = ''; // Reset input to allow re-selecting same file
    }
  };

  const processFiles = (fileList) => {
    const validImageFiles = fileList.filter(f => f.type.startsWith('image/'));
    if (validImageFiles.length === 0) {
      alert('Please select valid image files (JPEG, PNG, WEBP).');
      return;
    }

    // Enforce maximum 5 images limit
    const remainingSlots = 5 - selectedImages.length;
    if (remainingSlots <= 0) {
      alert('Maximum 5 package sides allowed. Please remove some images first.');
      return;
    }
    const filesToProcess = validImageFiles.slice(0, remainingSlots);
    if (filesToProcess.length < validImageFiles.length) {
      alert(`Only ${filesToProcess.length} of ${validImageFiles.length} images added (max 5 sides total).`);
    }

    const newItems = [];
    let completedCount = 0;
    const sideLabels = ['Front Side', 'Back Side', 'Left Side', 'Right Side', 'Top Side'];

    filesToProcess.forEach((file, index) => {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.src = reader.result;
        img.onload = () => {
          const totalSoFar = selectedImages.length + newItems.length;
          const defaultLabel = sideLabels[totalSoFar] || `Side ${totalSoFar + 1}`;

          newItems.push({
            id: `${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
            file: file,
            name: file.name,
            label: defaultLabel,
            size: (file.size / 1024).toFixed(1) + ' KB',
            width: img.width,
            height: img.height,
            previewUrl: reader.result
          });

          completedCount++;
          if (completedCount === filesToProcess.length) {
            onImagesSelected([...selectedImages, ...newItems]);
          }
        };
      };
      reader.readAsDataURL(file);
    });
  };

  const removeImage = (idToRemove) => {
    const updated = selectedImages.filter(img => img.id !== idToRemove);
    onImagesSelected(updated);
  };

  const clearAll = () => {
    onImagesSelected([]);
  };

  // Webcam Capture
  const startCamera = async () => {
    try {
      setShowCamera(true);
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      alert('Camera error: ' + err.message);
      setShowCamera(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setShowCamera(false);
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth || 1280;
    canvas.height = videoRef.current.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      const snapNum = selectedImages.length + 1;
      const file = new File([blob], `package_side_${snapNum}.jpg`, { type: 'image/jpeg' });
      stopCamera();
      processFiles([file]);
    }, 'image/jpeg', 0.92);
  };

  // Generate Sample Multi-Side Package (Front + Back of Same Product)
  const loadMultiSideDemo = () => {
    // 1. Front Side Canvas
    const c1 = document.createElement('canvas');
    c1.width = 700;
    c1.height = 500;
    const ctx1 = c1.getContext('2d');

    ctx1.fillStyle = '#18261c';
    ctx1.fillRect(0, 0, 700, 500);
    ctx1.strokeStyle = '#d4af37';
    ctx1.lineWidth = 6;
    ctx1.strokeRect(15, 15, 670, 470);

    ctx1.fillStyle = '#ffd700';
    ctx1.font = 'bold 34px Arial';
    ctx1.fillText('ASSAM ROYAL TEA', 50, 110);

    ctx1.fillStyle = '#ffffff';
    ctx1.font = 'bold 22px Arial';
    ctx1.fillText('Generic Commodity: Premium Black Tea', 50, 190);

    ctx1.font = 'bold 28px Arial';
    ctx1.fillText('Net Quantity: 250 g', 50, 270);

    ctx1.font = '16px Arial';
    ctx1.fillStyle = '#b4d2b4';
    ctx1.fillText('100% Pure Orthodox Whole Leaf • Selected Garden Flush', 50, 340);

    // 2. Back Side Canvas
    const c2 = document.createElement('canvas');
    c2.width = 700;
    c2.height = 500;
    const ctx2 = c2.getContext('2d');

    ctx2.fillStyle = '#1e2a20';
    ctx2.fillRect(0, 0, 700, 500);
    ctx2.strokeStyle = '#3c5a46';
    ctx2.lineWidth = 4;
    ctx2.strokeRect(15, 15, 670, 470);

    ctx2.fillStyle = '#ffd700';
    ctx2.font = 'bold 18px Arial';
    ctx2.fillText('ASSAM ROYAL TEA - MANDATORY DECLARATIONS', 40, 60);

    ctx2.fillStyle = '#ffffff';
    ctx2.font = 'bold 20px Arial';
    ctx2.fillText('MRP Rs. 185.00 (Incl. of all taxes)', 40, 120);

    ctx2.font = '16px Arial';
    ctx2.fillText('Mfg Date: NOV 2025 | Expiry Date: OCT 2026', 40, 180);
    ctx2.fillText('Mfd & Pkd By: Royal Tea Estates Pvt Ltd, Jorhat, Assam - 785001', 40, 240);
    ctx2.fillText('Customer Care: 1800-123-4567 | email: care@royaltea.com', 40, 300);

    ctx2.fillStyle = '#ffd700';
    ctx2.font = 'bold 18px Arial';
    ctx2.fillText('FSSAI Lic. No. 10321012000456', 40, 360);

    // Convert both to files
    c1.toBlob((b1) => {
      const f1 = new File([b1], 'tea_front_label.jpg', { type: 'image/jpeg' });
      c2.toBlob((b2) => {
        const f2 = new File([b2], 'tea_back_label.jpg', { type: 'image/jpeg' });
        processFiles([f1, f2]);
      }, 'image/jpeg');
    }, 'image/jpeg');
  };

  // Generate Sample Mismatch Conflict (Tea Front + Biscuit Back) to test rejection
  const loadMismatchDemo = () => {
    const c1 = document.createElement('canvas');
    c1.width = 600;
    c1.height = 400;
    const ctx1 = c1.getContext('2d');
    ctx1.fillStyle = '#18261c';
    ctx1.fillRect(0, 0, 600, 400);
    ctx1.fillStyle = '#ffd700';
    ctx1.font = 'bold 26px Arial';
    ctx1.fillText('ASSAM ROYAL TEA (Front)', 40, 80);
    ctx1.fillStyle = '#ffffff';
    ctx1.font = '20px Arial';
    ctx1.fillText('Generic Commodity: Premium Black Tea', 40, 150);
    ctx1.fillText('Net Quantity: 250 g', 40, 220);

    const c2 = document.createElement('canvas');
    c2.width = 600;
    c2.height = 400;
    const ctx2 = c2.getContext('2d');
    ctx2.fillStyle = '#fafaf6';
    ctx2.fillRect(0, 0, 600, 400);
    ctx2.fillStyle = '#b41e1e';
    ctx2.font = 'bold 24px Arial';
    ctx2.fillText('CRUNCHY NUT BISCUITS (Back)', 40, 80);
    ctx2.fillStyle = '#333333';
    ctx2.font = '16px Arial';
    ctx2.fillText('MRP Rs. 30.00 INCL ALL TAXES', 40, 150);
    ctx2.fillText('Manufactured by: Golden Bakery Pvt Ltd', 40, 210);
    ctx2.fillText('FSSAI Lic. No. 11518014000890', 40, 270);

    c1.toBlob((b1) => {
      const f1 = new File([b1], 'tea_front_label.jpg', { type: 'image/jpeg' });
      c2.toBlob((b2) => {
        const f2 = new File([b2], 'biscuit_back_label.jpg', { type: 'image/jpeg' });
        processFiles([f1, f2]);
      }, 'image/jpeg');
    }, 'image/jpeg');
  };

  // Generate Sample Label with Harmful Ingredients (TBHQ, Palm Oil, Tartrazine, Trans Fat)
  const loadHarmfulIngredientsDemo = () => {
    const c = document.createElement('canvas');
    c.width = 800;
    c.height = 640;
    const ctx = c.getContext('2d');

    ctx.fillStyle = '#1e1b18';
    ctx.fillRect(0, 0, 800, 640);
    ctx.strokeStyle = '#e11d48';
    ctx.lineWidth = 6;
    ctx.strokeRect(15, 15, 770, 610);

    ctx.fillStyle = '#f43f5e';
    ctx.font = 'bold 30px Arial';
    ctx.fillText('CRUNCHY CHIPZ SPICY MASALA', 40, 70);

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 20px Arial';
    ctx.fillText('Generic Commodity: Potato Wafers / Snack', 40, 125);
    ctx.fillText('Net Quantity: 150 g', 40, 175);
    ctx.fillText('MRP Rs. 40.00 (Incl. of all taxes)', 40, 225);

    ctx.fillStyle = '#fca5a5';
    ctx.font = 'bold 16px Arial';
    ctx.fillText('INGREDIENTS:', 40, 280);
    ctx.fillStyle = '#ffffff';
    ctx.font = '14px Arial';
    ctx.fillText('Refined Wheat Flour, Palm Oil, TBHQ (INS 319), Tartrazine (INS 102),', 40, 310);
    ctx.fillText('Monosodium Glutamate (INS 621), Partially Hydrogenated Vegetable Oil, Salt, Spices', 40, 335);

    ctx.fillStyle = '#e2e8f0';
    ctx.font = '14px Arial';
    ctx.fillText('Mfg Date: DEC 2025 | Expiry Date: NOV 2026', 40, 395);
    ctx.fillText('Mfd By: Snack Foods Ltd, GIDC Industrial Estate, Surat, Gujarat - 395001', 40, 440);
    ctx.fillText('Customer Care: 1800-888-9999 | email: care@chipz.in', 40, 485);

    ctx.fillStyle = '#fbbf24';
    ctx.font = 'bold 16px Arial';
    ctx.fillText('FSSAI Lic. No. 10721014000321', 40, 540);

    c.toBlob((blob) => {
      const f = new File([blob], 'harmful_snack_label.jpg', { type: 'image/jpeg' });
      processFiles([f]);
    }, 'image/jpeg', 0.95);
  };

  // Generate Sample Label with 100% Safe Natural Organic Ingredients
  const loadSafeOrganicDemo = () => {
    const c = document.createElement('canvas');
    c.width = 800;
    c.height = 640;
    const ctx = c.getContext('2d');

    ctx.fillStyle = '#14281d';
    ctx.fillRect(0, 0, 800, 640);
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 6;
    ctx.strokeRect(15, 15, 770, 610);

    ctx.fillStyle = '#34d399';
    ctx.font = 'bold 30px Arial';
    ctx.fillText('ORGANIC ROYAL OATS & HONEY', 40, 70);

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 20px Arial';
    ctx.fillText('Generic Commodity: 100% Whole Rolled Oats', 40, 125);
    ctx.fillText('Net Quantity: 500 g', 40, 175);
    ctx.fillText('MRP Rs. 195.00 (Incl. of all taxes)', 40, 225);

    ctx.fillStyle = '#a7f3d0';
    ctx.font = 'bold 16px Arial';
    ctx.fillText('INGREDIENTS:', 40, 280);
    ctx.fillStyle = '#ffffff';
    ctx.font = '14px Arial';
    ctx.fillText('100% Organic Rolled Oats, Raw Honey, Roasted Almonds, Whole Chia Seeds, Natural Vanilla Extract', 40, 315);

    ctx.fillStyle = '#e2e8f0';
    ctx.font = '14px Arial';
    ctx.fillText('Mfg Date: JAN 2026 | Expiry Date: DEC 2026', 40, 380);
    ctx.fillText('Mfd By: Organic Valley Foods Ltd, Pune, Maharashtra - 411001', 40, 430);
    ctx.fillText('Customer Care: 1800-444-1111 | email: help@organicvalley.in', 40, 480);

    ctx.fillStyle = '#fbbf24';
    ctx.font = 'bold 16px Arial';
    ctx.fillText('FSSAI Lic. No. 11520015000456', 40, 535);

    c.toBlob((blob) => {
      const f = new File([blob], 'safe_organic_oats.jpg', { type: 'image/jpeg' });
      processFiles([f]);
    }, 'image/jpeg', 0.95);
  };

  const hasImages = selectedImages.length > 0;

  return (
    <div className="space-y-4">

      {/* Hidden Multi-file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*"
        multiple
        className="hidden"
      />

      {/* Main Upload / Drag Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-6 sm:p-8 text-center transition-all cursor-pointer bg-white ${isDragging ? 'border-emerald-600 bg-emerald-50/50' : 'border-gray-300 hover:border-gray-400'
          }`}
      >
        <div className="space-y-1 mb-4">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-gray-100 text-gray-700 mb-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 className="text-base font-bold text-gray-900">
            {hasImages ? 'Add More Sides (Front / Back / Side Panels)' : 'Upload Product Package Images'}
          </h3>
          <p className="text-xs text-gray-500 max-w-md mx-auto">
            Upload multiple photos of the <strong className="text-gray-700">same product</strong> (e.g. Front brand panel, Back declarations, or Sides). MetroLens checks and verifies all sides match together.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2">
          <button
            type="button"
            className="px-4 py-2 rounded-lg bg-gray-900 text-white font-semibold text-xs hover:bg-gray-800 transition-colors cursor-pointer"
          >
            {hasImages ? 'Add Photos' : 'Choose Image(s)'}
          </button>

          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); startCamera(); }}
            className="px-4 py-2 rounded-lg bg-white border border-gray-300 text-gray-700 font-medium text-xs hover:bg-gray-50 transition-colors cursor-pointer"
          >
            Snap with Camera
          </button>

          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); loadHarmfulIngredientsDemo(); }}
            className="px-3.5 py-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 font-semibold text-xs hover:bg-rose-100 transition-colors cursor-pointer"
            title="Generates a snack label with Palm Oil, TBHQ, Tartrazine and Trans Fats to test harmful ingredient detection"
          >
            ★ Try Harmful Ingredients Demo
          </button>

          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); loadSafeOrganicDemo(); }}
            className="px-3.5 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 font-semibold text-xs hover:bg-emerald-100 transition-colors cursor-pointer"
            title="Generates an organic oats label with 100% wholesome natural ingredients"
          >
            ★ Try Safe Organic Demo
          </button>

          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); loadMultiSideDemo(); }}
            className="px-3.5 py-2 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 font-semibold text-xs hover:bg-blue-100 transition-colors cursor-pointer"
          >
            Multi-Side Demo (Front + Back)
          </button>

          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); loadMismatchDemo(); }}
            className="px-2.5 py-2 text-[11px] text-gray-500 hover:text-red-700 underline transition-colors cursor-pointer"
            title="Uploads 2 photos from different products to demonstrate the mismatch rejection protection"
          >
            Test Mismatch Protection
          </button>
        </div>
      </div>

      {/* Uploaded Package Sides Strip */}
      {hasImages && (
        <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-4 shadow-sm">

          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <h4 className="text-sm font-bold text-gray-900">
                Package Sides Ready for Audit ({selectedImages.length})
              </h4>
              <span className="text-[10px] uppercase font-mono font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                {selectedImages.length === 1 ? 'Single Side' : 'Multi-Side Same Product Check Active'}
              </span>
            </div>

            <button
              onClick={clearAll}
              className="text-xs text-red-600 hover:text-red-800 underline font-medium cursor-pointer"
            >
              Clear All
            </button>
          </div>

          {/* Grid of uploaded sides */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {selectedImages.map((img, idx) => (
              <div
                key={img.id}
                className="relative rounded-lg border border-gray-200 bg-gray-50 overflow-hidden flex flex-col group"
              >
                {/* Header tag */}
                <div className="p-2 bg-white border-b border-gray-100 flex items-center justify-between text-xs">
                  <span className="font-bold text-gray-800">
                    Side {idx + 1}: <span className="text-gray-500 font-normal">{img.label}</span>
                  </span>
                  <button
                    onClick={() => removeImage(img.id)}
                    className="text-gray-400 hover:text-red-600 font-bold px-1 rounded"
                    title="Remove this side"
                  >
                    ✕
                  </button>
                </div>

                {/* Thumbnail */}
                <div className="h-40 flex items-center justify-center p-2 bg-gray-100">
                  <img
                    src={img.previewUrl}
                    alt={img.name}
                    className="max-h-full max-w-full object-contain rounded"
                  />
                </div>

                {/* Meta footer */}
                <div className="p-2 bg-white text-[11px] text-gray-500 flex items-center justify-between border-t border-gray-100 font-mono">
                  <span className="truncate max-w-[140px]">{img.name}</span>
                  <span>{img.size}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Multi-side info note */}
          {selectedImages.length > 1 && (
            <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-lg text-xs text-emerald-900 flex items-center gap-2">
              <span className="font-bold">✓ Multi-Angle Audit:</span>
              <span>
                MetroLens will cross-verify that all {selectedImages.length} images belong to the same product and synthesize declarations across all faces.
              </span>
            </div>
          )}

          {/* Start Audit Button */}
          <div className="flex justify-end pt-2">
            <button
              onClick={onStartScan}
              disabled={isScanning}
              className="w-full sm:w-auto px-8 py-3 rounded-lg bg-gray-900 hover:bg-gray-800 text-white font-bold text-xs tracking-wide transition-all cursor-pointer disabled:opacity-50 shadow-sm"
            >
              {isScanning ? 'Analyzing All Package Sides...' : `Run Legal Metrology Audit (${selectedImages.length} ${selectedImages.length === 1 ? 'Side' : 'Sides'})`}
            </button>
          </div>

        </div>
      )}

      {/* Live Camera Modal */}
      {showCamera && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-4 space-y-3 shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 pb-2">
              <h3 className="text-sm font-bold text-gray-900">Live Package Scanner</h3>
              <button onClick={stopCamera} className="text-xs text-gray-500 hover:text-gray-900">Cancel</button>
            </div>

            <div className="rounded-lg overflow-hidden bg-black aspect-video">
              <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-[11px] text-gray-500">Capture each side of the product</span>
              <div className="flex gap-2">
                <button onClick={stopCamera} className="px-3 py-1.5 rounded text-xs text-gray-600 border border-gray-300">Close</button>
                <button onClick={capturePhoto} className="px-4 py-1.5 rounded bg-gray-900 text-white text-xs font-bold">Snap Side</button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
