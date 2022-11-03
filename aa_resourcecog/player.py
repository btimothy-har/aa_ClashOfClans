import coc
import discord
import time

from numerize import numerize
from itertools import chain

from coc.ext import discordlinks

from .constants import emotes_townhall, emotes_army, hero_availability, troop_availability, spell_availability
from .file_functions import get_current_alliance, season_file_handler, alliance_file_handler, data_file_handler

from .notes import aNote
from .clan import aClan
from .clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from .raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from .errors import TerminateProcessing, InvalidTag

class ClashPlayerError(Exception):
    def __init__(self,message):
        self.message = message

class aPlayer():
    def __init__(self,ctx,tag):
        self.timestamp = time.time()
        self.ctx = ctx
        self.tag = coc.utils.correct_tag(tag)

        if not coc.utils.is_valid_tag(tag):
            raise InvalidTag(tag)
            return None

        self.p = None
        self.name = None

        self.discord_link = None

        #Membership Attributes
        self.home_clan = None
        self.is_member = False
        self.arix_rank = 'Non-Member'
        self.discord_user = 0
        self.notes = []

        #Membership Statistics
        self.last_update = 0
        self.time_in_home_clan = 0
        self.other_clans = []

        #Player Attributes
        self.exp_level = 1

        self.clan = None
        self.role = ''

        #Home Village Stats
        self.town_hall = aTownHall(level=1,weapon=0)
        self.clan_castle = 0
        self.league = None
        self.trophies = 0
        self.best_trophies = 0
        self.war_stars = 0
        self.war_optin = 0

        #Builder Hall Stats
        self.builder_hall = 0
        self.versus_trophies = 0
        self.best_versus_trophies = 0

        #Home Village Offense
        self.heroes = []
        self.troops = []
        self.spells = []
        self.pets = []
        self.hero_strength = 0
        self.max_hero_strength = 0

        self.troop_strength = 0
        self.max_troop_strength = 0

        self.spell_strength = 0
        self.max_spell_strength = 0

        #Activity Stats
        self.attack_wins = aPlayerStat({})
        self.defense_wins = aPlayerStat({})

        self.donation_sent = aPlayerStat({})
        self.donation_rcvd = aPlayerStat({})

        self.loot_gold = aPlayerStat({})
        self.loot_elixir = aPlayerStat({})
        self.loot_darkelixir = aPlayerStat({})
        
        self.clangames = aPlayerStat({})

        self.capitalcontribution = aPlayerStat({})

        self.warLog = None
        self.warStats = None

        self.raidLog = None
        self.raidStats = None

    @classmethod
    async def create(cls,ctx,tag):
        self = aPlayer(ctx,tag)

        memberInfo = await alliance_file_handler(self.ctx,'members',self.tag)
        memberStats = await data_file_handler(self.ctx,'members',self.tag)

        self.name = memberStats.get('name',None)

        #Membership Attributes
        try:
            hcTag = memberInfo['home_clan']['tag']
        except:
            hcTag = None
        self.home_clan = await aClan.create(ctx,hcTag)
        self.is_member = memberInfo.get('is_member',False)
        self.arix_rank = memberInfo.get('rank','Non-Member')
        self.discord_user = memberInfo.get('discord_user',0)
        self.notes = [aNote(self.ctx,note) for note in memberInfo.get('notes',[])]

        #Membership Statistics
        self.last_update = memberStats.get('last_update',0)
        self.time_in_home_clan = memberStats.get('time_in_home_clan',0)
        self.other_clans = memberStats.get('other_clans',[])

        #Basic Stats
        self.exp_level = memberStats.get('exp_level',1)
        self.town_hall = aTownHall(
            level = memberStats.get('town_hall',1),
            weapon = memberStats.get('town_hall_weapon',0))
        self.clan_castle = memberStats.get('clan_castle',0)

        try:
            cTag = memberStats['current_clan']['tag']
        except:
            cTag = None
        self.clan = await aClan.create(ctx,cTag)
        self.role = memberStats.get('role','')

        #Home Village Stats
        self.league = await ctx.bot.coc_client.get_league_named(memberStats.get('league','Unranked')) 
        self.trophies = memberStats.get('trophies',0)
        self.best_trophies = memberStats.get('best_trophies',0)
        self.war_stars = memberStats.get('war_stars',0)
        self.war_optin = memberStats.get('war_optin',False)

        #Builder Hall Stats
        self.builder_hall = memberStats.get('builder_hall',0)
        self.versus_trophies = memberStats.get('versus_trophies',0)
        self.best_versus_trophies = memberStats.get('best_versus_trophies',0)

        self.heroes = [aHero.from_json(h) for h in memberStats.get('heroes',[])]
        self.troops = [aTroop.from_json(t) for t in memberStats.get('troops',[])]
        self.spells = [aSpell.from_json(s) for s in memberStats.get('spells',[])]
        self.pets = [aHeroPet.from_json(p) for p in memberStats.get('pets',[])]

        self.hero_strength = sum([hero.level for hero in self.heroes])
        self.max_hero_strength = sum([hero.maxlevel_for_townhall for hero in self.heroes])

        self.troop_strength = sum([troop.level for troop in self.troops])
        self.max_troop_strength = sum([troop.maxlevel_for_townhall for troop in self.troops])

        self.spell_strength = sum([spell.level for spell in self.spells])
        self.max_spell_strength = sum([spell.maxlevel_for_townhall for spell in self.spells])

        self.attack_wins = aPlayerStat(memberStats.get('attack_wins',{}))
        self.defense_wins = aPlayerStat(memberStats.get('defense_wins',{}))

        self.donations_sent = aPlayerStat(memberStats.get('donations_sent',{}))
        self.donations_rcvd = aPlayerStat(memberStats.get('donations_rcvd',{}))

        self.loot_gold = aPlayerStat(memberStats.get('loot_gold',{}))
        self.loot_elixir = aPlayerStat(memberStats.get('loot_elixir',{}))
        self.loot_darkelixir = aPlayerStat(memberStats.get('loot_darkelixir',{}))

        self.clangames = aPlayerStat(memberStats.get('clangames',{}))

        self.capitalcontribution = aPlayerStat(memberStats.get('capitalcontribution',{}))

        self.warlog = {wID:aPlayerWarLog.from_json(wID,wl) for (wID,wl) in memberStats.get('war_log',{}).items()}
        self.raidlog = {rID:aPlayerRaidLog.from_json(rID,self,rl) for (rID,rl) in memberStats.get('raid_log',{}).items()}

        self.war_stats = aPlayerWarStats(self.warlog)
        self.raid_stats = aPlayerRaidStats(self.raidlog)

        return self

    @classmethod
    async def create_from_data(cls,ctx,tag):
        self = aPlayer(ctx,tag)
        try:
            self.p = await ctx.bot.coc_client.get_player(self.tag)
            self.discord_link = await ctx.bot.discordlinks.get_links(self.tag)
        except (coc.HTTPException, coc.InvalidCredentials, coc.Maintenance, coc.GatewayError) as exc:
            raise TerminateProcessing(exc) from exc
            return None
        return self

    async def retrieve_data(self):
        self.timestamp = time.time()
        try:
            self.p = await self.ctx.bot.coc_client.get_player(self.tag)
            self.discord_link = await self.ctx.bot.discordlinks.get_links(self.tag)
        except (coc.HTTPException, coc.InvalidCredentials, coc.Maintenance, coc.GatewayError) as exc:
            raise TerminateProcessing(exc) from exc
            return None

        self.name = getattr(self.p,'name','')
        self.exp_level = getattr(self.p,'exp_level',1)

        clan = getattr(self.p,'clan',None)
        self.clan = await aClan.create(self.ctx,getattr(clan,'tag',None))
        self.role = str(getattr(self.p,'role',''))

        self.town_hall = aTownHall(level=getattr(self.p,'town_hall',1),weapon=getattr(self.p,'town_hall_weapon',0))
        self.clan_castle = sum([a.value for a in self.p.achievements if a.name=='Empire Builder'])
        self.league = getattr(self.p,'league',None)
        self.trophies = getattr(self.p,'trophies',0)
        self.best_trophies = getattr(self.p,'best_trophies',0)
        self.war_stars = getattr(self.p,'war_stars',0)
        self.war_optin = getattr(self.p,'war_opted_in',0)

        self.builder_hall = getattr(self.p,'builder_hall',0)
        self.versus_trophies = getattr(self.p,'versus_trophies',0)
        self.best_versus_trophies = getattr(self.p,'best_versus_trophies',0)

        self.heroes = []
        hero_d = [hero for (th,hero) in hero_availability.items() if th<=self.town_hall.level]
        for hero_name in list(chain.from_iterable(hero_d)):
            hero = self.p.get_hero(name=hero_name)
            hero = aHero.from_data(hero,self.town_hall.level)
            self.heroes.append(hero)

        self.troops = []
        troop_d = [troop for (th,troop) in troop_availability.items() if th<=self.town_hall.level]
        for troop_name in list(chain.from_iterable(troop_d)):
            troop = self.p.get_troop(name=troop_name,is_home_troop=True)
            troop = aTroop.from_data(troop,self.town_hall.level)
            self.troops.append(troop)

        self.spells = []
        spell_d = [spell for (th,spell) in spell_availability.items() if th<=self.town_hall.level]
        for spell_name in list(chain.from_iterable(spell_d)):
            spell = self.p.get_spell(name=spell_name)
            spell = aSpell.from_data(spell,self.town_hall.level)
            self.spells.append(spell)

        self.pets = [aHeroPet.from_data(pet) for pet in self.p.hero_pets]

        self.hero_strength = sum([hero.level for hero in self.heroes])
        self.max_hero_strength = sum([hero.maxlevel_for_townhall for hero in self.heroes])

        self.troop_strength = sum([troop.level for troop in self.troops])
        self.max_troop_strength = sum([troop.maxlevel_for_townhall for troop in self.troops])

        self.spell_strength = sum([spell.level for spell in self.spells])
        self.max_spell_strength = sum([spell.maxlevel_for_townhall for spell in self.spells])

    async def update_stats(self):
        #cannot update if data not retrieved
        if self.p:
            if self.clan.tag == self.home_clan.tag:
                self.time_in_home_clan += (self.timestamp - self.last_update)
            elif self.clan.tag not in self.other_clans:
                self.other_clans.append(self.clan.tag)

            self.attack_wins.update_stat(self.p.attack_wins)
            self.defense_wins.update_stat(self.p.defense_wins)

            self.donations_sent.update_stat(self.p.donations)
            self.donations_rcvd.update_stat(self.p.received)
            
            for achievement in self.p.achievements:
                if achievement.name == 'Gold Grab':
                    self.loot_gold.update_stat(achievement.value)
                if achievement.name == 'Elixir Escapade':
                    self.loot_elixir.update_stat(achievement.value)
                if achievement.name == 'Heroic Heist':
                    self.loot_darkelixir.update_stat(achievement.value)
                if achievement.name == 'Most Valuable Clanmate':
                    self.capitalcontribution.update_stat(achievement.value)
                if achievement.name == 'Games Champion':
                    self.clangames.update_stat(achievement.value)

    async def set_baselines(self):
        self.attack_wins.set_baseline(self.p.attack_wins)
        self.defense_wins.set_baseline(self.p.defense_wins)

        self.donations_sent.set_baseline(self.p.donations)
        self.donations_rcvd.set_baseline(self.p.received)

        for achievement in self.p.achievements:
            if achievement.name == 'Gold Grab':
                self.loot_gold.set_baseline(achievement.value)
            if achievement.name == 'Elixir Escapade':
                self.loot_elixir.set_baseline(achievement.value)
            if achievement.name == 'Heroic Heist':
                self.loot_darkelixir.set_baseline(achievement.value)
            if achievement.name == 'Most Valuable Clanmate':
                self.capitalcontribution.set_baseline(achievement.value)
            if achievement.name == 'Games Champion':
                self.clangames.set_baseline(achievement.value)

    async def save_to_json(self):
        allianceJson = {
            'name':self.name,
            'home_clan': {
                'tag': self.home_clan.tag,
                'name': self.home_clan.name
                },
            'is_member':self.is_member,
            'rank':self.arix_rank,
            'discord_user':self.discord_user,
            'notes':[n.to_json() for n in self.notes],
            }

        raid_log_dict = {}
        for rid, r in self.raidlog.items():
            rID, rjson = r.to_json()
            raid_log_dict[rID] = rjson

        war_log_dict = {}
        for wid, w in self.warlog.items():
            wID, wjson = w.to_json()
            war_log_dict[wID] = wjson

        memberJson = {
            'name': self.name,
            'last_update': self.timestamp,
            'time_in_home_clan': self.time_in_home_clan,
            'role': self.role,
            'current_clan': {
                'tag': self.clan.tag,
                'name': self.clan.name
                },
            'other_clans': self.other_clans,
            'town_hall': self.town_hall.level,
            'town_hall_weapon': self.town_hall.weapon,
            'clan_castle': self.clan_castle,
            'league': self.league.name,
            'trophies': self.trophies,
            'best_trophies': self.best_trophies,
            'war_stars': self.war_stars,
            'war_optin': self.war_optin,
            'builder_hall': self.builder_hall,
            'versus_trophies': self.versus_trophies,
            'best_versus_trophies': self.best_versus_trophies,
            'heroes': [h.to_json() for h in self.heroes],
            'troops': [t.to_json() for t in self.troops],
            'spells': [s.to_json() for s in self.spells],
            'pets': [p.to_json() for p in self.pets],
            'attack_wins': self.attack_wins.to_json(),
            'defense_wins': self.defense_wins.to_json(),
            'donations_sent': self.donations_sent.to_json(),
            'donations_rcvd': self.donations_rcvd.to_json(),
            'loot_gold': self.loot_gold.to_json(),
            'loot_elixir': self.loot_elixir.to_json(),
            'loot_darkelixir': self.loot_darkelixir.to_json(),
            'clangames': self.clangames.to_json(),
            'capitalcontribution': self.capitalcontribution.to_json(),
            'raid_log': raid_log_dict,
            'war_log': war_log_dict,
            }
        await alliance_file_handler(
            ctx=self.ctx,
            entry_type='members',
            tag=self.tag,
            new_data=allianceJson)

        await data_file_handler(
            ctx=self.ctx,
            file='members',
            tag=self.tag,
            new_data=memberJson)

    async def new_member(self,discord_user,home_clan):
        self.home_clan = home_clan
        self.is_member = True
        if discord_user == home_clan.leader:
            self.arix_rank = 'Leader'
        elif discord_user in home_clan.co_leaders:
            self.arix_rank = 'Co-Leader'
        elif discord_user in home_clan.elders:
            self.arix_rank = 'Elder'
        else:
            self.arix_rank = 'Member'
        self.discord_user = discord_user

    async def remove_member(self):
        self.arix_rank = 'Non-Member'
        self.is_member = False

    async def update_rank(self,new_rank):
        valid_ranks = ["Member","Elder","Co-Leader","Leader"]
        if new_rank not in valid_ranks:
            raise MemberPromoteError
        else:
            self.memberStatus = new_rank

    async def add_note(self,ctx,message):
        new_note = await aNote.create_new(ctx,message)
        self.notes.append(new_note)

        sorted_notes = sorted(self.notes,key=lambda n:(n.timestamp),reverse=False)
        self.notes = sorted_notes

    async def update_war(self,war_entry):
        player_log = aPlayerWarLog.from_war(war_entry)
        wID = player_log.wID
        self.warlog['wID'] = player_log

    async def update_raidweekend(self,raid_entry):
        player_log = aPlayerRaidLog.from_raid_member(raid_entry)
        rID = player_log.rID
        self.raidlog['rID'] = player_log

