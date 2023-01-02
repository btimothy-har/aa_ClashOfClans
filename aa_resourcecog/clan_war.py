import coc
import discord
import time
import pytz

from numerize import numerize
from itertools import chain
from datetime import datetime

from .notes import aNote
from .discordutils import convert_seconds_to_str, clash_embed
from .file_functions import get_current_season, read_file_handler, write_file_handler, eclipse_base_handler
from .constants import warTypeGrid, warResultOngoing, warResultEnded

class aClanWar():
    def __init__(self,**kwargs):

        json_data = kwargs.get('json',None)
        game_data = kwargs.get('game',None)
        clan = kwargs.get('clan',None)

        if json_data:
            self.type = json_data['type']
            self.state = json_data['state']
            self.preparation_start_time = json_data.get('preparation_start_time',0)
            self.start_time = json_data['start_time']
            self.end_time = json_data['end_time']

            self.result = json_data['result']
            if time.time() > self.end_time:
                self.result = warResultEnded[self.result]
            else:
                self.result = warResultOngoing[self.result]

            if 'team_size' in list(json_data.keys()):
                self.team_size = json_data['team_size']
            else:
                self.team_size = json_data['size']

            self.attacks_per_member = json_data.get('attacks_per_member',0)

            self.war_tag = json_data.get('war_tag',None)
            self.league_group = json_data.get('league_group',None)

            try:
                clan_1_json = json_data['clan_1']
            except:
                clan_1_json = json_data.get('clan',{})

            try:
                clan_2_json = json_data['clan_2']
            except:
                clan_2_json = json_data.get('opponent',{})

            clan_1 = aWarClan(self,json=clan_1_json)
            clan_2 = aWarClan(self,json=clan_2_json)

            if clan:
                if clan.tag == clan_2.tag:
                    self.clan = clan_2
                    self.opponent = clan_1
                else:
                    self.clan = clan_1
                    self.opponent = clan_2
            else:
                self.clan = clan_1
                self.opponent = clan_2

            self.attacks = []
            self.members = []

            try:
                json_attacks = json_data['attacks']
                json_members = json_data['members']
            except:
                clan_dict = json_data['clan']
                oppo_dict = json_data['opponent']

                for mem_json in clan_dict['members']:
                    member = aWarPlayer(self,json=mem_json,clan_tag=clan_dict['tag'])
                    self.members.append(member)

                    for att in mem_json['attacks']:
                        attack = aWarAttack(self,json=att)
                        self.attacks.append(attack)

                    for deff in mem_json['defenses']:
                        attack = aWarAttack(self,json=deff)
                        self.attacks.append(attack)

                for mem_json in oppo_dict['members']:
                    member = aWarPlayer(self,json=mem_json,clan_tag=oppo_dict['tag'])
                    self.members.append(member)
            else:
                self.attacks = [aWarAttack(self,json=attack) for attack in json_attacks]
                self.members = [aWarPlayer(self,json=member) for member in json_members]

        if game_data:
            data = game_data
            self.type = data.type
            self.state = data.state
            self.preparation_start_time = data.preparation_start_time.time.timestamp()
            self.start_time = data.start_time.time.timestamp()
            self.end_time = data.end_time.time.timestamp()
            self.result = data.status

            self.team_size = data.team_size
            self.attacks_per_member = data.attacks_per_member

            self.war_tag = data.war_tag
            self.league_group = data.league_group

            self.clan = aWarClan(self,data=data.clan)
            self.opponent = aWarClan(self,data=data.opponent)

            self.attacks = [aWarAttack(self,data=att) for att in data.attacks]
            self.members = [aWarPlayer(self,data=mem) for mem in data.members]

        tag_id = self.clan.tag + self.opponent.tag
        tag_id = tag_id.replace('#','')
        tag_id = ''.join(sorted(tag_id))

        self.war_id = tag_id + f"{str(int(self.start_time))}"

        self.attacks = sorted(self.attacks, key=lambda x: x.order)
        self.members = sorted(self.members, key=lambda x:(x.map_position,(x.town_hall*-1)))
        [a.compute_attack_stats() for a in self.attacks]
        [m.compute_war_performance() for m in self.members]

        self.clan.get_members()
        self.clan.get_attacks()
        self.opponent.get_members()
        self.opponent.get_attacks()

    @classmethod
    async def get(cls,ctx,**kwargs):
        clan = kwargs.get('clan',None)
        json_data = kwargs.get('json',None)
        war_id = kwargs.get('war_id',0)
        z = kwargs.get('z',False)

        if war_id and war_id in list(ctx.bot.war_cache.keys()):
            return ctx.bot.war_cache[war_id]

        if not json_data and war_id:
            json_data = await read_file_handler(ctx=ctx,
                file='warlog',
                tag=war_id)

        if json_data:
            if z:
                try:
                    self = aClanWar(clan=clan,json=json_data)
                except:
                    return None
            else:
                self = aClanWar(clan=clan,json=json_data)

        elif clan.public_war_log:
            try:
                ch = ctx.bot.get_channel(856433806142734346)
                await ch.send(clan.tag)
                war = await ctx.bot.coc_client.get_current_war(clan.tag)
            except coc.errors.PrivateWarLog:
                return None
            if not war or war.state == 'notInWar':
                return None
            self = aClanWar(clan=clan,game=war)
        else:
            return None

        ctx.bot.war_cache[self.war_id] = self
        return self

    def to_json(self):
        wJson = {
            'type': self.type,
            'state': self.state,
            'preparation_start_time': self.preparation_start_time,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'result': self.result,
            'clan_1': self.clan.to_json(),
            'clan_2': self.opponent.to_json(),
            'team_size': self.team_size,
            'attacks_per_member': self.attacks_per_member,
            'war_tag': self.war_tag,
            'league_group': self.league_group,
            'members': [m.to_json() for m in self.members],
            'attacks': [a.to_json() for a in self.attacks]
            }
        return wJson

    async def save_to_json(self,ctx):
        wJson = self.to_json()

        await write_file_handler(ctx=ctx,
            file='warlog',
            tag=self.war_id,
            new_data=wJson)

