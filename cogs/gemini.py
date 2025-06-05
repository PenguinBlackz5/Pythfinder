import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
import google.generativeai.types as genai_types
import os
import logging
from dotenv import load_dotenv
from PIL import Image
import io
from typing import Optional, List, Dict, Any  # Dict, Any 추가
import json
import glob

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_MIME_TYPES = [
    "image/png", "image/jpeg", "image/webp", "image/heic", "image/heif",
]

COG_DIR = os.path.dirname(__file__)
CHARACTERS_DIR = os.path.join(COG_DIR, "characters")


class GeminiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20")
        self.model = None
        # user_conversations 구조: { user_id: { char_id1: {'session': ChatSession}, char_id2: {'session': ChatSession} } }
        self.user_conversations: Dict[int, Dict[str, Dict[str, Any]]] = {}
        self.characters_data: Dict[str, Dict[str, Any]] = {}
        self._load_characters()

        if not self.api_key:
            logger.error("🚨 GEMINI_API_KEY가 설정되지 않았습니다.")
            return
        try:
            genai.configure(api_key=self.api_key)
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            self.model = genai.GenerativeModel(self.model_name, safety_settings=safety_settings)
            logger.info(f"✅ Gemini 모델({self.model_name}) 초기화 성공 (안전 설정 적용됨).")
        except Exception as e:
            logger.error(f"Gemini 모델 ({self.model_name}) 초기화 중 오류: {e}")

    def _load_characters(self):  # 변경 없음
        if not os.path.exists(CHARACTERS_DIR):
            logger.warning(f"캐릭터 설정 폴더 '{CHARACTERS_DIR}'를 찾을 수 없습니다. 폴더를 생성하고 캐릭터 JSON 파일을 넣어주세요.")
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
                        if not isinstance(data.get("color"), list) or len(data["color"]) != 3:
                            data["color"] = [128, 0, 128]
                        data.setdefault("pre_prompt", "")
                        data.setdefault("icon_url", "")
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
            self.characters_data["default"] = {
                "id": "default", "name": "기본 AI", "description": "일반 Gemini AI 모드",
                "pre_prompt": "", "icon_url": "", "color": [128, 0, 128]
            }
            logger.info("로드된 캐릭터가 없어 임시 '기본 AI' 캐릭터를 사용합니다.")
        elif "default" not in self.characters_data and self.characters_data:
            # first_char_id = next(iter(self.characters_data)) # 사용하지 않으므로 주석 처리
            logger.warning(
                f"'default' ID를 가진 캐릭터를 찾을 수 없습니다. 'default.json' 파일을 추가하거나, 명령어 사용 시 'default' 캐릭터를 지정하지 않도록 주의해주세요.")

    async def character_autocomplete(  # 모든 설정된 캐릭터 목록 (새 대화 시작용)
            self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        choices = []
        if not self.characters_data:
            choices.append(app_commands.Choice(name="[오류] 캐릭터 없음", value="_error_no_char_"))
            return choices

        for char_id, char_info in self.characters_data.items():
            char_name = char_info.get("name", char_id)
            if current.lower() in char_name.lower() or current.lower() in char_id.lower() or not current:
                choices.append(app_commands.Choice(name=char_name, value=char_id))
        if not choices and current:  # 입력값이 있는데 매칭되는게 없을 때
            choices.append(app_commands.Choice(name=f"{current}(와)일치하는 캐릭터 없음", value="_nomatch_"))

        return choices[:25]

    async def active_character_session_autocomplete(  # 사용자가 대화 기록을 가진 캐릭터 목록 (조회용)
            self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        user_id = interaction.user.id
        choices = []
        if user_id in self.user_conversations and self.user_conversations[user_id]:
            for char_id_from_history in self.user_conversations[user_id].keys():
                char_name = self.characters_data.get(char_id_from_history, {}).get("name", char_id_from_history)
                display_name = f"{char_name} (대화 기록 있음)"
                if char_id_from_history not in self.characters_data:  # 설정 파일이 삭제된 경우
                    display_name = f"{char_id_from_history} (설정 파일 없음, 기록 존재)"

                if current.lower() in char_name.lower() or \
                        current.lower() in char_id_from_history.lower() or \
                        not current:
                    choices.append(app_commands.Choice(name=display_name, value=char_id_from_history))

        if not choices and not current:
            choices.append(app_commands.Choice(name="[정보] 대화 기록 없음", value="_no_history_"))
        elif not choices and current:
            choices.append(app_commands.Choice(name=f"{current}(와)일치하는 기록 없음", value="_nomatch_"))

        return choices[:25]

    async def reset_character_session_autocomplete(  # 사용자가 대화 기록을 가진 캐릭터 목록 + "모두" (초기화용)
            self, interaction: discord.Interaction, current: str,
    ) -> list[app_commands.Choice[str]]:
        user_id = interaction.user.id
        choices = []
        has_history = False
        if user_id in self.user_conversations and self.user_conversations[user_id]:
            has_history = True
            for char_id_from_history in self.user_conversations[user_id].keys():
                char_name = self.characters_data.get(char_id_from_history, {}).get("name", char_id_from_history)
                display_name = f"{char_name} (대화 기록 있음)"
                if char_id_from_history not in self.characters_data:
                    display_name = f"{char_id_from_history} (설정 파일 없음, 기록 존재)"

                if current.lower() in char_name.lower() or \
                        current.lower() in char_id_from_history.lower() or \
                        not current:  # current가 비어있을 때도 추가
                    choices.append(app_commands.Choice(name=display_name, value=char_id_from_history))

        # "모든 캐릭터 기록 초기화" 옵션 추가
        all_option_name = "모든 캐릭터 기록 초기화"
        if has_history and (all_option_name.lower().startswith(current.lower()) or not current):
            choices.insert(0, app_commands.Choice(name=all_option_name, value="_all_"))

        if not has_history and not current:  # 아무 기록도 없을때
            choices.append(app_commands.Choice(name="[정보] 초기화할 기록 없음", value="_no_history_"))
        elif not choices and current:  # 입력은 있는데 매칭되는게 없을때
            choices.append(app_commands.Choice(name=f"{current}(와)일치하는 기록/옵션 없음", value="_nomatch_"))

        return choices[:25]

    async def _send_gemini_request(self,  # 변경 없음 (내부 로직은 이전 턴에서 이미 수정됨)
                                   interaction: discord.Interaction,
                                   prompt_parts: list,
                                   character_id: str,
                                   attachment_image_url: str = None,
                                   ephemeral_response: bool = False,
                                   chat_session: Optional[genai.ChatSession] = None,
                                   is_first_message_in_session: bool = False):
        # ... (이전 턴의 _send_gemini_request 코드와 동일)
        if not self.model:
            message_content = "죄송합니다, Gemini AI 모델이 현재 초기화되지 않았거나 사용할 수 없습니다. 😥 관리자에게 문의해주세요."
            if interaction.response.is_done():
                await interaction.followup.send(message_content, ephemeral=True)
            else:
                await interaction.response.send_message(message_content, ephemeral=True)
            return

        try:
            char_data = self.characters_data.get(character_id)
            if not char_data:
                logger.warning(f"요청된 캐릭터 ID '{character_id}'를 찾을 수 없어 'default' 캐릭터로 대체 시도.")
                char_data = self.characters_data.get("default")
                if not char_data:
                    logger.error("기본 'default' 캐릭터 정보도 찾을 수 없습니다. 임시 데이터를 사용합니다.")
                    char_data = {
                        "id": "fallback_default", "name": "기본 AI (오류)", "pre_prompt": "",
                        "icon_url": "", "color": [100, 100, 100]
                    }

            processed_prompt_parts = list(prompt_parts)
            character_pre_prompt = char_data.get("pre_prompt", "").strip()
            log_persona_applied_this_turn = False

            actual_user_input_text = ""
            if isinstance(processed_prompt_parts[0], str):
                actual_user_input_text = processed_prompt_parts[0]

            if character_pre_prompt:
                apply_pre_prompt_now = False
                if chat_session:
                    if is_first_message_in_session:
                        apply_pre_prompt_now = True
                else:
                    apply_pre_prompt_now = True

                if apply_pre_prompt_now and isinstance(processed_prompt_parts[0], str):
                    processed_prompt_parts[0] = f"{character_pre_prompt}\n{actual_user_input_text}"
                    log_persona_applied_this_turn = True

            log_prompt_part = processed_prompt_parts[0] if isinstance(processed_prompt_parts[0], str) else "[이미지 포함]"
            logger.info(
                f"➡️ Gemini API 요청 (캐릭터: {char_data['name']}, 페르소나 이번 턴 적용: {'예' if log_persona_applied_this_turn else '아니오'}): '{str(log_prompt_part)[:100]}...' (요청자: {interaction.user.name})"
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
                    if finish_reason_str not in ["STOP", "FINISH_REASON_UNSPECIFIED", "UNKNOWN"]:
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

            char_rgb_color = char_data.get("color", [128, 0, 128])
            embed_color = discord.Color.from_rgb(char_rgb_color[0], char_rgb_color[1], char_rgb_color[2])

            embed = discord.Embed(color=embed_color, timestamp=interaction.created_at)

            author_name = char_data.get("name", "AI Assistant")
            author_icon_url = char_data.get("icon_url", "")
            if not author_icon_url:
                author_icon_url = self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url

            embed.set_author(name=author_name, icon_url=author_icon_url)

            original_user_prompt_display = ""
            if actual_user_input_text:
                prompt_text_for_display = discord.utils.escape_markdown(actual_user_input_text)
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

    @app_commands.command(name="ai-chat", description="✨ AI에게 일회성 질문을 합니다 (대화 기억 X).")
    @app_commands.describe(
        prompt="Gemini AI에게 전달할 질문 내용입니다.",
        character="사용할 AI 캐릭터를 선택하세요 (기본: default)."
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def ask_gemini_single(self, interaction: discord.Interaction, prompt: str,
                                character: Optional[str] = "default"):
        if not prompt.strip():
            await interaction.response.send_message("🤔 질문 내용을 입력해주세요!", ephemeral=True)
            return

        # 선택된 캐릭터 ID 유효성 검사 (character_autocomplete에서 _error_나 _nomatch_ 반환 가능성)
        if character in ["_error_no_char_", "_nomatch_"] or character not in self.characters_data:
            # 'default'가 아니라면, 그리고 characters_data에 없다면 오류
            if character == "default" and "default" not in self.characters_data:  # default 조차 없을때
                await interaction.response.send_message("⚠️ 'default' 캐릭터를 포함하여 어떤 캐릭터 설정도 찾을 수 없습니다. 관리자에게 문의해주세요.",
                                                        ephemeral=True)
                return
            elif character != "default":  # default가 아닌데, 없는 캐릭터일때 (autocomplete에서 이상한 값 넘어온 경우)
                await interaction.response.send_message(f"⚠️ 선택한 캐릭터 '{character}'를 찾을 수 없습니다. 유효한 캐릭터를 선택해주세요.",
                                                        ephemeral=True)
                return
            # 만약 character가 default이고, default가 없으면 위의 fallback_default를 사용하게됨 (send_gemini_request에서)

        selected_character_id = character if character in self.characters_data else "default"

        await interaction.response.defer(thinking=True, ephemeral=False)
        await self._send_gemini_request(interaction, [prompt], character_id=selected_character_id,
                                        ephemeral_response=False)

    @app_commands.command(name="ai-chat-memory", description="💬 특정 AI 캐릭터와 대화를 이어가거나 시작합니다 (캐릭터별 대화 기억 O).")
    @app_commands.describe(
        character="대화할 AI 캐릭터를 선택하세요.",
        prompt="AI 캐릭터에게 전달할 메시지입니다."
    )
    @app_commands.autocomplete(character=character_autocomplete)  # 모든 설정된 캐릭터를 보여줌
    async def ask_gemini_context(self, interaction: discord.Interaction, character: str, prompt: str):
        if not self.model:
            await interaction.response.send_message("죄송합니다, Gemini AI 모델이 현재 사용할 수 없습니다. 😥", ephemeral=True)
            return
        if not prompt.strip():
            await interaction.response.send_message("🤔 메시지 내용을 입력해주세요!", ephemeral=True)
            return

        # 선택된 캐릭터 ID 유효성 검사
        if character in ["_error_no_char_", "_nomatch_"] or character not in self.characters_data:
            await interaction.response.send_message(
                f"⚠️ 선택한 캐릭터 '{character}'는 유효하지 않습니다. 목록에서 올바른 캐릭터를 선택해주세요.", ephemeral=True
            )
            return

        selected_character_id = character  # 사용자가 명시적으로 선택한 캐릭터 ID

        await interaction.response.defer(thinking=True, ephemeral=False)

        user_id = interaction.user.id
        is_first_message_for_this_character_session = False

        # 사용자 ID에 대한 항목이 없으면 생성
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = {}

        # 해당 사용자의 특정 캐릭터에 대한 세션이 없으면 생성
        if selected_character_id not in self.user_conversations[user_id]:
            char_name_for_log = self.characters_data.get(selected_character_id, {}).get('name', selected_character_id)
            self.user_conversations[user_id][selected_character_id] = {
                'session': self.model.start_chat(history=[])
            }
            is_first_message_for_this_character_session = True
            logger.info(f"사용자 {interaction.user.name} [{user_id}]와(과) 캐릭터 '{char_name_for_log}'의 새로운 대화 세션 시작.")

        chat_session_obj = self.user_conversations[user_id][selected_character_id]['session']

        await self._send_gemini_request(
            interaction,
            [prompt],
            character_id=selected_character_id,
            chat_session=chat_session_obj,
            ephemeral_response=False,
            is_first_message_in_session=is_first_message_for_this_character_session
        )

    @app_commands.command(name="ai-chat-reset", description="🧹 특정 또는 모든 AI 캐릭터와의 대화 기록을 초기화합니다.")
    @app_commands.describe(character="기록을 초기화할 AI 캐릭터 (또는 '모든 캐릭터')")
    @app_commands.autocomplete(character=reset_character_session_autocomplete)
    async def reset_gemini_context(self, interaction: discord.Interaction, character: str):
        user_id = interaction.user.id

        if character in ["_no_history_", "_nomatch_"]:  # 자동완성에서 온 정보성 값
            await interaction.response.send_message(
                f"ℹ️ '{character}' 선택은 유효한 작업이 아닙니다. 목록에서 실제 캐릭터나 '모든 캐릭터' 옵션을 선택해주세요.", ephemeral=True)
            return

        if user_id not in self.user_conversations or not self.user_conversations[user_id]:
            await interaction.response.send_message("ℹ️ 초기화할 대화 기록이 없습니다.", ephemeral=True)
            return

        if character == "_all_":
            count = len(self.user_conversations[user_id])
            del self.user_conversations[user_id]
            logger.info(f"사용자 {interaction.user.name} [{user_id}]의 모든 ({count}개) 캐릭터 대화 기록 초기화.")
            await interaction.response.send_message(f"✅ 당신의 모든 AI 캐릭터({count}개)와의 대화 기록이 성공적으로 초기화되었습니다.",
                                                    ephemeral=True)
        elif character in self.user_conversations[user_id]:
            char_name = self.characters_data.get(character, {}).get("name", character)
            del self.user_conversations[user_id][character]
            if not self.user_conversations[user_id]:
                del self.user_conversations[user_id]
            logger.info(f"사용자 {interaction.user.name} [{user_id}]와(과) 캐릭터 '{char_name}'의 대화 기록 초기화.")
            await interaction.response.send_message(f"✅ 당신과 AI 캐릭터 '{char_name}'의 대화 기록이 성공적으로 초기화되었습니다.",
                                                    ephemeral=True)
        else:
            char_name_maybe = self.characters_data.get(character, {}).get("name", character)
            await interaction.response.send_message(f"ℹ️ AI 캐릭터 '{char_name_maybe}'와의 대화 기록이 없거나 잘못된 선택입니다.",
                                                    ephemeral=True)

    @app_commands.command(name="ai-chat-history", description="💬 특정 AI 캐릭터와의 현재 진행중인 대화 기록을 간략히 봅니다.")
    @app_commands.describe(
        character="대화 기록을 볼 AI 캐릭터를 선택하세요.",
        turns="표시할 최근 대화 턴 수를 입력하세요 (기본값: 5, 최대: 10)."
    )
    @app_commands.autocomplete(character=active_character_session_autocomplete)
    async def view_gemini_history(self, interaction: discord.Interaction, character: str,
                                  turns: Optional[app_commands.Range[int, 1, 10]] = 5):
        user_id = interaction.user.id

        if character in ["_no_history_", "_nomatch_"]:  # 자동완성에서 온 정보성 값
            await interaction.response.send_message(f"ℹ️ '{character}' 선택은 유효한 작업이 아닙니다. 목록에서 실제 캐릭터를 선택해주세요.",
                                                    ephemeral=True)
            return

        if user_id not in self.user_conversations or \
                character not in self.user_conversations[user_id] or \
                not self.user_conversations[user_id][character]:  # 캐릭터 세션 자체가 없는 경우
            char_name_display = self.characters_data.get(character, {}).get("name", character)
            await interaction.response.send_message(
                f"ℹ️ AI 캐릭터 '{char_name_display}'와의 대화 기록이 없습니다. 먼저 `/ai-chat-memory`로 대화를 시작해주세요.",
                ephemeral=True
            )
            return

        session_data_for_char = self.user_conversations[user_id][character]
        history: List[genai_types.Content] = session_data_for_char['session'].history

        char_info = self.characters_data.get(character, {})  # 없는 경우 빈 dict로 fallback
        if not char_info:  # 캐릭터 설정 파일이 아예 삭제된 경우에 대한 대비
            logger.warning(f"캐릭터 ID '{character}'에 대한 설정 파일을 찾을 수 없습니다. 기록 표시 시 기본값을 사용합니다.")
            char_info = {"name": character, "icon_url": "", "color": [100, 100, 100], "pre_prompt": ""}

        char_name = char_info.get("name", character)  # ID를 fallback 이름으로 사용
        char_icon_url = char_info.get("icon_url", "")
        if not char_icon_url:
            char_icon_url = self.bot.user.avatar.url if self.bot.user.avatar else self.bot.user.default_avatar.url

        char_color_rgb = char_info.get("color", [100, 100, 100])
        char_pre_prompt = char_info.get("pre_prompt", "").strip()

        if not history:  # 세션은 있으나 history가 비어있는 경우 (이론상 거의 없음)
            await interaction.response.send_message(f"{char_name}와(과)의 대화 기록이 아직 없습니다.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title=f"{char_name}와(과)의 대화 기록",
            color=discord.Color.from_rgb(char_color_rgb[0], char_color_rgb[1], char_color_rgb[2]),
            timestamp=interaction.created_at
        )
        embed.set_author(name=char_name, icon_url=char_icon_url)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"최근 {turns}턴의 대화 (요청자: {interaction.user.display_name})")

        history_entries_to_display = []
        start_index = max(0, len(history) - (turns * 2))

        for i in range(start_index, len(history)):
            message_content = history[i]
            display_name_for_role: str
            if message_content.role == "user":
                display_name_for_role = interaction.user.display_name
            else:
                display_name_for_role = char_name

            text_parts_combined = ""
            for part in message_content.parts:
                if hasattr(part, 'text'):
                    text_parts_combined += part.text + " "
            full_text = text_parts_combined.strip()

            if not full_text: continue

            if message_content.role == "user" and i == 0 and char_pre_prompt and full_text.startswith(char_pre_prompt):
                actual_user_text = full_text.replace(char_pre_prompt, "", 1).lstrip('\n').strip()
                entry = f"**[System]** *{char_name}의 캐릭터 페르소나 적용됨*\n"
                if actual_user_text:
                    entry += f"**{display_name_for_role}:** {discord.utils.escape_markdown(actual_user_text[:100])}{'...' if len(actual_user_text) > 100 else ''}"
                else:
                    entry += f"**{display_name_for_role}:** *(첫 메시지)*"
                history_entries_to_display.append(entry)
            else:
                history_entries_to_display.append(
                    f"**{display_name_for_role}:** {discord.utils.escape_markdown(full_text[:120])}{'...' if len(full_text) > 120 else ''}")

        if not history_entries_to_display:
            embed.description = "표시할 텍스트 대화 내용이 없습니다."
        else:
            full_history_text = "\n\n".join(history_entries_to_display)
            if len(full_history_text) > 4096:
                full_history_text = full_history_text[:4090] + "\n...(중략)..."
            embed.description = full_history_text

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="ai-chat-file", description="🖼️ Gemini AI에게 파일과 함께 질문합니다 (이미지 지원, 대화 기억 X).")
    @app_commands.describe(
        attachment="이미지 파일을 첨부해주세요 (PNG, JPEG, WEBP, HEIC, HEIF).",
        prompt=" (선택 사항) 이미지에 대한 질문이나 지시사항을 입력하세요.",
        character="사용할 AI 캐릭터를 선택하세요 (기본: default)."
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def ask_gemini_file(self, interaction: discord.Interaction, attachment: discord.Attachment,
                              prompt: Optional[str] = None, character: Optional[str] = "default"):
        # ... (ask_gemini_single과 유사한 캐릭터 유효성 검사)
        if not self.model:
            await interaction.response.send_message("죄송합니다, Gemini AI 모델이 현재 사용할 수 없습니다. 😥", ephemeral=True)
            return

        if attachment.content_type not in SUPPORTED_IMAGE_MIME_TYPES:
            await interaction.response.send_message(
                f"⚠️ 지원하지 않는 파일 형식입니다. 다음 형식 중 하나를 사용해주세요: {', '.join(SUPPORTED_IMAGE_MIME_TYPES)}", ephemeral=True)
            return

        if attachment.size > 20 * 1024 * 1024:
            await interaction.response.send_message("파일 크기가 너무 큽니다 (최대 20MB).", ephemeral=True)
            return

        if character in ["_error_no_char_", "_nomatch_"] or character not in self.characters_data:
            if character == "default" and "default" not in self.characters_data:
                await interaction.response.send_message("⚠️ 'default' 캐릭터를 포함하여 어떤 캐릭터 설정도 찾을 수 없습니다. 관리자에게 문의해주세요.",
                                                        ephemeral=True)
                return
            elif character != "default":
                await interaction.response.send_message(f"⚠️ 선택한 캐릭터 '{character}'를 찾을 수 없습니다. 유효한 캐릭터를 선택해주세요.",
                                                        ephemeral=True)
                return

        selected_character_id = character if character in self.characters_data else "default"

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

            image_part = {"mime_type": attachment.content_type, "data": image_bytes}
            prompt_to_send = prompt.strip() if prompt and prompt.strip() else "이 이미지에 대해 설명해주세요."
            request_parts = [prompt_to_send, image_part]

            await self._send_gemini_request(interaction, request_parts,
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
    cog_instance = GeminiCog(bot)
    await bot.add_cog(cog_instance)
    if cog_instance.model and cog_instance.characters_data:
        char_count = len(cog_instance.characters_data)
        default_loaded = "'default' 포함" if "default" in cog_instance.characters_data else "'default' 미포함"
        logger.info(
            f"🚀 GeminiCog (모델: {cog_instance.model_name}, 캐릭터 {char_count}개 [{default_loaded}])가 봇에 성공적으로 추가되었습니다.")
    elif not cog_instance.api_key:
        logger.error("🚨 GeminiCog 추가 시도: GEMINI_API_KEY가 없어 기능이 매우 제한됩니다.")
    else:
        logger.warning(f"⚠️ GeminiCog가 추가되었으나, 모델 또는 캐릭터 데이터 초기화에 문제가 있을 수 있습니다. 로그를 확인해주세요.")