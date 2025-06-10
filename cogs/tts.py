import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
import io
import wave
import asyncio
import logging

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# Google Gemini 클라이언트 초기화
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. TTS 기능이 작동하지 않을 수 있습니다.")
    client = None
else:
    client = genai.Client(api_key=GEMINI_API_KEY)

# Google Gemini TTS에서 사용 가능한 음성 목록
AVAILABLE_VOICES = {
    # 밝은 계열
    'Zephyr': '밝음',
    'Autonoe': '밝음',
    'Leda': '젊음',

    # 경쾌한 계열
    'Puck': '경쾌함',
    'Aoede': '상쾌함',
    'Laomedeia': '경쾌함',

    # 차분한 계열
    'Kore': '확고함',
    'Charon': '정보 제공',
    'Iapetus': '명확함',
    'Erinome': '명확함',
    'Schedar': '균등함',

    # 부드러운 계열
    'Callirrhoe': '호락호락',
    'Algieba': '부드러움',
    'Despina': '부드러움',
    'Achernar': '부드러움',
    'Vindemiatrix': '부드러움',

    # 친근한 계열
    'Umbriel': '호의적',
    'Achird': '친근함',
    'Sulafat': '따뜻함',

    # 활기찬 계열
    'Fenrir': '흥분',
    'Sadachbia': '활기참',

    # 전문적인 계열
    'Orus': '회사',
    'Gacrux': '성인용',
    'Sadaltager': '전문 지식',
    'Rasalgethi': '유용한 정보',

    # 특별한 계열
    'Enceladus': '숨소리',
    'Algenib': '자갈',
    'Alnilam': '확실함',
    'Pulcherrima': '앞으로',
    'Zubenelgenubi': '캐주얼'
}


