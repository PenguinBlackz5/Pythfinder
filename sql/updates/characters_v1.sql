-- characters 데이터 타입 버전 1 업데이트
-- game_characters 테이블에 gold 컬럼 추가

ALTER TABLE game_characters
ADD COLUMN gold INT NOT NULL DEFAULT 0;
 
-- game_data_versions 테이블에 'characters' 타입을 추가하거나, 이미 있다면 버전 정보를 업데이트합니다.
-- 이 스크립트는 버전 1에 해당하므로, 버전을 1로 설정합니다.
INSERT INTO game_data_versions (data_type, version)
VALUES ('characters', 1)
ON CONFLICT (data_type) DO UPDATE SET version = 1; 