# HuggingFace Spaces - AutoMetricX Backend
# Base image with Python 3.11
FROM python:3.11-slim

# Install system dependencies required by OpenCV, pyzbar, and PaddleOCR
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    libzbar0 \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire backend app
COPY . .

# Create required directories
RUN mkdir -p uploads rules pdf_exports

# HuggingFace Spaces uses port 7860
ENV PORT=7860

# Expose port
EXPOSE 7860

# Start FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
