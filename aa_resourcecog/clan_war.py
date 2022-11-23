import time

from .constants import warTypeGrid, warResultGrid
from .notes import aNote

class aClanWar():
    def __init__(self,ctx):
        self.timestamp = time.time()
        self.ctx = ctx
        self.wID = ''

        self.w = None
        self.type = ''
        self.state = ''
        self.result = ''
        self.size = 0
        self.attacks_per_member = 0
        self.start_time = 0
        self.end_time = 0

        self.clan = None
        self.opponent = None

    @classmethod
    def from_json(cls,ctx,wID,json_data):
        self = aClanWar(ctx)
        self.wID = wID

        self.type = json_data['type']
        self.state = json_data['state']
        self.result = warResultGrid[json_data['result']]
        self.size = json_data['size']
        self.attacks_per_member = json_data['attacks_per_member']
        self.start_time = json_data['start_time']
        self.end_time = json_data['end_time']

        self.clan = aWarClan.from_json(war=self,json_data=json_data['clan'],is_opponent=False)
        self.opponent = aWarClan.from_json(war=self,json_data=json_data['opponent'],is_opponent=True)

        if self.timestamp > self.end_time:
            self.state = 'warEnded'

        return self

    @classmethod
    def from_game(cls,ctx,game_data):
        self = aClanWar(ctx)
        self.w = game_data

        self.type = warTypeGrid[self.w.type]
        self.state = self.w.state
        self.result = warResultGrid[self.w.status]
        self.size = self.w.team_size
        self.attacks_per_member = self.w.attacks_per_member
        self.start_time = self.w.start_time.time.timestamp()
        self.end_time = self.w.end_time.time.timestamp()
        self.wID = str(self.start_time)

        self.clan = aWarClan.from_game(war=self,game_data=self.w.clan,is_opponent=False)
        self.opponent = aWarClan.from_game(war=self,game_data=self.w.opponent,is_opponent=True)

        return self

    def to_json(self):
        wJson = {
            'type': self.type,
            'state': self.state,
            'result': self.result,
            'size': self.size,
            'attacks_per_member': self.attacks_per_member,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'clan': self.clan.to_json(),
            'opponent':self.opponent.to_json(),
            }
        return self.wID, wJson

class aWarClan():
    def __init__(self,war):
        self.war = war
        self.c = None

        self.tag = ''
        self.name = ''
        self.is_opponent = False

        self.total_attacks = 0
        self.missed_attacks = 0
        self.stars = 0
        self.destruction = 0
        self.average_attack_duration = 0
        self.triples = 0

        self.members = []

    @classmethod
    def from_json(cls,war,json_data,is_opponent:bool):
        self = aWarClan(war)
        self.war = war

        self.tag = json_data['tag']
        self.name = json_data['name']
        self.is_opponent = is_opponent

        self.total_attacks = json_data['total_attacks']
        self.missed_attacks = (self.war.attacks_per_member * self.war.size) - self.total_attacks
        self.stars = json_data['stars']
        self.destruction = json_data['destruction']
        self.average_attack_duration = json_data['average_attack_duration']
        self.triples = json_data['triples']

        self.members = [aWarPlayer.from_json(clan=self,json_data=m) for m in json_data['members']]
        return self

    @classmethod
    def from_game(cls,war,game_data,is_opponent:bool):
        self = aWarClan(war)
        self.c = game_data

        self.tag = self.c.tag
        self.name = self.c.name
        self.is_opponent = is_opponent
        
        self.total_attacks = self.c.attacks_used
        self.missed_attacks = (self.war.attacks_per_member * self.war.size) - self.total_attacks
        self.stars = self.c.stars
        self.destruction = self.c.destruction
        self.average_attack_duration = self.c.average_attack_duration
        self.triples = len([a for a in self.c.attacks if a.stars==3 and a.attacker.town_hall <= a.defender.town_hall])

        self.members = [aWarPlayer.from_game(clan=self,game_data=m) for m in self.c.members]
        return self

    def to_json(self):
        clanJson = {
            'tag': self.tag,
            'name': self.name,
            'total_attacks': self.total_attacks,
            'missed_attacks': self.missed_attacks,
            'stars': self.stars,
            'destruction': self.destruction,
            'average_attack_duration': self.average_attack_duration,
            'triples': self.triples,
            'members': [m.to_json() for m in self.members],
            }
        return clanJson