class aTownHall():
    def __init__(self,level=1,weapon=0):
        self.level = level
        self.weapon = weapon
        self.emote = emotes_townhall[self.level]
        if self.level >= 12:
            self.description = f"**{self.level}**-{self.weapon}"
        else:
            self.description = f"**{self.level}**"

class aPlayerStat():
    def __init__(self,inputJson):
        self.season = inputJson.get('season',0)
        self.lastupdate = inputJson.get('lastUpdate',0)

        if self.lastupdate >= 2000000000:
            self.statdisplay = 'max'

    def update_stat(self,new_value):
        if new_value >= self.lastupdate:
            stat_increment = new_value - self.lastupdate
        else:
            stat_increment = new_value
        self.season += stat_increment

    def set_baseline(self,base_value):
        self.lastupdate = base_value

    def to_json(self):
        statJson = {
            'season': self.season,
            'lastUpdate': self.lastupdate
            }
        return statJson

class aHero():
    def __init__(self):
        self.hero = None
        self.id = 0
        self.name = ''
        self.level = 0
        self.village = ''
        self.maxlevel_for_townhall = 0
        self.minlevel_for_townhall = 0
        self.is_rushed = False

    @classmethod
    def from_json(cls,inputJson):
        self = aHero()
        self.id = inputJson.get('id',0)
        self.name = inputJson.get('name','')
        self.level = inputJson.get('level',0)
        self.village = inputJson.get('village','')
        self.maxlevel_for_townhall = inputJson.get('maxlevel_for_townhall',0)
        self.minlevel_for_townhall = inputJson.get('minlevel_for_townhall',0)

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        else:
            self.is_rushed = False
        return self

    @classmethod
    def from_data(cls,gameData,th_level):
        self = aHero()
        self.hero = gameData

        self.id = getattr(self.hero,'id',0)
        self.name = getattr(self.hero,'name','')
        self.level = getattr(self.hero,'level',0)
        self.village = getattr(self.hero,'village','')

        maxlevel_for_townhall = self.hero.get_max_level_for_townhall(th_level)
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        minlevel_for_townhall = self.hero.get_max_level_for_townhall(th_level-1)
        self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        else:
            self.is_rushed = False
        return self

    def to_json(self):
        hJson = {
            'id': self.id,
            'name': self.name,
            'level': self.level,
            'village': self.village,
            'maxlevel_for_townhall': self.maxlevel_for_townhall,
            'minlevel_for_townhall': self.minlevel_for_townhall
            }
        return hJson

