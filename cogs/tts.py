import discord
from discord import app_commands
from discord.ext import commands
from elevenlabs import Voice, VoiceSettings
from elevenlabs.client import ElevenLabs
import os
from dotenv import load_dotenv
import io

load_dotenv()

# ElevenLabs 클라이언트 초기화
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    print("경고: ELEVENLABS_API_KEY 환경 변수가 설정되지 않았습니다. TTS 기능이 작동하지 않을 수 있습니다.")
    client = None
else:
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)


class TTSCog(commands.Cog):
    """
    ElevenLabs API를 사용하여 텍스트를 음성으로 변환하는 기능을 담은 Cog입니다.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._voices_cache = None  # 목소리 목록을 캐싱하기 위한 변수

    async def _get_voice_id(self, voice_name: str) -> str | None:
        """목소리 이름으로 Voice ID를 찾습니다. 캐시를 활용하여 API 호출을 줄입니다."""
        if self._voices_cache is None:
            try:
                self._voices_cache = client.voices.get_all().voices
            except Exception as e:
                print(f"목소리 목록 캐싱 실패: {e}")
                return None

        for voice in self._voices_cache:
            if voice.name.lower() == voice_name.lower():
                return voice.voice_id
        return None

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
    @app_commands.describe(
        text="봇이 말할 내용을 입력하세요.",
        voice="사용할 목소리 이름 (기본: Alice)",
        stability="목소리 안정성 (0.0 ~ 1.0)",
        similarity_boost="유사성 증폭 (0.0 ~ 1.0)"
    )
    async def say(self,
                  interaction: discord.Interaction,
                  text: str,
                  voice: str = "Alice",
                  stability: app_commands.Range[float, 0.0, 1.0] = None,
                  similarity_boost: app_commands.Range[float, 0.0, 1.0] = None):
        """입력된 텍스트를 음성으로 변환하여 채널에서 재생합니다."""
        if client is None:
            await interaction.response.send_message("오류: ElevenLabs 클라이언트가 초기화되지 않았습니다. 봇 관리자는 API 키 설정을 확인해주세요.",
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
            # 목소리 이름으로 Voice ID를 조회
            voice_id = await self._get_voice_id(voice)
            if not voice_id:
                await interaction.followup.send(f"`{voice}`라는 목소리를 찾을 수 없습니다. `/voices` 명령어로 사용 가능한 목소리를 확인해주세요.",
                                                ephemeral=True)
                return

            voice_settings = None
            if stability is not None or similarity_boost is not None:
                voice_settings = VoiceSettings(
                    stability=stability if stability is not None else 0.75,
                    similarity_boost=similarity_boost if similarity_boost is not None else 0.75
                )

            audio_iterator = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                voice_settings=voice_settings
            )

            audio_data = b"".join(audio_iterator)

            if not audio_data:
                await interaction.followup.send("음성 데이터를 생성하는 데 실패했습니다. API 키 또는 입력 내용을 확인해주세요.", ephemeral=True)
                return

            audio_source = io.BytesIO(audio_data)

            voice_client.play(
                discord.FFmpegPCMAudio(source=audio_source, pipe=True),
                after=lambda e: print(f'재생 완료. 오류: {e}' if e else None)
            )

            await interaction.followup.send(f"🔊 **{voice}**: {text}")

        except Exception as e:
            print(f"ElevenLabs TTS 기능에서 오류 발생: {e}")
            error_message = str(e).lower()
            if "unauthenticated" in error_message:
                await interaction.followup.send("API 키가 잘못되었거나 설정되지 않았습니다. 봇 관리자에게 문의해주세요.", ephemeral=True)
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

    @app_commands.command(name="voices", description="사용 가능한 ElevenLabs 목소리 목록을 보여줍니다.")
    async def voices(self, interaction: discord.Interaction):
        """API를 통해 사용 가능한 목소리 목록을 가져와 보여줍니다."""
        if client is None:
            await interaction.response.send_message("오류: ElevenLabs 클라이언트가 초기화되지 않았습니다. 봇 관리자는 API 키 설정을 확인해주세요.",
                                                    ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            self._voices_cache = client.voices.get_all().voices
            if not self._voices_cache:
                await interaction.followup.send("사용 가능한 목소리를 찾을 수 없습니다.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🎤 ElevenLabs 목소리 목록",
                description="`/say` 명령어의 `voice` 옵션에 아래 이름을 사용하세요.",
                color=discord.Color.teal()
            )

            premade_voices = sorted([v.name for v in self._voices_cache if v.category == 'premade'])
            cloned_voices = sorted([v.name for v in self._voices_cache if v.category != 'premade'])

            if premade_voices:
                embed.add_field(name="기본 제공 목소리", value=", ".join(premade_voices), inline=False)

            if cloned_voices:
                embed.add_field(name="사용자 정의 목소리", value=", ".join(cloned_voices), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"목소리 목록을 가져오는 중 오류 발생: {e}")
            self._voices_cache = None  # 오류 발생 시 캐시 초기화
            await interaction.followup.send("목소리 목록을 가져오는 데 실패했습니다. API 키를 확인해주세요.", ephemeral=True)


async def setup(bot: commands.Bot):
    if client is None:
        print("ElevenLabs 클라이언트가 초기화되지 않아 TTSCog를 로드하지 않습니다.")
        return
    await bot.add_cog(TTSCog(bot))