class aWarPlayer():
    def __init__(self,clan):
        self.clan = clan
        self.p = None
        
        self.is_opponent = self.clan.is_opponent

        self.tag = ''
        self.name = ''
        self.town_hall = 1
        self.map_position = 0
        self.best_opponent_attack = None
        self.attacks = []
        self.defenses = []

    @classmethod
    def from_json(cls,clan,json_data):
        self = aWarPlayer(clan)

        self.tag = json_data['tag']
        self.name = json_data['name']
        self.town_hall = json_data['town_hall']
        self.map_position = json_data['map_position']

        self.best_opponent_attack = aWarAttack.from_json(war_id=self.clan.war.wID,json_data=json_data.get('best_opponent_attack',None))

        #only build attacks and defenses for own clan
        if not self.is_opponent:
            self.attacks = [aWarAttack.from_json(war_id=self.clan.war.wID,json_data=a) for a in json_data['attacks']]
            self.defenses = [aWarAttack.from_json(war_id=self.clan.war.wID,json_data=a) for a in json_data['defenses']]
        return self

    @classmethod
    def from_game(cls,clan,game_data):
        self = aWarPlayer(clan)
        self.p = game_data

        self.tag = self.p.tag
        self.name = self.p.name
        self.town_hall = self.p.town_hall
        self.map_position = self.p.map_position

        self.best_opponent_attack = aWarAttack.from_game(war_id=self.clan.war.wID, game_data=self.p.best_opponent_attack)

        if not self.is_opponent:
            self.attacks = [aWarAttack.from_game(war_id=self.clan.war.wID, game_data=a) for a in self.p.attacks]
            self.defenses = [aWarAttack.from_game(war_id=self.clan.war.wID, game_data=a) for a in self.p.defenses]
        return self

    def to_json(self):
        playerJson = {
            'tag': self.tag,
            'name': self.name,
            'town_hall': self.town_hall,
            'map_position': self.map_position,
            'best_opponent_attack': self.best_opponent_attack.to_json(),
            'attacks': [a.to_json() for a in self.attacks],
            'defenses': [d.to_json() for d in self.defenses]
            }
        return playerJson

class aWarAttack():
    def __init__(self,war_id):
        self.wID = war_id
        self.a = None

        self.order = None
        self.attacker = ''
        self.defender = ''
        self.stars = 0
        self.destruction = 0
        self.duration = 0
        self.is_triple = False
        self.is_fresh_hit = False

    @classmethod
    def from_json(cls,war_id,json_data=None):
        self = aWarAttack(war_id)
        if json_data:
            self.order = json_data['order']
            self.attacker = json_data['attacker']
            self.defender = json_data['defender']
            self.stars = json_data['stars']
            self.destruction = json_data['destruction']
            self.duration = json_data['duration']
            self.is_triple = json_data['is_triple']
            self.is_fresh_hit = json_data['is_fresh_hit']
        return self

    @classmethod
    def from_game(cls,war_id,game_data=None):
        self = aWarAttack(war_id)
        self.a = game_data

        if game_data:
            self.order = self.a.order
            self.attacker = self.a.attacker_tag
            self.defender = self.a.defender_tag
            self.stars = self.a.stars
            self.destruction = self.a.destruction
            self.duration = self.a.duration
            self.is_triple = (self.a.stars==3 and self.a.attacker.town_hall <= self.a.defender.town_hall)
            self.is_fresh_hit = self.a.is_fresh_attack
        return self

    def to_json(self):
        if self.order:
            attackJson = {
                'warID': self.wID,
                'order': self.order,
                'attacker': self.attacker,
                'defender': self.defender,
                'stars': self.stars,
                'destruction': self.destruction,
                'duration': self.duration,
                'is_triple': self.is_triple,
                'is_fresh_hit': self.is_fresh_hit
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
        self.result = warResultGrid[json_data.get('result','')]
        self.clan = aPlayerWarClan.from_json(json_data['clan'])
        self.opponent = aPlayerWarClan.from_json(json_data['opponent'])
        
        self.town_hall = json_data['town_hall']
        self.map_position = json_data['map_position']
        self.total_attacks = json_data['total_attacks']

        self.best_opponent_attack = aWarAttack.from_json(war_id=self.wID,json_data=json_data.get('best_opponent_attack',None))

        self.attacks = [aWarAttack.from_json(war_id=self.wID,json_data=attack) for attack in json_data.get('attacks',[])]
        self.defenses = [aWarAttack.from_json(war_id=self.wID,json_data=defense) for defense in json_data.get('defenses',[])]

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