class aWarClan():
    def __init__(self,war,**kwargs):
        self.war = war

        json_data = kwargs.get('json',None)
        game_data = kwargs.get('data',None)

        if json_data:
            self.tag = json_data['tag']
            self.name = json_data['name']
            self.badge = json_data.get('badge',None)
            self.level = json_data.get('level',None)
            self.stars = json_data['stars']
            self.destruction = json_data['destruction']
            self.average_attack_duration = json_data['average_attack_duration']

            if 'attacks_used' in list(json_data.keys()):
                self.attacks_used = json_data['attacks_used']
            else:
                self.attacks_used = json_data['total_attacks']

        if game_data:
            self.tag = game_data.tag
            self.name = game_data.name
            self.badge = game_data.badge.url
            self.level = game_data.level
            self.stars = game_data.stars
            self.destruction = game_data.destruction
            self.average_attack_duration = game_data.average_attack_duration
            self.attacks_used = game_data.attacks_used

        self.max_stars = self.war.team_size * self.war.attacks_per_member

        self.members = []
        self.attacks = []
        self.defenses = []

    def get_members(self):
        self.members = [m for m in self.war.members if m.clan_tag == self.tag]

    def get_attacks(self):
        self.attacks = [a for a in self.war.attacks if a.attacker_tag in [m.tag for m in self.members]]
        self.defenses = [a for a in self.war.attacks if a.defender_tag in [m.tag for m in self.members]]

    def to_json(self):
        clanJson = {
            'tag': self.tag,
            'name': self.name,
            'badge': self.badge,
            'level': self.level,
            'stars': self.stars,
            'destruction': self.destruction,
            'average_attack_duration': self.average_attack_duration,
            'attacks_used': self.attacks_used
            }
        return clanJson

