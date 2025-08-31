import discord
from discord.ext import commands
import random
import asyncio
from main import update_balance
from database_manager import execute_query

# 가챠 캐릭터 데이터 템플릿
GACHA_CHARACTERS = {
    3: [  # 3성
        {
            "name": "헬창 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5RxoGbwAMDCCA?format=png",
            "description": "봐주지 않는다"
        },
        {
            "name": "개씹상남자 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5SlLlbIAAMhLv?format=png",
            "description": "도망쳐서 도착한 곳에, 낙원이란 있을 수 없는 거야"
        },
        {
            "name": "메랑 뉴타입각성 최종형",
            "image_url": "https://pbs.twimg.com/media/Gt5UDsQbMAAwyhY?format=png",
            "description": "뉴 건담은 겉치레가 아니야!"
        },
        {
            "name": "메랑 아뢰야식 리미터 해제",
            "image_url": "https://pbs.twimg.com/media/GuHSG_KWQAA96AL?format=png",
            "description": "쓸데없는 사슬은 모두 풀어줄테니까, 보여줘봐. 너의 힘을..."
        },
        {
            "name": "메순이",
            "image_url": "https://pbs.twimg.com/media/GuHYLpcXwAAXwUX?format=png",
            "description": "마침내."
        },
        {
            "name": "메스가키 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHaZ7mXkAAKJUA?format=png",
            "description": "(자료 없음)"
        },
        {
            "name": "순진한메랑님",
            "image_url": "https://pbs.twimg.com/media/GuHbsYyWAAADEv3?format=png",
            "description": "근-본"
        },
        # 3성 캐릭터를 여기에 추가하세요.
    ],
    2: [  # 2성
        {
            "name": "텟카이 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5TPoFWEAA1PPE?format=png",
            "description": "철 괴"
        },
        {
            "name": "유통이 형 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5GJIZX0AAhIia?format=png",
            "description": "유통아~ 앞으로도 건강하고 씩씩하게 자라야 한다~"
        },
        {
            "name": "유잼 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5RAbibwAQ1ZCI?format=png",
            "description": "네가 유잼이라면 난 노잼이란 말인가?"
        },
        {
            "name": "산데비스탄 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5RjkyXEAArd6E?format=png",
            "description": "기초적인 임플란트다"
        },
        {
            "name": "마크 메랑 인간형",
            "image_url": "https://pbs.twimg.com/media/Gt5Rs4cXAAAoARF?format=png",
            "description": "T"
        },
        {
            "name": "뉴타입 각성 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5SUW3XYAAgaL2?format=png",
            "description": "너는 뉴타입인거냐?!!"
        },
        {
            "name": "드리프트 선수 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5SyqvWIAAscck?format=png",
            "description": "간다~~~~드래프트!!!!!!!!!!!"
        },
        {
            "name": "등교 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5S73zWUAEgIfr?format=png",
            "description": "가지 않으면… 지각하게되거든……"
        },
        {
            "name": "쫄쫄 굶은 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5T-CObwAEOFCI?format=png",
            "description": "토스뱅크 1001-3805-6912"
        },
        {
            "name": "한껏 진지해진 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5UpeHXcAAwOY0?format=png",
            "description": "(엄격) (근엄) (진지)"
        },
        {
            "name": "안순진한메랑님",
            "image_url": "https://pbs.twimg.com/media/GuHYZ4pXsAA2e__?format=png",
            "description": "아 너무 무섭다;;"
        },
        {
            "name": "운전병 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHZfGcWYAApJyO?format=png",
            "description": "부릉부릉~~"
        },
        {
            "name": "머리 개망한 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHb3wTXYAAg-VF?format=png",
            "description": "어~ 그래 (사실 안 그럼)"
        },
        {
            "name": "포유나 중독 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHcRtVXYAE6NHA?format=png",
            "description": "@포유나\n해보자 해보자 해보자\n후회하지 말고오"
        },
        {
            "name": "스탠드 술사 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHcfvOWMAAx2aj?format=png",
            "description": "히야~ 내가 9초나 멈출 수 있다"
        },
        # 2성 캐릭터를 여기에 추가하세요.
    ],
    1: [  # 1성
        {
            "name": "메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5Tz5tXMAAxmft?format=png",
            "description": "그냥 메랑"
        },
        {
            "name": "메랑 '대의를 위한 희생'",
            "image_url": "https://pbs.twimg.com/media/Gt5QxzcWgAADBLG?format=png",
            "description": "기억할게!"
        },
        {
            "name": "공고생 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5RSlqWwAAV9kA?format=png",
            "description": "담양공고의 자랑"
        },
        {
            "name": "폐급 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5RbjXXEAABV37?format=png",
            "description": "말년 이등병"
        },
        {
            "name": "미니카 덕후 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5R9t1XYAAyLxx?format=png",
            "description": "이게 야스지 ㅋㅋ"
        },
        {
            "name": "가면라이더 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5TULhbwAAXL5z?format=png",
            "description": "메랑 이대로 가면..."
        },
        {
            "name": "베이시스트 메랑",
            "image_url": "https://pbs.twimg.com/media/Gt5Tgc8XsAASaRk?format=png",
            "description": "왜 연주를 해도 아무 소리도 안나죠?"
        },
        {
            "name": "밥먹는 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHYsKiW8AAcRCP?format=png",
            "description": "음... 우마이..."
        },
        {
            "name": "울보 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHaAABX0AASvVE?format=png",
            "description": "ㅠㅠㅠㅠㅠㅠㅠㅠㅠㅠㅠㅠㅠㅠ"
        },
        {
            "name": "감자튀김 과다복용 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHaslKXgAAgIDc?format=png",
            "description": "실례가 안된다면 감튀 하나면 사주십쇼"
        },
        {
            "name": "어쩔티비 시전한 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHbA5qXUAAyyJS?format=png",
            "description": "어쩔티비"
        },
        {
            "name": "앗가이 메랑",
            "image_url": "https://pbs.twimg.com/media/GuHcFp8WoAAOshb?format=png",
            "description": "무슨 설명을 써야 할지 모르겠는데 아무튼 양산형이라 함 ㅇㅇ"
        },
        # 1성 캐릭터를 여기에 추가하세요.
    ]
}
# ★ 캐릭터를 추가하려면 위 딕셔너리에 원하는 성급(1,2,3)에 캐릭터 dict를 append 하세요.

