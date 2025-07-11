# 게임 디자인 상세 기획서: 던전 앤 디스코드 (v3.0 - Tarkov-lite)

### 1. 컨셉 및 비전 (Concept & Vision)

- **게임명**: 던전 앤 디스코드 (Dungeons & Discord)
- **장르**: 장비 기반 로그라이트 (Equipment-based Rogue-lite)
- **핵심 비전**: 디스코드에서 즐기는, 리스크와 리턴의 저울질이 핵심인 텍스트 기반 로그라이트. 플레이어는 자신의 '기지'에서 직접 장비를 세팅하여 탐험에 나서고, 죽음의 리스크를 감수하며 더 좋은 전리품을 획득하여 돌아오는 중독적인 플레이 루프를 경험한다.

### 2. 주요 레퍼런스 (Key References)

- **Escape from Tarkov / Dark and Darker**: **"리스크와 리턴"**의 핵심 철학. 자신이 가진 장비를 걸고 더 큰 보상을 위해 탐험에 나서며, 죽음으로 모든 것을 잃는 극도의 긴장감.
- **Slay the Spire**: **"아이템 시너지"**의 중요성. 각기 다른 장비와 소모품들이 조합되어 강력한 효과를 내는 빌드 구성의 재미를 벤치마킹.
- **로그라이크 본연의 가치**: 절차적으로 생성되는 맵과 아이템 배치를 통해, 암기가 아닌 **임기응변**으로 위기를 극복하는 재미를 유지.

### 3. 핵심 디자인 철학 (Core Design Philosophy)


- **철학 1: 모든 탐험은 한 판의 투자다 (Every Run is an Investment)**
    - 플레이어는 탐험을 시작하기 전에 '이번 판에 무엇을 걸 것인가?'를 결정해야 한다. 맨몸으로 들어가 적은 리스크를 질 수도, 최고의 장비를 모두 걸고 큰 리턴을 노릴 수도 있다. 이 선택 자체가 게임 플레이의 시작이다.

- **철학 2: 소유는 탈출해야 완성된다 (Ownership is Earned by Extraction)**
    - 던전 안에서 획득한 아이템은 '내 것'이 아니다. 오직 '탈출'에 성공했을 때만 비로소 '나의 자산'이 된다. 이는 플레이어가 탐욕과 생존 본능 사이에서 끊임없이 갈등하게 만든다.

- **철학 3: 지식과 경험이 곧 레벨이다 (Knowledge and Experience are Your Levels)**
    - 캐릭터의 레벨은 존재하지 않는다. 플레이어의 성장은 몬스터의 패턴, 아이템의 가치, 맵의 위험 요소를 학습하는 '플레이어 자신의 경험'과, 성공적인 탐험을 통해 축적한 '기지의 자산'으로 이루어진다.

### 4. 게임의 흐름 (Game Flow Cycle)

게임은 `기지 → 탐험 → 기지`로 이어지는 순환 구조를 가집니다.

1.  **준비 (`/기지`)**:
    - 플레이어는 자신의 **창고(Stash)**를 확인한다.
    - 이번 탐험의 목표와 리스크 수준을 고려하여, 창고의 아이템을 캐릭터 인벤토리로 옮겨 장비를 세팅한다.
    - `/탐험시작` 명령어로 준비된 캐릭터를 던전에 보낸다.

2.  **탐험 (The Run)**:
    - 절차적으로 생성된 던전에 입장한다. 던전은 아래로만 향하는 **일방통행 구조**이다.
    - 몬스터를 처치하고 상자를 열어 새로운 아이템과 **'마석(Magic Stone)'**을 획득한다.
    - 탐험 중 획득한 장비로 실시간으로 더 강해지거나, 상황에 맞게 장비를 교체한다.

