-- =================================================================
-- TextRPG: 던전 앤 디스코드 테이블 생성 스크립트
-- 버전: 2.0
-- 마지막 수정: (현재 날짜)
-- 설명: 클래식 로그라이크 게임 컨셉에 맞춘 전체 데이터베이스 스키마.
-- 재실행 가능하도록 DROP 및 CREATE IF NOT EXISTS 구문 사용.
-- =================================================================

-- ==== 마스터 데이터 테이블 ====

-- 1. 종족 마스터 테이블 (Races)
CREATE TABLE IF NOT EXISTS game_races (
    race_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    base_hp INT NOT NULL,
    base_mp INT NOT NULL,
    base_attack INT NOT NULL,
    base_defense INT NOT NULL
);

-- 2. 직업 마스터 테이블 (Classes)
CREATE TABLE IF NOT EXISTS game_classes (
    class_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    starting_items JSONB -- 예: [{"item_name": "단검", "quantity": 1}, {"item_name": "체력 물약", "quantity": 2}]
);

-- 3. 아이템 마스터 테이블 (Items)
CREATE TABLE IF NOT EXISTS game_items (
    item_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    item_type VARCHAR(50) NOT NULL, -- 'WEAPON', 'ARMOR', 'CONSUMABLE', 'SCROLL', 'POTION'
    effects JSONB -- 예: {"hp": 20} 또는 {"attack": 5}
);

-- 4. 몬스터 마스터 테이블 (Monsters)
CREATE TABLE IF NOT EXISTS game_monsters (
    monster_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    hp INT NOT NULL,
    attack INT NOT NULL,
    defense INT NOT NULL,
    reward_exp INT NOT NULL,
    reward_gold INT NOT NULL,
    dungeon_level_min INT NOT NULL DEFAULT 1 -- 몬스터가 등장하는 최소 던전 깊이
);

-- 5. 계약 마스터 테이블 (Covenants)
CREATE TABLE IF NOT EXISTS game_covenants (
    covenant_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    -- 계약의 규칙과 효과를 JSON으로 저장하여 유연성 확보
    -- 'clauses' (조항), 'powers' (권능), 'backlash' (반발) 등의 키를 가짐
    details JSONB
);


-- ==== 플레이어 데이터 테이블 ====

-- 6. 현재 살아있는 캐릭터 정보
-- 한 유저는 동시에 하나의 살아있는 캐릭터만 가질 수 있도록 user_id에 UNIQUE 제약 추가
CREATE TABLE IF NOT EXISTS game_characters (
    character_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    race_id INT NOT NULL,
    class_id INT NOT NULL,
    
    level INT NOT NULL DEFAULT 1,
    exp INT NOT NULL DEFAULT 0,
    next_exp INT NOT NULL DEFAULT 100,

    hp INT NOT NULL,
    max_hp INT NOT NULL,
    mp INT NOT NULL,
    max_mp INT NOT NULL,

    attack INT NOT NULL,
    defense INT NOT NULL,
    
    food INT NOT NULL DEFAULT 2000, -- 턴마다 감소하는 식량
    dungeon_level INT NOT NULL DEFAULT 1, -- 현재 위치한 던전 깊이
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (race_id) REFERENCES game_races(race_id),
    FOREIGN KEY (class_id) REFERENCES game_classes(class_id)
);

-- 7. 죽거나 클리어한 캐릭터 기록 (묘비)
CREATE TABLE IF NOT EXISTS game_character_history (
    history_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    race_name VARCHAR(50) NOT NULL,
    class_name VARCHAR(50) NOT NULL,
    
    level INT NOT NULL,
    cause_of_death VARCHAR(255), -- "슬라임에게 맞아 죽었습니다", "함정에 빠졌습니다", "굶어 죽었습니다", "던전을 정복했습니다!"
    cleared_dungeon_level INT NOT NULL,
    play_time_seconds INT NOT NULL,
    
    ended_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. 캐릭터 인벤토리
CREATE TABLE IF NOT EXISTS game_inventory (
    inventory_id SERIAL PRIMARY KEY,
    character_id INT NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    is_equipped BOOLEAN DEFAULT FALSE,
    is_identified BOOLEAN DEFAULT FALSE, -- 아이템 식별 여부

    FOREIGN KEY (character_id) REFERENCES game_characters(character_id) ON DELETE CASCADE, -- 캐릭터가 삭제되면 인벤토리도 함께 삭제
    FOREIGN KEY (item_id) REFERENCES game_items(item_id)
);

-- 9. 캐릭터-계약 관계 테이블
CREATE TABLE IF NOT EXISTS game_character_covenants (
    character_covenant_id SERIAL PRIMARY KEY,
    character_id INT NOT NULL,
    covenant_id INT NOT NULL,
    contribution_score INT NOT NULL DEFAULT 0, -- 공헌도
    is_active BOOLEAN DEFAULT FALSE, -- 계약이 활성화(체결)되었는지 여부

    UNIQUE (character_id, covenant_id), -- 캐릭터는 각 계약과 하나의 관계만 가질 수 있음
    FOREIGN KEY (character_id) REFERENCES game_characters(character_id) ON DELETE CASCADE,
    FOREIGN KEY (covenant_id) REFERENCES game_covenants(covenant_id)
);


-- ==== 시스템 테이블 ====

-- 10. 데이터 버전 관리 테이블
CREATE TABLE IF NOT EXISTS game_data_versions (
    data_type VARCHAR(50) PRIMARY KEY,
    version INT NOT NULL DEFAULT 0
);


-- ==== 초기 데이터 삽입 ====

-- 초기 데이터는 각 데이터 타입의 v1 업데이트 스크립트로 이전하는 것을 권장.
-- 이 파일은 테이블 구조만 정의하고, 데이터는 sql/updates/ 폴더에서 관리.
-- 예시로 초기 버전만 설정.
INSERT INTO game_data_versions (data_type, version) VALUES
('races', 0),
('classes', 0),
('items', 0),
('monsters', 0),
('covenants', 0)
ON CONFLICT (data_type) DO NOTHING; 