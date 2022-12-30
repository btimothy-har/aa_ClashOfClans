import coc
import discord
import time
import pytz
import random

from aa_resourcecog.file_functions import get_current_season, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select, paginate_embed

class MemberIneligible(Exception):
    def __init__(self,message):
        self.message = message

class aChallengePass():
    def __init__(self,ctx,member):
        self.member = member
        self.season = season

        self.track = None
        self.points = 0
        self.tokens = 0

        self.active_challenge = None
        self.challenges = []

    @classmethod
    async def create(cls,ctx,member):

        if not member.is_member or member.town_hall.level < 11:
            raise MemberIneligible
            return None

        if member.tag in list(ctx.bot.pass_cache.keys()):
            self = ctx.bot.pass_cache[member.tag]
        else:
            self = aChallengePass(ctx,member)

            passJson = await data_file_handler(ctx,'challengepass',self.member.tag)

            if passJson:
                self.track = passJson.get('track',None)
                self.points = passJson.get('points',0)
                self.tokens = passJson.get('tokens',0)
                self.active_challenge = aPassChallenge(ctx,self,passJson.get('active_challenge',None))
                if not self.active_challenge.status:
                    self.active_challenge = None

                self.challenges = [aPassChallenge(ctx,self,challenge) for challenge in passJson.get('challenges',[])]

        return self

    async def to_embed(self,ctx):
        challenge_message = ""
        if not self.track:
            challenge_message += f"You haven't started a Challenge Pass on this account."
            challenge_message += f"\n\nTo get started, click on <:challengepass:1054997157654036561>."

        else:
            challenge_message += f"**Your Pass Track**: {self.track}"
            challenge_message += f"\n\n__Your Pass Stats:__"
            challenge_message += f"\n> Pass Completion: {self.points:,} / 10,000"
            challenge_message += f"\n> Pass Tokens: {self.tokens}"
            challenge_message += f"\n> Completed: {len([c for c in self.challenges if c.status=='Completed'])}"
            challenge_message += f"\n> Missed: {len([c for c in self.challenges if c.status=='Missed'])}"
            challenge_message += f"\n> Trashed: {len([c for c in self.challenges if c.status=='Trashed'])}"

        challengeEmbed = await clash_embed(ctx,
            title=f"**AriX Challenge Pass: {self.member.name}** ({self.member.tag})",
            message=challenge_message)

        return challengeEmbed

    async def update_pass(self,ctx,action):
        if action not in ['update','trash']:
            return

        if action == 'update' and self.active_challenge:
            self.active_challenge.update_challenge(ctx)

            if self.active_challenge.status == 'Missed':
                self.challenges.append(self.active_challenge)
                self.active_challenge = None
                return

            if self.active_challenge.status == "Completed":
                self.points += self.active_challenge.reward
                if self.active_challenge.token_rew:
                    self.tokens += 1

                self.challenges.append(self.active_challenge)
                self.active_challenge = None
                return

        if action == 'trash' and self.active_challenge:
            if self.tokens == 0:
                return

            self.tokens -= 1
            self.active_challenge.trash_challenge(ctx)
            self.challenges.append(self.active_challenge)
            self.active_challenge = None
            return

        if not self.active_challenge:
            self.active_challenge = aPassChallenge.new_challenge(ctx,self)
            return

    async def save_to_json(self,ctx):
        passJson = {
            'track': self.track,
            'points': self.points,
            'tokens': self.tokens,
            'challenges': [c.to_json() for c in self.challenges]
            }

        await data_file_handler(
            ctx=ctx,
            file='challengepass',
            tag=self.member.tag,
            new_data=passJson)


