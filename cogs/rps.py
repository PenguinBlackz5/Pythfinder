import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from typing import Dict, Tuple, List, Optional
from Pythfinder import update_balance, check_balance
from database_manager import execute_query


# 게임의 실제 구현부
class RPSGameView(discord.ui.View):
    def __init__(self, bot: commands.Bot,
                 challenger: discord.Member,
                 opponent: discord.Member,
                 interaction: discord.Interaction,
                 bet_amount: int,
                 bet_history: List[Tuple[discord.Member, int, discord.Member]]):
        super().__init__()
        self.bot: commands.Bot = bot
        self.challenger: discord.Member = challenger  # 플레이어 1
        self.opponent: discord.Member = opponent  # 플레이어 2 - 봇이 들어올 수 있음
        self.interaction: discord.Interaction = interaction
        self.init_bet_amount: int = bet_amount  # 최초 베팅 금액
        self.total_bet_amount: int = bet_amount * 2  # 총 베팅 금액 - 기본값은 참가자 두 명의 최초 베팅금
        self.bet_history: List[Tuple[discord.Member, int, discord.Member]] = bet_history  # 전체 베팅 기록
        self.choices: Dict[discord.Member, str] = {}  # 유저들의 선택 기록

        # 봇과 대전할 경우 봇의 선택 처리
        if opponent == bot:
            # bot.user를 서버에서 Member 객체로 변환
            self.opponent = bot.get_guild(interaction.guild.id).get_member(bot.user.id)
            self.choices[self.opponent] = random.choice(['가위', '바위', '보'])
        self.timer_task = None  # 타이머 작업 저장
        self.ready_user = None  # 첫 번째 선택한 사용자
        self.remaining_time = 60  # 타이머 시작 시간 (60초)
        self.bet_message = self.generate_bet_message()

    @discord.ui.button(label="가위 ✌️", style=discord.ButtonStyle.primary)
    async def choose_scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "가위")

    @discord.ui.button(label="바위 ✊", style=discord.ButtonStyle.primary)
    async def choose_rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "바위")

    @discord.ui.button(label="보 ✋", style=discord.ButtonStyle.primary)
    async def choose_paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "보")

    async def record_choice(self, interaction, choice):
        if interaction.user not in [self.challenger, self.opponent]:
            await interaction.response.send_message("이 게임에 참여할 수 없습니다!", ephemeral=True)
            return

        await interaction.response.defer()
        self.choices[interaction.user] = choice

        # 두 플레이어 모두 선택했을 때 게임 결과 처리
        if len(self.choices) == 1:
            self.ready_user = interaction.user
        if len(self.choices) == 2:
            await self.resolve_game()

    def generate_bet_message(self):
        """베팅 기록을 요약하여 생성"""
        # 베팅 기록 집계 (유저별, 타겟별 베팅 금액 합산)
        bet_summary = {}
        for user, amount, target in self.bet_history:
            key = (user, target)
            bet_summary[key] = bet_summary.get(key, 0) + amount
            self.total_bet_amount += amount
            print(f"초기 베팅 금액 합 {self.init_bet_amount * 2}에 {amount} 추가 = {self.total_bet_amount}")

        # 베팅 기록 문자열 생성
        bet_lines = []
        for (user, target), amount in bet_summary.items():
            # 사용자 이름은 그대로 유지
            user_name = user.name if hasattr(user, 'name') else str(user)

            # 봇일 경우 하드코딩된 이름 사용
            if isinstance(target, commands.Bot):
                target_name = "봇"
            else:
                target_name = target.name if hasattr(target, 'name') else str(target)

            bet_lines.append(f"{user_name}님이 {target_name}님에게 💰{amount}원을 베팅했습니다!")

        # 총 베팅 금액 정보 추가
        full_message = (
                f"💰 **총 베팅 금액: {self.total_bet_amount}원**\n"
                f"💰 **최초 참가 금액: {self.init_bet_amount}원**\n"
                f"📜 **베팅 기록:**\n" +
                "\n".join(bet_lines)
        )

        return full_message

    def determine_winner(self, challenger: discord.Member, choice1: str, opponent: discord.Member, choice2: str):
        """게임 결과 판정 및 상금 분배 로직"""
        outcomes = {"가위": "보", "바위": "가위", "보": "바위"}

        # 메인 게임 참가자들의 베팅금
        main_bet_amount = self.init_bet_amount * 2
        # 추가 베팅금 계산
        additional_bet_amount = self.total_bet_amount - main_bet_amount

        # 승리 판정
        if choice1 == choice2:
            # 무승부 처리
            return {
                "winner": None,
                "loser": None,
                "drawn_bet_amount": self.total_bet_amount,
                "additional_bet_amount": 0
            }
        elif outcomes[choice1] == choice2:
            # 사용자 플레이어 승리
            return {
                "winner": challenger,
                "loser": opponent,
                "winner_bet_amount": main_bet_amount,
                "additional_bet_amount": additional_bet_amount
            }
        else:
            # 상대 플레이어 승리
            return {
                "winner": opponent,
                "loser": challenger,
                "winner_bet_amount": main_bet_amount,
                "additional_bet_amount": additional_bet_amount
            }

    async def resolve_game(self):
        # 플레이어들의 선택을 정확히 매칭시켜서 결과를 처리
        challenger_choice = self.choices.get(self.challenger)
        opponent_choice = self.choices.get(self.opponent)
        print(f"{self.challenger}가 {challenger_choice}를 냄\n"
              f"{self.opponent}가 {opponent_choice}를 냄")
        result_details = self.determine_winner(
            self.challenger, challenger_choice,
            self.opponent, opponent_choice
        )

        # 분배 로직
        if result_details["winner"] is None:
            # 무승부 베팅금은 봇에게
            await update_balance(self.bot.user.id, result_details["drawn_bet_amount"])
            result_message = f"{self.challenger.name}({challenger_choice}) vs {self.opponent.name}({opponent_choice}) - 무승부! 총 베팅금은 봇의 통장으로 들어갑니다."
        else:
            # 주 베팅금 승자에게 분배
            winner: discord.Member | None
            loser: discord.Member | None
            winner, loser = result_details["winner"], result_details["loser"]

            print(winner, loser)
            winner_choice = self.choices[winner]
            loser_choice = self.choices[loser]

            # 추가 베팅 처리
            side_bet_distribution = await self.distribute_side_bets(
                winner,
                loser,
                result_details["additional_bet_amount"]
            )

            result_message = (
                f"{winner.name}({winner_choice})가 "
                f"{loser.name}({loser_choice})를 이겼습니다!\n"
                f"{winner.name}님이 {loser.name}님의 {self.init_bet_amount}원을 획득하셨습니다.\n"
                f"{side_bet_distribution}"
            )

        await self.interaction.edit_original_response(content=result_message, view=None)
        await asyncio.sleep(10)
        await self.interaction.delete_original_response()

    async def distribute_side_bets(self, winner, loser, additional_bet_amount):
        """추가 베팅 분배 로직"""
        side_bet_winners = []  # 승리 예측 베팅자
        side_bet_losers = []  # 패배 예측 베팅자
        side_bet_distribution_message = []

        # 메인 게임 참가자의 베팅 제외
        side_bets = [bet for bet in self.bet_history
                     if bet[0] not in [self.challenger, self.opponent]]

        # 베팅 분류
        for user, amount, target in side_bets:
            if target == winner:
                side_bet_winners.append((user, amount))
            else:
                side_bet_losers.append((user, amount))

        # 승리 예측자가 있는 경우에만 분배
        if side_bet_winners:
            total_winner_bet = sum(amount for _, amount in side_bet_winners)

            # 승리 예측자들에게 비례적으로 분배
            for user, amount in side_bet_winners:
                # 각 승리 예측자의 베팅 비율에 따라 추가 베팅금 분배
                proportional_gain = (amount / total_winner_bet) * additional_bet_amount
                total_payout = amount + proportional_gain

                # 사용자 통장에 추가
                await update_balance(user.id, total_payout)

                side_bet_distribution_message.append(
                    f"{user.name}님이 {total_payout}원을 획득하셨습니다!"
                )

        # 패배 예측자들의 베팅금은 몰수
        for user, amount in side_bet_losers:
            side_bet_distribution_message.append(
                f"{user.name}님의 {amount}원 베팅금이 몰수되었습니다."
            )

        return "\n".join(side_bet_distribution_message) if side_bet_distribution_message else ""

    async def on_timeout(self):
        """시간이 초과되면 실행"""
        try:
            await self.interaction.edit_original_response(
                content=f"⏳ 선택 시간이 만료되었습니다! {self.challenger.name}님의 가위바위보 게임이 취소되었습니다.\n베팅 금액이 환불됩니다.",
                view=None  # 버튼 제거
            )

            # 첫 두 명의 참가자 베팅금 환불
            await update_balance(self.challenger.id, self.init_bet_amount)
            if self.opponent == self.bot:
                await update_balance(self.opponent.user.id, self.init_bet_amount)
            else:
                await update_balance(self.opponent.id, self.init_bet_amount)

            # 추가 베팅한 사용자들 환불
            side_bets = [bet for bet in self.bet_history
                         if bet[0] not in [self.challenger, self.opponent]]

            for user, amount, _ in side_bets:
                await update_balance(user.id, amount)

            await asyncio.sleep(5)
            await self.interaction.delete_original_response()

        except discord.NotFound:
            pass  # 메시지가 이미 삭제되었거나 찾을 수 없음

    async def start_timer(self):
        """타이머를 1초마다 업데이트"""
        while self.remaining_time > 0:
            await asyncio.sleep(1)
            if len(self.choices) == 2:  # 선택이 종료되면 타이머 종료
                break
            self.remaining_time -= 1
            await self.update_message(self.remaining_time)
        if self.remaining_time == 0:  # 타이머가 종료되면 취소 처리
            await self.on_timeout()

    async def update_message(self, remaining_time):
        """남은 시간을 메시지로 업데이트"""
        try:
            # 타이머를 포함한 메시지를 업데이트
            if self.ready_user is not None and self.opponent is not self.bot:
                time_message = (f"⏳ {remaining_time}초 남았습니다! {self.ready_user.name}님이 선택을 기다리는 중...\n"
                                f"{self.bet_message}")
            else:
                time_message = (f"⏳ {remaining_time}초 남았습니다! 선택을 기다리는 중...\n"
                                f"{self.bet_message}")
            await self.interaction.edit_original_response(content=time_message, view=self)
        except discord.NotFound:
            pass

    def start(self):
        """게임 시작"""
        if self.timer_task is None:
            print("[DEBUG] start() 호출됨, 타이머 시작")
            self.timer_task = asyncio.create_task(self.start_timer())
        else:
            print("[DEBUG] start() 이미 실행됨, 무시")


