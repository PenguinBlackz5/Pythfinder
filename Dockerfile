FROM python:3.13

WORKDIR /app

# 시스템 패키지 업데이트 및 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    python3-dev \
    ffmpeg \
    opus-tools \
    libopus-dev \
    libffi-dev \
    libnacl-dev \
    build-essential \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 Python 패키지 설치
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 봇 실행
CMD ["python", "main.py"]