class aPassChallenge():
    def __init__(self,ctx,challenge_pass,inputJson=None):
        self.cpass = challenge_pass

        self.status = inputJson.get('status',None)
        self.task = inputJson.get('task',None)
        self.target = inputJson.get('target',None)

        self.current_score = inputJson.get('current_score',0)
        self.baseline = inputJson.get('baseline',0)
        self.max_score = inputJson.get('max_score',0)

        self.start_time = inputJson.get('start_time',0)
        self.end_time = inputJson.get('end_time',0)

        self.reward = inputJson.get('reward',0)
        self.token_rew = inputJson.get('token_rew',False)

        self.description = inputJson.get('description',"")

    def to_json(self):
        challengeJson = {
            'status': self.status,
            'task': self.task,
            'target': self.target,
            'current_score': self.current_score,
            'baseline': self.baseline,
            'max_score': self.max_score,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'reward': self.reward,
            'token_rew': self.token_rew,
            'description': self.description
            }
        return challengeJson

    @classmethod
    def new_challenge(cls,ctx,challenge_pass):
        self = aPassChallenge(ctx,challenge_pass)

        self.start_time = time.time()

        durationMultiplier = {
            1: 1,
            2: 1.5,
            3: 2,
            4: 2.5,
            5: 3,
            6: 3.5,
            7: 4
            }

        common_track = ['donations','destroyTarget','builderBase']
        war_track = ['warStars','trophies','winBattles','boostTroop']
        farm_track = ['loot','upgradeHero','clearObstacles','seasonPoints','collectTreasury']

        eligible_challenges = common_track

        if self.cpass.track == "war":
            eligible_challenges += war_track
        if self.cpass.track == "farm":
            eligible_challenges += farm_track

        self.reward = random.choice(range(350,550))
        self.token_rew = False

        while True:

            self.task = random.choice(eligible_challenges)

            if self.task == 'donations':
                available_duration = [1,2,3]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                target_score = {
                    'any': 100,
                    'spells': 10}
                if self.cpass.member.town_hall.level >= 12:
                    target_score['siege_machines'] = 3

                self.target = random.choice(list(target_score.keys()))
                self.max_score = target_score[self.target]

                self.baseline = [a.value for a in self.cpass.member.p.achievements if a.name == donationsAchievement[self.target]][0]
                break


            if self.task == 'destroyTarget':
                available_duration = [1,2,3]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                target_score = {
                    'Builder Huts': 10,
                    'Mortars': 8,
                    'Walls': 200,
                    'Townhalls': 2}
                if self.cpass.member.town_hall.level >= 8:
                    target_score['X-Bows'] = 8
                if self.cpass.member.town_hall.level >= 9:
                    target_score['Inferno Towers'] = 6
                if self.cpass.member.town_hall.level >= 10:
                    target_score['Eagle Artilleries'] = 2
                if self.cpass.member.town_hall.level >= 12:
                    target_score['Scattershots'] = 4

                if self.cpass.member.town_hall.level >= 11:
                    target_score['Weaponized Townhalls'] = 2
                if self.cpass.member.town_hall.level >= 13:
                    target_score['Weaponized Builder Huts'] = 10
                if self.cpass.member.town_hall.level >= 14:
                    target_score['Spell Towers'] = 4
                    target_score['Monoliths'] = 2

                self.target = random.choice(list(target_score.keys()))
                self.max_score = target_score[self.target]

                self.baseline = [a.value for a in self.cpass.member.p.achievements if a.name == destroyTargetAchievement[self.target]][0]
                break


            if self.task == 'builderBase':
                if self.cpass.member.builder_hall <= 1:
                    continue
                available_duration = [1,2,3]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                self.max_score = 3
                self.baseline = [a.value for a in self.cpass.member.p.achievements if a.name == "Un-Build It"][0]
                break


            if self.task == 'warStars':
                ch1 = False
                ch2 = False
                ch3 = False
                wm = [wm for wm in self.cpass.member.home_clan.current_war.clan.members if wm.tag == self.cpass.member.tag]

                if self.cpass.member.home_clan.current_war.state == 'inWar':
                    ch1 = True
                if len(wm) == 1:
                    ch2 = True
                if self.cpass.member.home_clan.current_war.attacks_per_member - len(wm[0].attacks) >= 1:
                    ch3 = True

                if ch1 and ch2 and ch3:
                    available_duration = [1]
                    duration = random.choice(available_duration)
                    self.end_time = self.start_time + (duration * 86400)

                    self.max_score = 2
                    self.baseline = self.cpass.member.war_stats.offense_stars
                    break
                else:
                    continue


            if self.task == 'trophies':
                if self.cpass.member.league.name in ['Legend League','Titan League I']:
                    continue

                else:
                    available_duration = [1,3,5]
                    duration = random.choice(available_duration)
                    self.end_time = self.start_time + (duration * 86400)

                    self.max_score = 60
                    self.baseline = self.cpass.member.trophies
                    break


            if self.task == 'winBattles':
                available_duration = [1,3,5]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                self.max_score = 3
                self.baseline = self.cpass.member.attack_wins.season
                break


            if self.task == 'boostTroop':
                available_duration = [3]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                eligible_targets = []
                for super_troop in coc.SUPER_TROOP_ORDER:
                    super_troop = ctx.bot.coc_client.get_troop(super_troop)

                    if super_troop:
                        player_super_troop = self.cpass.member.p.get_troop(super_troop.name,is_home_troop=True)
                        player_troop = self.cpass.member.p.get_troop(super_troop.original_troop.name,is_home_troop=True)

                        if player_super_troop:
                            continue

                        if player_troop.level > super_troop.min_original_level:
                            eligible_targets.append(super_troop.name)

                if len(eligible_targets) == 0:
                    continue

                self.target = random.choice(eligible_targets)
                self.max_score = 1
                self.baseline = 0
                break


            if self.task == 'loot':
                available_duration = [1,3,5]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                eligible_targets = []
                if self.cpass.member.loot_gold.lastupdate <= 1900000000:
                    eligible_targets.append('Gold')
                if self.cpass.member.loot_elixir.lastupdate <= 1900000000:
                    eligible_targets.append('Elixir')
                if self.cpass.member.loot_darkelixir.lastupdate <= 1900000000:
                    eligible_targets.append('Dark Elixir')

                self.target = random.choice(eligible_targets)

                if self.target in ['Dark Elixir']:
                    self.max_score = 50000
                    self.baseline = self.cpass.member.loot_darkelixir.lastupdate

                if self.target in ['Gold']:
                    self.max_score = 3000000
                    self.baseline = self.cpass.member.loot_gold.lastupdate

                if self.target in ['Elixir']:
                    self.max_score = 3000000
                    self.baseline = self.cpass.member.loot_elixir.lastupdate
                break


            if self.task == 'upgradeHero':
                available_duration = [7]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                eligible_targets = []
                for hero in coc.HERO_ORDER:
                    hero = self.cpass.member.p.get_hero(hero)

                    if hero and hero.village == 'home':
                        if not hero.is_max_for_townhall:
                            eligible_targets.append(hero)

                self.target = random.choice(eligible_targets)

                self.max_score = 1
                self.baseline = self.target.level
                self.target = self.target.name
                break


            if self.task == 'clearObstacles':
                available_duration = [1,3,5]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                self.max_score = 10
                self.baseline = [a.value for a in self.cpass.member.p.achievements if a.name == "Nice and Tidy"][0]
                break


            if self.task == 'seasonPoints':
                available_duration = [1,3,5]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                self.max_score = 60
                self.baseline = [a.value for a in self.cpass.member.p.achievements if a.name == "Well Seasoned"][0]
                break


            if self.task == 'collectTreasury':
                available_duration = [1,3,5]
                duration = random.choice(available_duration)
                self.end_time = self.start_time + (duration * 86400)

                self.max_score = 500000
                self.baseline = [a.value for a in self.cpass.member.p.achievements if a.name == "Clan War Wealth"][0]
                break


        token_chance = random.choice(range(1,11))
        if token_chance <= duration:
            self.token_rew = True

        self.status = "In Progress"
        self.max_score = self.max_score * durationMultiplier[duration]
        self.reward = self.reward * durationMultiplier[duration]

        if self.task == 'donations':
            if self.target == 'any':
                self.description = f"Donate {self.max_score} reinforcements (Troops, Spells or Siege Machines) to your Clan Mates."
            if self.target == 'spells':
                self.description = f"Donate {self.max_score} spell storage capacity worth of Spells to your Clan Mates."
            if self.target == 'siege_machines':
                self.description = f"Donate {self.max_score} Siege Machines to your Clan Mates."

        if self.task == 'destroyTarget':
            self.description = f"Destroy {self.max_score} {self.target} in multiplayer battles."

        if self.task == 'builderBase':
            self.description = f"Win {self.max_score} Builder Base Battles."

        if self.task == 'warStars':
            self.description = f"Earn {self.max_score} Stars in Clan War Attacks."

        if self.task == 'trophies':
            self.description = f"Earn {self.max_score} Trophies from multiplayer battles."

        if self.task == 'winBattles':
            self.description = f"Win {self.max_score} Multiplayer Battles."

        if self.task == 'boostTroop':
            self.description = f"Boost {self.target} once."

        if self.task == 'loot':
            self.description = f"Farm {self.max_score:,} {self.target} from multiplayer battles."

        if self.task == 'upgradeHero':
            self.description = f"Upgrade your {self.target} to level {self.baseline + self.max_score}."

        if self.task == 'clearObstacles':
            self.description = f"Clear {self.max_score} Obstacles from your Home Village or Builder Base."

        if self.task == 'seasonPoints':
            self.description = f"Complete {self.max_score} points of challenges in the Season Pass."

        if self.task == 'collectTreasury':
            self.description = f"Collect {self.max_score:,} Gold from your Clan Castle Treasury."

        return self


    def update_challenge(self,ctx):
        new_score = 0

        if time.time() > self.end_time:
            self.status = 'Missed'
            return

        if self.task == 'donations':
            new_score = [a.value for a in self.cpass.member.p.achievements if a.name == donationsAchievement[self.target]][0]

        if self.task == 'destroyTarget':
            new_score = [a.value for a in self.cpass.member.p.achievements if a.name == destroyTargetAchievement[self.target]][0]

        if self.task == 'builderBase':
            new_score = [a.value for a in self.cpass.member.p.achievements if a.name == "Un-Build It"][0]

        if self.task == 'warStars':
            new_score = self.cpass.member.war_stats.offense_stars

        if self.task == 'trophies':
            new_score = self.cpass.member.trophies

        if self.task == 'winBattles':
            new_score = self.cpass.member.attack_wins.season

        if self.task == 'boostTroop':
            s_troop = self.cpass.member.p.get_troop(self.target,is_home_troop=True)
            if s_troop:
                new_score = 1

        if self.task == 'loot':
            if self.target in ['Dark Elixir']:
                new_score = self.cpass.member.loot_darkelixir.lastupdate

            if self.target in ['Gold']:
                new_score = self.cpass.member.loot_gold.lastupdate

            if self.target in ['Elixir']:
                new_score = self.cpass.member.loot_elixir.lastupdate

        if self.task == 'upgradeHero':
            s_hero = self.cpass.member.p.get_hero(self.target)
            new_score = s_hero.level

        if self.task == 'clearObstacles':
            new_score = [a.value for a in self.cpass.member.p.achievements if a.name == "Nice and Tidy"][0]

        if self.task == 'seasonPoints':
            new_score = [a.value for a in self.cpass.member.p.achievements if a.name == "Well Seasoned"][0]

        if self.task == 'collectTreasury':
            new_score = [a.value for a in self.cpass.member.p.achievements if a.name == "Clan War Wealth"][0]

        self.current_score += (new_score - self.baseline)
        self.baseline = new_score

        if self.current_score >= self.max_score:
            self.status = "Completed"


    def trash_challenge(self,ctx):
        self.status = "Trashed"