class RockPaperScissorsInfoView(discord.ui.View):
    def __init__(self, bot, challenger, interaction, bet_amount):
        super().__init__()
        self.bot = bot
        self.challenger = challenger  # 게임을 실행한 유저
        self.opponent = None  # 대전 상대방
        self.interaction = interaction
        self.init_bet_amount = bet_amount  # 게임 실행시의 최초 판돈
        self.total_bet_amount = bet_amount
        self.bet_history = []  # 판돈 증가 기록
        self.timer_task = None  # 타이머 업데이트 작업
        self.is_vs_bot = interaction.namespace.vs_bot
        self.remaining_time = 10 if self.is_vs_bot else 30  # 타이머의 시작 시간을 설정 (30초)
        self.bet_message = ""
        self.bet_summary = ""

        # 봇과 대전할 경우 처리
        if interaction.namespace.vs_bot:
            self.opponent = bot  # 봇을 직접 상대로 설정
            self.add_item(IncreaseBetButton(view=self, target=self.challenger))
            self.add_item(IncreaseBetButton(view=self, target=bot))
        else:
            # 일반 대전 시 기존 로직 유지
            self.add_item(JoinGameButton(view=self))
            self.add_item(IncreaseBetButton(view=self, target=self.challenger))

    async def on_timeout(self):
        """시간이 초과되면 실행"""
        try:
            if self.opponent is None:
                # 시간이 지나도 상대가 없으면 메시지를 수정하여 알림
                await self.interaction.edit_original_response(
                    content=f"⏳ 대전 상대를 찾지못했습니다! {self.challenger.name}님의 가위바위보 게임이 취소되었습니다.",
                    view=None  # 버튼 제거
                )
                await asyncio.sleep(5)
                await self.interaction.delete_original_response()

                # 베팅금 환불
                await update_balance(self.challenger.id, self.init_bet_amount)

                # 추가금 환불
                for user, amount, _ in self.bet_history:
                    await update_balance(user.id, amount)
            else:
                # 대전 상대와 게임 시작
                if self.is_vs_bot:
                    await self.interaction.edit_original_response(
                        content=f"{self.challenger.mention} vs 봇! 게임이 시작됩니다!",
                        view=None)
                else:
                    await self.interaction.edit_original_response(
                        content=f"{self.challenger.mention} vs {self.opponent.mention}! 게임이 시작됩니다!",
                        view=None)

                await asyncio.sleep(3)
                if self.timer_task:
                    self.timer_task.cancel()

                game_view = RPSGameView(
                    self.bot,
                    self.challenger,
                    self.opponent if not self.is_vs_bot else self.bot,
                    self.interaction,
                    self.init_bet_amount,
                    self.bet_history
                )
                game_view.start()

                if self.is_vs_bot:
                    await self.interaction.edit_original_response(
                        content=f"{self.challenger.name} vs 봇! 아래 버튼을 눌러 선택하세요!",
                        view=game_view)
                else:
                    await self.interaction.edit_original_response(
                        content=f"{self.challenger.name} vs {self.opponent.name}! 아래 버튼을 눌러 선택하세요!",
                        view=game_view)
        except discord.NotFound:
            pass

    async def start_timer(self):
        """타이머를 1초마다 업데이트"""
        while self.remaining_time > 0:
            await asyncio.sleep(1)
            self.remaining_time -= 1
            await self.update_message(self.remaining_time)

            # 타이머가 완료되면 중단
            if self.remaining_time == 0:
                break

        # 타이머 종료 시 타임아웃 처리
        if self.remaining_time == 0:
            await self.on_timeout()

    async def update_message(self, remaining_time):
        """메시지를 업데이트"""
        try:
            await self.interaction.edit_original_response(
                content=f"💰 베팅 금액: {self.bet_amount}원\n\n"
                        f"{self.bet_message}"
                        f"👤 도전자: {self.challenger.name}\n"
                        f"👥 상대방: {self.opponent.name if self.opponent else '대기 중...'}\n\n"
                        f"⏳ 남은 시간: {remaining_time}초",
                view=self
            )
        except discord.NotFound:
            pass

    def start(self):
        """게임 시작"""
        self.timer_task = asyncio.create_task(self.start_timer())
        asyncio.create_task(self.interaction.edit_original_response(
            content=f"💰 베팅 금액: {self.bet_amount}원\n\n"
                    f"{self.bet_message}"
                    f"👤 도전자: {self.challenger.name}\n"
                    f"👥 상대방: 대기 중...\n\n"
                    f"⏳ 남은 시간: {self.remaining_time}초",
            view=self
        ))


