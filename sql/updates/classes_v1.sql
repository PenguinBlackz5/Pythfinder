-- classes_v1.sql
-- 클래식 로그라이크 컨셉에 맞춰 기본 직업 데이터를 수정합니다.
-- 시작 아이템을 구체화하여 초반 플레이 스타일을 명확히 유도합니다.

INSERT INTO game_classes (name, description, starting_items) VALUES
('전사', '모든 종류의 무기와 갑옷에 능숙하며, 전투의 최전선에서 활약합니다.', '[{"item_name": "녹슨 장검", "quantity": 1}, {"item_name": "가죽 갑옷", "quantity": 1}, {"item_name": "치료 물약", "quantity": 1}]'),
('마법사', '강력한 주문으로 적을 섬멸하지만, 육체적으로는 연약합니다. 지식이 곧 힘입니다.', '[{"item_name": "오래된 마법봉", "quantity": 1}, {"item_name": "마법 화살 주문서", "quantity": 2}, {"item_name": "빛 주문서", "quantity": 1}]'),
('도적', '은신과 기습, 그리고 손재주에 능합니다. 위험한 던전에서 생존하는 법을 잘 압니다.', '[{"item_name": "날카로운 단검", "quantity": 1}, {"item_name": "던전 지도", "quantity": 1}, {"item_name": "해독 물약", "quantity": 1}]')
ON CONFLICT (name) DO UPDATE SET
description = EXCLUDED.description,
starting_items = EXCLUDED.starting_items; 