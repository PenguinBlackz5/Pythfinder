# Discord TTS 봇 기획서

## 1. 프로젝트 개요
Google Gemini API를 활용한 Discord TTS(Text-to-Speech) 봇 개발 기획서입니다. 이 봇은 텍스트를 음성으로 변환하여 Discord 음성 채널에서 재생하는 기능을 제공합니다.

## 2. 주요 기능 요구사항

### 2.1 기본 기능
- Discord 음성 채널 참여/퇴장 기능
- 텍스트를 음성으로 변환하여 재생
- 다양한 음성 옵션 제공
- 감정 표현 기능 지원
- 음성 파일 다운로드 기능

### 2.2 음성 옵션
- 8개 카테고리, 총 25개의 다양한 음성 제공
  - 밝은 계열 (Zephyr, Autonoe, Leda)
  - 경쾌한 계열 (Puck, Aoede, Laomedeia)
  - 차분한 계열 (Kore, Charon, Iapetus 등)
  - 부드러운 계열 (Callirrhoe, Algieba, Despina 등)
  - 친근한 계열 (Umbriel, Achird, Sulafat)
  - 활기찬 계열 (Fenrir, Sadachbia)
  - 전문적인 계열 (Orus, Gacrux, Sadaltager 등)
  - 특별한 계열 (Enceladus, Algenib, Alnilam 등)

### 2.3 감정 표현
- 기본, 차분하게, 화난듯이, 슬프게, 행복하게, 신나게, 속삭이듯이, 무섭게, 피곤하게, 열정적으로
- 커스텀 감정 표현 지원

## 3. 기술 스택

### 3.1 사용 모듈
- discord.py: Discord 봇 개발
- google.genai: Google Gemini API 연동
- python-dotenv: 환경 변수 관리
- asyncio: 비동기 처리
- wave: 오디오 파일 처리
- io: 바이트 스트림 처리

### 3.2 API 요구사항
- Google Gemini API 키 필요
- Discord 봇 토큰 필요

## 4. 코드 구조

### 4.1 클래스 구조
```python
class TTSCog(commands.Cog):
    def __init__(self, bot)
    async def _generate_tts_async(self, text, voice)
    def _create_wave_file(self, pcm_data, channels, rate, sample_width)
    async def voice_autocomplete(self, interaction, current)
    async def join(self, interaction)
    async def say(self, interaction, text, emotion, custom_emotion, voice)
    async def leave(self, interaction)
    async def voices(self, interaction)
```

### 4.2 주요 명령어
- `/join`: 봇을 음성 채널에 참여
- `/say`: 텍스트를 음성으로 변환하여 재생
- `/leave`: 봇을 음성 채널에서 퇴장
- `/voices`: 사용 가능한 음성 목록 표시

## 5. 에러 처리
- API 키 누락/오류 처리
- 음성 채널 연결 상태 확인
- 재생 중복 방지
- API 할당량 초과 처리
- 일반적인 오류 처리 및 로깅

## 6. 보안 고려사항
- API 키는 환경 변수로 관리
- 사용자 권한 검증
- 에러 메시지의 적절한 표시

## 7. 확장 가능성
- 새로운 음성 추가 용이
- 감정 표현 확장 가능
- 오디오 품질 설정 추가 가능
- 다국어 지원 가능

## 8. 제한사항
- Google Gemini API 할당량 제한
- Discord 음성 채널 연결 제한
- 동시 재생 불가
- 음성 파일 크기 제한 