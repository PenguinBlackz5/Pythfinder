-- favorited_dccons 테이블의 local_path 컬럼을 NULL 허용으로 변경합니다.
-- 이 변경은 즐겨찾기 기능이 더 이상 로컬 파일 경로를 저장하지 않고,
-- URL 기반으로 작동하도록 수정됨에 따라 필요합니다.
ALTER TABLE favorited_dccons ALTER COLUMN local_path DROP NOT NULL; 