-- 즐겨찾기한 디시콘 정보를 저장하는 테이블
CREATE TABLE IF NOT EXISTS favorited_dccons (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    dccon_title VARCHAR(255) NOT NULL,
    image_url TEXT UNIQUE NOT NULL, -- 동일한 이미지가 중복 저장되는 것을 방지
    local_path TEXT NOT NULL,
    favorited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, image_url) -- 사용자는 동일한 이미지를 한 번만 즐겨찾기 가능
);

-- 인덱스 추가로 검색 속도 향상
CREATE INDEX IF NOT EXISTS idx_favorited_dccons_user_id ON favorited_dccons (user_id); 