class aHeroPet():
    def __init__(self):
        self.pet = None
        self.id = 0
        self.name = ''
        self.level = 0
        self.maxlevel = 0

    @classmethod
    def from_json(cls,inputJson):
        self = aHeroPet()
        self.id = inputJson.get('id',0)
        self.name = inputJson.get('name','')
        self.level = inputJson.get('level',0)
        self.maxlevel = inputJson.get('maxlevel',0)
        return self

    @classmethod
    def from_data(cls,gameData):
        self = aHeroPet()
        self.pet = gameData

        self.id = getattr(self.pet,'id',0)
        self.name = getattr(self.pet,'name','')
        self.level = getattr(self.pet,'level',0)
        self.maxlevel = getattr(self.pet,'max_level',0)
        return self

    def to_json(self):
        pJson = {
            'id': self.id,
            'name': self.name,
            'level': self.level,
            'maxlevel': self.maxlevel,
            }
        return pJson

class aTroop():
    def __init__(self):
        self.troop = None
        self.id = 0
        self.name = ''
        self.level = 0
        self.village = ''
        self.is_elixir_troop = False
        self.is_dark_troop = False
        self.is_siege_machine = False
        self.is_super_troop = False
        self.original_troop = False
        self.maxlevel_for_townhall = 0
        self.minlevel_for_townhall = 0
        self.is_rushed = False

    @classmethod
    def from_json(cls,inputJson):
        self = aTroop()
        self.id = inputJson.get('id',0)
        self.name = inputJson.get('name','')
        self.level = inputJson.get('level',0)
        self.village = inputJson.get('village','')

        self.is_elixir_troop = inputJson.get('is_elixir_troop',False)
        self.is_dark_troop = inputJson.get('is_dark_troop',False)
        self.is_siege_machine = inputJson.get('is_siege_machine',False)
        self.is_super_troop = inputJson.get('is_super_troop',False)
        self.original_troop = inputJson.get('original_troop','')
        self.maxlevel_for_townhall = inputJson.get('maxlevel_for_townhall',0)
        self.minlevel_for_townhall = inputJson.get('minlevel_for_townhall',0)

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        return self

    @classmethod
    def from_data(cls,gameData,th_level):
        self = aTroop()
        self.troop = gameData

        self.id = getattr(self.troop,'id',0)
        self.name = getattr(self.troop,'name','')
        self.level = getattr(self.troop,'level',0)
        self.village = getattr(self.troop,'village','')

        self.is_elixir_troop = getattr(self.troop,'is_elixir_troop',False)
        self.is_dark_troop = getattr(self.troop,'is_dark_troop',False)
        self.is_siege_machine = getattr(self.troop,'is_siege_machine',False)
        self.is_super_troop = getattr(self.troop,'is_super_troop',False)
        self.original_troop = getattr(self.troop,'original_troop',None)

        maxlevel_for_townhall = self.troop.get_max_level_for_townhall(th_level)
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        minlevel_for_townhall = self.troop.get_max_level_for_townhall(th_level-1)
        self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        return self

    def to_json(self):
        tJson = {
            'id': self.id,
            'name': self.name,
            'level': self.level,
            'village': self.village,
            'is_elixir_troop': self.is_elixir_troop,
            'is_dark_troop': self.is_dark_troop,
            'is_siege_machine': self.is_siege_machine,
            'is_super_troop': self.is_super_troop,
            'original_troop': self.original_troop,
            'maxlevel_for_townhall': self.maxlevel_for_townhall,
            'minlevel_for_townhall': self.minlevel_for_townhall
            }
        return tJson

