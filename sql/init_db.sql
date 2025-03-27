-- 필요한 테이블들을 여기에 생성합니다
-- 예시:
```
CREATE TABLE IF NOT EXISTS example (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

-- 다른 테이블들도 필요에 따라 추가하세요 

-- user_attendance 테이블 생성
CREATE TABLE IF NOT EXISTS user_attendance (
    user_id BIGINT PRIMARY KEY,
    last_attendance TIMESTAMP,
    streak_count INTEGER DEFAULT 0,
    attendance_count INTEGER DEFAULT 0
);

-- attendance_channels 테이블 생성
CREATE TABLE IF NOT EXISTS attendance_channels (
    channel_id BIGINT PRIMARY KEY
);

-- user_balance 테이블 생성
CREATE TABLE IF NOT EXISTS user_balance (
    user_id BIGINT PRIMARY KEY,
    balance INTEGER DEFAULT 0
)