# TextRPG (던전 앤 디스코드) 개발 가이드라인

### 1. 개요 (Overview)
- 이 문서는 '던전 앤 디스코드' 게임(`TextRPG` cog) 개발에 참여하는 개발자를 위한 공식 가이드입니다.
- 코드 스타일, 개발 절차, 데이터 관리 방법을 통일하여 프로젝트의 일관성을 유지하고 협업 효율을 높이는 것을 목표로 합니다.

### 2. 프로젝트 구조 (Project Structure)
- **`cogs/text_rpg.py`**: 게임의 핵심 로직, 명령어, 이벤트 처리를 담당하는 메인 파일입니다.
- **`docs/game_plan.md`**: 모든 기능 개발 전 반드시 숙지해야 할 공식 기획서입니다.
- **`sql/`**: 데이터베이스 관련 스크립트를 관리하는 디렉토리입니다.
    - `create_game_tables.sql`: 프로젝트 초기 설정 시 모든 게임 관련 테이블을 한 번에 생성하는 스크립트입니다.
    - `sql/updates/`: 아이템, 몬스터, 퀘스트 등 정적(static) 데이터의 버전별 업데이트 스크립트를 저장하는 공간입니다. (예: `items_v2.sql`, `monsters_v3.sql`)

### 3. 개발 워크플로우 (Development Workflow)

#### 새로운 기능/명령어 추가 시
1. **기획 확인**: `docs/game_plan.md`에서 추가하려는 기능의 명세를 확인합니다.
2. **코드 작성**: `cogs/text_rpg.py`에 `@app_commands.command`를 사용하여 슬래시 명령어를 추가합니다.
3. **UI 구현**: 사용자와의 복잡한 상호작용이 필요할 경우, `discord.ui.View`와 `discord.ui.Button`을 활용하여 직관적인 인터페이스를 제공합니다.
4. **DB 연동**: 데이터베이스 접근이 필요할 때는 반드시 `database_manager.py`에 구현된 `execute_query` 함수를 통해 수행합니다.

#### 정적 데이터 (아이템, 몬스터 등) 추가/수정 시
> 이 절차는 봇의 자동화된 데이터 버전 관리 시스템을 따릅니다.

1. **버전 상수 수정**: `cogs/text_rpg.py` 파일 상단에 정의된 데이터 버전(예: `LATEST_ITEM_VERSION`)의 숫자를 1 올립니다.
2. **업데이트 SQL 파일 생성**: `sql/updates/` 디렉토리에 `[데이터타입]_v[새로운 버전].sql` 형식으로 파일을 만듭니다.
    - 예시: 아이템 데이터의 2번째 업데이트일 경우 `items_v2.sql` 파일을 생성합니다.
3. **쿼리 작성**: 생성한 SQL 파일에 `INSERT`, `UPDATE`, `DELETE` 등 필요한 쿼리를 작성합니다.
4. **자동 적용 및 확인**: 봇이 재시작되면 버전 관리 시스템이 코드와 DB의 버전 차이를 감지하고, 해당 SQL 스크립트를 자동으로 실행합니다. **초기 설정을 제외하고 수동으로 `/db실행` 명령을 호출하지 마세요.** 개발 후에는 `/버전` 명령어를 실행하여 코드와 데이터 버전이 모두 정상적으로 적용되었는지 확인합니다.

### 4. 핵심 규칙 및 코딩 컨벤션 (Key Rules & Conventions)
- **버전 확인**: 개발 및 배포 후에는 `/버전` 명령어를 사용하여 현재 봇의 **코드 버전(Git)**과 **데이터 버전(DB)**이 의도한 대로 적용되었는지 반드시 확인합니다.
- **데이터베이스 접근**: 절대 `asyncpg`를 직접 호출하지 않고, 항상 `database_manager.py`의 래퍼(wrapper) 함수를 사용해야 합니다. 이는 연결 풀 관리와 에러 로깅을 중앙화하기 위함입니다.
- **에러 처리**: `try...except` 구문을 적극적으로 활용해 예상치 못한 오류를 처리합니다. 사용자에게는 `interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)`와 같이 간결한 오류 메시지를 임시 메시지로 전달하고, 개발자가 확인할 수 있는 상세한 로그는 `sentry_sdk.capture_exception(e)`를 통해 기록합니다.
- **보안**: SQL 인젝션 공격을 방지하기 위해, 쿼리에 f-string이나 `+` 연산자로 변수를 직접 삽입하는 것을 금지합니다. 항상 `execute_query`의 `params` 인자를 사용하여 쿼리와 데이터를 분리하세요.
    - **Bad**: `await execute_query(f"SELECT * FROM users WHERE id = {user_id}")`
    - **Good**: `await execute_query("SELECT * FROM users WHERE id = $1", (user_id,))`
- **코드 스타일**: [PEP 8](https://peps.python.org/pep-0008/) 스타일 가이드를 준수하여 코드의 가독성과 일관성을 유지합니다. 