-- races_v1.sql
-- 클래식 로그라이크 컨셉에 맞춰 기본 종족 데이터를 수정합니다.
-- 각 종족의 특성을 강화하여 역할 분담을 명확하게 합니다.

INSERT INTO game_races (name, description, base_hp, base_mp, base_attack, base_defense) VALUES
('인간', '적응력이 뛰어난 종족. 다른 종족보다 음식을 덜 소비하며, 경험치를 약간 더 얻습니다.', 100, 50, 10, 10),
('엘프', '숲과 교감하는 고대 종족. 마법에 대한 저항력이 높고, 시야가 한 칸 더 넓습니다.', 85, 80, 8, 8),
('드워프', '돌과 강철의 자손. 물리 피해에 대한 저항력을 가지며, 숨겨진 문이나 함정을 더 잘 발견합니다.', 120, 20, 12, 13)
ON CONFLICT (name) DO UPDATE SET
description = EXCLUDED.description,
base_hp = EXCLUDED.base_hp,
base_mp = EXCLUDED.base_mp,
base_attack = EXCLUDED.base_attack,
base_defense = EXCLUDED.base_defense; 