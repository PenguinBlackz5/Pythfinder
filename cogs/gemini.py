import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
import os
import logging
from dotenv import load_dotenv
from PIL import Image
import io
from typing import Optional
import json
import glob

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_MIME_TYPES = [
    "image/png", "image/jpeg", "image/webp", "image/heic", "image/heif",
]

# Cog 파일의 디렉토리 경로를 기준으로 'characters' 폴더 경로 설정
COG_DIR = os.path.dirname(__file__)
CHARACTERS_DIR = os.path.join(COG_DIR, "characters")


class GeminiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20")  # 사용자의 원래 모델명 유지
        self.model = None
        self.user_conversations = {}
        self.characters_data = {}
        self._load_characters()  # 캐릭터 로딩 함수 호출

        if not self.api_key:
            logger.error("🚨 GEMINI_API_KEY가 설정되지 않았습니다.")
            return
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"✅ Gemini 모델({self.model_name}) 초기화 성공.")
        except Exception as e:
            logger.error(f"Gemini 모델 ({self.model_name}) 초기화 중 오류: {e}")

    def _load_characters(self):
        """characters 폴더에서 JSON 파일들을 읽어 캐릭터 데이터를 로드합니다."""
        if not os.path.exists(CHARACTERS_DIR):
            logger.warning(f"캐릭터 설정 폴더 '{CHARACTERS_DIR}'를 찾을 수 없습니다. 폴더를 생성하고 캐릭터 JSON 파일을 넣어주세요.")
            # 폴더가 없으면 최소한의 기본 'default' 캐릭터 생성
            self.characters_data["default"] = {
                "id": "default", "name": "기본 AI", "description": "일반 Gemini AI 모드",
                "pre_prompt": "", "icon_url": "", "color": [128, 0, 128]
            }
            logger.info("임시 '기본 AI' 캐릭터를 로드했습니다.")
            return

        loaded_chars = 0
        for file_path in glob.glob(os.path.join(CHARACTERS_DIR, "*.json")):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "id" in data and "name" in data:
                        # color 필드가 없거나 형식이 맞지 않을 경우 기본값 설정
                        if not isinstance(data.get("color"), list) or len(data["color"]) != 3:
                            data["color"] = [128, 0, 128]  # 기본 보라색
                        data.setdefault("pre_prompt", "")  # pre_prompt가 없으면 빈 문자열
                        data.setdefault("icon_url", "")  # icon_url이 없으면 빈 문자열
                        self.characters_data[data["id"]] = data
                        logger.info(f"캐릭터 로드: {data['name']} (ID: {data['id']})")
                        loaded_chars += 1
                    else:
                        logger.warning(f"캐릭터 파일 {file_path}에 'id' 또는 'name' 필드가 누락되었습니다.")
            except json.JSONDecodeError:
                logger.error(f"캐릭터 파일 {file_path} 파싱 중 오류 발생.")
            except Exception as e:
                logger.error(f"캐릭터 파일 {file_path} 로드 중 예외 발생: {e}")

        if loaded_chars == 0 and "default" not in self.characters_data:
            # 폴더는 있지만 유효한 파일이 하나도 없는 경우
            self.characters_data["default"] = {
                "id": "default", "name": "기본 AI", "description": "일반 Gemini AI 모드",
                "pre_prompt": "", "icon_url": "", "color": [128, 0, 128]
            }
            logger.info("로드된 캐릭터가 없어 임시 '기본 AI' 캐릭터를 사용합니다.")
        elif "default" not in self.characters_data:
            logger.warning("'default' ID를 가진 캐릭터를 찾을 수 없습니다. 기능이 제한될 수 있습니다. 'characters/default.json' 파일을 추가해주세요.")
            # 이 경우 첫 번째 로드된 캐릭터를 임시 기본값으로 사용하거나, 에러를 발생시킬 수 있습니다.
            # 여기서는 경고만 하고 넘어갑니다. 명령어에서 character_id 부재 시 처리합니다.

    async def character_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> list[app_commands.Choice[str]]:
        """명령어에서 캐릭터 선택 시 자동완성 목록을 제공합니다."""
        choices = []
        if not self.characters_data:  # 캐릭터 데이터가 전혀 로드되지 않은 경우
            choices.append(app_commands.Choice(name="기본 AI (로드 실패)", value="default"))

        for char_id, char_info in self.characters_data.items():
            char_name = char_info.get("name", char_id)
            # 현재 입력값(current)이 캐릭터 이름이나 ID에 포함되어 있으면 목록에 추가
            if current.lower() in char_name.lower() or current.lower() in char_id.lower():
                choices.append(app_commands.Choice(name=char_name, value=char_id))
            elif not current:  # 입력값이 없으면 모든 캐릭터 표시
                choices.append(app_commands.Choice(name=char_name, value=char_id))
        return choices[:25]  # 최대 25개의 선택지만 표시 가능

    async def _send_gemini_request(self,
                                   interaction: discord.Interaction,
                                   prompt_parts: list,
                                   character_id: str,  # apply_persona 대신 character_id 사용
                                   attachment_image_url: str = None,
                                   ephemeral_response: bool = False,
                                   chat_session: Optional[genai.ChatSession] = None):  # genai.ChatSession으로 타입 명시
        if not self.model:
            message_content = "죄송합니다, Gemini AI 모델이 현재 초기화되지 않았거나 사용할 수 없습니다. 😥 관리자에게 문의해주세요."
            if interaction.response.is_done():
                await interaction.followup.send(message_content, ephemeral=True)
            else:
                await interaction.response.send_message(message_content, ephemeral=True)
            return

        try:
            # 선택된 캐릭터 정보 가져오기, 없으면 'default' 사용
            char_data = self.characters_data.get(character_id)
            if not char_data:
                logger.warning(f"요청된 캐릭터 ID '{character_id}'를 찾을 수 없어 'default' 캐릭터로 대체합니다.")
                char_data = self.characters_data.get("default")
                if not char_data:
                    logger.error("기본 'default' 캐릭터 정보도 찾을 수 없습니다. 임시 데이터를 사용합니다.")
                    char_data = {  # 완전 비상용 데이터
                        "id": "fallback_default", "name": "기본 AI (오류)", "pre_prompt": "",
                        "icon_url": "", "color": [100, 100, 100]  # 회색
                    }

            processed_prompt_parts = list(prompt_parts)
            is_persona_really_applied = False
            character_pre_prompt = char_data.get("pre_prompt", "").strip()

            if isinstance(processed_prompt_parts[0], str):
                actual_user_prompt = processed_prompt_parts[0]
                if character_pre_prompt:  # 페르소나 프롬프트가 비어있지 않으면 적용
                    processed_prompt_parts[0] = f"{character_pre_prompt}\n{actual_user_prompt}"
                    is_persona_really_applied = True
                    logger.info(f"'{char_data['name']}' 캐릭터 페르소나 적용됨. (요청자: {interaction.user.name})")
                else:
                    processed_prompt_parts[0] = actual_user_prompt

            log_prompt_part = processed_prompt_parts[0] if isinstance(processed_prompt_parts[0], str) else "[이미지 포함]"
            logger.info(
                f"➡️ Gemini API 요청 (캐릭터: {char_data['name']}, 페르소나 적용: {'예' if is_persona_really_applied else '아니오'}): '{str(log_prompt_part)[:100]}...' (요청자: {interaction.user.name})"
            )

            response = None
            if chat_session:
                content_to_send = processed_prompt_parts[0] if len(processed_prompt_parts) == 1 and isinstance(
                    processed_prompt_parts[0], str) else processed_prompt_parts
                response = await chat_session.send_message_async(content_to_send)
            else:
                response = await self.model.generate_content_async(processed_prompt_parts)

            response_text_content = ""

            if response.text:
                response_text_content = response.text
                logger.info(f"⬅️ Gemini API 응답 성공 (요청자: {interaction.user.name}, 캐릭터: {char_data['name']})")
            else:
                # (기존과 동일한 응답 실패/차단 처리 로직)
                block_reason = "알 수 없음"
                finish_reason_str = "알 수 없음"
                safety_info_str = ""
                if hasattr(response,
                           'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                    block_reason = response.prompt_feedback.block_reason.name
                error_message_parts = [f"Gemini AI로부터 텍스트 응답을 받지 못했습니다. 😔"]
                if block_reason != "BLOCK_REASON_UNSPECIFIED" and block_reason != "알 수 없음":
                    error_message_parts.append(f"차단 사유: {block_reason}")
                if hasattr(response, 'candidates') and response.candidates:
                    current_candidate = response.candidates[0]
                    if current_candidate.finish_reason:
                        finish_reason_str = current_candidate.finish_reason.name
                    if finish_reason_str not in ["STOP", "FINISH_REASON_UNSPECIFIED"]:
                        error_message_parts.append(f"종료 사유: {finish_reason_str}")
                    if current_candidate.safety_ratings:
                        safety_info_parts = [f"{s.category.name.replace('HARM_CATEGORY_', '')}: {s.probability.name}"
                                             for s in current_candidate.safety_ratings if
                                             s.probability.name not in ["NEGLIGIBLE", "LOW"]]
                        if safety_info_parts:
                            safety_info_str = ", ".join(safety_info_parts)
                            error_message_parts.append(f"감지된 안전 문제: {safety_info_str}")
                response_text_content = "\n".join(error_message_parts)
                logger.warning(
                    f"Gemini API 응답 문제 (요청자: {interaction.user.name}, 캐릭터: {char_data['name']}, 차단: {block_reason}, 종료: {finish_reason_str}, 안전: '{safety_info_str or '없음'}')")

            char_rgb_color = char_data.get("color", [128, 0, 128])  # 기본 보라색
            embed_color = discord.Color.from_rgb(char_rgb_color[0], char_rgb_color[1], char_rgb_color[2])

            embed = discord.Embed(
                color=embed_color,
                timestamp=interaction.created_at
            )

            author_name = char_data.get("name", "AI Assistant")
            author_icon_url = char_data.get("icon_url", "")
            if not author_icon_url:  # 아이콘 URL이 비어있으면 봇의 기본 아바타 사용
                author_icon_url = self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url

            embed.set_author(name=author_name, icon_url=author_icon_url)

            # 원본 요청 프롬프트 표시
            original_user_prompt_display = ""
            if isinstance(prompt_parts[0], str):
                original_input_prompt = interaction.data.get('options', [{}])[0].get('value', '') if interaction.data else \
                prompt_parts[0]
                if isinstance(original_input_prompt, str):
                    prompt_text_for_display = discord.utils.escape_markdown(original_input_prompt)
                    if len(prompt_text_for_display) > 1000:
                        prompt_text_for_display = prompt_text_for_display[:1000] + "..."
                    original_user_prompt_display = f"```{prompt_text_for_display}```"

            is_file_attached_to_api = any(isinstance(part, dict) and "mime_type" in part for part in prompt_parts)
            if is_file_attached_to_api and attachment_image_url:
                original_user_prompt_display += f"\n🖼️ (첨부 이미지와 함께 요청됨)" if original_user_prompt_display else "🖼️ (첨부 이미지와 함께 요청됨)"

            if original_user_prompt_display:
                embed.add_field(name="📝 내가 보낸 내용", value=original_user_prompt_display, inline=False)

            if attachment_image_url:
                embed.set_image(url=attachment_image_url)

            if not response_text_content.strip():
                response_text_content = "응답 내용이 비어있습니다. API 제한 또는 다른 문제가 발생했을 수 있습니다."

            if len(response_text_content) <= 4000:
                embed.description = response_text_content
                await interaction.followup.send(embed=embed, ephemeral=ephemeral_response)
            else:
                embed.description = response_text_content[:4000] + "\n\n**(내용이 길어 일부만 표시됩니다...)**"
                await interaction.followup.send(embed=embed, ephemeral=ephemeral_response)
                remaining_response = response_text_content[4000:]
                chunks = [remaining_response[i:i + 1990] for i in range(0, len(remaining_response), 1990)]
                for chunk_idx, chunk in enumerate(chunks):
                    chunk_embed = discord.Embed(description=chunk, color=embed_color, timestamp=interaction.created_at)
                    # 이어지는 메시지에도 캐릭터 이름과 아이콘 적용
                    chunk_author_name = f"{author_name}의 다음 이야기~ ({chunk_idx + 1}/{len(chunks)})"
                    chunk_embed.set_author(name=chunk_author_name, icon_url=author_icon_url)
                    await interaction.followup.send(embed=chunk_embed, ephemeral=ephemeral_response)

        except Exception as e:
            logger.error(f"Gemini API 처리 중 예기치 않은 오류 발생: {e}", exc_info=True)
            error_message = f"죄송합니다, 요청 처리 중 예기치 않은 오류가 발생했습니다: `{type(e).__name__}` 😭"
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)

    @app_commands.command(name="ai-chat", description="✨ Gemini AI에게 일회성 질문을 합니다 (대화 기억 X).")
    @app_commands.describe(
        prompt="Gemini AI에게 전달할 질문 내용입니다.",
        character="사용할 AI 캐릭터를 선택하세요."
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def ask_gemini_single(self, interaction: discord.Interaction, prompt: str,
                                character: Optional[str] = "default"):
        if not prompt.strip():
            await interaction.response.send_message("🤔 질문 내용을 입력해주세요!", ephemeral=True)
            return

        selected_character_id = character if character and character in self.characters_data else "default"

        await interaction.response.defer(thinking=True, ephemeral=False)
        await self._send_gemini_request(interaction, [prompt], character_id=selected_character_id,
                                        ephemeral_response=False)

    @app_commands.command(name="ai-chat-memory", description="💬 Gemini AI와 대화를 이어갑니다 (대화 기억 O).")
    @app_commands.describe(
        prompt="Gemini AI에게 전달할 메시지입니다.",
        character="사용할 AI 캐릭터를 선택하세요."
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def ask_gemini_context(self, interaction: discord.Interaction, prompt: str,
                                 character: Optional[str] = "default"):
        if not self.model:
            await interaction.response.send_message("죄송합니다, Gemini AI 모델이 현재 사용할 수 없습니다. 😥", ephemeral=True)
            return
        if not prompt.strip():
            await interaction.response.send_message("🤔 메시지 내용을 입력해주세요!", ephemeral=True)
            return

        selected_character_id = character if character and character in self.characters_data else "default"

        await interaction.response.defer(thinking=True, ephemeral=False)
        user_id = interaction.user.id

        # 캐릭터 선택은 매번 메시지마다 가능. 세션별 캐릭터 고정은 추가 구현 필요.
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = self.model.start_chat(history=[])
            logger.info(f"새로운 대화 세션 시작 (사용자: {interaction.user.name} [{user_id}])")

        chat_session = self.user_conversations[user_id]
        await self._send_gemini_request(interaction, [prompt], character_id=selected_character_id,
                                        chat_session=chat_session, ephemeral_response=False)

    @app_commands.command(name="ai-chat-reset", description="🧹 현재 사용자의 Gemini AI 대화 기록을 초기화합니다.")
    async def reset_gemini_context(self, interaction: discord.Interaction):
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
        character="사용할 AI 캐릭터를 선택하세요."
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def ask_gemini_file(self, interaction: discord.Interaction, attachment: discord.Attachment,
                              prompt: Optional[str] = None, character: Optional[str] = "default"):
        if not self.model:
            await interaction.response.send_message("죄송합니다, Gemini AI 모델이 현재 사용할 수 없습니다. 😥", ephemeral=True)
            return

        if attachment.content_type not in SUPPORTED_IMAGE_MIME_TYPES:
            await interaction.response.send_message(
                f"⚠️ 지원하지 않는 파일 형식입니다. 다음 형식 중 하나를 사용해주세요: {', '.join(SUPPORTED_IMAGE_MIME_TYPES)}", ephemeral=True)
            return

        if attachment.size > 20 * 1024 * 1024:  # 예시: 20MB 제한
            await interaction.response.send_message("파일 크기가 너무 큽니다 (최대 20MB).", ephemeral=True)  # 사용자에게 알림
            return

        selected_character_id = character if character and character in self.characters_data else "default"

        await interaction.response.defer(thinking=True, ephemeral=False)

        try:
            image_bytes = await attachment.read()
            try:
                with Image.open(io.BytesIO(image_bytes)) as img:
                    img.verify()  # 이미지 유효성 검사
            except Exception as img_e:
                logger.error(f"잘못되거나 손상된 이미지 파일입니다: {img_e} (요청자: {interaction.user.name})")
                await interaction.followup.send("⚠️ 첨부된 파일이 유효한 이미지 파일이 아니거나 손상되었습니다. 다른 파일을 시도해주세요.", ephemeral=True)
                return

            image_part = {"mime_type": attachment.content_type, "data": image_bytes}
            prompt_to_send = prompt.strip() if prompt and prompt.strip() else "이 이미지에 대해 설명해주세요."
            request_parts = [prompt_to_send, image_part]

            await self._send_gemini_request(interaction,
                                            request_parts,
                                            character_id=selected_character_id,
                                            attachment_image_url=attachment.url,
                                            ephemeral_response=False)

        except discord.HTTPException as e:
            logger.error(f"첨부 파일 처리 중 Discord 오류 발생: {e} (요청자: {interaction.user.name})", exc_info=True)
            await interaction.followup.send("죄송합니다, 첨부 파일을 처리하는 중 Discord 관련 오류가 발생했습니다. 😥", ephemeral=True)
        except Exception as e:
            logger.error(f"파일 첨부 요청 처리 중 예기치 않은 오류 발생: {e} (요청자: {interaction.user.name})", exc_info=True)
            await interaction.followup.send(f"죄송합니다, 파일과 함께 요청 처리 중 오류가 발생했습니다: `{type(e).__name__}` 😥", ephemeral=True)


async def setup(bot: commands.Bot):
    # Cog 인스턴스 생성 시 API 키 유무는 Cog 내부에서 확인 및 로깅하므로 여기서 중복 확인 불필요
    cog_instance = GeminiCog(bot)
    await bot.add_cog(cog_instance)
    # Cog 추가 후 모델 상태에 따른 로그는 Cog 내부 __init__ 에서 이미 처리되므로,
    # 여기서는 Cog가 성공적으로 추가되었는지 여부만 로깅 가능
    if cog_instance.model and cog_instance.characters_data:  # 모델과 캐릭터 데이터 모두 로드 성공 시
        logger.info(
            f"🚀 GeminiCog (모델: {cog_instance.model_name}, 캐릭터 {len(cog_instance.characters_data)}개)가 봇에 성공적으로 추가되었습니다.")
    elif not cog_instance.api_key:
        logger.error("🚨 GeminiCog 추가 시도: GEMINI_API_KEY가 없어 기능이 매우 제한됩니다.")
    else:
        logger.warning(f"⚠️ GeminiCog가 추가되었으나, 모델 또는 캐릭터 데이터 초기화에 문제가 있을 수 있습니다. 로그를 확인해주세요.")