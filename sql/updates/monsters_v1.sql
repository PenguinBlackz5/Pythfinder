-- monsters_v1.sql
-- 클래식 로그라이크 컨셉에 맞춰 기본 몬스터 데이터를 수정합니다.
-- 던전 1층에서 만날 수 있는 기본적인 몬스터들을 설정합니다.

INSERT INTO game_monsters (name, hp, attack, defense, reward_exp, reward_gold, dungeon_level_min) VALUES
('굶주린 쥐', 10, 8, 2, 5, 2, 1),
('고블린', 20, 12, 5, 10, 8, 1),
('독사', 15, 10, 3, 12, 10, 1), -- 독 공격 특수 능력을 가질 수 있음
('던전 슬라임', 30, 8, 8, 15, 5, 1) -- 높은 방어력, 낮은 공격력
ON CONFLICT (name) DO UPDATE SET
hp = EXCLUDED.hp,
attack = EXCLUDED.attack,
defense = EXCLUDED.defense,
reward_exp = EXCLUDED.reward_exp,
reward_gold = EXCLUDED.reward_gold,
dungeon_level_min = EXCLUDED.dungeon_level_min; 