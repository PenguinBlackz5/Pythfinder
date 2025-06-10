import discord
from discord.ext import commands
from discord import app_commands
import os

# 지원할 오디오 파일 확장자 목록
SUPPORTED_EXTENSIONS = ('.wav', '.mp3', '.flac', '.ogg', '.m4a')


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="play_audio_file", description="첨부된 오디오 파일을 음성 채널에서 재생합니다.")
    @app_commands.describe(audio_file="재생할 오디오 파일 (mp3, wav, flac, ogg, m4a 등)을 첨부해주세요.")
    async def play(self, interaction: discord.Interaction, audio_file: discord.Attachment):
        """사용자가 첨부한 다양한 오디오 파일을 재생합니다."""

        # 사용자가 음성 채널에 있는지 확인
        if interaction.user.voice is None:
            await interaction.response.send_message("먼저 음성 채널에 접속해주세요!", ephemeral=True)
            return

        # 파일 확장자가 지원되는 형식인지 확인
        if not audio_file.filename.lower().endswith(SUPPORTED_EXTENSIONS):
            await interaction.response.send_message(
                f"지원하지 않는 파일 형식입니다!\n지원 형식: `{'`, `'.join(e.strip('.') for e in SUPPORTED_EXTENSIONS)}`",
                ephemeral=True
            )
            return

        voice_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client

        # 봇이 다른 음성 채널에 있다면, 이동
        if voice_client and voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
        # 봇이 음성 채널에 없다면, 새로 연결
        elif not voice_client:
            voice_client = await voice_channel.connect()

        # 이미 재생 중인 오디오가 있다면 중지
        if voice_client.is_playing():
            voice_client.stop()

        # 파일 다운로드 및 처리에 시간이 걸릴 수 있으므로 '생각 중' 상태로 전환
        await interaction.response.defer(thinking=True)

        temp_file_path = f"temp_{interaction.id}{os.path.splitext(audio_file.filename)[1]}"

        try:
            # 첨부 파일을 임시로 저장 (원본 확장자 유지)
            await audio_file.save(temp_file_path)

            # FFmpeg를 사용하여 오디오 소스 생성 및 재생
            # FFmpeg가 다양한 포맷을 자동으로 처리해줍니다.
            audio_source = discord.FFmpegPCMAudio(temp_file_path)

            # 재생이 끝나면 임시 파일을 삭제하도록 콜백 설정
            def after_playing(error):
                if error:
                    print(f'재생 중 오류 발생: {error}')
                try:
                    os.remove(temp_file_path)
                except OSError as e:
                    print(f"임시 파일 삭제 오류: {e}")

            voice_client.play(audio_source, after=after_playing)

            await interaction.followup.send(f"🎵 **{audio_file.filename}** 파일을 재생합니다.")

        except Exception as e:
            await interaction.followup.send(f"오류가 발생했습니다: {e}")
            # 오류 발생 시에도 임시 파일이 남아있으면 삭제
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))