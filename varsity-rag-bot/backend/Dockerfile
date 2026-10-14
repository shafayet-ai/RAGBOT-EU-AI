# lightweight Python image
FROM python:3.12-slim

# Working directory সেট করা
WORKDIR /app

# সিস্টেম লেভেলের দরকারি টুলস ইনস্টল
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /lib/apt/lists/*

# requirements.txt কপি ও ডিপেন্ডেন্সি ইনস্টল
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ব্যাকএন্ডের সব কোড কপি করা
COPY . .

# FastAPI / Uvicorn রান করার কমান্ড (Port 8000)
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
