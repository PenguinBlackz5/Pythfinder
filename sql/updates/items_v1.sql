-- items_v1.sql
-- 클래식 로그라이크 컨셉에 맞춰 기본 아이템 데이터를 수정 및 확장합니다.
-- 직업별 시작 아이템과 기본적인 소모품(물약, 주문서)을 포함합니다.

INSERT INTO game_items (name, description, item_type, effects) VALUES
-- 무기
('녹슨 장검', '오랫동안 사용되지 않은 듯한 장검입니다. 기본적인 무기입니다.', 'WEAPON', '{"attack": 5}'),
('오래된 마법봉', '끝에 작은 보석이 박힌 마법봉. 희미한 마력이 느껴집니다.', 'WEAPON', '{"attack": 2, "magic_power": 4}'),
('날카로운 단검', '잘 벼려져 있어 치명적인 일격을 가하기 좋은 단검입니다.', 'WEAPON', '{"attack": 3, "crit_chance": 0.1}'),

-- 방어구
('가죽 갑옷', '가볍고 활동성이 좋은 기본적인 방어구입니다.', 'ARMOR', '{"defense": 5}'),

-- 소모품 (물약)
('치료 물약', '마시면 상처가 회복되는 붉은색 물약입니다.', 'POTION', '{"heal_hp": 50}'),
('해독 물약', '독을 중화시키는 효과가 있는 푸른색 물약입니다.', 'POTION', '{"cure_poison": true}'),
('마나 물약', '마시면 정신이 맑아지며 마나가 회복됩니다.', 'POTION', '{"heal_mp": 30}'),

-- 소모품 (주문서)
('마법 화살 주문서', '읽으면 마법 화살이 날아갑니다. "Iactus Sagitta" 라고 적혀있습니다.', 'SCROLL', '{"cast_spell": "magic_missile", "damage": 20}'),
('빛 주문서', '읽으면 주변을 밝히는 빛을 생성합니다. "Fiat Lux" 라고 적혀있습니다.', 'SCROLL', '{"cast_spell": "light", "duration": 100}'),
('순간이동 주문서', '읽으면 현재 층의 무작위 위치로 이동합니다. "Teleportus" 라고 적혀있습니다.', 'SCROLL', '{"cast_spell": "teleport"}'),
('아이템 식별 주문서', '읽으면 가지고 있는 아이템 하나의 정체를 밝혀줍니다.', 'SCROLL', '{"cast_spell": "identify"}'),

-- 소모품 (기타)
('던전 지도', '사용하면 현재 층의 구조를 모두 밝혀줍니다. 일회용품입니다.', 'CONSUMABLE', '{"reveal_map": true}')

ON CONFLICT (name) DO UPDATE SET
description = EXCLUDED.description,
item_type = EXCLUDED.item_type,
effects = EXCLUDED.effects; 