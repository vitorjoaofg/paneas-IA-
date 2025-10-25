FROM paddlepaddle/paddle:2.6.1-gpu-cuda11.7-cudnn8.4-trt8.4

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libxml2 \
        libxslt1.1 \
        poppler-utils \
        ffmpeg \
        curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app

EXPOSE 9004

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9004", "--proxy-headers"]
