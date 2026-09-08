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
  const [selectedImage, setSelectedImage] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

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
    if (!selectedImage || !selectedImage.file) return;

    setIsScanning(true);
    setErrorMsg(null);
    setOcrResult(null);

    const formData = new FormData();
    formData.append('file', selectedImage.file);

    try {
      const response = await fetch(`${API_BASE_URL}/scan`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      setOcrResult(data);
    } catch (err) {
      console.error('Scan API error:', err);
      setErrorMsg(err.message || 'Failed to connect to backend server.');
    } finally {
      setIsScanning(false);
    }
  };

  const handleResetScan = () => {
    setSelectedImage(null);
    setOcrResult(null);
    setErrorMsg(null);
    setCurrentNav('scan');
  };

  const handleSelectHistoricalScan = (fullReport) => {
    setOcrResult(fullReport);
    setCurrentNav('scan');
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex flex-col font-sans">
      
      {/* Top Header */}
      <Header
        backendConnected={backendConnected}
        currentNav={currentNav}
        onNavChange={(nav) => {
          if (nav === 'scan' && !ocrResult) {
            setSelectedImage(null);
          }
          setCurrentNav(nav);
        }}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 space-y-6">
        
        {/* Error Alert */}
        {errorMsg && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center justify-between text-red-800 text-sm">
            <span>{errorMsg}</span>
            <button
              onClick={() => setErrorMsg(null)}
              className="text-xs px-2.5 py-1 rounded bg-red-100 hover:bg-red-200 text-red-900 font-medium cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Navigation View Switcher */}
        {currentNav === 'history' ? (
          <HistoryView onSelectScan={handleSelectHistoricalScan} />
        ) : isScanning ? (
          <ProcessingCard />
        ) : ocrResult ? (
          <OCRResultView
            result={ocrResult}
            imagePreviewUrl={selectedImage?.previewUrl || `${API_BASE_URL}/uploads/${ocrResult.saved_file}`}
            onResetScan={handleResetScan}
          />
        ) : (
          <>
            <div className="text-center space-y-2 py-2">
              <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
                Product Label Compliance Audit
              </h2>
              <p className="text-sm text-gray-600 max-w-xl mx-auto">
                Upload a packaged product label photo to verify mandatory legal declarations, font letter sizes, and barcode accuracy against Legal Metrology Rules.
              </p>
            </div>

            <ImageUploader
              selectedImage={selectedImage}
              onImageSelected={setSelectedImage}
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
