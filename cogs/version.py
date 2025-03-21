import os

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import requests
import datetime
from dotenv import load_dotenv
import subprocess
import pytz

# .env 파일에서 환경 변수 로드
load_dotenv()


class Version(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.github_token = os.getenv("GITHUB_TOKEN")

        # 봇의 로컬 버전 정보를 저장할 변수들
        self.local_commit_hash = None
        self.local_commit_date = None
        self.local_commit_message = None
        self.local_commit_author = None

        # 봇이 시작될 때 로컬 버전 정보 가져오기
        self.get_local_version()

    def get_local_version(self):
        """봇의 로컬 git 정보를 가져오는 함수"""
        try:
            # 현재 커밋 해시 가져오기

            self.local_commit_hash = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                universal_newlines=True,
                encoding="utf-8"
            ).strip()[:7]  # 7자리만 사용

            # 현재 커밋 날짜 가져오기
            date_str = subprocess.check_output(
                ["git", "show", "-s", "--format=%ci", "HEAD"],
                universal_newlines=True,
                encoding="utf-8"
            ).strip()
            self.local_commit_date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")

            # 현재 커밋 메시지 가져오기
            self.local_commit_message = subprocess.check_output(
                ["git", "show", "-s", "--format=%s", "HEAD"],
                universal_newlines=True,
                encoding="utf-8"
            ).strip()

            # 현재 커밋 작성자 가져오기
            self.local_commit_author = subprocess.check_output(
                ["git", "show", "-s", "--format=%an", "HEAD"],
                universal_newlines=True,
                encoding="utf-8"
            )

            print(f"✅ 로컬 버전 정보 로드 완료: {self.local_commit_hash}")
        except Exception as e:
            print(f"로컬 버전 정보 로드 실패: {e}")
            self.local_commit_hash = None
            self.local_commit_date = None
            self.local_commit_message = "Git 정보를 가져올 수 없습니다."
            self.local_commit_author = "홍길동"
        except FileNotFoundError as e:
            print(e)

    PUBLIC_OR_NOT_CHOICES = [
        app_commands.Choice(name="True", value="True"),
        app_commands.Choice(name="False", value="False")
    ]

    @app_commands.command(name="버전", description="봇의 현재 버전과 최신 업데이트 정보를 확인합니다.")
    @app_commands.describe(public="공개 메세지 여부를 선택하세요.")
    @app_commands.choices(public=PUBLIC_OR_NOT_CHOICES)
    async def version(self, interaction: discord.Interaction, public: app_commands.Choice[str]):
        if public == "True":
            await interaction.response.defer(ephemeral=True)
        else:
            await interaction.response.defer()

        try:
            # GitHub API를 통해 최신 커밋 정보 가져오기
            api_url = f"https://api.github.com/repos/PenguinBlackz5/Pythfinder/commits"
            headers = {
                'Accept': 'application/vnd.github.v3+json'
            }

            # GitHub 개인 액세스 토큰을 헤더에 추가
            if self.github_token:
                headers['Authorization'] = f"token {self.github_token}"

            response = requests.get(api_url, headers=headers)

            if response.status_code == 200:
                commits = response.json()
                if commits:
                    latest_commit = commits[0]

                    # 최신 커밋 정보 추출
                    remote_commit_hash = latest_commit['sha'][:7]
                    remote_commit_message = latest_commit['commit']['message']
                    remote_commit_url = latest_commit['html_url']
                    remote_commit_author = latest_commit['commit']['author']['name']

                    # 커밋 날짜 변환
                    remote_date_str = latest_commit['commit']['author']['date']
                    remote_commit_date = datetime.datetime.strptime(remote_date_str, "%Y-%m-%dT%H:%M:%SZ")

                    # 한국 시간
                    kst_timezone = pytz.timezone('Asia/Seoul')
                    remote_commit_date_kst = remote_commit_date.replace(tzinfo=timezone.utc).astimezone(kst_timezone)

                    # KST로 포맷팅
                    remote_formatted_date = remote_commit_date_kst.strftime("%Y년 %m월 %d일 %H:%M")

                    # 로컬 커밋 날짜 포맷팅
                    if self.local_commit_date is not None:
                        local_formatted_date = self.local_commit_date.strftime("%Y년 %m월 %d일 %H:%M")
                    else:
                        local_formatted_date = "unknown"

                    # 버전 비교
                    if self.local_commit_hash:
                        is_latest = self.local_commit_hash == remote_commit_hash
                        status_emoji = "✅" if is_latest else "⚠️"
                        status_text = "최신 버전입니다!" if is_latest else "업데이트가 필요합니다!"
                    else:
                        self.local_commit_hash = "unknown"
                        status_emoji = "✅"
                        status_text = "최신 버전의 정보를 표시합니다."


                    # 임베드 생성
                    embed = discord.Embed(
                        title=f"{status_emoji} 봇 버전 정보",
                        description=f"**상태**: {status_text}\n**저장소**: [PenguinBlackz5/Pythfinder](https://github.com/PenguinBlackz5/Pythfinder)",
                        color=0x00ff00 if is_latest else 0xffcc00
                    )

                    # 현재 버전 필드
                    if self.local_commit_hash:
                        embed.add_field(
                            name="📌 현재 실행 중인 버전",
                            value=f"```#️⃣: {self.local_commit_hash}\n📅: {local_formatted_date}\n🗣️:"
                                  f" {self.local_commit_author} / {self.local_commit_message}```",
                            inline=False
                        )

                    # 최신 버전 필드
                    embed.add_field(
                        name="🔄 GitHub 최신 버전",
                        value=f"```#️⃣: {remote_commit_hash}\n📅: {remote_formatted_date}\n🗣️: {remote_commit_author} / {remote_commit_message}```\n[GitHub에서 보기]({remote_commit_url})",
                        inline=False
                    )

                    embed.set_footer(
                        text=f"봇 버전 확인 시간: {datetime.datetime.now(kst_timezone).strftime('%Y-%m-%d %H:%M:%S')}")

                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("저장소에서 커밋 정보를 찾을 수 없습니다.")
            elif response.status_code == 401:
                await interaction.followup.send("GitHub API 인증 실패: 토큰이 유효하지 않거나 권한이 부족합니다.")
            elif response.status_code == 404:
                await interaction.followup.send("GitHub API 요청 실패: 리포지토리를 찾을 수 없거나 접근 권한이 없습니다.")
            else:
                await interaction.followup.send(f"GitHub API 요청 실패: {response.status_code}")

        except Exception as e:
            await interaction.followup.send(f"오류 발생: {str(e)}")


async def setup(bot):
    await bot.add_cog(Version(bot))