class JoinGameButton(discord.ui.Button):
    """현재 베팅금에 콜 하여 참가하는 버튼입니다."""

    def __init__(self, view: RockPaperScissorsInfoView):
        label = f"💰{view.init_bet_amount}원으로 경기 참가"  # 동적 라벨 설정
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        """버튼 클릭 시 실행되는 함수"""
        view: RockPaperScissorsInfoView = getattr(self, "view", None)

        if view.opponent is not None:
            await interaction.response.send_message("이미 상대가 정해졌습니다!", ephemeral=True)
            return
        if interaction.user == view.challenger:
            await interaction.response.send_message("자기 자신과 대전할 수 없습니다!", ephemeral=True)
            return

        # 잔액 확인
        if not check_balance(interaction.user.id, view.init_bet_amount):
            error_embed = discord.Embed(
                title="❌ 오류",
                description="보유 금액이 부족합니다!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=error_embed)
            await asyncio.sleep(3)
            await interaction.delete_original_response()
            return

        # 잔액 차감
        try:
            if not update_balance(interaction.user.id, -view.init_bet_amount):
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description="베팅금 차감 중 오류가 발생했습니다.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed)
                await asyncio.sleep(3)
                await interaction.delete_original_response()
                return
        except Exception as e:
            print(f"베팅금 차감 중 오류 발생: {e}")
            error_embed = discord.Embed(
                title="❌ 오류",
                description="베팅금 차감 중 오류가 발생했습니다.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            await asyncio.sleep(3)
            await interaction.delete_original_response()
            return

        await interaction.response.defer()

        view.opponent = interaction.user
        view.remaining_time = 30
        view.interaction = interaction
        view.total_bet_amount += view.init_bet_amount

        if view.bet_summary:
            view.bet_message = (
                f"{view.challenger.mention}님과 {view.opponent.mention}님이 💰***{view.total_bet_amount}원***을 걸고 경기를 기다리고 있습니다!\n"
                f"📜 **베팅 기록:**\n{view.bet_summary}"
            )
        else:
            view.bet_message = (
                f"{view.challenger.mention}님과 {view.opponent.mention}님이 💰***{view.total_bet_amount}원***을 걸고 경기를 기다리고 있습니다!"
            )

        await interaction.edit_original_response(view=view)


class BetAmountModal(discord.ui.Modal):
    def __init__(self, view: RockPaperScissorsInfoView, user: discord.Member):
        super().__init__(title="베팅 금액 입력")
        self.view = view
        self.user = user
        self.bet_amount = discord.ui.TextInput(
            label="베팅 금액",
            placeholder="베팅할 금액을 입력하세요",
            required=True,
            min_length=1,
            max_length=10
        )
        self.add_item(self.bet_amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.bet_amount.value)
            if amount <= 0:
                await interaction.response.send_message("베팅 금액은 0보다 커야 합니다!", ephemeral=True)
                return

            # 사용자의 잔액 확인
            balance = await check_balance(self.user.id)
            if balance < amount:
                await interaction.response.send_message("잔액이 부족합니다!", ephemeral=True)
                return

            # 베팅 처리
            view.total_bet_amount += self.increase_amount
            self.view.bet_history.append((self.user, amount, self.view.challenger))
            # 베팅 기록 메시지 변환
            view.bet_summary = "\n".join([
                f"{user.mention}님이 " +
                (f"{view.bot.user.name}님에게" if target == view.bot else f"{target.mention}님에게") +
                f" 💰{amount}원을 추가 베팅했습니다!"
                for user, amount, target in view.bet_history
            ])
            if view.opponent is not None:
                if view.opponent is view.bot:
                    view.bet_message = (
                        f"{view.challenger.mention}님과 봇이 💰***{view.total_bet_amount}원***을 걸고 경기를 기다리고 있습니다!\n"
                        f"📜 **베팅 기록:**\n{view.bet_summary}"
                    )
                else:
                    view.bet_message = (
                        f"{view.challenger.mention}님과 {view.opponent.mention}님이 💰***{view.total_bet_amount}원***을 걸고 경기를 기다리고 있습니다!\n"
                        f"📜 **베팅 기록:**\n{view.bet_summary}"
                    )
            else:
                view.bet_message = (
                    f"{view.challenger.mention}님이 💰***{view.total_bet_amount}원***을 걸고 가위바위보 상대를 찾고 있습니다!\n"
                    f"📜 **베팅 기록:**\n{view.bet_summary}"
                )


        except ValueError:
            await interaction.response.send_message("올바른 숫자를 입력해주세요!", ephemeral=True)


class RockPaperScissors(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command(name="가위바위보", description="가위바위보 상대를 찾습니다.")
        @app_commands.describe(bet_amount="베팅할 금액입니다.\n 대전에 참가하는 상대도 해당 금액만큼 베팅합니다.",
                               vs_bot="봇과 대전할지 여부입니다.")
        async def 가위바위보(
                interaction: discord.Interaction,
                bet_amount: int,
                vs_bot: bool = False
        ):
            # 베팅금 검사
            if bet_amount <= 0:
                await interaction.response.send_message("베팅 금액은 0보다 커야 합니다!", ephemeral=True)
                return

            # 사용자의 잔액 확인
            balance = await check_balance(interaction.user.id, bet_amount)
            if balance < bet_amount:
                await interaction.response.send_message("잔액이 부족합니다!", ephemeral=True)
                return

            # 봇과 대전할 경우
            if vs_bot:
                await update_balance(bot.user.id, -bet_amount)
                game_view = RPSGameView(
                    bot,
                    interaction.user,
                    bot,
                    interaction,
                    bet_amount,
                    []
                )
                game_view.start()
                return

            # 다른 사용자와 대전할 경우
            info_view = RockPaperScissorsInfoView(
                bot,
                interaction.user,
                interaction,
                bet_amount
            )
            info_view.start()


async def setup(bot):
    await bot.add_cog(RockPaperScissors(bot))
