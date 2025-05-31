# cogs/gemini_cog.py

import discord
from discord import app_commands  # app_commands 임포트
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
            self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')  # 또는 'gemini-pro' 등
            logger.info("✅ Gemini Cog가 성공적으로 로드되었으며, Gemini 모델이 초기화되었습니다.")
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

        if not prompt:
            await interaction.response.send_message(
                "🤔 질문 내용을 입력해주세요!",
                ephemeral=True
            )
            return

        # API 호출 시간이 걸릴 수 있으므로 defer를 호출하여 사용자에게 응답 대기 중임을 알림
        # ephemeral=False로 설정하면 "Bot is thinking..." 메시지가 공개적으로 보임
        # 답변 자체를 ephemeral=True로 하고 싶다면 여기서 ephemeral=True로 설정할 수 있음
        await interaction.response.defer(thinking=True, ephemeral=False)

        try:
            logger.info(f"➡️ Gemini API 요청 (Slash): '{prompt}' (요청자: {interaction.user.name})")

            # 비동기 API 호출
            response = await self.model.generate_content_async(prompt)

            response_text = ""
            if response.text:
                response_text = response.text
                logger.info(f"⬅️ Gemini API 응답 성공 (요청자: {interaction.user.name})")
            else:
                # 응답이 비어있거나, 안전상의 이유로 차단된 경우 처리
                block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "알 수 없음"
                error_message_parts = [f"Gemini AI로부터 응답을 받지 못했습니다. 😔 (차단 사유: {block_reason})"]

                candidate_info_available = hasattr(response, 'candidates') and response.candidates
                if candidate_info_available:
                    finish_reason = response.candidates[0].finish_reason.name if response.candidates[
                        0].finish_reason else "알 수 없음"
                    if finish_reason != "STOP":  # STOP이 아닌 다른 이유로 종료된 경우
                        error_message_parts.append(f"종료 사유: {finish_reason}")

                    if response.candidates[0].safety_ratings:
                        safety_info_parts = [
                            f"{s.category.name.replace('HARM_CATEGORY_', '')}: {s.probability.name}"
                            for s in response.candidates[0].safety_ratings
                            if s.probability.name not in ["NEGLIGIBLE", "LOW"]  # 보통 또는 높음만 표시 (조정 가능)
                        ]
                        if safety_info_parts:
                            error_message_parts.append("감지된 안전 문제: " + ", ".join(safety_info_parts))

                response_text = "\n".join(error_message_parts)
                logger.warning(
                    f"Gemini API 응답 없음 또는 차단됨 (요청자: {interaction.user.name}, 사유: {block_reason}, "
                    f"종료 사유: {finish_reason if candidate_info_available and 'finish_reason' in locals() else 'N/A'})"
                )

            # defer를 사용했으므로 followup.send로 응답합니다.
            if len(response_text) > 1990:
                chunks = [response_text[i:i + 1990] for i in range(0, len(response_text), 1990)]
                await interaction.followup.send(chunks[0])  # 첫 번째 청크 전송
                for chunk in chunks[1:]:
                    # 후속 청크는 채널에 직접 보내거나, followup을 여러 번 사용
                    # followup을 여러 번 사용하면 각 청크가 별도
                    await interaction.followup.send(chunk)
            else:
                await interaction.followup.send(response_text)

        except Exception as e:
            logger.error(f"Gemini API 처리 중 오류 발생 (Slash): {e} (요청자: {interaction.user.name})")
            # 이미 defer 되었으므로 followup.send 사용
            await interaction.followup.send(
                f"죄송합니다, Gemini API와 통신 중 오류가 발생했습니다: `{type(e).__name__}: {e}` 😭",
                ephemeral=True  # 오류는 사용자에게만 보이도록
            )


async def setup(bot: commands.Bot):
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    cog_instance = GeminiCog(bot)

    if not gemini_api_key:
        logger.error("🚨 GEMINI_API_KEY 환경 변수가 설정되지 않아 GeminiCog를 로드할 수 없습니다 (기능 제한됨).")
        # Cog는 추가하되, model이 None이므로 커맨드 사용 시 오류
    # API 키가 있더라도 모델 초기화 실패 시 self.model이 None

    await bot.add_cog(cog_instance)
    if cog_instance.model:  # 모델이 성공적으로 초기화된 경우에만
        logger.info("🚀 GeminiCog가 봇에 성공적으로 추가되었으며, 슬래시 커맨드 등록 준비가 되었습니다.")
    else:
        logger.warning("⚠️ GeminiCog가 봇에 추가되었으나, Gemini 모델이 초기화되지 않아 기능이 제한됩니다.")