import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
import os
import logging
from dotenv import load_dotenv
from PIL import Image  # 이미지 처리를 위해 추가
import io  # 바이트 스트림 처리를 위해 추가

# .env 파일에서 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

# 지원하는 이미지 MIME 타입 (Gemini API 기준)
SUPPORTED_IMAGE_MIME_TYPES = [
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
]


class GeminiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20")

        self.model = None
        if not self.api_key:
            logger.error("🚨 GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. Cog를 로드할 수 없습니다.")
            return

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"✅ Gemini Cog가 성공적으로 로드되었으며, Gemini 모델({self.model.model_name})이 초기화되었습니다.")
        except Exception as e:
            logger.error(f"Gemini 모델 ({self.model_name}) 초기화 중 오류 발생: {e}")
            self.model = None

        # 사용자별 대화 기록 (ChatSession 저장)
        self.user_conversations = {}  # {user_id: ChatSession}

    async def _send_gemini_request(self, interaction: discord.Interaction, prompt_parts: list,
                                   ephemeral_response: bool = False, chat_session: genai.ChatSession = None):
        """
        Gemini API에 요청을 보내고 응답을 처리하는 내부 헬퍼 함수.
        prompt_parts: 텍스트 또는 [텍스트, 이미지_데이터] 형태의 리스트.
        chat_session: 대화형 요청인 경우 ChatSession 객체.
        ephemeral_response: 응답을 요청자에게만 보이게 할지 여부.
        """
        if not self.model:
            # defer가 이미 호출된 경우 followup 사용
            message_content = "죄송합니다, Gemini AI 모델이 현재 초기화되지 않았거나 사용할 수 없습니다. 😥 관리자에게 문의해주세요."
            if interaction.response.is_done():
                await interaction.followup.send(message_content, ephemeral=True)
            else:  # 거의 발생하지 않지만, 만약을 위해
                await interaction.response.send_message(message_content, ephemeral=True)
            return

        try:
            # 프롬프트 로깅 (간소화)
            log_prompt_part = prompt_parts[0] if isinstance(prompt_parts[0], str) else "[이미지 포함된 프롬프트]"
            logger.info(
                f"➡️ Gemini API 요청: '{str(log_prompt_part)[:100]}...' (요청자: {interaction.user.name} ({interaction.user.id}), 대화형: {'예' if chat_session else '아니오'})"
            )

            response = None
            if chat_session:
                # ChatSession 사용 시, content는 단일 값 또는 리스트 ([text, image])
                content_to_send = prompt_parts
                if len(prompt_parts) == 1 and isinstance(prompt_parts[0], str):
                    content_to_send = prompt_parts[0]  # 텍스트만 있는 경우 문자열로 전달
                response = await chat_session.send_message_async(content_to_send)
            else:
                response = await self.model.generate_content_async(prompt_parts)

            response_text_content = ""

            if response.text:
                response_text_content = response.text
                logger.info(f"⬅️ Gemini API 응답 성공 (요청자: {interaction.user.name})")
            else:
                block_reason = "알 수 없음"
                finish_reason_str = "알 수 없음"
                safety_info_str = ""

                if hasattr(response,
                           'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                    block_reason = response.prompt_feedback.block_reason.name

                error_message_parts = [f"Gemini AI로부터 텍스트 응답을 받지 못했습니다. 😔"]
                if block_reason != "BLOCK_REASON_UNSPECIFIED" and block_reason != "알 수 없음":
                    error_message_parts.append(f"차단 사유: {block_reason}")

                candidate_info_available = hasattr(response, 'candidates') and response.candidates
                if candidate_info_available:
                    current_candidate = response.candidates[0]
                    if current_candidate.finish_reason:
                        finish_reason_str = current_candidate.finish_reason.name
                    if finish_reason_str not in ["STOP", "FINISH_REASON_UNSPECIFIED"]:  # STOP이 아니면 문제로 간주
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
                    f"Gemini API 응답 없음 또는 문제 발생 (요청자: {interaction.user.name}, 차단: {block_reason}, 종료: {finish_reason_str}, 안전문제: '{safety_info_str if safety_info_str else '없음'}')"
                )

            # Embed 생성
            embed = discord.Embed(
                color=discord.Color.purple(),  # Embed 색상 변경
                timestamp=interaction.created_at
            )
            embed.set_author(
                name=f"{interaction.user.display_name} 님의 요청에 대한 응답:",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else discord.Embed.Empty
            )

            prompt_display_text = ""
            if isinstance(prompt_parts[0], str):  # 텍스트 프롬프트가 있는 경우
                prompt_text_for_display = discord.utils.escape_markdown(prompt_parts[0])
                if len(prompt_text_for_display) > 1000:  # 필드 값 제한 고려
                    prompt_text_for_display = prompt_text_for_display[:1000] + "..."
                prompt_display_text = f"```{prompt_text_for_display}```"

            # 파일 첨부 여부 표시
            is_file_attached = any(isinstance(part, dict) and "mime_type" in part for part in prompt_parts)
            if is_file_attached:
                if prompt_display_text:
                    prompt_display_text += "\n📄 (첨부 파일과 함께 요청됨)"
                else:  # 프롬프트 없이 파일만 첨부한 경우 (ai-chat-file에서 빈 프롬프트 시 기본 프롬프트 사용)
                    prompt_display_text = "📄 (첨부 파일과 함께 요청됨)"

            if prompt_display_text:
                embed.add_field(name="📝 원본 요청", value=prompt_display_text, inline=False)

            if not response_text_content.strip():
                response_text_content = "응답 내용이 비어있습니다. API 제한 또는 다른 문제가 발생했을 수 있습니다."

            if len(response_text_content) <= 4000:  # Embed 설명 최대 4096자
                embed.description = response_text_content
                await interaction.followup.send(embed=embed, ephemeral=ephemeral_response)
            else:
                embed.description = response_text_content[:4000] + "\n\n**(내용이 길어 일부만 표시됩니다. 전체 내용은 아래 메시지를 참고하세요.)**"
                await interaction.followup.send(embed=embed, ephemeral=ephemeral_response)
                remaining_response = response_text_content[4000:]
                chunks = [remaining_response[i:i + 1990] for i in range(0, len(remaining_response), 1990)]
                for chunk_idx, chunk in enumerate(chunks):
                    chunk_embed = discord.Embed(
                        description=chunk,
                        color=discord.Color.purple(),
                        timestamp=interaction.created_at
                    )
                    chunk_embed.set_author(
                        name=f"이어지는 응답 ({chunk_idx + 1}/{len(chunks)})",
                        icon_url=self.bot.user.avatar.url if self.bot.user.avatar else discord.Embed.Empty
                    )
                    await interaction.followup.send(embed=chunk_embed, ephemeral=ephemeral_response)

        except Exception as e:
            logger.error(f"Gemini API 처리 중 예기치 않은 오류 발생: {e}", exc_info=True)
            error_message = f"죄송합니다, 요청 처리 중 예기치 않은 오류가 발생했습니다: `{type(e).__name__}` 😭"
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.api_key:
            logger.warning("⚠️ GeminiCog: GEMINI_API_KEY가 없어 Gemini 관련 기능을 사용할 수 없습니다.")
        elif not self.model:
            logger.warning(f"⚠️ GeminiCog: Gemini 모델({self.model_name}) 초기화에 실패하여 관련 기능을 사용할 수 없습니다.")
        else:
            logger.info(f'{self.bot.user.name} 봇의 GeminiCog가 준비되었습니다 (모델: {self.model.model_name}).')

    @app_commands.command(name="ai-chat", description="✨ Gemini AI에게 일회성 질문을 합니다 (대화 기억 X).")
    @app_commands.describe(prompt="Gemini AI에게 전달할 질문 내용입니다.")
    async def ask_gemini_single(self, interaction: discord.Interaction, prompt: str):
        if not prompt.strip():
            await interaction.response.send_message("🤔 질문 내용을 입력해주세요!", ephemeral=True)
            return
        # 공개 응답, defer thinking=True
        await interaction.response.defer(thinking=True, ephemeral=False)
        await self._send_gemini_request(interaction, [prompt], ephemeral_response=False)

    @app_commands.command(name="ai-chat-memory", description="💬 Gemini AI와 대화를 이어갑니다 (대화 기억 O).")
    @app_commands.describe(prompt="Gemini AI에게 전달할 메시지입니다.")
    async def ask_gemini_context(self, interaction: discord.Interaction, prompt: str):
        if not self.model:
            await interaction.response.send_message("죄송합니다, Gemini AI 모델이 현재 사용할 수 없습니다. 😥", ephemeral=True)
            return
        if not prompt.strip():
            await interaction.response.send_message("🤔 메시지 내용을 입력해주세요!", ephemeral=True)
            return

        # 공개 응답, defer thinking=True
        await interaction.response.defer(thinking=True, ephemeral=False)

        user_id = interaction.user.id
        if user_id not in self.user_conversations:
            # 새 대화 시작 시 안전 설정 등을 포함하여 ChatSession 초기화 가능
            # 예: safety_settings={'HARASSMENT': 'BLOCK_NONE'} 등
            self.user_conversations[user_id] = self.model.start_chat(history=[])
            logger.info(f"새로운 대화 세션 시작 (사용자: {interaction.user.name} [{user_id}])")

        chat_session = self.user_conversations[user_id]
        await self._send_gemini_request(interaction, [prompt], chat_session=chat_session, ephemeral_response=False)

    @app_commands.command(name="ai-chat-reset", description="🧹 현재 사용자의 Gemini AI 대화 기록을 초기화합니다.")
    async def reset_gemini_context(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.user_conversations:
            del self.user_conversations[user_id]  # ChatSession 객체 삭제
            logger.info(f"대화 기록 초기화 (사용자: {interaction.user.name} [{user_id}])")
            await interaction.response.send_message("✅ 당신의 AI 대화 기록이 성공적으로 초기화되었습니다. 새로운 대화를 시작할 수 있습니다.",
                                                    ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ 초기화할 대화 기록이 없습니다. `/ai-chat-memory`를 사용하여 먼저 대화를 시작해주세요.",
                                                    ephemeral=True)

    @app_commands.command(name="ai-chat-file", description="🖼️ Gemini AI에게 파일과 함께 질문합니다 (이미지 지원, 대화 기억 X).")
    @app_commands.describe(
        attachment="이미지 파일을 첨부해주세요 (PNG, JPEG, WEBP, HEIC, HEIF).",
        prompt=" (선택 사항) 이미지에 대한 질문이나 지시사항을 입력하세요."
    )
    async def ask_gemini_file(self, interaction: discord.Interaction, attachment: discord.Attachment,
                              prompt: str = None):
        if not self.model:
            await interaction.response.send_message("죄송합니다, Gemini AI 모델이 현재 사용할 수 없습니다. 😥", ephemeral=True)
            return

        if attachment.content_type not in SUPPORTED_IMAGE_MIME_TYPES:
            await interaction.response.send_message(
                f"⚠️ 지원하지 않는 파일 형식입니다. 다음 형식 중 하나를 사용해주세요: {', '.join(SUPPORTED_IMAGE_MIME_TYPES)}",
                ephemeral=True
            )
            return

        # Discord의 기본 파일 크기 제한은 25MB (Nitro 사용자는 더 큼)
        # Gemini API는 자체적인 제한이 있을 수 있음 (예: 이미지당 4MB 등 - 모델별 문서 확인)
        # 여기서는 Discord의 일반적인 제한 내에서 처리하도록 함.
        if attachment.size > 20 * 1024 * 1024:  # 예시: 20MB 제한
            await interaction.response.send_message("파일 크기가 너무 큽니다 (최대 20MB).", ephemeral=True)
            return

        # 공개 응답, defer thinking=True
        await interaction.response.defer(thinking=True, ephemeral=False)

        try:
            image_bytes = await attachment.read()

            # Pillow를 사용하여 이미지 유효성 검사 및 메타데이터 제거 시도 (선택 사항)
            try:
                with Image.open(io.BytesIO(image_bytes)) as img:
                    img.verify()  # 이미지 파일이 유효한지 기본 검사
                    # 필요한 경우 이미지 리사이징 또는 포맷 변경 등을 수행할 수 있음
                    # img.save(output_buffer, format='PNG') 등
            except Exception as img_e:
                logger.error(f"잘못되거나 손상된 이미지 파일입니다: {img_e} (요청자: {interaction.user.name})")
                await interaction.followup.send("⚠️ 첨부된 파일이 유효한 이미지 파일이 아니거나 손상되었습니다. 다른 파일을 시도해주세요.", ephemeral=True)
                return

            image_part = {
                "mime_type": attachment.content_type,
                "data": image_bytes
            }

            # 프롬프트가 제공되지 않은 경우, 이미지에 대한 일반적인 요청으로 설정
            prompt_to_send = prompt.strip() if prompt and prompt.strip() else "이 이미지에 대해 설명해주세요."

            # 멀티모달 요청: [텍스트, 이미지] 또는 [이미지, 텍스트]
            # 일반적으로 프롬프트가 먼저 오는 것이 자연스러움
            request_parts = [prompt_to_send, image_part]

            await self._send_gemini_request(interaction, request_parts, ephemeral_response=False)

        except discord.HTTPException as e:  # 파일 다운로드 실패 등 Discord 관련 HTTP 오류
            logger.error(f"첨부 파일 처리 중 Discord 오류 발생: {e} (요청자: {interaction.user.name})", exc_info=True)
            await interaction.followup.send("죄송합니다, 첨부 파일을 처리하는 중 Discord 관련 오류가 발생했습니다. 😥", ephemeral=True)
        except Exception as e:
            logger.error(f"파일 첨부 요청 처리 중 예기치 않은 오류 발생: {e} (요청자: {interaction.user.name})", exc_info=True)
            await interaction.followup.send(f"죄송합니다, 파일과 함께 요청 처리 중 오류가 발생했습니다: `{type(e).__name__}` 😥", ephemeral=True)


async def setup(bot: commands.Bot):
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    cog_instance = GeminiCog(bot)  # Cog 인스턴스는 항상 생성

    if not gemini_api_key:
        logger.error("🚨 GEMINI_API_KEY 환경 변수가 설정되지 않아 Gemini Cog의 기능이 매우 제한됩니다.")
    # Cog는 추가하되, 모델 초기화 실패는 Cog 내부에서 처리
    await bot.add_cog(cog_instance)

    if cog_instance.model:
        logger.info(f"🚀 GeminiCog (모델: {cog_instance.model.model_name})가 봇에 성공적으로 추가되었습니다.")
    else:
        # __init__에서 이미 API 키 부재 또는 모델 초기화 실패 로깅이 발생했을 것임
        logger.warning(
            f"⚠️ GeminiCog가 봇에 추가되었으나, Gemini 모델({cog_instance.model_name})이 제대로 초기화되지 않았을 수 있습니다. 로그를 확인해주세요.")