class aWarPlayer():
    def __init__(self,war,**kwargs):
        json_data = kwargs.get('json',None)
        game_data = kwargs.get('data',None)
        clan_tag = kwargs.get('clan_tag',None)

        self.war = war

        if json_data:
            self.tag = json_data['tag']
            self.name = json_data['name']
            self.town_hall = json_data['town_hall']
            self.map_position = json_data['map_position']

            self.clan_tag = json_data.get('clan_tag',clan_tag)

        if game_data:
            self.tag = game_data.tag
            self.name = game_data.name
            self.town_hall = game_data.town_hall
            self.map_position = game_data.map_position
            self.clan_tag = game_data.clan.tag

        if self.clan_tag == self.war.clan.tag:
            self.is_opponent = False
            self.clan = self.war.clan
        else:
            self.is_opponent = True
            self.clan = self.war.opponent

        self.attacks = [att for att in self.war.attacks if att.attacker_tag == self.tag]
        self.defenses = [att for att in self.war.attacks if att.defender_tag == self.tag]

        self.unused_attacks = self.war.attacks_per_member - len(self.attacks)
        self.defense_count = len(self.defenses)

        self.star_count = 0
        self.best_opponent_attack = None

    def compute_war_performance(self):
        best_defenses = sorted(self.defenses,key=lambda x:(x.order),reverse=True)
        for d in best_defenses:
            if d.new_stars > 0 or d.new_destruction > 0:
                self.best_opponent_attack = d
                break

        self.star_count = sum([a.new_stars for a in self.attacks])

    def to_json(self):
        playerJson = {
            'tag': self.tag,
            'name': self.name,
            'town_hall': self.town_hall,
            'map_position': self.map_position,
            'clan_tag': self.clan_tag
            }
        return playerJson

class aWarAttack():
    def __init__(self,war,**kwargs):
        json_data = kwargs.get('json',None)
        game_data = kwargs.get('data',None)

        self.war = war

        if json_data:
            self.order = json_data.get('order',None)

            if 'attacker_tag' in list(json_data.keys()):
                self.attacker_tag = json_data['attacker_tag']
            else:
                self.attacker_tag = json_data['attacker']

            if 'defender_tag' in list(json_data.keys()):
                self.defender_tag = json_data['defender_tag']
            else:
                self.defender_tag = json_data['defender']

            self.stars = json_data['stars']
            self.destruction = json_data['destruction']
            self.duration = json_data['duration']

            self.new_stars = json_data.get('new_stars',0)
            self.new_destruction = json_data.get('new_destruction',0)

            if 'is_fresh_attack' in list(json_data.keys()):
                self.is_fresh_attack = json_data['is_fresh_attack']
            else:
                self.is_fresh_attack = json_data['is_fresh_hit']

            self.is_triple = json_data.get('is_triple',False)
            self.is_best_attack = json_data.get('is_best_attack',False)

        if game_data:
            self.order = game_data.order
            self.attacker_tag = game_data.attacker_tag
            self.defender_tag = game_data.defender_tag

            self.stars = game_data.stars
            self.destruction = game_data.destruction
            self.duration = game_data.duration

            self.new_stars = 0
            self.new_destruction = 0

            self.is_fresh_attack = game_data.is_fresh_attack
            self.is_triple = False
            self.is_best_attack = False

        self.attacker = None
        self.defender = None


    def compute_attack_stats(self):
        self.attacker = [player for player in self.war.members if player.tag == self.attacker_tag][0]
        self.defender = [player for player in self.war.members if player.tag == self.defender_tag][0]
        self.is_triple = (self.stars==3 and self.attacker.town_hall <= self.defender.town_hall)

        all_attacks = [att for att in self.war.attacks if att.defender_tag == self.defender_tag]

        base_stars = 0
        base_destruction = 0
        is_best_attack = False

        for att in [att for att in self.war.attacks if att.order < self.order]:
            if att.stars > base_stars:
                base_stars = att.stars
            if att.destruction > base_destruction:
                base_destruction = att.destruction

        self.new_stars = max(0,self.stars - base_stars)
        self.new_destruction = max(0,self.destruction - base_destruction)

        if is_best_attack:
            self.is_best_attack = True

    def to_json(self):
        if self.order:
            attackJson = {
                'warID': self.war.war_id,
                'order': self.order,
                'stars': self.stars,
                'new_stars': self.new_stars,
                'destruction': self.destruction,
                'new_destruction': self.new_destruction,
                'duration': self.duration,
                'attacker_tag': self.attacker_tag,
                'defender_tag': self.defender_tag,
                'is_fresh_attack': self.is_fresh_attack,
                'is_triple': self.is_triple,
                'is_best_attack': self.is_best_attack
                }
            return attackJson
        else:
            return None

