# Discord Gemini AI 봇 기획서

## 1. 프로젝트 개요
Google Gemini API를 활용한 Discord AI 챗봇 개발 기획서입니다. 이 봇은 다양한 캐릭터 페르소나를 가진 AI와 대화할 수 있으며, 이미지 인식 기능도 제공합니다.

## 2. 주요 기능 요구사항

### 2.1 기본 기능
- 일회성 AI 대화 기능
- 캐릭터별 대화 기록 유지 기능
- 이미지 인식 및 분석 기능
- 대화 기록 조회 기능
- 대화 기록 초기화 기능

### 2.2 캐릭터 시스템
- JSON 파일 기반의 캐릭터 설정
- 캐릭터별 페르소나 적용
- 캐릭터별 아이콘 및 색상 커스터마이징
- 기본 AI 캐릭터 제공

### 2.3 이미지 처리
- 지원 이미지 형식: PNG, JPEG, WEBP, HEIC, HEIF
- 최대 파일 크기: 20MB
- 이미지 유효성 검증
- 이미지와 텍스트 조합 질문 지원

## 3. 기술 스택

### 3.1 사용 모듈
- discord.py: Discord 봇 개발
- google.genai: Google Gemini API 연동
- python-dotenv: 환경 변수 관리
- PIL (Pillow): 이미지 처리
- logging: 로깅 시스템
- json: 캐릭터 설정 파일 처리
- glob: 파일 시스템 검색
- asyncio: 비동기 처리
- io: 바이트 스트림 처리

### 3.2 API 요구사항
- Google Gemini API 키 필요
- Discord 봇 토큰 필요

## 4. 코드 구조

### 4.1 클래스 구조
```python
class GeminiCog(commands.Cog):
    def __init__(self, bot)
    def _load_characters(self)
    async def _send_gemini_request(self, interaction, prompt_parts, character_id, ...)
    async def character_autocomplete(self, interaction, current)
    async def active_character_session_autocomplete(self, interaction, current)
    async def reset_character_session_autocomplete(self, interaction, current)
    async def ask_gemini_single(self, interaction, prompt, character)
    async def ask_gemini_context(self, interaction, character, prompt)
    async def reset_gemini_context(self, interaction, character)
    async def view_gemini_history(self, interaction, character, turns)
    async def ask_gemini_file(self, interaction, attachment, prompt, character)
```

### 4.2 주요 명령어
- `/ai-chat`: 일회성 AI 대화
- `/ai-chat-memory`: 캐릭터별 대화 기록 유지
- `/ai-chat-reset`: 대화 기록 초기화
- `/ai-chat-history`: 대화 기록 조회
- `/ai-chat-file`: 이미지와 함께 질문

## 5. 에러 처리
- API 키 누락/오류 처리
- 이미지 파일 유효성 검증
- 파일 크기 제한 검사
- 캐릭터 설정 파일 오류 처리
- API 응답 오류 처리
- 안전성 검사 결과 처리

## 6. 보안 고려사항
- API 키는 환경 변수로 관리
- 사용자 권한 검증
- 안전성 설정 적용
- 에러 메시지의 적절한 표시

## 7. 확장 가능성
- 새로운 캐릭터 추가 용이
- 이미지 처리 기능 확장
- 대화 기록 관리 기능 확장
- 다국어 지원 가능
- 안전성 설정 커스터마이징

## 8. 제한사항
- Google Gemini API 할당량 제한
- 이미지 파일 크기 제한 (20MB)
- 지원 이미지 형식 제한
- 대화 기록 저장 용량 제한
- 응답 길이 제한 (Discord 임베드 제한) 