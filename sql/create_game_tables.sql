-- 게임 캐릭터 정보를 저장하는 테이블
CREATE TABLE IF NOT EXISTS game_characters (
    user_id BIGINT PRIMARY KEY,
    level INT NOT NULL DEFAULT 1,
    hp INT NOT NULL DEFAULT 100,
    max_hp INT NOT NULL DEFAULT 100,
    attack INT NOT NULL DEFAULT 10,
    defense INT NOT NULL DEFAULT 5,
    exp INT NOT NULL DEFAULT 0,
    next_exp INT NOT NULL DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 아이템 마스터 테이블
CREATE TABLE IF NOT EXISTS game_items (
    item_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    item_type VARCHAR(50) NOT NULL, -- 'EQUIPMENT', 'CONSUMABLE'
    effects JSONB -- 예: {"hp": 20} 또는 {"attack": 5}
);

-- 유저 인벤토리 테이블
CREATE TABLE IF NOT EXISTS game_inventory (
    inventory_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    is_equipped BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES game_characters(user_id),
    FOREIGN KEY (item_id) REFERENCES game_items(item_id)
);

-- 몬스터 마스터 테이블
CREATE TABLE IF NOT EXISTS game_monsters (
    monster_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    hp INT NOT NULL,
    attack INT NOT NULL,
    defense INT NOT NULL,
    reward_exp INT NOT NULL,
    reward_gold INT NOT NULL
);

-- 기본 아이템 및 몬스터 데이터 추가 (예시)
INSERT INTO game_items (name, description, item_type, effects) VALUES
('허름한 검', '기본적인 공격을 할 수 있는 검입니다.', 'EQUIPMENT', '{"attack": 2}'),
('가죽 갑옷', '기본적인 방어구입니다.', 'EQUIPMENT', '{"defense": 2}'),
('체력 물약', '사용 시 체력을 30 회복합니다.', 'CONSUMABLE', '{"hp": 30}')
ON CONFLICT (name) DO NOTHING;

INSERT INTO game_monsters (name, hp, attack, defense, reward_exp, reward_gold) VALUES
('슬라임', 20, 5, 2, 10, 5),
('고블린', 35, 8, 4, 15, 10),
('오크', 50, 12, 6, 25, 20)
ON CONFLICT (name) DO NOTHING; 