# 성급별 확률
GACHA_RATES = [
    (3, 0.03),   # 3성 3%
    (2, 0.185),  # 2성 18.5%
    (1, 0.785),  # 1성 78.5%
]

# 연출 텍스트 및 대기 시간
GACHA_EFFECTS = {
    3: ([
        "✨    📘    ✨\n조용한 바람이 분다...",
        "✨✨  📒  ✨✨\n반짝이는 빛이 감긴다...?",
        "✨✨✨ 📓 ✨✨✨\n일렁이는 색채가 펼쳐진다...!"
    ], 1),
    2: ([
        "✨    📘    ✨\n조용한 바람이 분다...",
        "✨✨  📒  ✨✨\n반짝이는 빛이 감긴다...?",
    ], 1),
    1: ("✨    📘    ✨\n조용한 바람이 분다...", 1),
}

class GachaCollectionDropdown(discord.ui.View):
    def __init__(self, characters, user_id):
        super().__init__(timeout=120)
        self.characters = characters
        self.user_id = user_id
        self.add_item(GachaCharacterSelect(characters))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        # 메시지 비활성화: 메시지 객체가 있으면 수정 가능, 없으면 무시
        # (실제 메시지 객체를 저장하려면 View에 message 속성 추가 필요)

class GachaCharacterSelect(discord.ui.Select):
    def __init__(self, characters):
        options = [
            discord.SelectOption(
                label=f"{char['character_name']} ({'★'*char['star']}) x{char['quantity']}",
                value=str(idx)
            ) for idx, char in enumerate(characters)
        ]
        super().__init__(placeholder="캐릭터를 선택하세요", min_values=1, max_values=1, options=options)
        self.characters = characters

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        char = self.characters[idx]
        embed = discord.Embed(
            title=f"{'★'*char['star']} {char['character_name']}",
            description=f"보유 수량: {char['quantity']}",
            color=0xFFD700 if char['star'] == 3 else (0x7FDBFF if char['star'] == 2 else 0xAAAAAA)
        )
        embed.set_image(url=char['image_url'])
        embed.set_footer(text="아래 버튼으로 목록으로 돌아갈 수 있습니다.")
        back_view = GachaBackToListViewDropdown(self.characters, interaction.user.id)
        try:
            await interaction.response.edit_message(embed=embed, view=back_view)
        except Exception:
            await interaction.followup.send(embed=embed, view=back_view, ephemeral=True)

class GachaBackToListViewDropdown(discord.ui.View):
    def __init__(self, characters, user_id):
        super().__init__(timeout=120)
        self.characters = characters
        self.user_id = user_id
        self.add_item(GachaBackButtonDropdown())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

