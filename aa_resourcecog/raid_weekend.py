import coc
import discord
import time
import pytz

from numerize import numerize
from itertools import chain
from datetime import datetime

#from .constants import 
from .notes import aNote
from .discordutils import convert_seconds_to_str, clash_embed
from .constants import warTypeGrid, warResultOngoing, warResultEnded
from .file_functions import get_current_season, alliance_file_handler, data_file_handler, eclipse_base_handler

class aRaidWeekend():
    def __init__(self,**kwargs):

        json_data = kwargs.get('json',None)
        game_data = kwargs.get('game',None)
        clan = kwargs.get('clan',None)

        if json_data:
            self.clan_tag = json_data.get('clan_tag',getattr(clan,'tag',None))
            self.clan_name = json_data.get('clan_name',getattr(clan,'name',None))
            self.clan_badge = json_data.get('clan_badge',getattr(clan,'badge',None))
            self.clan_level = json_data.get('clan_level',getattr(clan,'level',None))

            self.state = json_data['state']
            self.start_time = json_data['start_time']
            self.end_time = json_data['end_time']
            self.total_loot = json_data['total_loot']

            self.destroyed_district_count = json_data['districts_destroyed']

            if 'attack_count' in list(json_data.keys()):
                self.attack_count = json_data['attack_count']
            else:
                self.attack_count = json_data['raid_attack_count']

            if 'offensive_reward' in list(json_data.keys()):
                self.offensive_reward = json_data['offensive_reward']
            else:
                self.offensive_reward = json_data.['offense_rewards']

            if 'defensive_reward' in list(json_data.keys()):
                self.defensive_reward = json_data['defensive_reward']
            else:
                self.defensive_reward = json_data.['defense_rewards']

            self.attack_log = [aRaidClan(self,json=attack) for attack in json_data['attack_log']]
            self.defense_log = [aRaidClan(self,json=attack) for attack in json_data['defense_log']]
            self.members = [aRaidMember(self,json=member) for member in json_data['members']]

        if game_data:
            data = game_data

            self.clan_tag = clan.tag
            self.clan_name = clan.name
            self.clan_badge = clan.badge
            self.clan_level = clan.level

            self.state = data.state
            self.start_time = data.start_time.time.timestamp()
            self.end_time = data.end_time.time.timestamp()
            self.total_loot = data.total_loot
            self.attack_count = data.attack_count
            self.destroyed_district_count = data.destroyed_district_count
            self.offensive_reward = data.offensive_reward
            self.defensive_reward = data.defensive_reward

            self.attack_log = [aRaidClan(self,data=attack) for attack in data.attack_log]
            self.defense_log = [aRaidClan(self,data=defe) for defe in data.defense_log]

            self.members = [aRaidMember(self,data=member) for member in data.members]

        self.offense_raids_completed = len([a for a in self.attack_log if a.destroyed_district_count == a.district_count])
        self.defense_raids_completed = len([a for a in self.defense_log if a.destroyed_district_count == a.district_count])

        tag_id = self.clan_tag
        tag_id = tag_id.replace('#','')

        self.raid_id = tag_id + f"{str(int(self.start_time))}"

    @classmethod
    async def get(cls,ctx,**kwargs):
        clan = kwargs.get('clan',None)
        json_data = kwargs.get('json',None)
        raid_id = kwargs.get('raid_id',None)
        z = kwargs.get('z',False)

        if raid_id:
            json_data = await data_file_handler(
                ctx=ctx,
                file='capitalraid',
                tag=raid_id)
        if json_data:
            if z:
                try:
                    self = aRaidWeekend(clan=clan,json=json_data)
                except:
                    return None
            else:
                self = aRaidWeekend(clan=clan,json=json_data)
        elif clan:
            raidloggen = await ctx.bot.coc_client.get_raidlog(clan_tag=clan.tag,page=False,limit=1)
            if len(raidloggen) == 0:
                return None
            self = aRaidWeekend(clan=clan,game=raidloggen[0])
        else:
            return None

        return self

    async def get_results_embed(self,ctx):
        members_ranked = sorted(self.members, key=lambda x: (x.capital_resources_looted),reverse=True)

        rank = 0
        rank_table = f"`{'P':^3}`\u3000`{'Player':^18}`\u3000`{'Looted':^8}`"
        for m in members_ranked[0:5]:
            rank += 1
            rank_table += f"\n`{rank:^3}`\u3000`{m.name:<18}`\u3000`{m.capital_resources_looted:>8,}`"

        raid_end_embed = await clash_embed(ctx=ctx,
            title=f"Raid Weekend Results: {self.clan_name}",
            message=f"\n<:RaidMedals:983374303552753664> **Maximum Reward: {(self.offensive_reward * 6) + self.defensive_reward:,}** <:RaidMedals:983374303552753664>"
                + f"\n\nOffensive Rewards: {(self.offensive_reward * 6):,} <:RaidMedals:983374303552753664>"
                + f"\nDefensive Rewards: {self.defensive_reward:,} <:RaidMedals:983374303552753664>",
            thumbnail=self.clan_badge,
            show_author=False)

        raid_end_embed.add_field(
            name="Start Date",
            value=f"{datetime.fromtimestamp(self.start_time).strftime('%d %b %Y')}",
            inline=True)

        raid_end_embed.add_field(
            name="End Date",
            value=f"{datetime.fromtimestamp(self.end_time).strftime('%d %b %Y')}",
            inline=True)

        raid_end_embed.add_field(
            name="Number of Participants",
            value=f"{len(self.members)}",
            inline=False)

        raid_end_embed.add_field(
            name="Total Loot Gained",
            value=f"{self.total_loot:,} <:CapitalGoldLooted:1045200974094028821>",
            inline=True)

        raid_end_embed.add_field(
            name="Number of Attacks",
            value=f"{self.attack_count}",
            inline=True)

        raid_end_embed.add_field(
            name="Districts Destroyed",
            value=f"{self.destroyed_district_count}",
            inline=True)

        raid_end_embed.add_field(
            name="Offensive Raids Completed",
            value=f"{self.offense_raids_completed}",
            inline=True)

        raid_end_embed.add_field(
            name="Defensive Raids Completed",
            value=f"{self.defense_raids_completed}",
            inline=True)

        raid_end_embed.add_field(
            name='**Raid Leaderboard**',
            value=f"{rank_table}",
            inline=False)

        return raid_end_embed

    async def save_to_json(self,ctx):
        rwJson = {
            'clan_tag': self.clan_tag,
            'clan_name': self.clan_name,
            'clan_badge': self.clan_badge,
            'clan_level': self.clan_level,
            'state': self.state,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_loot': self.total_loot,
            'attack_count': self.attack_count,
            'districts_destroyed': self.destroyed_district_count,
            'offensive_reward': self.offensive_reward,
            'defensive_reward': self.defensive_reward,
            'attack_log': [r.to_json() for r in self.attack_log],
            'defense_log': [r.to_json() for r in self.defense_log],
            'members': [m.to_json() for m in self.members]
            }

        await data_file_handler(
            ctx=ctx,
            file='capitalraid',
            tag=self.raid_id,
            new_data=rwJson)

