-- attendance 테이블의 money 열을 user_money 테이블로 복사

INSERT INTO "user_money" (user_id, money)
SELECT user_id, money FROM "attendance";

-- attendance 테이블의 money 열을 삭제
-- 혹시 모르니 백업해두기!!
ALTER TABLE "attendance" DROP COLUMN money;