class aSpell():
    def __init__(self):
        self.spell = None
        self.id = 0
        self.name = ''
        self.level = 0
        self.village = ''
        self.is_elixir_spell = False
        self.is_dark_spell = False
        
        self.maxlevel_for_townhall = 0
        self.minlevel_for_townhall = 0
        self.is_rushed = False

    @classmethod
    def from_json(cls,inputJson):
        self = aSpell()
        self.id = inputJson.get('id',0)
        self.name = inputJson.get('name','')
        self.level = inputJson.get('level',0)
        self.village = inputJson.get('village','')

        self.is_elixir_spell = inputJson.get('is_elixir_spell',False)
        self.is_dark_spell = inputJson.get('is_dark_spell',False)
        
        self.maxlevel_for_townhall = inputJson.get('maxlevel_for_townhall',0)
        self.minlevel_for_townhall = inputJson.get('minlevel_for_townhall',0)

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        return self

    @classmethod
    def from_data(cls,gameData,th_level):
        self = aSpell()
        self.spell = gameData

        self.id = getattr(self.spell,'id',0)
        self.name = getattr(self.spell,'name','')
        self.level = getattr(self.spell,'level',0)
        self.village = getattr(self.spell,'village','')

        self.is_elixir_spell = getattr(self.spell,'is_elixir_spell',False)
        self.is_dark_spell = getattr(self.spell,'is_dark_spell',False)

        maxlevel_for_townhall = self.spell.get_max_level_for_townhall(th_level)
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        minlevel_for_townhall = self.spell.get_max_level_for_townhall(th_level-1)
        self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        return self

    def to_json(self):
        sJson = {
            'id': self.id,
            'name': self.name,
            'level': self.level,
            'village': self.village,
            'is_elixir_spell': self.is_elixir_spell,
            'is_dark_spell': self.is_dark_spell,
            'maxlevel_for_townhall': self.maxlevel_for_townhall,
            'minlevel_for_townhall': self.minlevel_for_townhall
            }
        return sJson

class aPlayerWarStats():
    def __init__(self,warlog):
        self.wars_participated = len(warlog)
        self.offense_stars = 0
        self.offense_destruction = 0
        self.defense_stars = 0
        self.defense_destruction = 0
        self.total_attacks = 0
        self.triples = 0
        self.missed_attacks = 0

        for wID, war in warlog.items():
            self.missed_attacks += (war.total_attacks - len(war.attacks))
            for a in war.attacks:
                self.offense_stars += a.stars
                self.offense_destruction += a.destruction
                self.total_attacks += 1
                if a.is_triple:
                    self.triples += 1

            self.defense_stars += getattr(war.best_opponent_attack,'stars',0)
            self.defense_destruction += getattr(war.best_opponent_attack,'destruction',0)

class aPlayerRaidStats():
    def __init__(self,raidlog):
        self.raids_participated = len(raidlog)
        self.raid_attacks = 0
        self.resources_looted = 0
        self.medals_earned = 0

        for rID, raid in raidlog.items():
            self.raid_attacks += raid.attack_count
            self.resources_looted += raid.resources_looted
            self.medals_earned += raid.medals_earned