class aRaidClan():
    def __init__(self,raid_entry,**kwargs):
        self.raid = raid_entry

        json_data = kwargs.get('json',None)
        game_data = kwargs.get('data',None)

        if json_data:
            self.tag = json_data['tag']
            self.name = json_data['name']
            self.badge = json_data.get('badge',None)
            self.level = json_data.get('level',0)
            self.attack_count = json_data['attack_count']
            self.district_count = json_data['district_count']
            self.destroyed_district_count = json_data['districts_destroyed']
            self.districts = [aRaidDistrict(self.raid,self,json=district) for district in json_data['districts']]
            #self.attacks = [aRaidAttack(self.raid,self,json=attack) for attack in json_data['attacks']]

        if game_data:
            data = game_data
            self.tag = data.tag
            self.name = data.name
            self.badge = data.badge.url
            self.level = data.level
            self.attack_count = data.attack_count
            self.district_count = data.district_count
            self.destroyed_district_count = data.destroyed_district_count
            self.districts = [aRaidDistrict(self.raid,self,data=district) for district in data.districts]
            #self.attacks = [aRaidAttack(self.raid,self,data=attack) for attack in data.attacks]

        #[d.get_attacks() for d in self.districts]
        #[a.get_district() for a in self.attacks]

    def to_json(self):
        rcJson = {
            'tag': self.tag,
            'name': self.name,
            'badge': self.badge,
            'level': self.level,
            'attack_count': self.attack_count,
            'district_count': self.district_count,
            'districts_destroyed': self.destroyed_district_count,
            'districts': [d.to_json() for d in self.districts]
            }
        return rcJson