3.  **탈출 또는 사망**:
    - **탈출**: 던전의 특정 지점에서 '탈출 포탈'을 활성화하거나, 희귀 소모품 `귀환 스크롤`을 사용하여 탐험을 성공적으로 마칠 수 있다.
        - **결과**: 탐험에 사용된 캐릭터가 장착/소지하고 있던 모든 아이템과 '마석'이 `/기지`의 창고로 안전하게 이전된다.
    - **사망**: HP가 0이 되어 탐험에 실패한다.
        - **결과**: **탐험에 가져갔던 모든 장비와, 그 안에서 새로 주운 모든 아이템, 그리고 수집한 '마석'까지 전부 영구적으로 소실된다.**

4.  **성장 및 재정비 (`/기지`)**:
    - 성공적으로 가져온 전리품을 창고에 정리한다.
    - 획득한 '마석'을 팔아 '골드'를 마련하거나, '마석'을 직접 사용하여 창고를 확장하는 등 영구적인 업그레이드를 진행한다.
    - 다시 1번 단계로 돌아가 다음 탐험을 준비한다.

### 5. 핵심 시스템 상세 설계 (Core System Details)

#### 5.1. 기지: 당신의 개인 공간
- **디자인 의도**: 플레이어의 모든 자산을 관리하고, 다음 탐험을 위한 전략을 구상하는 핵심 허브.
- **주요 기능**:
    - **창고 (Stash)**: 아이템을 보관하는 공간. 모든 아이템은 고유 ID를 가지며, DB의 `stash_items` 테이블에 플레이어 ID와 함께 저장된다. 창고 공간은 제한되며, '마석'으로 확장할 수 있다.
    - **캐릭터 관리**: 플레이어는 여러 캐릭터 슬롯을 가질 수 있다. 각 캐릭터는 고유한 종족/직업 조합을 가지며, 이는 기본 능력치(체력, 힘 등)에 영향을 준다. 탐험 준비 시, 창고의 아이템을 선택한 캐릭터의 인벤토리(`character_inventory`)로 옮긴다.
    - **상점 및 시설**:
        - **골드 상점**: '골드'를 화폐로 다른 유저나 NPC와 아이템을 거래합니다.
        - **마석 시설**: '마석'을 사용하여 창고 확장, 제작대 등 기지 시설물을 영구적으로 업그레이드합니다.

#### 5.2. 아이템 기반 성장
- **레벨 시스템 배제**: 캐릭터는 경험치를 얻거나 레벨업을 하지 않는다.
- **성장의 두 축**:
    1.  **단기적 성장 (탐험 내부)**: 탐험 중에 더 좋은 등급의 무기, 방어구를 주워 즉시 강해진다.
    2.  **장기적 성장 (기지)**: 성공적인 탈출을 통해 축적한 강력한 장비들을 기반으로, 다음 탐험의 시작점을 더 높게 설정한다.
- **아이템 등급**: 아이템은 `일반(회색)` < `고급(녹색)` < `희귀(파란색)` < `영웅(보라색)` < `전설(주황색)` 등급으로 나뉘며, 등급이 높을수록 강력한 고유 능력을 가질 확률이 높다.

#### 5.3. 절차적 던전 생성
- **알고리즘**: '방과 복도' 방식을 유지하되, **일방통행** 구조로 변경한다.
- **구조**:
    - 각 층은 `N`개의 방으로 구성된다.
    - 시작 지점은 항상 존재한다.
    - `N/2` 번째 방 이후부터 **'탈출 포탈'**이 무작위 위치의 방에 생성될 수 있다. '탈출 포탈'은 활성화하는 데 일정 턴이 소요되어 위험을 감수해야 한다.
    - 가장 마지막 방에는 다음 층으로 내려가는 **'계단'**이 항상 존재한다.

#### 5.4. 재화: 마석과 골드 (Currency: Magic Stones and Gold)
- **디자인 의도**: 게임의 핵심 루프를 강화하고, 플레이어에게 단기적 목표(장비 획득)와 장기적 목표(영구적 성장)를 동시에 제공하기 위해 이원화된 재화 시스템을 도입합니다.

