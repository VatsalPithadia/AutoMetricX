import React, { useState, useRef } from 'react';

export default function ImageUploader({ selectedImage, onImageSelected, onStartScan, isScanning }) {
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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = (file) => {
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file (JPEG, PNG, WEBP).');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.src = reader.result;
      img.onload = () => {
        onImageSelected({
          file: file,
          name: file.name,
          size: (file.size / 1024).toFixed(1) + ' KB',
          width: img.width,
          height: img.height,
          previewUrl: reader.result
        });
      };
    };
    reader.readAsDataURL(file);
  };

  // Live Camera Capture
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
      const file = new File([blob], `camera_capture_${Date.now()}.jpg`, { type: 'image/jpeg' });
      stopCamera();
      processFile(file);
    }, 'image/jpeg', 0.92);
  };

  // Generate sample product label for testing
  const loadSampleLabel = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 600;
    canvas.height = 400;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, 600, 400);

    ctx.strokeStyle = '#111827';
    ctx.lineWidth = 4;
    ctx.strokeRect(10, 10, 580, 380);

    ctx.fillStyle = '#111827';
    ctx.font = 'bold 22px Arial';
    ctx.fillText('SUPER CRUNCH POTATO CHIPS', 30, 45);

    ctx.font = '14px Arial';
    ctx.fillStyle = '#374151';
    ctx.fillText('Net Weight: 150 g', 30, 80);
    ctx.fillText('Mfd by: Apex Foods India Pvt Ltd', 30, 110);
    ctx.fillText('Plot 42, Industrial Area, Phase II, New Delhi - 110020', 30, 130);
    
    ctx.fillText('Month & Year of Mfg: 08/2026', 30, 165);
    
    ctx.font = 'bold 20px Arial';
    ctx.fillStyle = '#b91c1c';
    ctx.fillText('MRP Rs. 45.00 (Incl. of all taxes)', 30, 205);

    ctx.font = '12px Arial';
    ctx.fillStyle = '#4b5563';
    ctx.fillText('Consumer Care Officer: 1800-11-2233 | customercare@apexfoods.in', 30, 245);

    ctx.font = '12px Arial';
    ctx.fillStyle = '#111827';
    ctx.fillText('Lic. No. 10715016000063', 30, 270);

    ctx.fillStyle = '#000000';
    for (let i = 0; i < 40; i++) {
      const w = (i % 3 === 0) ? 4 : 2;
      ctx.fillRect(30 + (i * 6), 285, w, 50);
    }
    ctx.font = '12px monospace';
    ctx.fillText('8901234567890', 50, 350);

    canvas.toBlob((blob) => {
      const sampleFile = new File([blob], 'sample_packaged_product_label.png', { type: 'image/png' });
      processFile(sampleFile);
    }, 'image/png');
  };

  return (
    <div className="w-full max-w-2xl mx-auto space-y-4">
      
      {!selectedImage ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border border-dashed rounded-xl p-8 text-center transition-all cursor-pointer bg-white ${
            isDragging ? 'border-gray-900 bg-gray-50' : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/*"
            className="hidden"
          />

          <div className="space-y-1 mb-6">
            <h3 className="text-base font-semibold text-gray-900">
              Upload Label Image
            </h3>
            <p className="text-xs text-gray-500">
              Drag and drop an image file here, or click to browse.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              className="px-4 py-2 rounded-lg bg-gray-900 text-white font-medium text-xs hover:bg-gray-800 transition-colors"
            >
              Choose File
            </button>

            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); startCamera(); }}
              className="px-4 py-2 rounded-lg bg-white border border-gray-300 text-gray-700 font-medium text-xs hover:bg-gray-50 transition-colors"
            >
              Use Camera
            </button>

            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); loadSampleLabel(); }}
              className="px-4 py-2 text-xs text-gray-500 hover:text-gray-900 underline transition-colors"
            >
              Try Sample Label
            </button>
          </div>
        </div>
      ) : (
        /* Image Preview Box */
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <div>
              <h4 className="text-sm font-semibold text-gray-900 truncate max-w-xs">{selectedImage.name}</h4>
              <p className="text-xs text-gray-500 font-mono">{selectedImage.size} &bull; {selectedImage.width}x{selectedImage.height} px</p>
            </div>

            <button
              onClick={() => onImageSelected(null)}
              className="text-xs text-gray-500 hover:text-gray-900 underline cursor-pointer"
            >
              Remove
            </button>
          </div>

          <div className="bg-gray-50 rounded-lg p-2 flex items-center justify-center min-h-[220px]">
            <img
              src={selectedImage.previewUrl}
              alt="Selected Label"
              className="max-h-[320px] object-contain rounded"
            />
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={onStartScan}
              disabled={isScanning}
              className="w-full sm:w-auto px-6 py-2.5 rounded-lg bg-gray-900 hover:bg-gray-800 text-white font-semibold text-xs transition-colors cursor-pointer disabled:opacity-50"
            >
              {isScanning ? 'Analyzing Label...' : 'Run Compliance Audit'}
            </button>
          </div>
        </div>
      )}

      {/* Live Camera Modal */}
      {showCamera && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">Webcam Scanner</h3>
              <button onClick={stopCamera} className="text-xs text-gray-500 hover:text-gray-900">Cancel</button>
            </div>

            <div className="rounded-lg overflow-hidden bg-black aspect-video">
              <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
            </div>

            <div className="flex justify-end gap-2">
              <button onClick={stopCamera} className="px-3 py-1.5 rounded text-xs text-gray-600 border border-gray-300">Close</button>
              <button onClick={capturePhoto} className="px-4 py-1.5 rounded bg-gray-900 text-white text-xs font-semibold">Take Photo</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
