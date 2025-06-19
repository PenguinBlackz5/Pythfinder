import discord
from discord.ext import commands
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

    def get_app_id(self) -> Optional[str]:
        """JAR 파일을 실행하여 app_id를 가져옵니다."""
        jar_path = os.path.join("appid_generator", "build", "libs", "appid_generator-1.0-SNAPSHOT.jar")
        if not os.path.exists(jar_path):
            print(f"❌ JAR 파일을 찾을 수 없습니다: {jar_path}")
            return None
        
        command = ["java", "-jar", jar_path]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"❌ app_id 생성 중 오류 발생: {e}")
            return None

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
                
                if title != "N/A" and package_idx != "N/A" and thumbnail_url != "N/A":
                    results.append({
                        "name": title,
                        "package_idx": package_idx,
                        "thumbnail_url": thumbnail_url,
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

    def get_details(self, package_idx: str) -> Optional[Dict[str, Any]]:
        """패키지 ID로 디시콘의 상세 정보(정보, 이미지 URL 목록)를 가져옵니다."""
        if not self.csrf_token:
            print("❌ CSRF 토큰이 없습니다. search()를 먼저 호출해야 합니다.")
            return None

        app_id = self.get_app_id()
        if not app_id:
            return None

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
            
            # 썸네일 이미지 선택자 수정
            main_img_tag = soup.select_one('div.dccon-caption-box div.thum-img > img')
            info['main_img_url'] = main_img_tag['src'] if main_img_tag else None

            image_urls = [img['src'] for img in soup.select('ul.dccon-img-lst img') if img.has_attr('src')]
            
            if not image_urls: return None
            return {'info': info, 'images': image_urls}

        except requests.exceptions.RequestException as e:
            print(f"❌ 상세 정보 요청 중 오류 발생: {e}")
        return None


# --- 즐겨찾기 뷰 ---
class FavoriteDcconView(discord.ui.View):
    """즐겨찾기한 디시콘을 보여주는 View"""
    def __init__(self, cog: 'Dccon', favorites: List[Dict[str, Any]], author: discord.User):
        super().__init__(timeout=300)
        self.cog = cog
        self.favorites = favorites
        self.author = author
        self.current_page = 0
        self.message: Optional[discord.WebhookMessage] = None
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
        prev_button = discord.utils.get(self.children, custom_id="fav_prev")
        next_button = discord.utils.get(self.children, custom_id="fav_next")
        if prev_button: prev_button.disabled = self.current_page == 0
        if next_button: next_button.disabled = self.current_page >= len(self.favorites) - 1

    async def show_current_page(self, interaction: discord.Interaction):
        if not self.favorites:
            await interaction.response.edit_message(content="즐겨찾기 목록이 비었습니다.", view=None, embed=None, attachments=[])
            return

        self.update_buttons()
        fav = self.favorites[self.current_page]
        filepath = fav['local_path']
        filename = os.path.basename(filepath)
        embed = self.create_embed()
        embed.set_image(url=f"attachment://{filename}")

        try:
            with open(filepath, 'rb') as f:
                file = discord.File(f, filename=filename)
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self, attachments=[file])
                else:
                    await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
        except FileNotFoundError:
            await interaction.response.edit_message(content=f"오류: '{filepath}' 파일을 찾을 수 없습니다. 즐겨찾기에서 삭제합니다.", view=None, embed=None, attachments=[])
            await remove_dccon_favorite(self.author.id, fav['image_url'])
            self.favorites.pop(self.current_page)
            if self.current_page >= len(self.favorites) and self.favorites:
                self.current_page -= 1
            await self.show_current_page(interaction) # Refresh view

    @discord.ui.button(label="◀", style=discord.ButtonStyle.grey, custom_id="fav_prev")
    async def prev_button(self, i: discord.Interaction, b: discord.ui.Button):
        self.current_page -= 1
        await self.show_current_page(i)

    @discord.ui.button(label="✅ 보내기", style=discord.ButtonStyle.success, custom_id="fav_send")
    async def send_button(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        filepath = self.favorites[self.current_page]['local_path']
        try:
            with open(filepath, 'rb') as f:
                file = discord.File(f, filename=os.path.basename(filepath))
                await i.channel.send(content=f"{i.user.mention}:", file=file)
                await i.edit_original_response(content="✅ 전송했습니다.", view=None, embed=None, attachments=[])
        except Exception as e:
            await i.edit_original_response(content=f"오류: {e}", view=None, embed=None, attachments=[])
        self.stop()

    @discord.ui.button(label="💔 삭제", style=discord.ButtonStyle.danger, custom_id="fav_delete")
    async def delete_button(self, i: discord.Interaction, b: discord.ui.Button):
        fav_to_delete = self.favorites[self.current_page]
        deleted_path = await remove_dccon_favorite(self.author.id, fav_to_delete['image_url'])

        if deleted_path and os.path.exists(deleted_path):
            os.remove(deleted_path)
            print(f"[✅] 즐겨찾기 파일 삭제: {deleted_path}")

        self.favorites.pop(self.current_page)
        if self.current_page >= len(self.favorites) and self.favorites:
            self.current_page -= 1
        
        await self.show_current_page(i)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.grey, custom_id="fav_next")
    async def next_button(self, i: discord.Interaction, b: discord.ui.Button):
        self.current_page += 1
        await self.show_current_page(i)


class DcconImageView(discord.ui.View):
    """디시콘 이미지를 넘겨보는 View (로컬 파일 기반)"""
    def __init__(self, cog: 'Dccon', title: str, image_urls: List[str], image_paths: List[str], author: discord.User):
        super().__init__(timeout=300)
        self.cog = cog
        self.title = title
        self.image_urls = image_urls # 원본 URL 저장
        self.image_paths = image_paths
        self.author = author
        self.current_page = 0
        self.message: Optional[discord.WebhookMessage] = None
        self.update_buttons()

    def create_embed(self) -> discord.Embed:
        """현재 페이지에 맞는 임베드를 생성합니다."""
        embed = discord.Embed(
            title=f"디시콘: {self.title}",
            description=f"페이지: {self.current_page + 1}/{len(self.image_paths)}",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"요청자: {self.author.display_name}")
        return embed

    def update_buttons(self):
        """버튼 활성화/비활성화 상태를 업데이트합니다."""
        # custom_id를 사용하여 버튼을 찾습니다.
        prev_button = discord.utils.get(self.children, custom_id="prev_page")
        next_button = discord.utils.get(self.children, custom_id="next_page")
        
        if prev_button:
            prev_button.disabled = self.current_page == 0
        if next_button:
            next_button.disabled = self.current_page >= len(self.image_paths) - 1

    async def handle_interaction(self, interaction: discord.Interaction):
        """버튼 상호작용을 처리하고, 새 이미지 파일을 첨부하여 메시지를 수정합니다."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("명령어를 실행한 사용자만 조작할 수 있습니다.", ephemeral=True)
            return
        
        self.update_buttons()
        
        filepath = self.image_paths[self.current_page]
        filename = os.path.basename(filepath)
        embed = self.create_embed()
        embed.set_image(url=f"attachment://{filename}")

        try:
            with open(filepath, 'rb') as f:
                file = discord.File(f, filename=filename)
                await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
        except FileNotFoundError:
            await interaction.response.edit_message(content="오류: 이미지 파일을 찾을 수 없습니다. 처음부터 다시 시도해주세요.", view=None, embed=None, attachments=[])
            self.stop()
            await self.cleanup_files()

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.grey, custom_id="prev_page")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        await self.handle_interaction(interaction)

    @discord.ui.button(label="⭐ 즐겨찾기", style=discord.ButtonStyle.primary, custom_id="favorite_dccon")
    async def favorite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_image_url = self.image_urls[self.current_page]
        
        if await is_dccon_favorited(self.author.id, current_image_url):
            await interaction.response.send_message("이미 즐겨찾기에 추가된 디시콘입니다.", ephemeral=True)
            return

        temp_path = self.image_paths[self.current_page]
        filename = os.path.basename(temp_path)
        permanent_path = os.path.join(self.cog.favorites_dir, filename)

        try:
            shutil.copy(temp_path, permanent_path)
            success = await add_dccon_favorite(self.author.id, self.title, current_image_url, permanent_path)
            if success:
                await interaction.response.send_message("✅ 즐겨찾기에 추가했습니다!", ephemeral=True)
                print(f"[✅] 즐겨찾기 저장: {self.author.id} -> {permanent_path}")
            else:
                os.remove(permanent_path) # DB 저장 실패시 파일도 삭제
                await interaction.response.send_message("즐겨찾기 추가에 실패했습니다. (DB 오류)", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"즐겨찾기 추가 중 오류 발생: {e}", ephemeral=True)

    @discord.ui.button(label="✅ 보내기", style=discord.ButtonStyle.success, custom_id="select_dccon")
    async def select_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """현재 디시콘을 채널에 전송합니다."""
        await interaction.response.defer() # 응답 지연

        filepath = self.image_paths[self.current_page]
        try:
            with open(filepath, 'rb') as f:
                discord_file = discord.File(f, filename=os.path.basename(filepath))
                await interaction.channel.send(content=f"{interaction.user.mention}:", file=discord_file)
        except FileNotFoundError:
            await interaction.followup.send("오류: 이미지 파일을 찾을 수 없습니다. 다시 시도해주세요.", ephemeral=True)
            return # 파일이 없으므로 여기서 중단
        except Exception as e:
            await interaction.followup.send(f"오류: 파일을 전송하는 중 문제가 발생했습니다: {e}", ephemeral=True)
            return
            
        # 성공적으로 전송 후, 원본 임시 메시지 삭제
        await interaction.delete_original_response()
        
        print("\n[✅] 디시콘 전송 완료. 임시 파일 정리를 시작합니다...")
        self.stop()
        await self.cleanup_files()

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.grey, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.image_paths) - 1:
            self.current_page += 1
        await self.handle_interaction(interaction)
        
    async def cleanup_files(self):
        """View와 관련된 모든 임시 파일을 삭제합니다."""
        if not self.image_paths:
            return
        
        print(f"\n[ℹ️] DcconImageView 파일 정리. {len(self.image_paths)}개 파일 삭제 시작...")
        for path in self.image_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"  - 삭제: {path}")
                except Exception as e:
                    print(f"  - 🚨 파일 삭제 실패: {path}, 오류: {e}")
        self.image_paths.clear()

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
            content="선택한 디시콘의 모든 이미지를 다운로드 중입니다... 📦\n(디시콘 크기에 따라 시간이 걸릴 수 있습니다)", 
            view=None, embed=None, attachments=[]
        )
        
        try:
            details = self.cog.scraper.get_details(package_idx)
            if not details or not details.get('images'):
                # get_details 내부에서 이미 print로 로그를 남기므로 여기서는 사용자에게만 알림
                await interaction.edit_original_response(content="디시콘 상세 정보를 가져오거나 이미지 목록을 찾는 데 실패했습니다. 😥\n(서버 로그를 확인해주세요)")
                return

            image_paths = []
            async with aiohttp.ClientSession() as session:
                tasks = [self.cog.download_image(session, url) for url in details['images']]
                download_results = await asyncio.gather(*tasks)
                image_paths = [path for path in download_results if path]

            if not image_paths:
                await interaction.edit_original_response(content="이미지를 다운로드하는 데 실패했습니다. 😥")
                return
        
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

        image_view = DcconImageView(
            cog=self.cog,
            title=details['info']['title'],
            image_urls=details['images'],
            image_paths=image_paths,
            author=interaction.user
        )
        
        first_image_path = image_paths[0]
        file = discord.File(first_image_path, filename=os.path.basename(first_image_path))
        embed = image_view.create_embed()
        embed.set_image(url=f"attachment://{os.path.basename(first_image_path)}")

        await interaction.edit_original_response(
            content=f"**{details['info']['title']}** 디시콘을 표시합니다. (총 {len(image_paths)}개)",
            embed=embed,
            view=image_view,
            attachments=[file]
        )
        image_view.message = await interaction.original_response()

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

    async def download_image(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """주어진 URL에서 이미지를 다운로드하고, APNG인 경우 GIF로 변환합니다."""
        print(f"\n--- 🖼️ 이미지 다운로드 시작 ---")
        print(f"URL: {url}")
        
        temp_filepath = os.path.join(self.temp_dir, f"{uuid.uuid4()}")
        img = None
        
        try:
            # 1. 파일 다운로드
            headers = {'Referer': 'https://m.dcinside.com/'}
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    print(f"--- ❌ 이미지 다운로드 실패 (상태 코드: {response.status}) ---")
                    return None
                
                content_type = response.content_type
                print(f"응답 상태: {response.status}, Content-Type: {content_type}")

                with open(temp_filepath, 'wb') as f:
                    f.write(await response.read())

            # 2. Pillow로 이미지 분석 및 처리
            img = Image.open(temp_filepath)
            
            # APNG인 경우 GIF로 변환
            if hasattr(img, 'n_frames') and img.n_frames > 1:
                print(f"✅ APNG 감지됨 ({img.n_frames} 프레임). GIF로 변환을 시작합니다.")
                final_filepath = temp_filepath + ".gif"
                
                # Pillow의 공식적인 APNG -> GIF 변환 방식 사용
                img.save(final_filepath, 'GIF', save_all=True, append_images=list(ImageSequence.Iterator(img))[1:], loop=0, disposal=2)
                print(f"-> GIF 변환 완료: {final_filepath}")

            # 일반 이미지인 경우 확장자 추가
            else:
                ext = 'png'
                if 'image/gif' in content_type: ext = 'gif'
                elif 'image/jpeg' in content_type: ext = 'jpg'
                final_filepath = temp_filepath + f".{ext}"
                
                # 원본 파일을 그대로 새 이름으로 복사/이동
                # close() 후 rename() 보다 shutil.move가 더 안정적일 수 있음
                # 하지만 핸들을 먼저 닫는 것이 핵심.
                img.close()
                img = None # 핸들이 닫혔음을 명시
                os.rename(temp_filepath, final_filepath)

            print(f"최종 저장된 파일 경로: {final_filepath}")
            print(f"파일 크기: {os.path.getsize(final_filepath)} bytes")
            print(f"--- 🖼️ 이미지 다운로드 성공 ---")
            return final_filepath

        except Exception as e:
            print(f"--- ❌ 이미지 다운로드/변환 중 오류: {e} ---")
            return None
        
        finally:
            # 3. 모든 작업 후, 열려있는 핸들이 있다면 닫고 원본 임시 파일을 삭제
            if img:
                img.close()
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)

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
            embed.add_field(name=f"{i+1}. {result['name']}", value=f"패키지 ID: {result['package_idx']}", inline=False)
        
        # 첫 번째 결과의 미리보기 이미지를 썸네일로 설정 (이제는 로컬 파일로)
        temp_image_path = None
        if search_results and search_results[0].get('thumbnail_url'):
            async with aiohttp.ClientSession() as session:
                temp_image_path = await self.download_image(session, search_results[0]['thumbnail_url'])

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
        
        # 첫 번째 즐겨찾기 표시
        first_fav = favorites[0]
        filepath = first_fav['local_path']
        filename = os.path.basename(filepath)
        
        try:
            with open(filepath, 'rb') as f:
                file = discord.File(f, filename=filename)
                embed = view.create_embed()
                embed.set_image(url=f"attachment://{filename}")
                message = await interaction.followup.send(embed=embed, view=view, file=file, ephemeral=True)
                view.message = message
        except FileNotFoundError:
            await interaction.followup.send(f"오류: 즐겨찾기 파일을 찾을 수 없습니다. ({filepath})", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Dccon(bot)) 