- **`마석 (Magic Stone)`: 성장의 촉매**
    - **획득처**: 몬스터 드랍, 숨겨진 상자 등 **오직 던전 내부**에서만 획득 가능.
    - **소유권 확정**: '탈출'에 성공해야만 플레이어의 자산(`player_wallet`)으로 확정된다. 사망 시 모두 잃는다.
    - **주요 사용처**:
        1.  **기지 시설물 업그레이드**: 창고 확장, 제작대 활성화 등 영구적인 메타 프로그레션에 사용된다.
        2.  **골드 환전**: 기지의 특정 NPC에게 판매하여 주류 경제 화폐인 '골드'로 교환할 수 있다.
        3.  **고급 서비스 이용**: 희귀 아이템 상인 호출, 특수 제작 의뢰 등 후반 컨텐츠에 사용된다.

- **`골드 (Gold)`: 경제의 기반**
    - **획득처**: '마석'이나 불필요한 장비를 판매하여 획득.
    - **소유권 확정**: 기지에서 거래가 이루어지므로 잃을 위험이 없다.
    - **주요 사용처**:
        1.  **장비 및 소모품 구매**: 다른 플레이어나 NPC 상인으로부터 다음 탐험에 필요한 아이템을 구매한다.
        2.  **서비스 이용료**: 장비 수리, 아이템 감정 등 각종 편의 서비스를 이용할 때 지불한다.

### 6. UI/UX 및 렌더링 상세

