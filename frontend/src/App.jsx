import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import ImageUploader from './components/ImageUploader';
import ProcessingCard from './components/ProcessingCard';
import OCRResultView from './components/OCRResultView';
import HistoryView from './components/HistoryView';

const API_BASE_URL = 'http://localhost:8000';

export default function App() {
  const [backendConnected, setBackendConnected] = useState(false);
  const [currentNav, setCurrentNav] = useState('scan'); // 'scan' | 'history'
  const [selectedImages, setSelectedImages] = useState([]); // Array of image objects
  const [isScanning, setIsScanning] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
  const [mismatchError, setMismatchError] = useState(null); // Product mismatch rejection detail

  // Poll backend health endpoint on load
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/health`);
        if (res.ok) {
          setBackendConnected(true);
        } else {
          setBackendConnected(false);
        }
      } catch (err) {
        setBackendConnected(false);
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStartScan = async () => {
    if (!selectedImages || selectedImages.length === 0) return;

    setIsScanning(true);
    setErrorMsg(null);
    setMismatchError(null);
    setOcrResult(null);

    const formData = new FormData();

    if (selectedImages.length === 1) {
      // Single image — use 'file' parameter (FastAPI accepts either)
      formData.append('file', selectedImages[0].file, selectedImages[0].name);
    } else {
      // Multiple images — send each as 'files' list entries
      selectedImages.forEach((img) => {
        formData.append('files', img.file, img.name);
      });
    }

    try {
      const response = await fetch(`${API_BASE_URL}/scan`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        // Product mismatch rejection (HTTP 400 with product_mismatch: true)
        if (response.status === 400 && data.product_mismatch) {
          setMismatchError(data.detail || 'These images appear to be from different products.');
          return;
        }
        throw new Error(data.detail || `Server returned HTTP ${response.status}`);
      }

      setOcrResult(data);
    } catch (err) {
      console.error('Scan API error:', err);
      setErrorMsg(err.message || 'Failed to connect to backend server.');
    } finally {
      setIsScanning(false);
    }
  };

  const handleResetScan = () => {
    setSelectedImages([]);
    setOcrResult(null);
    setErrorMsg(null);
    setMismatchError(null);
    setCurrentNav('scan');
  };

  const handleSelectHistoricalScan = (fullReport) => {
    setOcrResult(fullReport);
    setSelectedImages([]);
    setCurrentNav('scan');
  };

  // Build primary preview URL — first selected image preview, or uploaded file URL
  const primaryPreviewUrl = selectedImages.length > 0
    ? selectedImages[0].previewUrl
    : (ocrResult?.saved_file ? `${API_BASE_URL}/uploads/${ocrResult.saved_file}` : null);

  // Build all side preview URLs for multi-side display
  const sidePreviewUrls = selectedImages.length > 1
    ? selectedImages.map((img) => img.previewUrl)
    : null;

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex flex-col font-sans">
      
      {/* Top Header */}
      <Header
        backendConnected={backendConnected}
        currentNav={currentNav}
        onNavChange={(nav) => {
          if (nav === 'scan' && !ocrResult) {
            setSelectedImages([]);
          }
          setCurrentNav(nav);
        }}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 space-y-6">
        
        {/* General Error Alert */}
        {errorMsg && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between text-red-800 text-sm">
            <span>⚠️ {errorMsg}</span>
            <button
              onClick={() => setErrorMsg(null)}
              className="text-xs px-2.5 py-1 rounded bg-red-100 hover:bg-red-200 text-red-900 font-medium cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Product Mismatch Rejection Alert */}
        {mismatchError && (
          <div className="p-4 bg-amber-50 border-2 border-amber-300 rounded-xl space-y-3">
            <div className="flex items-start gap-3">
              <div className="shrink-0 w-9 h-9 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 font-bold text-lg">
                ✕
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-bold text-amber-900 mb-1">Product Mismatch Detected — Upload Rejected</h3>
                <p className="text-xs text-amber-800 leading-relaxed">{mismatchError}</p>
                <p className="text-xs text-amber-700 mt-2 font-medium">
                  All uploaded images must be different sides of the <strong>same product</strong>. 
                  Please remove conflicting images and try again.
                </p>
              </div>
            </div>
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => { setMismatchError(null); setSelectedImages([]); }}
                className="px-4 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-semibold hover:bg-amber-700 cursor-pointer"
              >
                Clear & Start Over
              </button>
              <button
                onClick={() => setMismatchError(null)}
                className="px-4 py-1.5 rounded-lg bg-white border border-amber-300 text-amber-800 text-xs font-medium hover:bg-amber-50 cursor-pointer"
              >
                Dismiss (Edit Images)
              </button>
            </div>
          </div>
        )}

        {/* Navigation View Switcher */}
        {currentNav === 'history' ? (
          <HistoryView onSelectScan={handleSelectHistoricalScan} />
        ) : isScanning ? (
          <ProcessingCard totalImages={selectedImages.length} />
        ) : ocrResult ? (
          <OCRResultView
            result={ocrResult}
            imagePreviewUrl={primaryPreviewUrl}
            sidePreviewUrls={sidePreviewUrls}
            onResetScan={handleResetScan}
          />
        ) : (
          <>
            <div className="text-center space-y-2 py-2">
              <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
                Product Label Compliance Audit
              </h2>
              <p className="text-sm text-gray-600 max-w-xl mx-auto">
                Upload one or more photos of a packaged product label to verify mandatory legal declarations, 
                font letter sizes, and barcode accuracy against Legal Metrology Rules.
              </p>
            </div>

            <ImageUploader
              selectedImages={selectedImages}
              onImagesSelected={setSelectedImages}
              onStartScan={handleStartScan}
              isScanning={isScanning}
            />
          </>
        )}

      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-gray-200 bg-white py-4 text-center text-xs text-gray-500">
        <p>MetroLens &bull; Legal Metrology (Packaged Commodities) Compliance Platform</p>
      </footer>

    </div>
  );
}
