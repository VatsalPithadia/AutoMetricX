# AutoMetricX - Start Backend + ngrok
# Run this script every time you need to start the backend
# Usage: Right-click -> "Run with PowerShell"  OR  run in terminal: .\start_backend.ps1

$NGROK = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
$BACKEND_DIR = "$PSScriptRoot\backend"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   AutoMetricX Backend Starter" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Start ngrok in background
Write-Host "[1/3] Starting ngrok tunnel..." -ForegroundColor Yellow
Start-Process -FilePath $NGROK -ArgumentList "http 8000" -WindowStyle Normal

# Wait for ngrok to initialize
Write-Host "      Waiting for ngrok to start..." -ForegroundColor Gray
Start-Sleep -Seconds 4

# Step 2: Get the public URL from ngrok API
Write-Host "[2/3] Getting your public URL..." -ForegroundColor Yellow
try {
    $tunnels = Invoke-RestMethod http://localhost:4040/api/tunnels
    $publicUrl = $tunnels.tunnels[0].public_url
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "   YOUR NGROK URL:" -ForegroundColor Green
    Write-Host "   $publicUrl" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "ACTION REQUIRED:" -ForegroundColor Red
    Write-Host "  1. Go to https://vercel.com/dashboard" -ForegroundColor White
    Write-Host "  2. Open your AutoMetricX project -> Settings -> Environment Variables" -ForegroundColor White
    Write-Host "  3. Update VITE_API_URL to: $publicUrl" -ForegroundColor White
    Write-Host "  4. Go to Deployments -> Click '...' -> Redeploy" -ForegroundColor White
    Write-Host ""
    # Copy URL to clipboard
    $publicUrl | Set-Clipboard
    Write-Host "  (URL copied to clipboard!)" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "  Could not auto-detect URL. Check the ngrok window for your URL." -ForegroundColor Red
}

# Step 3: Start FastAPI backend in this window
Write-Host "[3/3] Starting FastAPI backend..." -ForegroundColor Yellow
Write-Host "      (Keep this window open!)" -ForegroundColor Gray
Write-Host ""

Set-Location $BACKEND_DIR

# Activate venv and start uvicorn
& "$BACKEND_DIR\.venv\Scripts\Activate.ps1"
uvicorn app.main:app --host 0.0.0.0 --port 8000
