# cogs/gemini_cog.py

import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
import os
import logging
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)


class GeminiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("🚨 GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. Cog를 로드할 수 없습니다.")
            self.model = None
            return

        try:
            genai.configure(api_key=self.api_key)
            # 사용자가 제공한 모델 이름 사용
            self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
            logger.info(f"✅ Gemini Cog가 성공적으로 로드되었으며, Gemini 모델({self.model.model_name})이 초기화되었습니다.")
        except Exception as e:
            logger.error(f"Gemini 모델 초기화 중 오류 발생: {e}")
            self.model = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.api_key:
            logger.warning("⚠️ GeminiCog: GEMINI_API_KEY가 없어 Gemini 관련 기능을 사용할 수 없습니다.")
        elif not self.model:
            logger.warning("⚠️ GeminiCog: Gemini 모델 초기화에 실패하여 관련 기능을 사용할 수 없습니다.")
        else:
            logger.info(f'{self.bot.user.name} 봇의 GeminiCog가 준비되었습니다.')

    @app_commands.command(name="ai-chat", description="✨ Gemini AI에게 질문합니다.")
    @app_commands.describe(prompt="Gemini AI에게 전달할 질문 내용입니다.")
    async def ask_gemini_slash(self, interaction: discord.Interaction, prompt: str):
        """Gemini AI 모델에게 주어진 프롬프트에 대한 응답을 요청합니다."""

        if not self.model:
            await interaction.response.send_message(
                "죄송합니다, Gemini AI 모델이 현재 초기화되지 않았거나 사용할 수 없습니다. 😥 관리자에게 문의해주세요.",
                ephemeral=True
            )
            return

        # 프롬프트가 비어있는 경우 (일반적으로 슬래시 커맨드에서 'required=True'로 설정되므로 불필요할 수 있음)
        if not prompt.strip():
            await interaction.response.send_message(
                "🤔 질문 내용을 입력해주세요!",
                ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=False)

        try:
            logger.info(
                f"➡️ Gemini API 요청 (Slash): '{prompt[:200]}...' (요청자: {interaction.user.name} ({interaction.user.id}))")

            response = await self.model.generate_content_async(prompt)

            response_text_content = ""  # AI의 실제 답변 또는 정보/오류 메시지

            if response.text:
                response_text_content = response.text
                logger.info(f"⬅️ Gemini API 응답 성공 (요청자: {interaction.user.name})")
            else:
                block_reason = "알 수 없음"
                finish_reason_str = "알 수 없음"
                safety_info_str = ""

                if response.prompt_feedback:
                    block_reason = response.prompt_feedback.block_reason.name if response.prompt_feedback.block_reason else "제공되지 않음"

                error_message_parts = [f"Gemini AI로부터 응답을 받지 못했습니다. 😔 (차단 사유: {block_reason})"]

                candidate_info_available = hasattr(response, 'candidates') and response.candidates
                if candidate_info_available:
                    current_candidate = response.candidates[0]
                    if current_candidate.finish_reason:
                        finish_reason_str = current_candidate.finish_reason.name
                    if finish_reason_str != "STOP":
                        error_message_parts.append(f"종료 사유: {finish_reason_str}")

                    if current_candidate.safety_ratings:
                        safety_info_parts = [
                            f"{s.category.name.replace('HARM_CATEGORY_', '')}: {s.probability.name}"
                            for s in current_candidate.safety_ratings
                            if s.probability.name not in ["NEGLIGIBLE", "LOW"]
                        ]
                        if safety_info_parts:
                            safety_info_str = ", ".join(safety_info_parts)
                            error_message_parts.append(f"감지된 안전 문제: {safety_info_str}")

                response_text_content = "\n".join(error_message_parts)
                logger.warning(
                    f"Gemini API 응답 없음 또는 차단됨 (요청자: {interaction.user.name}, 차단: {block_reason}, 종료: {finish_reason_str}, 안전문제: '{safety_info_str if safety_info_str else '없음'}')"
                )

            # Embed 생성
            embed = discord.Embed(
                color=discord.Color.from_rgb(123, 104, 238),  # MediumSlateBlue 색상 또는 원하는 색상
                timestamp=interaction.created_at  # 메시지 생성 시간
            )
            embed.set_author(
                name=f"{interaction.user.display_name} 님의 질문에 대한 응답:",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else discord.Embed.Empty
            )

            # 프롬프트 표시 (Embed 필드 값 최대 1024자)
            # discord.utils.escape_markdown을 사용하여 마크다운 특수문자 처리
            prompt_display_value = discord.utils.escape_markdown(prompt)
            if len(prompt_display_value) > 1020:  # 약간의 여유
                prompt_display_value = prompt_display_value[:1020] + "..."
            embed.add_field(name="📝 원본 프롬프트", value=f"```{prompt_display_value}```", inline=False)

            # AI 답변 또는 정보 메시지 처리
            if not response_text_content.strip():
                response_text_content = "알 수 없는 이유로 응답 내용이 비어있습니다."

            # 답변을 Embed 설명에 추가 (Embed 설명 최대 4096자)
            if len(response_text_content) <= 4000:  # 약간의 여유
                embed.description = response_text_content
                await interaction.followup.send(embed=embed)
            else:
                # 내용이 너무 길 경우, Embed 설명에는 일부만 표시하고 나머지는 별도 메시지로 전송
                embed.description = response_text_content[:4000] + "\n\n**(내용이 길어 일부만 표시됩니다. 전체 내용은 아래 메시지를 참고하세요.)**"
                await interaction.followup.send(embed=embed)

                remaining_response = response_text_content[4000:]
                # Discord 메시지당 최대 2000자 제한
                chunks = [remaining_response[i:i + 1990] for i in range(0, len(remaining_response), 1990)]
                for chunk in chunks:
                    await interaction.followup.send(chunk)

        except Exception as e:
            logger.error(f"Gemini API 처리 중 예기치 않은 오류 발생 (Slash): {e}", exc_info=True)
            await interaction.followup.send(
                f"죄송합니다, 요청 처리 중 예기치 않은 오류가 발생했습니다: `{type(e).__name__}` 😭 관리자에게 문의해주세요.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    cog_instance = GeminiCog(bot)

    if not gemini_api_key:  # API 키가 없어도 Cog는 로드되지만, 기능은 제한됨
        logger.error("🚨 GEMINI_API_KEY 환경 변수가 설정되지 않았습니다 (기능 제한됨).")

    await bot.add_cog(cog_instance)
    if cog_instance.model:
        logger.info(f"🚀 GeminiCog (모델: {cog_instance.model.model_name})가 봇에 성공적으로 추가되었습니다.")
    else:
        logger.warning("⚠️ GeminiCog가 봇에 추가되었으나, Gemini 모델이 초기화되지 않아 기능이 제한됩니다.")