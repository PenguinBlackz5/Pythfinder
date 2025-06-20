import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
import os
import re
import subprocess
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any
import aiohttp
import asyncio
import uuid
import shutil
from PIL import Image, ImageSequence
import hashlib
import time
import io

# 디스코드 파일 용량 제한 (8MB) 보다 약간 작은 값으로 설정 (7.5MB)
DISCORD_MAX_FILE_SIZE = int(7.5 * 1024 * 1024)

# --- 데이터베이스 함수 임포트 ---
from database_manager import (
    add_dccon_favorite,
    remove_dccon_favorite,
    get_user_favorites,
    is_dccon_favorited
)

# DcconScraper 클래스를 디스코드 봇에 맞게 일부 수정합니다.
# print() 대신 로깅이나 다른 방식을 사용하는 것이 좋으나, 여기서는 간단하게 유지합니다.
class DcconScraper:
    """DCinside 디시콘 스크래핑을 담당하는 클래스"""
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        })
        self.csrf_token = None
        self.base_url = "https://m.dcinside.com"

    def get_app_id(self) -> (Optional[str], Optional[str]):
        """Python 네이티브 코드로 app_id를 생성합니다. (app_id, error_message) 튜플을 반환합니다."""
        try:
            # KotlinInside 라이브러리의 app_id 생성 로직을 Python으로 재현
            # "dcinside.app" 문자열과 현재 타임스탬프(밀리초)를 조합하여 MD5 해시 생성
            current_time_millis = int(time.time() * 1000)
            app_id_raw = f"dcinside.app{current_time_millis}"
            app_id = hashlib.md5(app_id_raw.encode()).hexdigest()
            print(f"✅ Python 네이티브 app_id 생성 성공: {app_id}")
            return app_id, None
        except Exception as e:
            error = f"❌ Python 네이티브 app_id 생성 중 오류 발생: {e}"
            print(error)
            return None, error

    def search(self, keyword: str, limit: int = 25) -> List[Dict[str, str]]:
        """키워드로 디시콘을 검색하고, 상위 n개의 결과를 반환합니다."""
        search_url = f"{self.base_url}/dcconShop/dcconList"
        params = {"s_type": "title", "s_word": keyword}
        results = []
        
        print(f"\n--- 🔍 DCcon Scraper: 검색 시작 ---")
        print(f"키워드: '{keyword}', URL: {search_url}, 파라미터: {params}")

        try:
            response = self.session.get(search_url, params=params)
            print(f"응답 상태 코드: {response.status_code}")
            response.raise_for_status()
            
            # --- HTML 저장 코드 추가 ---
            try:
                with open("dccon_search_result.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                print("\n[ℹ️] 디버깅을 위해 'dccon_search_result.html' 파일에 현재 HTML을 저장했습니다.")
            except Exception as e:
                print(f"\n[🚨] HTML 파일 저장 실패: {e}")
            # --------------------------
            
            soup = BeautifulSoup(response.text, 'html.parser')

            if "검색결과가 없습니다." in response.text:
                print("페이지에 '검색결과가 없습니다.' 문구가 포함되어 있습니다.")

            csrf_tag = soup.find('meta', {'name': 'csrf-token'})
            if csrf_tag:
                self.csrf_token = csrf_tag.get('content')
                print(f"CSRF 토큰 추출 성공: {self.csrf_token[:10]}...")
            else:
                print("CSRF 토큰을 찾을 수 없습니다.")

            items_container = soup.select_one("#dcconList")
            if not items_container:
                print("\n[🚨 크리티컬 오류] 디시콘 목록 컨테이너('#dcconList')를 찾지 못했습니다.")
                print("--- 수신된 전체 HTML ---")
                print(soup.prettify())
                print("------------------------")
                return []

            items = items_container.select("li.lst-item")
            print(f"\n[📊 파싱 시작] '{items_container.get('id', 'ID 없음')}' 컨테이너에서 {len(items)}개의 아이템 발견")

            for i, item in enumerate(items[:limit]):
                print(f"\n--- {i+1}번째 아이템 처리 ---")
                
                title = "N/A"
                title_tag = item.select_one('div.thum-txt span.name')
                if title_tag:
                    author_span = title_tag.find('span', class_='namein')
                    if author_span:
                        author_span.decompose()
                        print("  - 제작자 이름(span.namein) 제거 완료")
                    title = title_tag.text.strip()
                    print(f"  - 제목 추출 성공: '{title}'")
                else:
                    print("  - 🚨 제목 태그('div.thum-txt span.name')를 찾지 못함")

                package_idx = "N/A"
                link_tag = item.select_one('a')
                if link_tag and link_tag.has_attr('href'):
                    href = link_tag['href']
                    print(f"  - 링크 href 발견: {href}")
                    match = re.search(r"viewDcconDetail\('(\d+)'", href)
                    if match:
                        package_idx = match.group(1)
                        print(f"  - ID 추출 성공: '{package_idx}'")
                    else:
                        print("  - 🚨 href에서 정규식으로 ID 추출 실패")
                else:
                    print("  - 🚨 링크 태그('a') 또는 href 속성을 찾지 못함")

                thumbnail_url = "N/A"
                img_tag = item.select_one('div.thum-img img')
                if img_tag and img_tag.has_attr('src'):
                    thumbnail_url = img_tag['src']
                    print(f"  - 썸네일 URL 추출 성공: {thumbnail_url}")

                    # URL이 완전한 형태인지 확인하고, 아니라면 수정
                    if thumbnail_url.startswith('//'):
                        thumbnail_url = 'https:' + thumbnail_url
                        print(f"  - URL 수정됨 (// 접두사): {thumbnail_url}")
                    elif not thumbnail_url.startswith('http'):
                        # m.dcinside.com을 기준으로 한 상대 경로일 수 있음
                        # 하지만 dcimg5.dcinside.com과 같은 다른 도메인일 가능성이 높음
                        # dccon.php로 시작하는 경우를 특정하여 처리
                        if thumbnail_url.startswith('/dccon.php'):
                             thumbnail_url = 'https://dcimg5.dcinside.com' + thumbnail_url
                             print(f"  - URL 수정됨 (상대 경로): {thumbnail_url}")
                        else: # 그 외의 경우는 일단 기본 도메인을 붙여봄
                             thumbnail_url = self.base_url + thumbnail_url
                             print(f"  - URL 수정됨 (기타 상대 경로): {thumbnail_url}")

                else:
                    print("  - 🚨 이미지 태그('div.thum-img img') 또는 src 속성을 찾지 못함")
                
                description = "설명 없음"
                # 올바른 선택자로 수정: 'div.thum-txt' 아래의 'span.caption'
                desc_tag = item.select_one('div.thum-txt > span.caption')
                if desc_tag:
                    description = desc_tag.text.strip()
                    print(f"  - 설명 추출 성공: '{description[:30]}...'")
                else:
                    print("  - ℹ️ 설명 태그('div.thum-txt > span.caption')를 찾지 못함 (선택 사항)")

                if title != "N/A" and package_idx != "N/A" and thumbnail_url != "N/A":
                    results.append({
                        "name": title,
                        "package_idx": package_idx,
                        "thumbnail_url": thumbnail_url,
                        "description": description
                    })
                    print("  -> ✅ 모든 정보 추출 성공. 결과에 추가합니다.")
                else:
                    print("  -> ❌ 일부 정보 추출 실패. 이 아이템은 건너뜁니다.")
        
        except requests.exceptions.RequestException as e:
            print(f"❌ 검색 중 HTTP 오류 발생: {e}")
        
        except Exception as e:
            print(f"❌ 파싱 중 예기치 않은 오류 발생: {e}")

        print(f"\n--- ✅ 검색 및 파싱 완료 ---")
        print(f"최종적으로 {len(results)}개의 디시콘 정보를 추출했습니다.")
        return results

    def get_details(self, package_idx: str) -> (Optional[Dict[str, Any]], Optional[str]):
        """패키지 ID로 디시콘 상세 정보(정보, 이미지 URL 목록)를 가져옵니다. (details, error_message) 튜플을 반환합니다."""
        if not self.csrf_token:
            error = "❌ CSRF 토큰이 없습니다. search()를 먼저 호출해야 합니다."
            print(error)
            return None, error

        app_id, error_msg = self.get_app_id()
        if error_msg:
            return None, error_msg

        detail_url = f"{self.base_url}/dccon/getDcconDetail"
        data = {"dcconInfo": package_idx, "app_id": app_id}
        headers = {
            "Referer": f"{self.base_url}/dcconShop/dcconList",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-TOKEN": self.csrf_token
        }
        
        try:
            response = self.session.post(detail_url, data=data, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            info = {}
            info['title'] = (soup.select_one('div.top-tit > span.name') or soup.new_tag('span')).text.strip()
            info['maker'] = (soup.select_one('div.make > span.by') or soup.new_tag('span')).text.strip()
            info['description'] = (soup.select_one('div.txt') or soup.new_tag('p')).text.strip()
            
            main_img_tag = soup.select_one('div.dccon-caption-box div.thum-img > img')
            info['main_img_url'] = main_img_tag['src'] if main_img_tag else None

            image_urls = [img['src'] for img in soup.select('ul.dccon-img-lst img') if img.has_attr('src')]
            
            if not image_urls: 
                error = "❌ 상세 정보 HTML 파싱 후 이미지 URL 목록을 찾지 못했습니다."
                print(error)
                return None, error
            return {'info': info, 'images': image_urls}, None

        except requests.exceptions.RequestException as e:
            error = f"❌ 상세 정보 요청 중 네트워크 오류 발생: {e}"
            print(error)
            return None, error
        except Exception as e:
            import traceback
            error = f"❌ 상세 정보 파싱 중 알 수 없는 오류 발생:\n{traceback.format_exc()}"
            print(error)
            return None, error


# --- 즐겨찾기 뷰 ---
class FavoriteDcconView(discord.ui.View):
    """즐겨찾기한 디시콘을 보여주는 View (실시간 다운로드 방식)"""
    def __init__(self, cog: 'Dccon', favorites: List[Dict[str, Any]], author: discord.User):
        super().__init__(timeout=300)
        self.cog = cog
        self.favorites = favorites # 이제 {'dccon_title', 'image_url'}의 리스트
        self.author = author
        self.current_page = 0
        self.message: Optional[discord.WebhookMessage] = None
        self.current_temp_file_path: Optional[str] = None
        self.update_buttons()

    def create_embed(self) -> discord.Embed:
        current_fav = self.favorites[self.current_page]
        embed = discord.Embed(
            title=f"⭐ 즐겨찾기: {current_fav['dccon_title']}",
            description=f"페이지: {self.current_page + 1}/{len(self.favorites)}",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"요청자: {self.author.display_name}")
        return embed

    def update_buttons(self):
        is_empty = not self.favorites
        
        prev_button = discord.utils.get(self.children, custom_id="fav_prev")
        next_button = discord.utils.get(self.children, custom_id="fav_next")
        send_button = discord.utils.get(self.children, custom_id="fav_send")
        delete_button = discord.utils.get(self.children, custom_id="fav_delete")

        if prev_button: prev_button.disabled = self.current_page == 0 or is_empty
        if next_button: next_button.disabled = self.current_page >= len(self.favorites) - 1 or is_empty
        if send_button: send_button.disabled = is_empty
        if delete_button: delete_button.disabled = is_empty

    async def _cleanup_file(self):
        if self.current_temp_file_path and os.path.exists(self.current_temp_file_path):
            try:
                os.remove(self.current_temp_file_path)
            except OSError: pass
        self.current_temp_file_path = None

    async def show_current_page(self, interaction: discord.Interaction):
        await self._cleanup_file()

        if not self.favorites:
            self.update_buttons()
            await interaction.response.edit_message(content="즐겨찾기 목록이 비었습니다.", view=self, embed=None, attachments=[])
            return

        self.update_buttons()
        
        fav = self.favorites[self.current_page]
        image_url = fav['image_url']
        
        async with aiohttp.ClientSession() as session:
            path, error = await self.cog.download_image(session, image_url)
        
        if error:
            await interaction.response.edit_message(content=f"오류: 이미지를 불러올 수 없습니다.\n> {error}", view=self, embed=None, attachments=[])
            return

        self.current_temp_file_path = path
        filename = os.path.basename(path)
        embed = self.create_embed()
        embed.set_image(url=f"attachment://{filename}")

        try:
            with open(path, 'rb') as f:
                file = discord.File(f, filename=filename)
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self, attachments=[file])
                else:
                    # 최초 호출 시에는 is_done()이 False일 수 있음
                    await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
        except FileNotFoundError:
            await interaction.edit_original_response(content=f"오류: 임시 파일을 찾을 수 없습니다.", view=self, embed=None, attachments=[])


    @discord.ui.button(label="◀", style=discord.ButtonStyle.grey, custom_id="fav_prev")
    async def prev_button(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        self.current_page -= 1
        await self.show_current_page(i)

    @discord.ui.button(label="✅ 보내기", style=discord.ButtonStyle.success, custom_id="fav_send")
    async def send_button(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        if not self.current_temp_file_path:
            await i.followup.send("전송할 파일이 없습니다.", ephemeral=True)
            return
            
        try:
            with open(self.current_temp_file_path, 'rb') as f:
                file = discord.File(f, filename=os.path.basename(self.current_temp_file_path))
                await i.channel.send(content=f"{i.user.mention}:", file=file)
                await i.delete_original_response()
        except Exception as e:
            await i.followup.send(f"오류: {e}", ephemeral=True)
        
        self.stop()
        await self._cleanup_file()


    @discord.ui.button(label="💔 삭제", style=discord.ButtonStyle.danger, custom_id="fav_delete")
    async def delete_button(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        fav_to_delete = self.favorites[self.current_page]
        
        success = await remove_dccon_favorite(self.author.id, fav_to_delete['image_url'])

        if not success:
            await i.followup.send("즐겨찾기 삭제에 실패했습니다 (DB 오류).", ephemeral=True)
            return

        self.favorites.pop(self.current_page)
        if self.current_page >= len(self.favorites) and self.favorites:
            self.current_page -= 1
        
        await self.show_current_page(i)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.grey, custom_id="fav_next")
    async def next_button(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        self.current_page += 1
        await self.show_current_page(i)

    async def on_timeout(self):
        await self._cleanup_file()
        if self.message:
            try:
                await self.message.edit(content="시간이 만료되었습니다.", view=None, embed=None, attachments=[])
            except discord.NotFound:
                pass
        self.stop()


class DcconImageView(discord.ui.View):
    """디시콘 이미지를 실시간으로 다운로드하여 보여주는 View"""
    def __init__(self, cog: 'Dccon', title: str, image_urls: List[str], author: discord.User):
        super().__init__(timeout=300)
        self.cog = cog
        self.title = title
        self.image_urls = image_urls
        self.author = author
        self.current_page = 0
        self.message: Optional[discord.WebhookMessage] = None
        self.current_temp_file_path: Optional[str] = None
        self.current_error: Optional[str] = None
        self.update_buttons()

    def create_embed(self) -> discord.Embed:
        """현재 페이지에 맞는 임베드를 생성합니다."""
        embed = discord.Embed(
            title=f"디시콘: {self.title}",
            description=f"페이지: {self.current_page + 1}/{len(self.image_urls)}",
            color=discord.Color.red() if self.current_error else discord.Color.blue()
        )

        if self.current_error:
            embed.add_field(name="⚠️ 이미지 로드 오류", value=self.current_error, inline=False)

        embed.set_footer(text=f"요청자: {self.author.display_name}")
        return embed

    def update_buttons(self):
        """버튼 활성화/비활성화 상태를 업데이트합니다."""
        prev_button = discord.utils.get(self.children, custom_id="prev_page")
        next_button = discord.utils.get(self.children, custom_id="next_page")
        favorite_button = discord.utils.get(self.children, custom_id="favorite_dccon")
        select_button = discord.utils.get(self.children, custom_id="select_dccon")
        
        if prev_button: prev_button.disabled = self.current_page == 0
        if next_button: next_button.disabled = self.current_page >= len(self.image_urls) - 1

        is_errored = self.current_error is not None
        if favorite_button: favorite_button.disabled = is_errored
        if select_button: select_button.disabled = is_errored

    async def _cleanup_previous_file(self):
        """이전 임시 파일을 삭제합니다."""
        if self.current_temp_file_path and os.path.exists(self.current_temp_file_path):
            try:
                os.remove(self.current_temp_file_path)
            except OSError as e:
                print(f"🚨 임시 파일 삭제 실패: {e}")
        self.current_temp_file_path = None
        self.current_error = None
        
    async def show_page(self, interaction: discord.Interaction, is_initial: bool = False):
        """
        요청된 페이지의 디시콘을 실시간으로 다운로드하고 표시합니다.
        is_initial 플래그는 처음 View가 생성될 때를 위함입니다.
        """
        # 이전 파일 정리
        await self._cleanup_previous_file()

        # 현재 페이지 URL 가져오기
        current_url = self.image_urls[self.current_page]

        # 이미지 다운로드 및 처리
        async with aiohttp.ClientSession() as session:
            path, error = await self.cog.download_image(session, current_url)
        
        self.current_temp_file_path = path
        self.current_error = error
        
        # UI 업데이트 (버튼, 임베드)
        self.update_buttons()
        embed = self.create_embed()
        attachments = []
        
        if self.current_temp_file_path:
            filename = os.path.basename(self.current_temp_file_path)
            embed.set_image(url=f"attachment://{filename}")
            attachments.append(discord.File(self.current_temp_file_path, filename=filename))

        # 메시지 수정 또는 새로 전송
        content = f"**{self.title}** 디시콘을 표시합니다. (총 {len(self.image_urls)}개)"
        if is_initial:
            await interaction.edit_original_response(content=content, embed=embed, view=self, attachments=attachments)
            self.message = await interaction.original_response()
        else:
            await interaction.edit_original_response(embed=embed, view=self, attachments=attachments)

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.grey, custom_id="prev_page")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            await self.show_page(interaction)

    @discord.ui.button(label="⭐ 즐겨찾기", style=discord.ButtonStyle.primary, custom_id="favorite_dccon")
    async def favorite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_image_url = self.image_urls[self.current_page]
        
        if await is_dccon_favorited(self.author.id, current_image_url):
            await interaction.response.send_message("이미 즐겨찾기에 추가된 디시콘입니다.", ephemeral=True)
            return

        try:
            # 이제 파일을 복사하지 않고 DB에 URL만 저장
            success = await add_dccon_favorite(self.author.id, self.title, current_image_url)
            if success:
                await interaction.response.send_message("✅ 즐겨찾기에 추가했습니다!", ephemeral=True)
                print(f"[✅] 즐겨찾기 저장 (URL): {self.author.id} -> {current_image_url}")
            else:
                await interaction.response.send_message("즐겨찾기 추가에 실패했습니다. (DB 오류)", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"즐겨찾기 추가 중 오류 발생: {e}", ephemeral=True)

    @discord.ui.button(label="✅ 보내기", style=discord.ButtonStyle.success, custom_id="select_dccon")
    async def select_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """현재 디시콘을 채널에 전송합니다."""
        await interaction.response.defer()

        if not self.current_temp_file_path:
             await interaction.followup.send("전송할 파일이 없습니다.", ephemeral=True)
             return

        try:
            with open(self.current_temp_file_path, 'rb') as f:
                discord_file = discord.File(f, filename=os.path.basename(self.current_temp_file_path))
                await interaction.channel.send(content=f"{interaction.user.mention}:", file=discord_file)
        except FileNotFoundError:
            await interaction.followup.send("오류: 이미지 파일을 찾을 수 없습니다. 다시 시도해주세요.", ephemeral=True)
            return
        except Exception as e:
            await interaction.followup.send(f"오류: 파일을 전송하는 중 문제가 발생했습니다: {e}", ephemeral=True)
            return
            
        await interaction.delete_original_response()
        self.stop() # 전송 후 View는 멈추고 파일 정리
        await self._cleanup_previous_file()

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.grey, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page < len(self.image_urls) - 1:
            self.current_page += 1
            await self.show_page(interaction)
        
    async def cleanup_files(self):
        """View와 관련된 모든 임시 파일을 삭제합니다."""
        await self._cleanup_previous_file()

    async def on_timeout(self):
        """타임아웃 시 버튼을 비활성화하고 임시 파일을 삭제합니다."""
        print("\n[⏰] 뷰어 타임아웃. 임시 파일 정리를 시작합니다...")
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(content="시간이 만료되어 디시콘 뷰어가 비활성화되었습니다.", view=self, embed=None, attachments=[])
            except discord.NotFound:
                pass # 사용자가 메시지를 삭제한 경우

        await self.cleanup_files()
        self.stop()


class DcconSelect(discord.ui.Select):
    """검색된 디시콘 목록을 보여주는 드롭다운 선택 메뉴"""
    def __init__(self, cog, search_results: List[Dict[str, str]]):
        self.cog = cog
        self.search_results = search_results
        options = [
            discord.SelectOption(label=res['name'], value=res['package_idx'])
            for res in search_results
        ]
        super().__init__(placeholder="결과에서 디시콘을 선택하세요...", options=options)

    async def callback(self, interaction: discord.Interaction):
        package_idx = self.values[0]
        self.view.stop()

        await interaction.response.edit_message(
            content="디시콘 뷰어를 준비하고 있습니다. 첫 번째 이미지를 불러옵니다... 🖼️", 
            view=None, embed=None, attachments=[]
        )
        
        try:
            details, error_msg = self.cog.scraper.get_details(package_idx)
            
            # 에러가 있다면, 사용자에게 바로 보여줌
            if error_msg:
                error_embed = discord.Embed(
                    title="오류 발생",
                    description=f"디시콘 상세 정보를 가져오는 데 실패했습니다. 😥",
                    color=discord.Color.red()
                )
                error_embed.add_field(name="서버 로그", value=f"```\n{error_msg[:1000]}\n```", inline=False)
                await interaction.edit_original_response(embed=error_embed, content="", view=None, attachments=[])
                return

            # 위에서 에러를 잡았으므로, 여기서는 details가 확실히 있다고 가정할 수 있음
            if not details or not details.get('images'):
                 await interaction.edit_original_response(content="알 수 없는 이유로 디시콘 상세 정보를 가져오지 못했습니다. (이미지 목록 없음)")
                 return

            image_urls = details['images']
            title = details['info']['title']

            if not image_urls:
                await interaction.edit_original_response(content="이 디시콘에는 이미지가 없습니다.")
                return

            # View를 생성하고, 첫 페이지를 로드 및 전송하는 과정을 View에 위임합니다.
            image_view = DcconImageView(
                cog=self.cog,
                title=title,
                image_urls=image_urls,
                author=interaction.user
            )
            await image_view.show_page(interaction, is_initial=True)
        
        except Exception as e:
            # traceback을 사용하여 더 상세한 에러 정보 로깅
            import traceback
            error_details = f"```\n{traceback.format_exc()}\n```"
            print(f"❌ DcconSelect 콜백에서 예외 발생: {e}")
            await interaction.edit_original_response(
                content=f"디시콘을 불러오는 중 심각한 오류가 발생했습니다. 😥\n**오류 내용:**\n{error_details}",
                view=None, embed=None, attachments=[]
            )
            return

class DcconSelectView(discord.ui.View):
    """DcconSelect를 담는 View"""
    def __init__(self, cog, search_results: List[Dict[str, str]], author_id: int):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.add_item(DcconSelect(cog, search_results))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("명령어를 실행한 사용자만 선택할 수 있습니다.", ephemeral=True)
            return False
        return True

class Dccon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scraper = DcconScraper()
        self.temp_dir = "temp_images"
        self.favorites_dir = "favorited_dccons"
        for dir_path in [self.temp_dir, self.favorites_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    @tasks.loop(hours=1.0)
    async def cleanup_task(self):
        """주기적으로 오래된 임시 파일을 정리하는 백그라운드 작업입니다."""
        print("\n--- 🧹 주기적인 임시 파일 정리 시작 ---")
        now = time.time()
        # 3시간 이상된 파일들을 삭제 대상으로 설정
        cleanup_age_seconds = 3 * 60 * 60  

        deleted_count = 0
        for dir_path in [self.temp_dir, self.favorites_dir]:
            print(f"[{dir_path}] 폴더를 확인합니다...")
            try:
                for filename in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, filename)
                    # 파일인지 확인 (하위 폴더는 무시)
                    if os.path.isfile(file_path):
                        try:
                            file_age = now - os.path.getmtime(file_path)
                            if file_age > cleanup_age_seconds:
                                os.remove(file_path)
                                deleted_count += 1
                                print(f"  - 삭제 (오래됨): {file_path}")
                        except FileNotFoundError:
                            # 파일을 확인하고 삭제하는 사이에 다른 로직에 의해 삭제된 경우
                            continue
            except Exception as e:
                print(f"🚨 [{dir_path}] 폴더 정리 중 오류 발생: {e}")
        
        if deleted_count > 0:
            print(f"--- ✅ 주기적인 정리 완료. {deleted_count}개의 오래된 파일을 삭제했습니다. ---")
        else:
            print(f"--- ✅ 주기적인 정리 완료. 삭제할 오래된 파일이 없습니다. ---")

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """루프가 시작되기 전에 봇이 준비될 때까지 기다립니다."""
        await self.bot.wait_until_ready()

    def _process_and_convert_image(self, temp_filepath: str, content_type: str) -> (Optional[str], Optional[str]):
        """
        다운로드된 이미지 파일을 처리합니다. (동기 함수)
        APNG인 경우 GIF로 변환하고, 일반 이미지는 확장자를 추가합니다.
        CPU 집약적인 작업이므로 별도 스레드에서 실행되어야 합니다.
        """
        img = None
        final_filepath = None
        try:
            img = Image.open(temp_filepath)
            
            # APNG인 경우, FFmpeg를 사용하여 WebP로 변환 (최고의 호환성 보장)
            if hasattr(img, 'n_frames') and img.n_frames > 1:
                print(f"✅ APNG 감지됨 ({img.n_frames} 프레임). 'FFmpeg'를 사용한 'Fast Path' 최적화를 시작합니다.")
                
                # Pillow 라이브러리가 더 이상 필요 없으므로 핸들을 닫음
                img.close()
                img = None

                final_filepath = temp_filepath + ".webp"
                
                # --- FFmpeg Fast Path / Slow Path 최적화 로직 ---
                FAST_PATH_QUALITY = 100
                best_quality = None
                
                def run_ffmpeg(quality: int) -> bool:
                    """주어진 품질로 FFmpeg 변환을 실행하고 성공 여부를 반환합니다."""
                    command = [
                        'ffmpeg',
                        '-y',  # 덮어쓰기 허용
                        '-i', temp_filepath,
                        '-c:v', 'libwebp',
                        '-lossless', '0',
                        '-quality', str(quality),
                        '-loop', '0',
                        '-preset', 'default',
                        '-an',
                        '-vsync', '0',
                        final_filepath
                    ]
                    try:
                        # FFmpeg의 상세 로그는 숨기고, 오류 발생 시에만 표시
                        result = subprocess.run(command, check=True, capture_output=True, text=True)
                        return True
                    except subprocess.CalledProcessError as e:
                        print(f"--- 🚨 FFmpeg 오류 (quality: {quality}) ---")
                        print(e.stderr)
                        return False

                # 1. Fast Path
                print(f"  - Fast Path: 품질 {FAST_PATH_QUALITY}로 변환 시도...")
                if run_ffmpeg(FAST_PATH_QUALITY):
                    file_size = os.path.getsize(final_filepath)
                    print(f"  - 결과 크기: {file_size / (1024*1024):.2f}MB")
                    if file_size <= DISCORD_MAX_FILE_SIZE:
                        best_quality = FAST_PATH_QUALITY
                
                # 2. Slow Path
                if best_quality is None:
                    print(f"  -> Fast Path 실패. Slow Path (정밀 탐색)를 시작합니다.")
                    for quality in range(FAST_PATH_QUALITY - 10, 35, -10): # 65, 55, 45
                        print(f"    - 품질 {quality} 테스트...")
                        if run_ffmpeg(quality):
                            file_size = os.path.getsize(final_filepath)
                            print(f"    - 결과 크기: {file_size / (1024*1024):.2f}MB")
                            if file_size <= DISCORD_MAX_FILE_SIZE:
                                best_quality = quality
                                break

                # 3. 최종 결과 처리
                if best_quality is not None:
                    print(f"-> ✅ FFmpeg 변환 완료. 최적 품질: {best_quality}")
                    # 최종 파일은 이미 final_filepath에 저장되어 있음
                else:
                    error = "FFmpeg 변환 실패 또는 가장 낮은 품질로도 파일 크기를 줄일 수 없었습니다."
                    print(f"--- ❌ {error} ---")
                    # 생성되었을 수 있는 최종 파일 삭제
                    if os.path.exists(final_filepath):
                        os.remove(final_filepath)
                    return None, error

            # 일반 이미지인 경우 확장자 추가
            else:
                ext = 'png'
                if 'image/gif' in content_type: ext = 'gif'
                elif 'image/jpeg' in content_type: ext = 'jpg'
                final_filepath = temp_filepath + f".{ext}"
                
                img.close()
                img = None # 핸들이 닫혔음을 명시
                shutil.move(temp_filepath, final_filepath) # os.rename 대신 shutil.move 사용

            # 변환/저장 후 파일 크기 확인
            final_size = os.path.getsize(final_filepath)
            if final_size > DISCORD_MAX_FILE_SIZE:
                size_in_mb = final_size / (1024 * 1024)
                error = f"변환된 파일 크기({size_in_mb:.2f}MB)가 너무 큽니다."
                print(f"--- ❌ {error} ---")
                os.remove(final_filepath)
                return None, error

            print(f"최종 저장된 파일 경로: {final_filepath}")
            print(f"파일 크기: {final_size} bytes")
            return final_filepath, None

        except Exception as e:
            error_msg = "이미지 처리 중 오류가 발생했습니다."
            print(f"--- ❌ {error_msg} (상세: {e}) ---")
            # 변환 실패 시 생성되었을 수 있는 파일 삭제
            if final_filepath and os.path.exists(final_filepath):
                os.remove(final_filepath)
            return None, error_msg
        finally:
            if img:
                img.close()
            # 원본 임시 파일(확장자 없는)이 남아있다면 삭제
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)


    async def download_image(self, session: aiohttp.ClientSession, url: str) -> (Optional[str], Optional[str]):
        """
        주어진 URL에서 이미지를 비동기적으로 다운로드하고,
        별도 스레드에서 이미지 처리(변환)를 수행합니다.
        """
        print(f"\n--- 🖼️ 이미지 다운로드 시작 ---")
        print(f"URL: {url}")
        
        temp_filepath = os.path.join(self.temp_dir, f"{uuid.uuid4()}")
        
        try:
            headers = {'Referer': 'https://m.dcinside.com/'}
            async with session.get(url, headers=headers) as response:
                print(f"응답 상태: {response.status}")
                if response.status != 200:
                    error = f"다운로드 실패 (상태 코드: {response.status})"
                    print(f"--- ❌ {error} ---")
                    return None, error
                
                # --- [디버그 로그] 원본 파일 크기 사전 확인 ---
                content_length = response.content_length
                if content_length:
                    size_in_mb = content_length / (1024 * 1024)
                    print(f"  [사전 확인] 서버가 알려준 크기: {size_in_mb:.2f}MB")
                    if content_length > DISCORD_MAX_FILE_SIZE:
                        error = f"원본 파일 크기({size_in_mb:.2f}MB)가 너무 큽니다."
                        print(f"--- ❌ {error} ---")
                        return None, error
                else:
                    print("  [사전 확인] 서버가 크기 정보를 제공하지 않음. 다운로드 후 확인합니다.")

                content_type = response.content_type
                print(f"  > Content-Type: {content_type}")
                print(f"  > 다운로드 시작...")

                with open(temp_filepath, 'wb') as f:
                    f.write(await response.read())
                print(f"  > 다운로드 완료.")
            
            # 다운로드 후 파일 크기 재확인 (헤더가 없는 경우 대비)
            downloaded_size = os.path.getsize(temp_filepath)
            size_in_mb = downloaded_size / (1024 * 1024)
            print(f"  [사후 확인] 다운로드된 실제 크기: {size_in_mb:.2f}MB")
            if downloaded_size > DISCORD_MAX_FILE_SIZE:
                error = f"다운로드된 파일 크기({size_in_mb:.2f}MB)가 너무 큽니다."
                print(f"--- ❌ {error} ---")
                os.remove(temp_filepath)
                return None, error

            # CPU 집약적인 이미지 처리 작업을 별도 스레드에서 실행
            loop = asyncio.get_running_loop()
            final_filepath, error_msg = await loop.run_in_executor(
                None, self._process_and_convert_image, temp_filepath, content_type
            )

            if final_filepath:
                print(f"--- 🖼️ 이미지 다운로드 및 처리 성공 ---")
            else:
                print(f"--- 🖼️ 이미지 처리 중 실패 ---")
            
            return final_filepath, error_msg

        except Exception as e:
            error = f"다운로드/처리 중 외부 오류: {e}"
            print(f"--- ❌ {error} ---")
            # 오류 발생 시 다운로드된 임시 파일 정리
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            return None, error

    @app_commands.command(name="디시콘", description="디시콘을 검색하고 다운로드합니다.")
    @app_commands.describe(keyword="검색할 디시콘의 이름 (예: 만두콘)")
    async def dccon_search(self, interaction: discord.Interaction, keyword: str):
        await interaction.response.defer(ephemeral=True)

        print(f"\n--- 🤖 /디시콘 명령어 실행 ---")
        print(f"사용자: {interaction.user}, 키워드: '{keyword}'")

        search_results = self.scraper.search(keyword, limit=25)

        print(f"\n--- scraper.search 결과 ---")
        print(f"반환된 결과 수: {len(search_results)}")
        if search_results:
            print("첫 번째 결과:", search_results[0])
        print("---------------------------")


        if not search_results:
            await interaction.followup.send(f"'{keyword}'에 대한 디시콘을 찾을 수 없어요. 😥 (자세한 내용은 콘솔 로그를 확인해주세요)", ephemeral=True)
            return

        # 검색 결과를 보여주는 초기 임베드 생성
        embed = discord.Embed(
            title=f"디시콘 검색 결과: '{keyword}'",
            description="아래 목록에서 원하는 디시콘을 선택해주세요.",
            color=discord.Color.gold()
        )

        for i, result in enumerate(search_results):
            description = result.get("description", "설명 없음")
            # 설명이 너무 길면 잘라냅니다.
            if len(description) > 50:
                description = description[:50] + "..."
            embed.add_field(name=f"{i+1}. {result['name']}", value=description, inline=False)
        
        # 첫 번째 결과의 미리보기 이미지를 썸네일로 설정 (이제는 로컬 파일로)
        temp_image_path = None
        if search_results and search_results[0].get('thumbnail_url'):
            async with aiohttp.ClientSession() as session:
                # 썸네일 다운로드는 실패해도 전체 기능에 영향이 없도록 간단히 처리
                temp_image_path, _ = await self.download_image(session, search_results[0]['thumbnail_url'])

        file = None
        if temp_image_path:
            file = discord.File(temp_image_path, filename=os.path.basename(temp_image_path))
            embed.set_thumbnail(url=f"attachment://{os.path.basename(temp_image_path)}")

        select_view = DcconSelectView(self, search_results, interaction.user.id)
        await interaction.followup.send(embed=embed, view=select_view, file=file, ephemeral=True)

        # 메시지 전송 후 임시 파일 삭제
        if temp_image_path and os.path.exists(temp_image_path):
             os.remove(temp_image_path)
             print(f"[✅] 임시 썸네일 파일 삭제: {temp_image_path}")

    @app_commands.command(name="즐겨찾기", description="즐겨찾기한 디시콘을 봅니다.")
    async def dccon_favorites(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        favorites = await get_user_favorites(interaction.user.id)
        if not favorites:
            await interaction.followup.send("⭐ 즐겨찾기한 디시콘이 없습니다. 검색 후 '⭐ 즐겨찾기' 버튼을 눌러 추가해보세요!", ephemeral=True)
            return

        view = FavoriteDcconView(self, favorites, interaction.user)
        
        # 첫 번째 즐겨찾기 표시 (View가 알아서 다운로드 및 표시)
        await view.show_current_page(interaction)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Dccon(bot)) 