class aPlayerWarLog():
    def __init__(self):
        self.p = None
        self.wID = 0

        self.type = ''
        self.result = ''

        self.clan = None
        self.opponent = None

        self.town_hall = 1
        self.map_position = 0
        self.total_attacks = 0
        self.best_opponent_attack = None
        self.attacks = []
        self.defenses = []

    @classmethod
    def from_war(cls,war_player):
        self = aPlayerWarLog()
        self.p = war_player
        self.wID = self.p.clan.war.wID
        self.type = self.p.clan.war.type
        self.result = self.p.clan.war.result

        self.clan = aPlayerWarClan.from_war(self.p.clan)
        if war_player.is_opponent:
            self.opponent = aPlayerWarClan.from_war(self.p.clan.war.clan)
        else:
            self.opponent = aPlayerWarClan.from_war(self.p.clan.war.opponent)

        self.town_hall = self.p.town_hall
        self.map_position = self.p.map_position

        self.total_attacks = self.p.clan.war.attacks_per_member

        self.best_opponent_attack = self.p.best_opponent_attack
        self.attacks = self.p.attacks
        self.defenses = self.p.defenses

        return self

    @classmethod
    def from_json(cls,war_id,json_data):
        self = aPlayerWarLog()
        self.wID = war_id
        self.type = json_data.get('type','')
        self.result = json_data.get('result','')
        self.clan = aPlayerWarClan.from_json(json_data['clan'])
        self.opponent = aPlayerWarClan.from_json(json_data['opponent'])

        #use 24 hours
        if time.time() > (float(self.wID) + 90000):
            self.result = warResultEnded[self.result]
        
        self.town_hall = json_data['town_hall']
        self.map_position = json_data['map_position']
        self.total_attacks = json_data['total_attacks']

        self.best_opponent_attack = aWarAttack(war=self,json_data=json_data.get('best_opponent_attack',None))

        self.attacks = [aWarAttack(war=self,json_data=attack) for attack in json_data.get('attacks',[])]
        self.defenses = [aWarAttack(war=self,json_data=defense) for defense in json_data.get('defenses',[])]

        return self

    def to_json(self):
        warJson = {
            'type': self.type,
            'result': self.result,
            'clan': self.clan.to_json(),
            'opponent': self.opponent.to_json(),
            'town_hall': self.town_hall,
            'map_position': self.map_position,
            'total_attacks': self.total_attacks,
            'best_opponent_attack': self.best_opponent_attack.to_json(),
            'attacks': [a.to_json() for a in self.attacks],
            'defenses': [d.to_json() for d in self.defenses]
            }
        return self.wID, warJson

class aPlayerWarClan():
    def __init__(self):
        self.tag = ''
        self.name = ''
        self.stars = 0
        self.destruction = 0
        self.average_attack_duration = 0

    @classmethod
    def from_war(cls,player_clan):
        self = aPlayerWarClan()
        self.tag = player_clan.tag
        self.name = player_clan.name
        self.stars = player_clan.stars
        self.destruction = player_clan.destruction
        self.average_attack_duration = player_clan.average_attack_duration
        return self

    @classmethod
    def from_json(cls,json_data):
        self = aPlayerWarClan()
        self.tag = json_data['tag']
        self.name = json_data['name']
        self.stars = json_data['stars']
        self.destruction = json_data['destruction']
        self.average_attack_duration = json_data['average_attack_duration']
        return self

    def to_json(self):
        clanJson = {
            'tag': self.tag,
            'name': self.name,
            'stars': self.stars,
            'destruction': self.destruction,
            'average_attack_duration': self.average_attack_duration
            }
        return clanJson
