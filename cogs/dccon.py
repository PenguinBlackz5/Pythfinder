import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
import re
import subprocess
from bs4 import BeautifulSoup

# DcconScraper 클래스를 디스코드 봇에 맞게 일부 수정합니다.
# print() 대신 로깅이나 다른 방식을 사용하는 것이 좋으나, 여기서는 간단하게 유지합니다.
class DcconScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        self.csrf_token = None
        self.base_url = "https://m.dcinside.com"

    def get_app_id(self):
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

    def search(self, keyword):
        search_url = f"{self.base_url}/dcconShop/dcconList"
        params = {"s_type": "title", "s_word": keyword}
        try:
            response = self.session.get(search_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            csrf_tag = soup.find('meta', {'name': 'csrf-token'})
            if csrf_tag:
                self.csrf_token = csrf_tag.get('content')
            
            first_result = soup.find('a', href=re.compile(r"viewDcconDetail\('\d+'"))
            if first_result:
                match = re.search(r"viewDcconDetail\('(\d+)'", first_result['href'])
                if match:
                    return match.group(1)
        except requests.exceptions.RequestException as e:
            print(f"❌ 검색 중 오류 발생: {e}")
        return None

    def get_details(self, package_idx):
        if not self.csrf_token:
            # 검색을 통해 토큰을 자동으로 가져오도록 시도
            self.search("initial_search") # 아무 키워드로 검색하여 토큰 확보
            if not self.csrf_token:
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

            # 디시콘 정보 추출
            info = {}
            title_tag = soup.select_one('div.top-tit > span.name')
            info['title'] = title_tag.text.strip() if title_tag else '이름 없음'
            
            maker_tag = soup.select_one('div.make > span.by')
            info['maker'] = maker_tag.text.strip() if maker_tag else '정보 없음'

            desc_tag = soup.select_one('div.txt')
            info['description'] = desc_tag.text.strip() if desc_tag else '설명 없음'
            
            main_img_tag = soup.select_one('div.thum-img > img')
            info['main_img_url'] = main_img_tag['src'] if main_img_tag else None

            # 개별 이미지 URL 추출
            image_urls = []
            img_tags = soup.select('ul.dccon-img-lst img')
            for img in img_tags:
                if src := img.get('src'):
                    image_urls.append(src)
            
            if not image_urls:
                return None

            return {'info': info, 'images': image_urls}

        except requests.exceptions.RequestException as e:
            print(f"❌ 상세 정보 요청 중 오류 발생: {e}")
        return None


class DcconView(discord.ui.View):
    def __init__(self, title, images, author):
        super().__init__(timeout=300)
        self.title = title
        self.images = images
        self.author = author
        self.current_page = 0

        self.update_buttons()

    def update_embed(self):
        embed = discord.Embed(
            title=f"디시콘: {self.title}",
            description=f"페이지: {self.current_page + 1}/{len(self.images)}",
            color=discord.Color.blue()
        )
        embed.set_image(url=self.images[self.current_page])
        embed.set_footer(text=f"요청자: {self.author.display_name}")
        return embed

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.images) - 1

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("명령어를 실행한 사용자만 조작할 수 있습니다.", ephemeral=True)
            return
        
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.update_embed(), view=self)

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("명령어를 실행한 사용자만 조작할 수 있습니다.", ephemeral=True)
            return
            
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.update_embed(), view=self)


class Dccon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scraper = DcconScraper()

    @app_commands.command(name="디시콘", description="키워드로 디시콘을 검색하고 결과를 보여줍니다.")
    @app_commands.describe(keyword="검색할 디시콘의 이름 (예: 만두콘)")
    async def dccon_search(self, interaction: discord.Interaction, keyword: str):
        await interaction.response.defer(ephemeral=False)

        package_id = self.scraper.search(keyword)
        if not package_id:
            await interaction.followup.send(f"'{keyword}'에 대한 디시콘을 찾을 수 없어요. 😥")
            return

        details = self.scraper.get_details(package_id)
        if not details or not details['images']:
            await interaction.followup.send("디시콘의 상세 정보를 가져오는 데 실패했어요. 😥")
            return

        info = details['info']
        images = details['images']

        # 초기 임베드 생성
        embed = discord.Embed(
            title=f"🔎 디시콘 검색 결과",
            description=f"**{info['title']}**",
            color=discord.Color.green()
        )
        embed.add_field(name="제작자", value=info['maker'], inline=True)
        embed.set_thumbnail(url=info['main_img_url'])
        
        # 첫 번째 이미지를 보여주기 위한 뷰 생성
        view = DcconView(title=info['title'], images=images, author=interaction.user)
        initial_embed = view.update_embed()

        await interaction.followup.send(
            content=f"**'{keyword}'** (으)로 검색한 결과입니다!", 
            embed=initial_embed, 
            view=view
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Dccon(bot)) 