class TTSCog(commands.Cog):
    """
    Google Gemini API를 사용하여 텍스트를 음성으로 변환하는 기능을 담은 Cog입니다.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _generate_tts_async(self, text: str, voice: str):
        """TTS 생성을 비동기로 처리합니다."""
        loop = asyncio.get_event_loop()

        def generate_tts():
            # 단일 화자 설정
            return client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            )
                        )
                    ),
                )
            )

        return await loop.run_in_executor(None, generate_tts)

    def _create_wave_file(self, pcm_data, channels=1, rate=24000, sample_width=2):
        """PCM 데이터를 WAV 파일로 변환합니다."""
        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)
        audio_buffer.seek(0)
        return audio_buffer

    # 자동완성 함수
    async def voice_autocomplete(self, interaction: discord.Interaction, current: str):
        """음성 이름 자동완성"""
        return [
                   app_commands.Choice(name=f"{voice} ({description})", value=voice)
                   for voice, description in AVAILABLE_VOICES.items()
                   if current.lower() in voice.lower() or current.lower() in description.lower()
               ][:25]  # Discord 제한: 최대 25개

    @app_commands.command(name="join", description="봇을 현재 음성 채널에 참여시킵니다.")
    async def join(self, interaction: discord.Interaction):
        """사용자가 속한 음성 채널에 봇을 연결합니다."""
        if not isinstance(interaction.user, discord.Member) or not interaction.user.voice:
            await interaction.response.send_message("음성 채널에 먼저 참여해주세요!", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client

        if voice_client:
            if voice_client.channel == voice_channel:
                await interaction.response.send_message("이미 같은 음성 채널에 있습니다.", ephemeral=True)
            else:
                await voice_client.move_to(voice_channel)
                await interaction.response.send_message(f"`{voice_channel.name}` 채널로 이동했습니다.")
        else:
            await voice_channel.connect()
            await interaction.response.send_message(f"`{voice_channel.name}` 채널에 참여했습니다.")

    @app_commands.command(name="say", description="봇이 음성 채널에서 텍스트를 말하게 합니다.")
    @app_commands.choices(emotion=[
        app_commands.Choice(name='기본', value=''),
        app_commands.Choice(name='차분하게', value='calmly'),
        app_commands.Choice(name='화난듯이', value='angrily'),
        app_commands.Choice(name='슬프게', value='sadly'),
        app_commands.Choice(name='행복하게', value='happily'),
        app_commands.Choice(name='신나게', value='excitedly'),
        app_commands.Choice(name='속삭이듯이', value='in a whisper'),
        app_commands.Choice(name='무섭게', value='in a spooky way'),
        app_commands.Choice(name='피곤하게', value='tiredly'),
        app_commands.Choice(name='열정적으로', value='enthusiastically')
    ])
    @app_commands.autocomplete(voice=voice_autocomplete)
    @app_commands.describe(
        text="봇이 말할 내용을 입력하세요.",
        emotion="목소리에 적용할 감정을 선택하세요.",
        custom_emotion="직접 감정/표현을 입력합니다 (예: '나른하게'). 이 옵션 사용 시, '감정' 선택은 무시됩니다.",
        voice="사용할 목소리 이름 (기본: Kore)"
    )
    async def say(self,
                  interaction: discord.Interaction,
                  text: str,
                  emotion: str = '',
                  custom_emotion: str = None,
                  voice: str = "Kore"):
        """입력된 텍스트를 음성으로 변환하여 채널에서 재생하고 파일을 업로드합니다."""
        if client is None:
            await interaction.response.send_message("오류: Google Gemini 클라이언트가 초기화되지 않았습니다. 봇 관리자는 API 키 설정을 확인해주세요.",
                                                    ephemeral=True)
            return

        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message("봇이 음성 채널에 없습니다. 먼저 `/join` 명령어를 사용해주세요.", ephemeral=True)
            return

        if voice_client.is_playing():
            await interaction.response.send_message("봇이 이미 무언가를 재생하고 있습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            # 음성 이름 검증
            if voice not in AVAILABLE_VOICES:
                await interaction.followup.send(f"`{voice}`는 사용할 수 없는 목소리입니다. `/voices` 명령어로 사용 가능한 목소리를 확인해주세요.",
                                                ephemeral=True)
                return

            # 감정 적용된 최종 텍스트 생성
            final_text = text
            display_emotion_name = None

            if custom_emotion:
                final_text = f"Say {custom_emotion}: {text}"
                display_emotion_name = custom_emotion
            elif emotion and emotion != '':
                final_text = f"Say {emotion}: {text}"
                emotion_param = discord.utils.get(self.say.parameters, name='emotion')
                if emotion_param:
                    choice = discord.utils.get(emotion_param.choices, value=emotion)
                    if choice:
                        display_emotion_name = choice.name

            # TTS 생성을 비동기로 처리
            response = await self._generate_tts_async(final_text, voice)
            audio_data = response.candidates[0].content.parts[0].inline_data.data

            if not audio_data:
                await interaction.followup.send("음성 데이터를 생성하는 데 실패했습니다. API 키 또는 입력 내용을 확인해주세요.", ephemeral=True)
                return

            # PCM 데이터를 WAV 파일로 변환 (비동기 처리)
            loop = asyncio.get_event_loop()
            audio_source = await loop.run_in_executor(None, self._create_wave_file, audio_data)

            discord_file = discord.File(audio_source, filename=f"say_{voice}.wav")

            audio_source.seek(0)

            voice_client.play(
                discord.FFmpegPCMAudio(source=audio_source, pipe=True),
                after=lambda e: logging.error(f'재생 오류: {e}') if e else logging.info('재생 완료')
            )

            response_message = f"🔊 **{voice}** ({AVAILABLE_VOICES[voice]}): {text}"
            if display_emotion_name:
                response_message = f"😊 **{display_emotion_name}** | " + response_message

            await interaction.followup.send(response_message, file=discord_file)

        except Exception as e:
            print(f"Google Gemini TTS 기능에서 오류 발생: {e}")
            error_message = str(e).lower()
            if "api key" in error_message or "unauthorized" in error_message:
                await interaction.followup.send("API 키가 잘못되었거나 설정되지 않았습니다. 봇 관리자에게 문의해주세요.", ephemeral=True)
            elif "quota" in error_message or "limit" in error_message:
                await interaction.followup.send("API 사용량이 초과되었습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
            else:
                await interaction.followup.send("음성을 재생하는 동안 오류가 발생했습니다. 봇 로그를 확인해주세요.", ephemeral=True)

    @app_commands.command(name="leave", description="봇을 음성 채널에서 내보냅니다.")
    async def leave(self, interaction: discord.Interaction):
        """봇을 현재 음성 채널에서 연결 해제합니다."""
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.response.send_message("봇이 음성 채널에 없습니다.", ephemeral=True)
            return

        await voice_client.disconnect()
        await interaction.response.send_message("음성 채널에서 나갔습니다.")

    @app_commands.command(name="voices", description="사용 가능한 Google Gemini TTS 목소리 목록을 보여줍니다.")
    async def voices(self, interaction: discord.Interaction):
        """사용 가능한 목소리 목록을 보여줍니다."""
        embed = discord.Embed(
            title="🎤 Google Gemini TTS 목소리 목록",
            description="`/say` 명령어의 `voice` 옵션에 아래 이름을 사용하세요.",
            color=discord.Color.blue()
        )

        # 카테고리별로 정리
        categories = {
            "밝은 계열": ["Zephyr", "Autonoe", "Leda"],
            "경쾌한 계열": ["Puck", "Aoede", "Laomedeia"],
            "차분한 계열": ["Kore", "Charon", "Iapetus", "Erinome", "Schedar"],
            "부드러운 계열": ["Callirrhoe", "Algieba", "Despina", "Achernar", "Vindemiatrix"],
            "친근한 계열": ["Umbriel", "Achird", "Sulafat"],
            "활기찬 계열": ["Fenrir", "Sadachbia"],
            "전문적인 계열": ["Orus", "Gacrux", "Sadaltager", "Rasalgethi"],
            "특별한 계열": ["Enceladus", "Algenib", "Alnilam", "Pulcherrima", "Zubenelgenubi"]
        }

        for category, voice_list in categories.items():
            voice_descriptions = []
            for voice in voice_list:
                description = AVAILABLE_VOICES.get(voice, "")
                voice_descriptions.append(f"`{voice}` ({description})")

            embed.add_field(
                name=category,
                value="\n".join(voice_descriptions),
                inline=False
            )

        embed.set_footer(text=f"총 {len(AVAILABLE_VOICES)}개의 목소리 사용 가능")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    """이 cog를 봇에 추가하기 위한 진입점 함수입니다."""
    if client is None:
        print("Google Gemini 클라이언트가 초기화되지 않아 TTSCog를 로드하지 않습니다.")
        return
    await bot.add_cog(TTSCog(bot))