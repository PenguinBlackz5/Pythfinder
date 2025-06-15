-- attendance 테이블의 money 열을 user_money 테이블로 복사

INSERT INTO user_balance (user_id, balance)
SELECT user_id, money FROM user_attendance;

-- attendance 테이블의 money 열을 삭제
-- 혹시 모르니 백업해두기!!
ALTER TABLE user_attendance DROP COLUMN money;

