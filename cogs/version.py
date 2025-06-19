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
from typing import Optional, List
from database_manager import execute_query
from main import is_admin_or_developer, DEVELOPER_IDS, KST
import sentry_sdk

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
        self.deploy_time = datetime.datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
        self.get_local_version()

    def get_local_version(self):
        """봇의 로컬 git 정보를 가져오는 함수
        없다면 대신 배포 시간을 가져움"""
        try:
            # 현재 커밋 해시 가져오기

            self.local_commit_hash = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                encoding="utf-8"
            ).strip()[:7]  # 7자리만 사용

            # 현재 커밋 날짜 가져오기
            date_str = subprocess.check_output(
                ["git", "show", "-s", "--format=%ci", "HEAD"],
                text=True,
                encoding="utf-8"
            ).strip()
            self.local_commit_date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")

            # 현재 커밋 메시지 가져오기
            self.local_commit_message = subprocess.check_output(
                ["git", "show", "-s", "--format=%s", "HEAD"],
                text=True,
                encoding="utf-8"
            ).strip()

            # 현재 커밋 작성자 가져오기
            self.local_commit_author = subprocess.check_output(
                ["git", "show", "-s", "--format=%an", "HEAD"],
                text=True,
                encoding="utf-8"
            ).strip()

            print(f"✅ 로컬 버전 정보 로드 완료: {self.local_commit_hash}")
        except FileNotFoundError:
            print("Git이 설치되어 있지 않거나 경로가 잘못되었습니다. 로컬 버전 정보를 로드할 수 없습니다.")
            self.local_commit_hash = "정보 없음"
            self.local_commit_date = None
            self.local_commit_message = "Git 정보를 찾을 수 없습니다."
            self.local_commit_author = "정보 없음"
        except Exception as e:
            print(f"로컬 버전 정보 로드 실패: {e}")
            self.local_commit_hash = "봇 실행 시간"
            self.local_commit_date = None
            self.local_commit_message = "재실행 될 때까지 기다려주세요!"
            self.local_commit_author = "봇이 마지막으로 실행된 시간입니다."

    PUBLIC_OR_NOT_CHOICES = [
        app_commands.Choice(name="True", value="True"),
        app_commands.Choice(name="False", value="False")
    ]

    @app_commands.command(name="버전", description="봇의 현재 버전과 최신 업데이트 정보를 확인합니다.")
    @app_commands.describe(public="공개 메세지 여부를 선택하세요.")
    @app_commands.choices(public=PUBLIC_OR_NOT_CHOICES)
    async def version(self, interaction: discord.Interaction, public: app_commands.Choice[str]):
        if public.value == "True":
            await interaction.response.defer(ephemeral=False)
        else:
            await interaction.response.defer(ephemeral=True)

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

                    # 한국 시간대 객체 생성
                    kst_timezone = pytz.timezone('Asia/Seoul')
                    
                    # UTC 시간을 KST로 변환
                    remote_commit_date_kst = remote_commit_date.replace(tzinfo=timezone.utc).astimezone(kst_timezone)

                    # 모든 날짜/시간 형식을 통일
                    common_format = "%Y년 %m월 %d일 %H:%M:%S"
                    remote_formatted_date = remote_commit_date_kst.strftime(common_format)

                    # 로컬 커밋 날짜 포맷팅 (존재하는 경우)
                    if self.local_commit_date:
                        local_formatted_date = self.local_commit_date.astimezone(kst_timezone).strftime(common_format)
                        deploy_dt = self.local_commit_date.astimezone(kst_timezone) # 비교를 위해 datetime 객체 저장
                    else:
                        # Git 정보를 못 가져왔을 때의 대체 시간 포맷팅
                        try:
                            # 'YYYY-MM-DD HH:MM:SS' 형식의 deploy_time을 datetime 객체로 파싱
                            deploy_dt = datetime.datetime.strptime(self.deploy_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=kst_timezone)
                            local_formatted_date = deploy_dt.strftime(common_format)
                        except ValueError:
                            deploy_dt = None
                            local_formatted_date = self.deploy_time # 파싱 실패 시 원본 표시

                    # 버전 비교 로직 개선
                    is_local_version_available = self.local_commit_hash not in ["정보 없음", "봇 실행 시간"]

                    if is_local_version_available:
                        # 로컬 Git 정보가 있을 경우: 커밋 해시로 비교
                        is_latest = self.local_commit_hash == remote_commit_hash
                        status_emoji = "✅" if is_latest else "⚠️"
                        status_text = "최신 버전입니다!" if is_latest else "업데이트가 필요합니다!"
                        color = 0x00ff00 if is_latest else 0xffcc00
                    elif deploy_dt:
                        # 로컬 Git 정보가 없을 경우: 봇 시작 시간과 최신 커밋 시간으로 비교
                        is_latest = deploy_dt >= remote_commit_date_kst
                        status_emoji = "✅" if is_latest else "⚠️"
                        status_text = "최신 버전입니다!" if is_latest else "업데이트가 필요합니다!"
                        color = 0x00ff00 if is_latest else 0xffcc00
                    else:
                        # 시간 정보도 없을 경우 (최악의 경우)
                        is_latest = False
                        status_emoji = "❓"
                        status_text = "로컬 버전을 확인할 수 없어, 업데이트 필요 여부를 판단할 수 없습니다."
                        color = 0x95a5a6  # 회색

                    # 임베드 생성
                    embed = discord.Embed(
                        title=f"{status_emoji} 봇 버전 정보",
                        description=f"**상태**: {status_text}\n**저장소**: [PenguinBlackz5/Pythfinder](https://github.com/PenguinBlackz5/Pythfinder)",
                        color=color
                    )

                    # 현재 버전 필드 (항상 표시)
                    embed.add_field(
                        name="📌 현재 실행 중인 버전",
                        value=f"```#️⃣: {self.local_commit_hash}\n"
                              f"📅: {local_formatted_date}\n"
                              f"🗣️: {self.local_commit_author} / {self.local_commit_message}```",
                        inline=False
                    )

                    # 최신 버전 필드
                    embed.add_field(
                        name="🔄 GitHub 최신 버전",
                        value=f"```#️⃣: {remote_commit_hash}\n"
                              f"📅: {remote_formatted_date}\n"
                              f"🗣️: {remote_commit_author} / {remote_commit_message}```\n"
                              f"[GitHub에서 보기]({remote_commit_url})",
                        inline=False
                    )

                    # 게임 데이터 버전 정보 추가
                    text_rpg_cog = self.bot.get_cog("TextRPG")
                    if text_rpg_cog and hasattr(text_rpg_cog, 'data_versions') and text_rpg_cog.data_versions:
                        data_version_info = []
                        for data_type, version in text_rpg_cog.data_versions.items():
                            data_version_info.append(f"- {data_type.capitalize()}: v{version}")
                        
                        embed.add_field(
                            name="🎮 게임 데이터 버전",
                            value="```" + "\n".join(data_version_info) + "```",
                            inline=False
                        )

                    embed.set_footer(
                        text=f"봇 버전 확인 시간: {datetime.datetime.now(kst_timezone).strftime(common_format)}"
                    )

                    await interaction.followup.send(embed=embed)
                else:
                    error_embed = discord.Embed(
                        title="❌ 오류",
                        description="저장소에서 커밋 정보를 찾을 수 없습니다.",
                        color=0xff0000
                    )
                    await interaction.followup.send(embed=error_embed)
            elif response.status_code == 401:
                error_embed = discord.Embed(
                    title="❌ 인증 오류",
                    description="GitHub API 인증 실패: 토큰이 유효하지 않거나 권한이 부족합니다.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=error_embed)
            elif response.status_code == 404:
                error_embed = discord.Embed(
                    title="❌ 리포지토리 오류",
                    description="GitHub API 요청 실패: 리포지토리를 찾을 수 없거나 접근 권한이 없습니다.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=error_embed)
            else:
                error_embed = discord.Embed(
                    title="❌ API 오류",
                    description=f"GitHub API 요청 실패: {response.status_code}",
                    color=0xff0000
                )
                await interaction.followup.send(embed=error_embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ 예외 오류",
                description=f"오류 발생: {str(e)}",
                color=0xff0000
            )
            sentry_sdk.capture_exception(e)
            await interaction.followup.send(embed=error_embed)


async def setup(bot):
    await bot.add_cog(Version(bot))
