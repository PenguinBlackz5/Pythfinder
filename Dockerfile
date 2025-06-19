
FROM gradle:7.6.4-jdk17 AS builder
WORKDIR /home/gradle/project
COPY appid_generator/ .
RUN chmod +x ./gradlew
RUN ./gradlew clean shadowJar

FROM python:3.13

WORKDIR /app

# 시스템 패키지 업데이트 및 필수 패키지 설치
# OpenJDK (Java) 추가
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

COPY --from=builder /home/gradle/project/build/libs/appid_generator-1.0-SNAPSHOT-all.jar /app/appid_generator/build/libs/

# requirements.txt 복사 및 Python 패키지 설치
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 봇 실행
CMD ["python", "main.py"]