import coc
import discord
import time

#from .constants import 
from .notes import aNote

class aRaidWeekend():
    def __init__(self,ctx,clan):
        self.timestamp = time.time()
        self.ctx = ctx
        self.clan = clan

        self.rw = None
        self.rID = ''
        self.state = ''

        self.start_time = 0
        self.end_time = 0

        self.total_loot = 0
        self.offense_raids_completed = 0
        self.defense_raids_completed = 0
        self.raid_attack_count = 0
        self.districts_destroyed = 0
        self.offense_rewards = 0
        self.defense_rewards = 0
        self.members = []
        self.attack_log = []
        self.defense_log = []

    @classmethod
    def from_json(cls,ctx,clan,raid_id,json_data):
        self = aRaidWeekend(ctx,clan)

        self.rID = raid_id
        self.state = json_data['state']

        self.start_time = json_data['start_time']
        self.end_time = json_data['end_time']

        self.total_loot = json_data['total_loot']
        self.offense_raids_completed = json_data['offense_raids_completed']
        self.defense_raids_completed = json_data['defense_raids_completed']

        self.raid_attack_count = json_data['raid_attack_count']
        self.districts_destroyed = json_data['districts_destroyed']

        self.offense_rewards = json_data['offense_rewards']
        self.defense_rewards = json_data['defense_rewards']

        self.members = [aRaidMember.from_json(clan=self.clan,raid_entry=self,json_data=m) for m in json_data['members']]

        self.attack_log = [aRaidClan.from_json(raid_entry=self,json_data=r,raid_type='offense') for r in json_data['attack_log']]
        self.defense_log = [aRaidClan.from_json(raid_entry=self,json_data=r,raid_type='defense') for r in json_data['defense_log']]
        return self

    @classmethod
    def from_game(cls,ctx,clan,game_data):
        self = aRaidWeekend(ctx,clan)
        self.rw = game_data

        self.state = self.rw.state

        self.start_time = self.rw.start_time.time.timestamp()
        self.end_time = self.rw.end_time.time.timestamp()

        self.rID = str(self.start_time)

        self.total_loot = self.rw.total_loot
        self.offense_raids_completed = len([r for r in self.rw.attack_log if r.destroyed_district_count==r.district_count])
        self.defense_raids_completed = len([r for r in self.rw.defense_log if r.destroyed_district_count==r.district_count])

        self.raid_attack_count = self.rw.attack_count
        self.districts_destroyed = self.rw.destroyed_district_count

        self.offense_rewards = self.rw.offensive_reward
        self.defense_rewards = self.rw.defensive_reward

        self.members = [aRaidMember.from_game(clan=self.clan,raid_entry=self,game_data=m) for m in self.rw.members]

        self.attack_log = [aRaidClan.from_game(raid_entry=self,game_data=a,raid_type='offense') for a in self.rw.attack_log]
        self.defense_log = [aRaidClan.from_game(raid_entry=self,game_data=a,raid_type='defense') for a in self.rw.defense_log]
        return self

    def to_json(self):
        rwJson = {
            'state': self.state,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_loot': self.total_loot,
            'offense_raids_completed': self.offense_raids_completed,
            'defense_raids_completed': self.defense_raids_completed,
            'raid_attack_count': self.raid_attack_count,
            'districts_destroyed': self.districts_destroyed,
            'offense_rewards': self.offense_rewards,
            'defense_rewards': self.defense_rewards,
            'members': [m.to_json() for m in self.members],
            'attack_log': [r.to_json() for r in self.attack_log],
            'defense_log': [r.to_json() for r in self.defense_log],
            }
        return self.rID, rwJson

class aRaidClan():
    def __init__(self,raid_entry,raid_type):
        self.raid_weekend = raid_entry
        self.r = None
        self.rID = self.raid_weekend.rID
        #offense or defense
        self.type = raid_type
        self.clan_tag = ''
        self.clan_name = ''
        self.attack_count = 0
        self.district_count = 0
        self.districts_destroyed = 0
        self.districts = []

    @classmethod
    def from_json(cls,raid_entry,json_data,raid_type):
        self = aRaidClan(raid_entry,raid_type)
        
        self.clan_tag = json_data['tag']
        self.clan_name = json_data['name']

        self.attack_count = json_data['attack_count']
        self.district_count = json_data['district_count']
        self.districts_destroyed = json_data['districts_destroyed']
        self.districts = [aRaidDistrict.from_json(raid_clan=self,json_data=d) for d in json_data['districts']]
        return self

    @classmethod
    def from_game(cls,raid_entry,game_data,raid_type):
        self = aRaidClan(raid_entry,raid_type)
        self.r = game_data

        self.clan_tag = self.r.tag
        self.clan_name = self.r.name

        self.attack_count = self.r.attack_count
        self.district_count = self.r.district_count
        self.districts_destroyed = self.r.destroyed_district_count

        self.districts = [aRaidDistrict.from_game(raid_clan=self,game_data=d) for d in self.r.districts]
        return self

    def to_json(self):
        rcJson = {
            'tag': self.clan_tag,
            'name': self.clan_name,
            'attack_count': self.attack_count,
            'district_count': self.district_count,
            'districts_destroyed': self.districts_destroyed,
            'districts': [d.to_json() for d in self.districts]
            }
        return rcJson