class aRaidDistrict():
    def __init__(self,raid_entry,raid_clan,**kwargs):
        self.raid = raid_entry
        self.clan = raid_clan

        json_data = kwargs.get('json',None)
        game_data = kwargs.get('data',None)

        if json_data:
            self.id = json_data['id']
            self.name = json_data['name']
            self.hall_level = json_data['hall_level']
            self.destruction = json_data['destruction']
            self.attack_count = json_data['attack_count']
            self.looted = json_data['resources_looted']

        if game_data:
            data = game_data
            self.id = data.id
            self.name = data.name

            self.hall_level = data.hall_level
            self.destruction = data.destruction
            self.attack_count = data.attack_count
            self.looted = data.looted

    def to_json(self):
        districtJson = {
            'id': self.id,
            'name': self.name,
            'hall_level': self.hall_level,
            'destruction': self.destruction,
            'attack_count': self.attack_count,
            'resources_looted': self.looted
            }
        return districtJson

# class aRaidAttack():
#     def __init__(self,raid_entry,raid_clan,**kwargs):
#         self.raid = raid_entry
#         self.raid_clan = raid_clan

#         json_data = kwargs.get('json',None)
#         game_data = kwargs.get('data',None)

#         if json_data:
#             self.clan_tag = json_data['raid_clan']
#             self.district_id = json_data['district']
#             self.attacker_tag = json_data['attacker_tag']
#             self.attacker_name = json_data['attacker_name']
#             self.destruction = json_data['destruction']

#         if game_data:
#             data = game_data
#             self.clan_tag = data.raid_clan.tag
#             self.district_id = data.district.id
#             self.attacker_tag = data.attacker_tag
#             self.attacker_name = data.attacker_name
#             self.destruction = data.destruction

#         self.raid_district = None
#         self.attacker = None

#     def get_district(self):
#         self.raid_district = [district for district in self.raid_clan.districts if self.district_id == district.id][0]

#     def get_attacker(self):
#         self.attacker = [member for member in self.raid.members if self.attacker_tag == member.tag][0]

#     def to_json(self):
#         attackJson = {
#             'raid_clan': self.clan_tag,
#             'district': self.district_id,
#             'attacker_tag': self.attacker_tag,
#             'attacker_name': self.attacker_name,
#             'destruction': self.destruction
#             }
#         return attackJson

class aRaidMember():
    def __init__(self,raid_entry,**kwargs):
        self.raid = raid_entry

        json_data = kwargs.get('json',None)
        game_data = kwargs.get('data',None)

        if json_data:
            self.tag = json_data['tag']
            self.name = json_data['name']
            self.attack_count = json_data['attack_count']
            self.capital_resources_looted = json_data['resources_looted']

        if game_data:
            data = game_data
            self.tag = data.tag
            self.name = data.name
            self.attack_count = data.attack_count
            self.capital_resources_looted = data.capital_resources_looted

        self.medals_earned = (self.raid.offensive_reward * self.attack_count) + self.raid.defensive_reward

    def to_json(self):
        memberJson = {
            'tag': self.tag,
            'name': self.name,
            'attack_count': self.attack_count,
            'resources_looted': self.capital_resources_looted,
            }
        return memberJson

class aPlayerRaidLog():
    def __init__(self):
        self.rID = 0
        self.clan_tag = ''
        self.clan_name = ''
        self.attack_count = 0
        self.resources_looted = 0
        self.medals_earned = 0
        self.attacks = []

    @classmethod
    def from_json(cls,raid_id,player,json_data):
        self = aPlayerRaidLog()
        self.rID = raid_id
        self.clan_tag = json_data['clan_tag']
        self.clan_name = json_data['clan_name']
        self.attack_count = json_data['attack_count']
        self.resources_looted = json_data['resources_looted']
        self.medals_earned = json_data['medals_earned']
        self.attacks = []
        return self

    @classmethod
    def from_raid_member(cls,raid_member):
        self = aPlayerRaidLog()
        self.rID = raid_member.raid_weekend.rID
        self.clan_tag = raid_member.clan.tag
        self.clan_name = raid_member.clan.name
        self.attack_count = raid_member.attack_count
        self.resources_looted = raid_member.resources_looted
        self.medals_earned = raid_member.medals_earned
        self.attacks = raid_member.attacks
        return self

    def to_json(self):
        raidlogJson = {
            'clan_tag': self.clan_tag,
            'clan_name': self.clan_name,
            'attack_count': self.attack_count,
            'resources_looted': self.resources_looted,
            'medals_earned': self.medals_earned,
            'attacks': [a.to_json() for a in self.attacks]
            }
        return self.rID, raidlogJson