#### 6.1. 화면 구성 (Screen Layout)
- **디자인 의도**: 한정된 공간 안에서 게임의 모든 정보를 효율적으로 전달합니다. 플레이어는 하나의 메시지만 보고도 게임의 모든 상황을 파악할 수 있어야 합니다.
- **레이아웃**: 모든 게임 정보는 단일 디스코드 메시지(임베드) 안에서 실시간으로 업데이트됩니다.
    1.  **미니맵 (Viewport)**: 플레이어를 중심으로 한정된 범위(예: 21x11)의 맵을 보여주는 **'뷰포트'** 방식. ` ``` ` 코드 블록을 사용하여 텍스트가 깨지지 않는 고정폭 글꼴로 렌더링합니다.
    2.  **상태 바 (Status Bar)**: 플레이어의 현재 HP, MP, 레벨, 던전 층수 등 핵심 스탯을 표시합니다.
    3.  **메시지 로그 (Message Log)**: "플레이어가 고블린을 공격하여 5의 피해를 입혔습니다." 와 같이, 전투나 탐험 중 발생하는 모든 이벤트 로그를 순서대로 보여줍니다.
    4.  **행동 버튼 (Action Buttons)**: 8방향 이동 버튼, `관찰하기`, `줍기`, `계단 이용` 등 현재 상황에서 가능한 행동 버튼들을 제공합니다. 8방향 이동 버튼은 3x3 격자로 배치하여 조작 편의성을 확보합니다.

#### 6.2. 렌더링 및 상호작용 설계 (Rendering & Interaction Design)

##### 6.2.1. 뷰포트 렌더링 (Viewport Rendering)
- **설계 의도**: 사용자의 Discord 클라이언트 환경(창 크기, 폰트 설정)이나 메시지 글자 수 제한에 관계없이, 언제나 동일하고 안정적인 그래픽을 제공하는 것을 목표로 합니다.
- **구현 방식**:
    - 전체 맵을 한 번에 전송하는 대신, 플레이어를 중심으로 한 고정된 크기(예: 21x11)의 **뷰포트**만 잘라내어 렌더링합니다.
    - 이 뷰포트 텍스트는 항상 코드 블록(\`\`\`)으로 감싸, 고정폭 글꼴로 출력되게 함으로써 이모지/문자 간의 정렬이 어긋나지 않도록 보장합니다.
    - 이 방식은 전송 데이터 양을 최소화하여 Discord의 메시지 글자 수 제한(2000자) 문제를 원천적으로 방지합니다.

##### 6.2.2. 그래픽 요소: 100% 이모지 (Graphical Elements: 100% Emoji)
- **설계 의도**: 아스키 문자와 이모지를 혼용할 때 발생하는 문자 폭 차이로 인한 그리드 깨짐 현상을 방지하고, 다채로운 비주얼을 통해 게임의 시각적 매력을 극대화합니다.
- **구현 방식**:
    - 맵을 구성하는 모든 그래픽 요소를 이모지로 통일합니다.
    - **이모지 규칙 (예시)**:
        - **플레이어**: `🙂`
        - **몬스터**: `👺`(고블린), `🐍`(독사), `🐀`(쥐)
        - **아이템**: `💎`(마석), `💰`(골드), `🧪`(물약), `📜`(주문서)
        - **지형**: `🟩`(바닥), `🟫`(벽), `🔼`(윗계단), `🔽`(아랫계단), `🚪`(문)

##### 6.2.3. 시야 시스템의 시각적 표현 (Visual Representation of FoV)
- **설계 의도**: 색상 사용이 불가능한 텍스트 환경의 한계를 극복하고, '시야', '기억', '미탐험' 상태를 직관적으로 구분하여 플레이어에게 명확한 정보를 전달합니다.
- **구현 방식**:
    - 각 시야 상태를 각기 다른 테마의 이모지 셋(Set)으로 표현합니다.
        - **`시야 내 (Visible)`**: 현재 플레이어의 시야에 들어오는 영역. 모든 오브젝트(몬스터, 아이템, 지형)가 **생생한 컬러 이모지**로 표시됩니다. (`👺`, `💎`, `🟩`)
        - **`기억 속 (Memorized)`**: 이전에 방문했지만 현재는 보이지 않는 영역. 지형의 구조만 **단색 도형 이모지**로 표시됩니다. (`▫️` 바닥, `🔳` 벽). 아이템이나 몬스터는 표시되지 않아 오래된 정보임을 암시합니다.
        - **`탐험 전 (Unexplored)`**: 아직 한 번도 방문하지 않은 미지의 영역. 안개를 상징하는 `⚫` 이모지로 채워집니다.

##### 6.2.4. 행동과 상호작용 (Actions & Interactions)
- **설계 의도**: 단순 이동 외에 '관찰'과 '줍기' 같은 명확한 상호작용을 정의하여, 플레이어가 더 깊이 있고 신중하게 게임을 플레이하도록 유도합니다.

- **주요 행동 정의**:
    - **`이동 (Movement)`**:
        - **방향**: 대각선을 포함한 8방향 이동을 지원합니다. 이는 위치 선정, 적 공격 회피, 원거리 공격 각 확보 등 전투와 탐험의 핵심적인 전략 요소로 작용합니다.
        - **UI**: 8개의 이동 버튼은 3x3 격자 형태로 배치하여(예: 숫자 키패드 모양) 많은 버튼이 난잡해 보이지 않고 직관적으로 조작할 수 있게 합니다. 중앙 버튼은 `대기` 혹은 `아이템 사용` 등으로 활용될 수 있습니다.
            - **기술적 구현**: Discord API는 한 메시지에 최대 5개의 '줄(ActionRow)'을, 각 줄에 최대 5개의 버튼을 허용합니다. 따라서 3x3 격자 버튼은 3개의 줄에 각각 3개의 버튼을 배치하는 방식으로 충분히 구현 가능합니다.
        - **액션 처리 및 최적화 (Action Handling & Optimization)**:
            - **문제 인식**: 플레이어가 이동 버튼을 빠르게 연속으로 누를 경우, 각 입력이 개별 턴으로 처리되어야 하지만 Discord API의 업데이트 속도 제한 문제가 발생할 수 있습니다. '관찰'과 달리 이동은 모든 입력이 순서대로 반영되어야 하므로 '디바운싱' 기법은 부적합합니다.
            - **해결 방안 (입력 잠금)**: '디바운싱' 대신 **입력 잠금(Input Locking)** 메커니즘을 사용합니다.
                1. 플레이어가 이동 버튼을 누르면, 즉시 모든 행동 버튼을 '비활성화'하여 추가 입력을 막습니다.
                2. 봇이 해당 턴의 모든 로직(플레이어 이동, 몬스터 행동 등)을 처리합니다.
                3. 게임 상태 업데이트가 완료되고 Discord 메시지(화면)가 성공적으로 갱신되면, 버튼을 다시 '활성화'합니다.
                4. 이를 통해 모든 입력이 순차적으로 처리되면서도 API 호출을 제어하여 안정적인 플레이 경험을 제공합니다.

    - **`관찰하기 (Observe)`**:
        - **개념**: 위험을 감수하기 전에 주변을 정찰하는 능력입니다. 단순 '조사'를 넘어선 '정찰'의 개념입니다.
        - **작동 방식**:
            1. 플레이어가 `관찰하기` 버튼을 누르면 '관찰 모드'로 전환됩니다.
            2. 이동 버튼이 '관찰 커서 이동' 기능으로 일시적으로 변경됩니다.
            3. 플레이어는 자신의 시야(FoV) 내에서 커서를 자유롭게 움직여 원하는 타일을 선택합니다.
            4. 커서가 위치한 타일의 상세 정보(예: `[지형:돌 바닥], [함정:화살 함정]이 설치되어 있습니다.`, `[적:고블린 정찰병]이 경계하고 있습니다.`)가 메시지 로그에 표시됩니다.
            5. `관찰하기`를 다시 누르거나 `취소` 버튼을 선택하면 원래의 탐험 모드로 돌아옵니다.
        - **업데이트 최적화 (Update Optimization)**:
            - **문제 인식**: '관찰 모드'에서 커서를 이동할 때마다 메시지를 수정하면, Discord API의 속도 제한(Rate Limit)에 의해 요청이 누락되거나 지연될 수 있습니다.
            - **해결 방안 (디바운싱)**: 플레이어가 커서 이동 버튼을 누를 때마다 즉시 메시지를 갱신하지 않습니다. 대신, 마지막 조작 후 일정 시간(예: 0.5초) 동안 추가 입력이 없으면, 그 때 한 번만 최신 커서 위치의 정보로 메시지를 갱신합니다. 이를 통해 불필요한 API 호출을 최소화하고 안정적인 사용자 경험을 제공합니다.

    - **`아이템 줍기 (Pick Up)`**:
        - **개념**: 바닥에 있는 아이템을 줍는 행동입니다.
        - **작동 방식**:
            1. 플레이어가 아이템이 있는 타일로 이동하면 `줍기` 버튼이 활성화됩니다.
            2. `줍기` 버튼을 누르면, 해당 타일의 아이템 목록을 보여주는 '타일 상세 보기' UI가 나타납니다.
            3. 플레이어는 이 UI를 통해 원하는 아이템만 골라서 줍거나, `모두 줍기`를 할 수 있습니다.

##### 6.2.5. 타일 점유 규칙 (Tile Occupancy Rules)
- **설계 의도**: 게임 내 객체들의 공간 배치를 명확히 하여, '몬스터와 플레이어가 겹치는' 등의 논리적 오류를 방지하고 예측 가능한 게임 환경을 만듭니다.
- **구현 방식**:
    - 타일은 `지형(Terrain)` → `아이템(Items)` → `액터(Actor)` 순의 논리적 레이어 구조를 가집니다.
    - **핵심 규칙**: 하나의 타일에는 단 하나의 **액터(플레이어 또는 몬스터)**만 존재할 수 있습니다.
    - 이에 따라, 플레이어가 몬스터와 같은 타일에 위치하는 경우는 발생하지 않습니다. 단, 플레이어는 아이템이 쌓여 있는 타일로는 자유롭게 이동할 수 있으며, 해당 타일에서 `조사하기`를 통해 상호작용합니다.