class aRaidDistrict():
    def __init__(self,raid_clan):
        self.raid_clan = raid_clan
        self.d = None
        self.id = 0
        self.name = ''
        self.hall_level = 0
        self.destruction = 0
        self.attack_count = 0
        self.resources_looted = 0

    @classmethod
    def from_json(cls,raid_clan,json_data):
        self = aRaidDistrict(raid_clan)
        self.id = json_data['id']
        self.name = json_data['name']
        self.hall_level = json_data['hall_level']
        self.destruction = json_data['destruction']
        self.attack_count = json_data['attack_count']
        self.resources_looted = json_data['resources_looted']
        return self

    @classmethod
    def from_game(cls,raid_clan,game_data):
        self = aRaidDistrict(raid_clan)
        self.d = game_data
        self.id = self.d.id
        self.name = self.d.name
        self.hall_level = self.d.hall_level
        self.destruction = self.d.destruction
        self.attack_count = self.d.attack_count
        self.resources_looted = self.d.looted
        return self

    def to_json(self):
        districtJson = {
            'id': self.id,
            'name': self.name,
            'hall_level': self.hall_level,
            'destruction': self.destruction,
            'attack_count': self.attack_count,
            'resources_looted': self.resources_looted
            }
        return districtJson

class aRaidMember():
    def __init__(self,clan,raid_entry):
        self.raid_weekend = raid_entry
        self.clan = clan
        self.tag = ''
        self.name = ''
        self.attack_count = 0
        self.resources_looted = 0
        self.medals_earned = 0
        self.attacks = []

    @classmethod
    def from_json(cls,clan,raid_entry,json_data):
        self = aRaidMember(clan,raid_entry)
        self.tag = json_data['tag']
        self.name = json_data['name']
        self.attack_count = json_data['attack_count']
        self.resources_looted = json_data['resources_looted']
        self.medals_earned = json_data['medals_earned']
        self.attacks = [aRaidAttack.from_json(raid_id=self.raid_weekend.rID,attacker_tag=self.tag,attacker_name=self.name,json_data=a) for a in json_data['attacks']]
        return self

    @classmethod
    def from_game(cls,clan,raid_entry,game_data):
        self = aRaidMember(clan,raid_entry)
        self.tag = game_data.tag
        self.name = game_data.name
        self.attack_count = game_data.attack_count
        self.resources_looted = game_data.capital_resources_looted
        self.medals_earned = (self.attack_count * self.raid_weekend.offense_rewards) + self.raid_weekend.defense_rewards
        self.attacks = [aRaidAttack.from_game(raid_id=self.raid_weekend.rID,game_data=a) for a in game_data.attacks]
        return self

    def to_json(self):
        memberJson = {
            'tag': self.tag,
            'name': self.name,
            'attack_count': self.attack_count,
            'resources_looted': self.resources_looted,
            'medals_earned': self.medals_earned,
            'attacks': [a.to_json() for a in self.attacks]
            }
        return memberJson

class aRaidAttack():
    def __init__(self,raid_id):
        self.rID = raid_id
        self.attacker_tag = ''
        self.attacker_name = ''
        self.destruction = 0
        self.raid_clan = ''
        self.district = ''

    @classmethod
    def from_json(cls,raid_id,attacker_tag,attacker_name,json_data):
        self = aRaidAttack(raid_id)
        self.attacker_tag = attacker_tag
        self.attacker_name = attacker_name
        self.destruction = json_data['destruction']
        self.raid_clan = json_data['raid_clan']
        self.district = json_data['district']
        return self

    @classmethod
    def from_game(cls,raid_id,game_data):
        self = aRaidAttack(raid_id)
        self.attacker_tag = game_data.attacker_tag
        self.attacker_name = game_data.attacker_name
        self.destruction = game_data.destruction
        self.raid_clan = game_data.raid_clan.tag
        self.district = game_data.district.name
        return self

    def to_json(self):
        attackJson = {
            'raid_clan': self.raid_clan,
            'district': self.district,
            'destruction': self.destruction
            }
        return attackJson

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
        self.attacks = [aRaidAttack.from_json(raid_id=self.rID,attacker_tag=player.tag,attacker_name=player.name,json_data=a) for a in json_data['attacks']]
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