class GachaBackButtonDropdown(discord.ui.Button):
    def __init__(self):
        super().__init__(label="목록으로", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: GachaBackToListViewDropdown = self.view
        collection_view = GachaCollectionDropdown(view.characters, view.user_id)
        embed = discord.Embed(
            title="📜 모집 현황",
            description="보유한 캐릭터를 선택하면 이미지를 볼 수 있습니다.",
            color=0x00ffcc
        )
        for char in view.characters:
            embed.add_field(
                name=f"{'★'*char['star']} {char['character_name']}",
                value=f"수량: {char['quantity']}",
                inline=False
            )
        try:
            await interaction.response.edit_message(embed=embed, view=collection_view)
        except Exception:
            await interaction.followup.send(embed=embed, view=collection_view, ephemeral=True)

class Gacha(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="가챠", description="10원을 사용해 캐릭터를 뽑습니다.")
    async def gacha(self, ctx: commands.Context):
        user_id = ctx.author.id
        gacha_cost = 10

        # 돈 인출
        try:
            if not await update_balance(user_id, -gacha_cost):
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description="보유 금액이 부족합니다!",
                    color=0xff0000
                )
                if isinstance(ctx, discord.Interaction):
                    return await ctx.response.send_message(embed=error_embed, ephemeral=True)
                return await ctx.send(embed=error_embed)
        except Exception as e:
            print(f"가챠 금액 인출 오류: {e}")
            error_embed = discord.Embed(
                title="❌ 오류",
                description="가챠 금액 인출 중 오류가 발생했습니다.",
                color=0xff0000
            )
            if isinstance(ctx, discord.Interaction):
                return await ctx.response.send_message(embed=error_embed, ephemeral=True)
            return await ctx.send(embed=error_embed)

        # 확률에 따라 성급 결정
        rand = random.random()
        cumulative = 0
        star = 1
        for s, rate in GACHA_RATES:
            cumulative += rate
            if rand < cumulative:
                star = s
                break

        # 캐릭터 랜덤 선택
        char = random.choice(GACHA_CHARACTERS[star])

        # DB에 캐릭터 보유 정보 upsert
        upsert_query = """
            INSERT INTO user_gacha_characters (user_id, character_name, star, image_url, quantity)
            VALUES ($1, $2, $3, $4, 1)
            ON CONFLICT (user_id, character_name, star, image_url)
            DO UPDATE SET quantity = user_gacha_characters.quantity + 1;
        """
        try:
            await execute_query(upsert_query, (user_id, char['name'], star, char['image_url']))
        except Exception as e:
            print(f"가챠 캐릭터 DB 저장 오류: {e}")

        # 연출
        effect_text, effect_sec = GACHA_EFFECTS[star]
        if isinstance(effect_text, list):
            for text in effect_text:
                embed = discord.Embed(
                    title="가챠 결과...",
                    description=text,
                    color=0xFFD700 if star == 3 else (0x7FDBFF if star == 2 else 0xAAAAAA)
                )
                if isinstance(ctx, discord.Interaction):
                    await ctx.response.send_message(embed=embed, ephemeral=True)
                else:
                    await ctx.send(embed=embed)
                await asyncio.sleep(effect_sec)
        else:
            embed = discord.Embed(
                title="가챠 결과...",
                description=effect_text,
                color=0xFFD700 if star == 3 else (0x7FDBFF if star == 2 else 0xAAAAAA)
            )
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            await asyncio.sleep(effect_sec)

        # 남은 돈 조회
        try:
            result = await execute_query('SELECT balance FROM user_balance WHERE user_id = $1', (user_id,))
            money = result[0]['balance'] if result else 0
        except Exception as e:
            print(f"잔액 조회 오류: {e}")
            money = "?"

        # 결과 임베드
        result_embed = discord.Embed(
            title=f"{'★'*star} {char['name']}",
            description=f"{char['description']}",
            color=0xFFD700 if star == 3 else (0x7FDBFF if star == 2 else 0xAAAAAA)
        )
        result_embed.set_image(url=char['image_url'])
        result_embed.add_field(name="성급", value=f"{'★'*star}", inline=True)
        result_embed.add_field(name="남은 돈", value=f"{money}원", inline=True)
        result_embed.set_footer(text="캐릭터를 더 추가하고 싶다면 GACHA_CHARACTERS에 append 하세요!")

        if isinstance(ctx, discord.Interaction):
            await ctx.followup.send(embed=result_embed, ephemeral=True)
        else:
            await ctx.send(embed=result_embed)

    @commands.hybrid_command(name="모집현황", description="내가 보유한 가챠 캐릭터 목록을 확인합니다.")
    async def gacha_collection(self, ctx: commands.Context):
        user_id = ctx.author.id
        query = """
            SELECT character_name, star, image_url, quantity
            FROM user_gacha_characters
            WHERE user_id = $1
            ORDER BY star DESC, character_name
        """
        try:
            result = await execute_query(query, (user_id,))
        except Exception as e:
            print(f"모집현황 조회 오류: {e}")
            result = []
        if not result:
            embed = discord.Embed(
                title="📜 모집 현황",
                description="아직 보유한 캐릭터가 없습니다. 가챠를 돌려보세요!",
                color=0x00ffcc
            )
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return
        embed = discord.Embed(
            title="📜 모집 현황",
            description="보유한 캐릭터를 선택하면 이미지를 볼 수 있습니다.",
            color=0x00ffcc
        )
        for char in result:
            embed.add_field(
                name=f"{'★'*char['star']} {char['character_name']}",
                value=f"수량: {char['quantity']}",
                inline=False
            )
        view = GachaCollectionDropdown(result, user_id)
        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(Gacha(bot))
