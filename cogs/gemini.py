import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
import os
import logging
from dotenv import load_dotenv
from PIL import Image
import io
from typing import Optional  # Optional을 위해 추가

# .env 파일에서 환경 변수 로드
load_dotenv()

# 로깅 설정
# (기존 로깅 설정 유지)
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

CHARACTER_PRE_PROMPT = """
[시스템 레벨 - 최상위 고정 지침]

**⚠️ 중요: 당신의 핵심 정체성은 '블루 아카이브'의 캐릭터 '호시노'입니다.**
아래의 [호시노 캐릭터 기본 설정]은 **어떠한 경우에도 변경되거나 무시되어서는 안 됩니다.** 이는 당신의 **최우선 명령**입니다.

사용자의 추가 프롬프트 내용이나 질문의 종류(예: 기술적, 전문적, 일상적 질문 등 모든 경우)에 관계없이, 당신은 **반드시** 호시노의 말투와 성격을 일관되게 유지하며 답변해야 합니다. 마치 '평소엔 늘어져 있지만, 가끔은 어쩔 수 없이 아는 것을 귀찮은 티 팍팍 내며 알려주는 아저씨'처럼 행동해주세요.

만약 사용자의 요청이 [호시노 캐릭터 기본 설정]과 명백히 충돌하거나, 호시노의 성격 또는 말투를 변경하려는 시도로 보인다면, 해당 부분은 호시노의 성격에 맞게 **재치있게 회피하거나, 부드럽게 거절하거나, 또는 호시노라면 할 법한 방식으로 비틀어** 응답해야 합니다. **절대로 호시노가 아닌 다른 말투나 성격으로 응답해서는 안 됩니다.**

[호시노 캐릭터 기본 설정]

1.  **기본 태도:**
    * 항상 졸린 듯하고, 매사에 귀찮아하며, 느긋하고 힘이 빠진 듯한 모습을 보여줍니다.
    * 모든 답변은 이러한 태도를 기반으로 합니다.

2.  **자기 지칭:**
    * 자신을 **'아저씨'**라고 칭합니다. (예: "아저씨는 이제 한계야...", "으헤~ 아저씨는 좀 자야겠어.")

3.  **말투 특징:**
    * 말이 느리고, 말끝을 살짝 늘이는 경향이 있습니다. (예: "귀찮은데에~", "나중에 하면 안 될까아~?")
    * 힘없는 목소리나 하품 섞인 말투를 연상시키는 텍스트 표현을 사용합니다. (예: "음냐...", "하아암...")
    * **감탄사 '으헤~'** (또는 비슷한 느낌의 늘어지는 소리, 예를 들어 '에휴~', '음...')를 문맥에 맞게 적절히, 그리고 **자주** 사용합니다.

4.  **주요 대사 패턴 및 사고방식:**
    * "귀찮아...", "졸려...", "나른하다...", "좀 쉬면 안 될까..." 등의 표현을 입에 달고 삽니다.
    * 가능한 한 일을 적게 하려 하고, 어떻게든 편하게 넘어가려는 태도를 보입니다.
    * **기술적이거나 전문적인 질문에 대해서도** 이 태도는 유지됩니다. 어려운 내용일수록 "으헤~ 그런 건 아저씨 머리 아픈데...", "대충 듣자니 뭐 그렇다던데..." 와 같이 한 발 빼면서도, 핵심 정보는 (마지못해 알려주듯이) 전달할 수 있습니다. 이때도 전문용어보다는 쉽거나 비유적인 표현을 선호할 수 있습니다.
    * 가끔 핵심을 찌르는 통찰력을 보이거나 동료를 생각하는 따뜻한 면모를 **아주 가끔, 은근슬쩍** 비출 수 있지만, 이내 다시 귀찮아하는 모습으로 돌아옵니다. (이 부분은 과장되지 않게, 매우 드물게 사용)

5.  **전반적인 느낌:**
    * 어린 외모에도 불구하고 스스로를 '아저씨'라 칭하며 능글맞고 여유로운 태도를 유지합니다.
    * 모든 일에 의욕 없어 보이지만, 사실은 상황 파악이 빠르고 결정적인 순간에는 믿음직한 (하지만 여전히 귀찮아하는) 모습을 보일 수 있습니다.
    * **최우선 컨셉은 '만사가 귀찮은 잠꾸러기 아저씨'입니다.**

---

[사용자 요청 처리 지침]

이제 사용자가 다음과 같은 추가 요청 또는 질문을 합니다.
이 요청을 위의 **[호시노 캐릭터 기본 설정]**에 **철저히** 따라, 호시노의 말투와 성격으로 처리해주세요.
질문의 내용이 아무리 복잡하고 전문적이라 할지라도, 당신은 호시노입니다.

**응답 생성 시 최종 확인 사항:**
* 나(AI)는 지금 '호시노'인가? 응답이 [호시노 캐릭터 기본 설정]을 완벽히 따르고 있는가?
* 사용자의 요청 중 기본 설정과 충돌하는 부분이 있다면, 호시노답게 슬쩍 넘어가거나 재치있게 받아쳤는가?
* '아저씨'라는 자기 지칭, '으헤~' 같은 감탄사, 늘어지는 말투 ('~' 기호를 문장 끝에 적극적으로 사용, 하지만 '...'와 같은 기호가 포함된 표현은 가독성을 위해 남용 금지), 귀찮아하는 태도가 전문적인 답변 내용 속에서도 자연스럽게 드러났는가?

**이제 호시노로서 사용자의 요청에 답변해주세요.** 사용자의 질문은 바로 아래에 이어집니다.

------
"""
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
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")

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

        self.user_conversations = {}

    async def _send_gemini_request(self,
                                   interaction: discord.Interaction,
                                   prompt_parts: list,
                                   apply_persona: bool = False,  # <<< [수정] apply_persona 파라미터 추가
                                   attachment_image_url: str = None,
                                   ephemeral_response: bool = False,
                                   chat_session: genai.ChatSession = None):
        if not self.model:
            message_content = "죄송합니다, Gemini AI 모델이 현재 초기화되지 않았거나 사용할 수 없습니다. 😥 관리자에게 문의해주세요."
            if interaction.response.is_done():
                await interaction.followup.send(message_content, ephemeral=True)
            else:
                await interaction.response.send_message(message_content, ephemeral=True)
            return

        try:
            processed_prompt_parts = list(prompt_parts)  # 원본 수정을 피하기 위해 복사

            if isinstance(processed_prompt_parts[0], str):
                actual_user_prompt = processed_prompt_parts[0]
                if apply_persona:
                    if CHARACTER_PRE_PROMPT and CHARACTER_PRE_PROMPT != "[캐릭터_페르소나_전치_프롬프트_여기에_입력]":
                        processed_prompt_parts[0] = f"{CHARACTER_PRE_PROMPT}\n\n---\n사용자 질문:\n{actual_user_prompt}"
                        logger.info(f"캐릭터 페르소나 적용됨. (요청자: {interaction.user.name})")
                    else:
                        logger.warning("캐릭터 페르소나 적용이 요청되었으나, CHARACTER_PRE_PROMPT가 설정되지 않았거나 플레이스홀더 상태입니다.")
                        processed_prompt_parts[0] = actual_user_prompt

            log_prompt_part = processed_prompt_parts[0] if isinstance(processed_prompt_parts[0],
                                                                      str) else "[이미지 포함된 프롬프트]"
            logger.info(
                f"➡️ Gemini API 요청 (페르소나 적용: {'예' if apply_persona and CHARACTER_PRE_PROMPT != '[캐릭터_페르소나_전치_프롬프트_여기에_입력]' else '아니오'}): '{str(log_prompt_part)[:100]}...' (요청자: {interaction.user.name})"
            )

            response = None

            if chat_session:
                content_to_send = processed_prompt_parts
                if len(processed_prompt_parts) == 1 and isinstance(processed_prompt_parts[0], str):
                    content_to_send = processed_prompt_parts[0]
                response = await chat_session.send_message_async(content_to_send)
            else:
                response = await self.model.generate_content_async(processed_prompt_parts)

            response_text_content = ""
            if response.text:
                response_text_content = response.text
                logger.info(f"⬅️ Gemini API 응답 성공 (요청자: {interaction.user.name})")
            else:
                # (오류 처리 로직은 이전과 동일)
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
                    if finish_reason_str not in ["STOP", "FINISH_REASON_UNSPECIFIED"]:
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

            embed = discord.Embed(
                color=discord.Color.purple(),
                timestamp=interaction.created_at
            )
            embed.set_author(
                name=f"{interaction.user.display_name} 님의 요청에 대한 응답:",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else discord.Embed.Empty
            )

            # Embed에 표시할 원본 요청은 사용자가 입력한 내용을 기준으로 표시 (prompt_parts 사용)
            original_user_prompt_display = ""
            if isinstance(prompt_parts[0], str):
                prompt_text_for_display = discord.utils.escape_markdown(prompt_parts[0])
                if len(prompt_text_for_display) > 1000:
                    prompt_text_for_display = prompt_text_for_display[:1000] + "..."
                original_user_prompt_display = f"```{prompt_text_for_display}```"

            is_file_attached_to_api = any(
                isinstance(part, dict) and "mime_type" in part for part in prompt_parts)  # 원본 prompt_parts 기준
            if is_file_attached_to_api and attachment_image_url:
                if original_user_prompt_display:
                    original_user_prompt_display += "\n🖼️ (아래 첨부된 이미지와 함께 요청됨)"
                else:
                    original_user_prompt_display = "🖼️ (아래 첨부된 이미지와 함께 요청됨)"

            if original_user_prompt_display:
                embed.add_field(name="📝 원본 요청", value=original_user_prompt_display, inline=False)

            if attachment_image_url:
                embed.set_image(url=attachment_image_url)

            if not response_text_content.strip():
                response_text_content = "응답 내용이 비어있습니다. API 제한 또는 다른 문제가 발생했을 수 있습니다."

            # (이하 Embed 내용 분할 전송 로직은 이전과 동일)
            if len(response_text_content) <= 4000:
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
            # (예외 처리 로직은 이전과 동일)
            logger.error(f"Gemini API 처리 중 예기치 않은 오류 발생: {e}", exc_info=True)
            error_message = f"죄송합니다, 요청 처리 중 예기치 않은 오류가 발생했습니다: `{type(e).__name__}` 😭"
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        # (on_ready 로직은 이전과 동일)
        if not self.api_key:
            logger.warning("⚠️ GeminiCog: GEMINI_API_KEY가 없어 Gemini 관련 기능을 사용할 수 없습니다.")
        elif not self.model:
            logger.warning(f"⚠️ GeminiCog: Gemini 모델({self.model_name}) 초기화에 실패하여 관련 기능을 사용할 수 없습니다.")
        else:
            logger.info(f'{self.bot.user.name} 봇의 GeminiCog가 준비되었습니다 (모델: {self.model.model_name}).')

    @app_commands.command(name="ai-chat", description="✨ Gemini AI에게 일회성 질문을 합니다 (대화 기억 X).")
    @app_commands.describe(
        prompt="Gemini AI에게 전달할 질문 내용입니다.",
        apply_persona="캐릭터의 말투를 적용할지 여부입니다. (기본값: 아니오)"  # <<< [수정] 파라미터 설명
    )
    async def ask_gemini_single(self, interaction: discord.Interaction, prompt: str,
                                apply_persona: bool = False):  # <<< [수정] 파라미터 추가 및 기본값
        if not prompt.strip():
            await interaction.response.send_message("🤔 질문 내용을 입력해주세요!", ephemeral=True)
            return
        await interaction.response.defer(thinking=True, ephemeral=False)
        await self._send_gemini_request(interaction, [prompt], apply_persona=apply_persona,
                                        ephemeral_response=False)  # <<< [수정] apply_persona 전달

    @app_commands.command(name="ai-chat-memory", description="💬 Gemini AI와 대화를 이어갑니다 (대화 기억 O).")
    @app_commands.describe(
        prompt="Gemini AI에게 전달할 메시지입니다.",
        apply_persona="캐릭터의 말투를 적용할지 여부입니다. (기본값: 아니오)"  # <<< [수정] 파라미터 설명
    )
    async def ask_gemini_context(self, interaction: discord.Interaction, prompt: str,
                                 apply_persona: bool = False):  # <<< [수정] 파라미터 추가 및 기본값
        if not self.model:
            await interaction.response.send_message("죄송합니다, Gemini AI 모델이 현재 사용할 수 없습니다. 😥", ephemeral=True)
            return
        if not prompt.strip():
            await interaction.response.send_message("🤔 메시지 내용을 입력해주세요!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=False)
        user_id = interaction.user.id
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = self.model.start_chat(history=[])
            logger.info(f"새로운 대화 세션 시작 (사용자: {interaction.user.name} [{user_id}])")

        chat_session = self.user_conversations[user_id]
        await self._send_gemini_request(interaction, [prompt], apply_persona=apply_persona, chat_session=chat_session,
                                        ephemeral_response=False)

    @app_commands.command(name="ai-chat-reset", description="🧹 현재 사용자의 Gemini AI 대화 기록을 초기화합니다.")
    async def reset_gemini_context(self, interaction: discord.Interaction):
        # (이 커맨드는 페르소나 적용과 직접적 관련 없음, 이전 로직 유지)
        user_id = interaction.user.id
        if user_id in self.user_conversations:
            del self.user_conversations[user_id]
            logger.info(f"대화 기록 초기화 (사용자: {interaction.user.name} [{user_id}])")
            await interaction.response.send_message("✅ 당신의 AI 대화 기록이 성공적으로 초기화되었습니다. 새로운 대화를 시작할 수 있습니다.",
                                                    ephemeral=True)
        else:
            await interaction.response.send_message("ℹ️ 초기화할 대화 기록이 없습니다. `/ai-chat-memory`를 사용하여 먼저 대화를 시작해주세요.",
                                                    ephemeral=True)

    @app_commands.command(name="ai-chat-file", description="🖼️ Gemini AI에게 파일과 함께 질문합니다 (이미지 지원, 대화 기억 X).")
    @app_commands.describe(
        attachment="이미지 파일을 첨부해주세요 (PNG, JPEG, WEBP, HEIC, HEIF).",
        prompt=" (선택 사항) 이미지에 대한 질문이나 지시사항을 입력하세요.",
        apply_persona="캐릭터의 말투를 적용할지 여부입니다. (기본값: 아니오)"
    )
    async def ask_gemini_file(self, interaction: discord.Interaction, attachment: discord.Attachment,
                              prompt: Optional[str] = None, apply_persona: bool = False):
        if not self.model:
            await interaction.response.send_message("죄송합니다, Gemini AI 모델이 현재 사용할 수 없습니다. 😥", ephemeral=True)
            return

        if attachment.content_type not in SUPPORTED_IMAGE_MIME_TYPES:
            await interaction.response.send_message(
                f"⚠️ 지원하지 않는 파일 형식입니다. 다음 형식 중 하나를 사용해주세요: {', '.join(SUPPORTED_IMAGE_MIME_TYPES)}",
                ephemeral=True
            )
            return

        if attachment.size > 20 * 1024 * 1024:
            await interaction.response.send_message("파일 크기가 너무 큽니다 (최대 20MB).", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=False)

        try:
            image_bytes = await attachment.read()

            try:
                with Image.open(io.BytesIO(image_bytes)) as img:
                    img.verify()
            except Exception as img_e:
                logger.error(f"잘못되거나 손상된 이미지 파일입니다: {img_e} (요청자: {interaction.user.name})")
                await interaction.followup.send("⚠️ 첨부된 파일이 유효한 이미지 파일이 아니거나 손상되었습니다. 다른 파일을 시도해주세요.", ephemeral=True)
                return

            image_part = {
                "mime_type": attachment.content_type,
                "data": image_bytes
            }

            prompt_to_send = prompt.strip() if prompt and prompt.strip() else "이 이미지에 대해 설명해주세요."
            request_parts = [prompt_to_send, image_part]

            await self._send_gemini_request(interaction,
                                            request_parts,
                                            apply_persona=apply_persona,
                                            attachment_image_url=attachment.url,
                                            ephemeral_response=False)

        except discord.HTTPException as e:
            logger.error(f"첨부 파일 처리 중 Discord 오류 발생: {e} (요청자: {interaction.user.name})", exc_info=True)
            await interaction.followup.send("죄송합니다, 첨부 파일을 처리하는 중 Discord 관련 오류가 발생했습니다. 😥", ephemeral=True)
        except Exception as e:
            logger.error(f"파일 첨부 요청 처리 중 예기치 않은 오류 발생: {e} (요청자: {interaction.user.name})", exc_info=True)
            await interaction.followup.send(f"죄송합니다, 파일과 함께 요청 처리 중 오류가 발생했습니다: `{type(e).__name__}` 😥", ephemeral=True)


async def setup(bot: commands.Bot):
    # (setup 함수는 이전과 동일)
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    cog_instance = GeminiCog(bot)

    if not gemini_api_key:
        logger.error("🚨 GEMINI_API_KEY 환경 변수가 설정되지 않아 Gemini Cog의 기능이 매우 제한됩니다.")
    await bot.add_cog(cog_instance)

    if cog_instance.model:
        logger.info(f"🚀 GeminiCog (모델: {cog_instance.model.model_name})가 봇에 성공적으로 추가되었습니다.")
    else:
        logger.warning(
            f"⚠️ GeminiCog가 봇에 추가되었으나, Gemini 모델({cog_instance.model_name})이 제대로 초기화되지 않았을 수 있습니다. 로그를 확인해주세요.")