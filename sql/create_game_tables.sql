-- =================================================================
-- TextRPG: 던전 앤 디스코드 테이블 생성 스크립트
-- 버전: 3.2 (User-Centric)
-- 마지막 수정: (현재 날짜)
-- 설명: 장비 기반 로그라이트 게임 컨셉에 맞춘 전체 데이터베이스 스키마.
--        'game_users' 테이블을 중심으로 데이터 구조를 재편.
-- 재실행 가능하도록 DROP 및 CREATE IF NOT EXISTS 구문 사용.
-- =================================================================

-- ==== 신규: 게임 유저 테이블 ====
-- 설명: 게임을 플레이하는 유저의 Discord ID를 관리하는 중앙 테이블.
--      다른 플레이어 데이터 테이블들이 이 테이블을 참조합니다.
CREATE TABLE IF NOT EXISTS game_users (
    user_id BIGINT PRIMARY KEY, -- Discord User ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- ==== 마스터 데이터 테이블 ====

-- 1. 종족 마스터 테이블 (Races)
CREATE TABLE IF NOT EXISTS game_races (
    race_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    base_stats JSONB -- 예: {"hp": 100, "strength": 10, "agility": 8}
);

-- 2. 직업 마스터 테이블 (Classes)
CREATE TABLE IF NOT EXISTS game_classes (
    class_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    starting_items JSONB -- 예: [{"item_name": "낡은 검", "quantity": 1}]
);

-- 3. 아이템 마스터 테이블 (Items)
CREATE TABLE IF NOT EXISTS game_items (
    item_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    item_type VARCHAR(50) NOT NULL, -- 'WEAPON', 'ARMOR', 'CONSUMABLE', 'MAGIC_STONE', 'MATERIAL'
    slot VARCHAR(50), -- 'HEAD', 'CHEST', 'LEGS', 'HANDS', 'FEET', 'MAIN_HAND', 'OFF_HAND'
    effects JSONB, -- 예: {"damage": 5, "defense": 3, "heal_amount": 20}
    is_stackable BOOLEAN DEFAULT FALSE
);

-- 4. 몬스터 마스터 테이블 (Monsters)
CREATE TABLE IF NOT EXISTS game_monsters (
    monster_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    base_stats JSONB, -- 예: {"hp": 50, "attack": 8, "defense": 2}
    drop_table JSONB, -- 예: {"magic_stone_min": 1, "magic_stone_max": 5, "items": [{"item_name": "가죽 조각", "chance": 0.5}]}
    dungeon_level_min INT NOT NULL DEFAULT 1
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


-- ==== 플레이어 영구 데이터 테이블 (대대적 수정) ====

-- 6. 플레이어 캐릭터 슬롯 정보
-- 설명: 플레이어가 보유한 영구적인 캐릭터 슬롯 목록. 레벨, 경험치 등 1회성 탐험 정보는 모두 제거.
-- user_id에 더 이상 UNIQUE 제약 없음 (한 유저가 여러 캐릭터 생성 가능).
CREATE TABLE IF NOT EXISTS player_characters (
    character_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    character_name VARCHAR(100) NOT NULL,
    race_id INT NOT NULL,
    class_id INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 탐험 중인지를 나타내는 상태. TRUE이면 해당 캐릭터는 은신처에 없음.
    is_on_run BOOLEAN NOT NULL DEFAULT FALSE, 

    UNIQUE (user_id, character_name), -- 한 유저는 동일한 이름의 캐릭터를 가질 수 없음
    FOREIGN KEY (user_id) REFERENCES game_users(user_id) ON DELETE CASCADE, -- 유저가 탈퇴하면 캐릭터도 삭제
    FOREIGN KEY (race_id) REFERENCES game_races(race_id),
    FOREIGN KEY (class_id) REFERENCES game_classes(class_id)
);

-- 7. 플레이어 은신처 창고 (신규)
-- 설명: 플레이어의 모든 자산(아이템)을 보관하는 영구적인 창고.
CREATE TABLE IF NOT EXISTS player_stash (
    stash_item_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL, -- 캐릭터가 아닌 유저에게 귀속
    item_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    
    -- 아이템의 개별 속성 (예: 내구도, 강화 단계 등)
    attributes JSONB,

    FOREIGN KEY (user_id) REFERENCES game_users(user_id) ON DELETE CASCADE, -- 유저가 탈퇴하면 창고 아이템도 삭제
    FOREIGN KEY (item_id) REFERENCES game_items(item_id)
);

-- 8. 플레이어 지갑 (신규, 구 '룬' 테이블 수정)
-- 설명: 플레이어의 영구적인 재화 '마석'과 '골드'를 관리.
CREATE TABLE IF NOT EXISTS player_wallet (
    user_id BIGINT PRIMARY KEY,
    magic_stones INT NOT NULL DEFAULT 0,
    gold BIGINT NOT NULL DEFAULT 0,

    FOREIGN KEY (user_id) REFERENCES game_users(user_id) ON DELETE CASCADE -- 유저가 탈퇴하면 지갑도 삭제
);

-- 9. 탐험 기록 (구 '묘비' 테이블 수정)
-- 설명: 사망 뿐 아니라 성공적인 탈출을 포함한 모든 탐험의 요약 기록.
CREATE TABLE IF NOT EXISTS game_run_history (
    run_id SERIAL PRIMARY KEY,
    character_id INT NOT NULL,
    user_id BIGINT NOT NULL,
    
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    
    -- 'ESCAPED', 'KILLED_BY_GOBLIN', 'DISCONNECTED' 등
    end_status VARCHAR(255), 
    
    floor_reached INT NOT NULL,
    magic_stones_extracted INT NOT NULL DEFAULT 0,

    FOREIGN KEY (character_id) REFERENCES player_characters(character_id) ON DELETE CASCADE, -- 캐릭터가 삭제되면 기록도 삭제
    FOREIGN KEY (user_id) REFERENCES game_users(user_id) ON DELETE CASCADE -- 유저가 탈퇴하면 기록도 삭제
);


-- ==== 시스템 테이블 (구조 유지 및 단순화) ====

-- 10. 데이터 버전 관리 테이블
-- 설명: 종족, 직업 등 마스터 데이터의 버전을 관리.
CREATE TABLE IF NOT EXISTS game_data_versions (
    data_type VARCHAR(50) PRIMARY KEY,
    version INT NOT NULL DEFAULT 0
);


-- ==== 삭제된 테이블 ====
-- game_inventory: 탐험 중 인벤토리는 게임 상태로 관리, DB에 저장하지 않음. 탈출 성공 시에만 player_stash로 이전.
-- game_character_covenants: 계약 시스템은 새로운 기획에서 보류.
-- (기존) game_characters: 1회성 탐험 정보가 많아 새로운 기획과 맞지 않아 재설계.
-- (기존) game_character_history: 이름과 역할을 더 명확하게 변경.


-- ==== 초기 데이터 삽입 ====
INSERT INTO game_data_versions (data_type, version) VALUES
('races', 0),
('classes', 0),
('items', 0),
('monsters', 0)
ON CONFLICT (data_type) DO NOTHING; 