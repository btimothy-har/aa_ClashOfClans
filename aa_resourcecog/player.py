import coc
import discord
import time
import pytz

from numerize import numerize
from itertools import chain
from datetime import datetime

from coc.ext import discordlinks

from .constants import clanRanks, emotes_townhall, emotes_builderhall, emotes_capitalhall, emotes_league, emotes_army, hero_availability, troop_availability, spell_availability, pet_availability
from .file_functions import get_current_season, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler

from .notes import aNote
from .clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from .raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aPlayerRaidLog
from .errors import TerminateProcessing, InvalidTag, error_end_processing

from .discordutils import convert_seconds_to_str, clash_embed

class ClashPlayerError(Exception):
    def __init__(self,message):
        self.message = message

########################################

### PLAYER OBJECT

########################################

class aPlayer(coc.Player):
    def __init__(self,**kwargs):
        ctx = kwargs.get('ctx',None)

        super().__init__(**kwargs)
        self.timestamp = time.time()

        self.discord_link = None
        self.discord_user = None

        self.readable_name = ""
        self.clan_castle = 0

        self.current_war = None
        self.current_raid_weekend = None

        self.clan_description = ''
        self.hero_description = ''

        self.hero_strength = 0
        self.max_hero_strength = 0
        self.min_hero_strength = 0
        self.hero_rushed_pct = 0

        self.troop_strength = 0
        self.max_troop_strength = 0
        self.min_troop_strength = 0
        self.troop_rushed_pct = 0

        self.spell_strength = 0
        self.max_spell_strength = 0
        self.min_spell_strength = 0
        self.spell_rushed_pct = 0

        self.overall_rushed_pct = 0

        #Membership Attributes
        self.home_clan = aClan()
        self.readable_name = self.name
        self.is_member = False
        self.is_arix_account = False
        self.arix_rank = 'Non-Member'
        self.notes = []

        #Membership Statistics
        self.last_update = time.time()
        self.current_season = aPlayerSeason(ctx,self,'current')
        self.season_data = []

        self.member_description = ""

        self.desc_title = ""
        self.desc_full_text = ""
        self.desc_summary_text = ""

    def __repr__(self):
        return f"Player {self.name} ({self.tag}) - AriX {self.arix_rank}"

    @classmethod
    async def create(cls,ctx,tag,**kwargs):
        refresh = kwargs.get('refresh',False)
        reset = kwargs.get('reset',False)
        init = False
        build = False

        tag = coc.utils.correct_tag(tag)

        if not coc.utils.is_valid_tag(tag):
            raise InvalidTag(tag)
            return None

        #get from cache
        if not reset and tag in list(ctx.bot.member_cache.keys()):
            self = ctx.bot.member_cache[tag]

            #override refresh if last 60 secs
            if (time.time() - self.timestamp) < 60:
                refresh = False

            #if more than 5mins, force refresh
            if (time.time() - self.timestamp) > 300:
                refresh = True
        else:
            init = True

        if init or refresh:
            build = True
        else:
            return self

        try:
            self = await ctx.bot.coc_client.get_player(tag,cls=aPlayer,ctx=ctx)
        except Exception as exc:
            raise TerminateProcessing(exc) from exc
            return None

        for season in ctx.bot.tracked_seasons:
            seasonStats = await data_file_handler(ctx,
                file='members',
                tag=self.tag,
                season=season)
            if seasonStats:
                stats = await aPlayerSeason.create(ctx,
                    player=self,
                    season=season,
                    memberStats=seasonStats)
                self.season_data.append(stats)

        #add to cache
        ctx.bot.member_cache[tag] = self

        self.readable_name = self.name

        if not self.clan:
            clan_tag = None
        else:
            clan_tag = self.clan.tag

        try:
            self.clan = await aClan.create(ctx,tag=clan_tag)
        except Exception as exc:
            raise TerminateProcessing(exc) from exc
            return None

        if self.clan:
            try:
                check_war = await aClanWar.get(ctx,clan=self.clan)
            except:
                pass
            else:
                if check_war:
                    if self.tag in [m.tag for m in check_war.members]:
                        self.current_war = check_war

            try:
                check_raid = await aRaidWeekend.get(ctx,clan=self.clan)
            except:
                pass
            else:
                if check_raid:
                    if self.tag in [m.tag for m in check_raid.members]:
                        self.current_raid_weekend = check_raid

        if self.clan.tag:
            self.clan_description = f"{str(self.role)} of {self.clan.name}"
        else:
            self.clan_description = "No Clan"

        ph_town_hall = aTownHall(level=self.town_hall,weapon=self.town_hall_weapon)
        self.town_hall = ph_town_hall
        self.clan_castle = sum([a.value for a in self.achievements if a.name=='Empire Builder'])

        self.heroes = []
        hero_d = [hero for (th,hero) in hero_availability.items() if th<=self.town_hall.level]
        for hero_name in list(chain.from_iterable(hero_d)):
            is_unlocked_at_this_level = False
            if hero_name in hero_availability[self.town_hall.level]:
                is_unlocked_at_this_level = True
            try:
                hero = self.get_hero(name=hero_name)
            except:
                hero = None

            if not hero:
                hero = ctx.bot.coc_client.get_hero(name=hero_name,townhall=self.town_hall.level)
            hero = aHero(hero,self.town_hall.level,is_unlocked_at_this_level)
            self.heroes.append(hero)

        self.troops = []
        troop_d = [troop for (th,troop) in troop_availability.items() if th<=self.town_hall.level]
        for troop_name in list(chain.from_iterable(troop_d)):
            is_unlocked_at_this_level = False
            if troop_name in troop_availability[self.town_hall.level]:
                is_unlocked_at_this_level = True
            try:
                troop = self.get_troop(name=troop_name,is_home_troop=True)
            except:
                troop = None

            if not troop:
                troop = ctx.bot.coc_client.get_troop(name=troop_name,townhall=self.town_hall.level)
            troop = aTroop(troop,self.town_hall.level,is_unlocked_at_this_level)
            self.troops.append(troop)

        self.spells = []
        spell_d = [spell for (th,spell) in spell_availability.items() if th<=self.town_hall.level]
        for spell_name in list(chain.from_iterable(spell_d)):
            is_unlocked_at_this_level = False
            if spell_name in spell_availability[self.town_hall.level]:
                is_unlocked_at_this_level = True
            try:
                spell = self.get_spell(name=spell_name)
            except:
                spell = None

            if not spell:
                spell = ctx.bot.coc_client.get_spell(name=spell_name,townhall=self.town_hall.level)
            spell = aSpell(spell,self.town_hall.level,is_unlocked_at_this_level)
            self.spells.append(spell)

        pets_placeholder = []
        pets_d = {th:pets for (th,pets) in pet_availability.items() if th<=self.town_hall.level}
        for th, pets in pets_d.items():
            minlevel = 0
            if th < self.town_hall.level:
                minlevel = 10
            for pet in pets:
                get_pet = [p for p in self.hero_pets if p.name==pet]
                if len(get_pet) == 0:
                    pet_object = aHeroPet.not_yet_unlocked(pet,minlevel)
                else:
                    pet_object = aHeroPet(get_pet[0],minlevel)
                pets_placeholder.append(pet_object)
        self.hero_pets = pets_placeholder

        self.hero_description = ""
        if self.town_hall.level >= 7:
            self.hero_description = f"{emotes_army['Barbarian King']} {sum([h.level for h in self.heroes if h.name=='Barbarian King'])}"
        if self.town_hall.level >= 9:
            self.hero_description += f"\u3000{emotes_army['Archer Queen']} {sum([h.level for h in self.heroes if h.name=='Archer Queen'])}"
        if self.town_hall.level >= 11:
            self.hero_description += f"\u3000{emotes_army['Grand Warden']} {sum([h.level for h in self.heroes if h.name=='Grand Warden'])}"
        if self.town_hall.level >= 13:
            self.hero_description += f"\u3000{emotes_army['Royal Champion']} {sum([h.level for h in self.heroes if h.name=='Royal Champion'])}"

        self.hero_strength = sum([hero.level for hero in self.heroes])
        self.max_hero_strength = sum([hero.maxlevel_for_townhall for hero in self.heroes])
        self.min_hero_strength = sum([hero.minlevel_for_townhall for hero in self.heroes])

        rushed_heroes = sum([(h.minlevel_for_townhall - h.level) for h in self.heroes if h.is_rushed])
        if self.min_hero_strength > 0:
            self.hero_rushed_pct = round((rushed_heroes / self.min_hero_strength)*100,2)

        self.troop_strength = sum([troop.level for troop in self.troops])
        self.max_troop_strength = (sum([troop.maxlevel_for_townhall for troop in self.troops]) + sum([pet.maxlevel_for_townhall for pet in self.hero_pets]))
        self.min_troop_strength = (sum([troop.minlevel_for_townhall for troop in self.troops]) + sum([pet.minlevel_for_townhall for pet in self.hero_pets]))

        rushed_troops = sum([(t.minlevel_for_townhall - t.level) for t in self.troops if t.is_rushed]) + sum([(p.minlevel_for_townhall - p.level) for p in self.hero_pets if p.level < p.minlevel_for_townhall])
        if self.min_troop_strength > 0:
            self.troop_rushed_pct = round((rushed_troops / self.min_troop_strength)*100,2)

        self.spell_strength = sum([spell.level for spell in self.spells])
        self.max_spell_strength = (sum([spell.maxlevel_for_townhall for spell in self.spells]))
        self.min_spell_strength = (sum([spell.minlevel_for_townhall for spell in self.spells]))

        rushed_spells = sum([(s.minlevel_for_townhall - s.level) for s in self.spells if s.is_rushed])
        if self.min_spell_strength > 0:
            self.spell_rushed_pct = round((rushed_spells / self.min_spell_strength)*100,2)

        if self.min_hero_strength + self.min_troop_strength + self.min_spell_strength > 0:
            rushed_pct = (rushed_heroes + rushed_troops + rushed_spells) / (self.min_hero_strength + self.min_troop_strength + self.min_spell_strength)
            self.overall_rushed_pct = round(rushed_pct*100,2)

        memberInfo = await alliance_file_handler(ctx,'members',self.tag)
        #From AriX Data File
        if memberInfo:

            home_clan_json = memberInfo.get('home_clan',None)

            if isinstance(home_clan_json,dict):
                home_clan_tag = home_clan_json['tag']
            else:
                home_clan_tag = home_clan_json

            self.home_clan = await aClan.create(ctx,tag=home_clan_tag)
            self.readable_name = memberInfo.get('readable_name',self.name)
            self.is_member = memberInfo.get('is_member',False)
            self.is_arix_account = True

            self.discord_user = int(memberInfo.get('discord_user',0))

            if self.is_member:
                if self.discord_user == self.home_clan.leader:
                    self.arix_rank = 'Leader'
                elif self.discord_user in self.home_clan.co_leaders:
                    self.arix_rank = 'Co-Leader'
                elif self.discord_user in self.home_clan.elders:
                    self.arix_rank = 'Elder'
                else:
                    self.arix_rank = 'Member'
            else:
                self.arix_rank = 'Non-Member'

            notes = [aNote.from_json(ctx,n) for n in memberInfo.get('notes',[])]
            self.notes = sorted(notes,key=lambda n:(n.timestamp),reverse=True)

        memberStats = await data_file_handler(ctx,'members',self.tag)

        if memberStats:
            self.last_update = memberStats['last_update']
            self.current_season = await aPlayerSeason.create(ctx,
                player=self,
                season='current',
                memberStats=memberStats)

        self.desc_title = f"{self.name}"

        self.member_description = ""
        if self.is_member and self.arix_rank not in ['Guest','Non-Member']:
            self.member_description = f"***{self.home_clan.emoji} {self.arix_rank} of {self.home_clan.name}***"
        elif self.is_arix_account:
            self.member_description = f"***<a:aa_AriX:1031773589231374407> AriX Guest Account***"

        self.desc_full_text = f"{self.member_description}"
        if self.member_description:
            self.desc_full_text += "\n"

        self.desc_full_text += (
            f"<:Exp:825654249475932170> {self.exp_level}\u3000<:Clan:825654825509322752> {self.clan_description}"
            + f"\n{self.town_hall.emote} {self.town_hall.description}\u3000{emotes_league[self.league.name]} {self.trophies} (best: {self.best_trophies})")

        if self.town_hall.level >= 7:
            self.desc_full_text += f"\n{self.hero_description}"

        self.desc_full_text += f"\n[Player Link: {self.tag}]({self.share_link})"

        self.desc_summary_text = f"{self.town_hall.emote} {self.town_hall.description}\u3000"

        if self.is_member and self.arix_rank not in ['Guest','Non-Member']:
            self.desc_summary_text += self.member_description
        else:
            self.desc_summary_text += f"<:Clan:825654825509322752> {self.clan_description}"

        if not self.discord_user:
            get_links = await ctx.bot.discordlinks.get_links(self.tag)
            self.discord_user = get_links[0][1]

        self.discord_user = await aMember.create(ctx,user_id=self.discord_user)

        return self

    async def save_to_json(self,ctx):
        allianceJson = {
            'name':self.name,
            'readable_name': self.readable_name,
            'is_member': self.is_member,
            'home_clan': self.home_clan.tag,
            'rank':self.arix_rank,
            'discord_user':self.discord_user,
            'notes':[n.to_json() for n in self.notes],
            }

        memberJson = {
            'name': self.name,
            'last_update': self.last_update,
            'current_clan': self.clan.tag,
            'role': str(self.role),
            'time_in_home_clan': self.current_season.time_in_home_clan,
            'other_clans': [c.tag for c in self.current_season.other_clans],
            'attacks': self.current_season.attacks.to_json(),
            'defenses': self.current_season.defenses.to_json(),
            'donations_sent': self.current_season.donations_sent.to_json(),
            'donations_rcvd': self.current_season.donations_rcvd.to_json(),
            'loot_gold': self.current_season.loot_gold.to_json(),
            'loot_elixir': self.current_season.loot_elixir.to_json(),
            'loot_darkelixir': self.current_season.loot_darkelixir.to_json(),
            'clangames': self.current_season.clangames.to_json(),
            'capitalcontribution': self.current_season.capitalcontribution.to_json(),
            'raid_log': [rid for (rid,raid) in self.current_season.raidlog.items()],
            'war_log': [wid for (wid,war) in self.current_season.warlog.items()],
            }
        await alliance_file_handler(
            ctx=ctx,
            entry_type='members',
            tag=self.tag,
            new_data=allianceJson)

        await data_file_handler(
            ctx=ctx,
            file='members',
            tag=self.tag,
            new_data=memberJson)


    async def update_stats(self,ctx):
        if self.clan.tag == self.home_clan.tag:
            self.current_season.time_in_home_clan += (self.timestamp - self.last_update)
        elif self.clan.tag not in [c.tag for c in self.other_clans]:
            self.other_clans.append(self.clan)

        self.current_season.attacks.update_stat(self.attack_wins)
        self.current_season.defenses.update_stat(self.defense_wins)

        self.current_season.donations_sent.update_stat(self.donations)
        self.current_season.donations_rcvd.update_stat(self.received)

        for achievement in self.achievements:
            if achievement.name == 'Gold Grab':
                self.current_season.loot_gold.update_stat(achievement.value)
            if achievement.name == 'Elixir Escapade':
                self.current_season.loot_elixir.update_stat(achievement.value)
            if achievement.name == 'Heroic Heist':
                self.current_season.loot_darkelixir.update_stat(achievement.value)
            if achievement.name == 'Most Valuable Clanmate':
                self.current_season.capitalcontribution.update_stat(achievement.value)

        self.last_update = self.timestamp
        await self.save_to_json(ctx)


    async def set_baselines(self,ctx):
        if self.clan.tag not in [c.tag for c in self.other_clans]:
            self.other_clans.append(self.clan)

        self.current_season.attacks.set_baseline(self.attack_wins)
        self.current_season.defenses.set_baseline(self.defense_wins)

        self.current_season.donations_sent.set_baseline(self.donations)
        self.current_season.donations_rcvd.set_baseline(self.received)

        self.current_season.clangames.set_baseline(self)

        for achievement in self.achievements:
            if achievement.name == 'Gold Grab':
                self.current_season.loot_gold.set_baseline(achievement.value)
            if achievement.name == 'Elixir Escapade':
                self.current_season.loot_elixir.set_baseline(achievement.value)
            if achievement.name == 'Heroic Heist':
                self.current_season.loot_darkelixir.set_baseline(achievement.value)
            if achievement.name == 'Most Valuable Clanmate':
                self.current_season.capitalcontribution.set_baseline(achievement.value)

        self.last_update = self.timestamp
        await self.save_to_json(ctx)


    async def set_readable_name(self,ctx,name):
        self.readable_name = name
        await self.save_to_json(ctx)


    async def update_warlog(self,ctx):
        if self.current_war.state in ['inWar','warEnded']:
            await self.current_war.save_to_json(ctx)

            if self.current_war.state in ['warEnded']:
                if self.current_war.war_id in [wid for (wid,war) in self.current_season.warlog.items()]:
                    self.current_season.warlog[self.current_war.war_id] = self.current_war

            else:
                self.current_season.warlog[self.current_war.war_id] = self.current_war

        await self.save_to_json(ctx)


    async def update_raid_weekend(self,ctx):
        await self.current_raid_weekend.save_to_json()

        if self.current_raid_weekend.state in ['ended']:
            if self.current_raid_weekend.raid_id in [rid for (rid,raid) in self.current_season.raidlog.items()]:
                self.current_season.raidlog[self.current_raid_weekend.raid_id] = self.current_raid_weekend

        else:
            self.current_season.raidlog[self.current_raid_weekend.raid_id] = self.current_raid_weekend

        await self.save_to_json(ctx)


    async def new_member(self,ctx,discord_user,home_clan=None):
        if home_clan:
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

        else:
            self.home_clan = await aClan.create(ctx,tag=None)
            self.is_member = False
            self.arix_rank = 'Non-Member'

        self.discord_user = await aMember.create(ctx,user_id=discord_user)

        await self.set_baselines(ctx)
        await self.save_to_json(ctx)


    async def remove_member(self,ctx):
        self.home_clan = await aClan.create(ctx,tag=None)
        self.arix_rank = 'Non-Member'
        self.is_member = False

        await self.save_to_json(ctx)


    async def add_note(self,ctx,message):
        new_note = aNote.create_new(ctx,message)
        self.notes.append(new_note)

        sorted_notes = sorted(self.notes,key=lambda n:(n.timestamp),reverse=False)
        self.notes = sorted_notes

        await self.save_to_json(ctx)


class aPlayerSeason():
    def __init__(self,ctx,player,season):
        self.player = player
        self.season = season
        self.time_in_home_clan = 0
        self.other_clans = []
        self.attacks = aPlayerStat({})
        self.defenses = aPlayerStat({})

        self.donations_sent = aPlayerStat({})
        self.donations_rcvd = aPlayerStat({})

        self.loot_gold = aPlayerStat({})
        self.loot_elixir = aPlayerStat({})
        self.loot_darkelixir = aPlayerStat({})

        self.clangames = aPlayerClanGames(self,self.season)

        self.capitalcontribution = aPlayerStat({})

        self.warlog = {}
        self.war_stats = aPlayerWarStats()

        self.raidlog = {}
        self.raid_stats = aPlayerRaidStats()

    @classmethod
    async def create(cls,ctx,player,season,memberStats):
        self = aPlayerSeason(ctx,player,season)

        self.time_in_home_clan = memberStats.get('time_in_home_clan',0)

        self.other_clans = [await aClan.create(ctx,tag=c) for c in memberStats.get('other_clans',[])]

        self.attacks = aPlayerStat(memberStats.get('attacks',{}))
        self.defenses = aPlayerStat(memberStats.get('defenses',{}))

        self.donations_sent = aPlayerStat(memberStats.get('donations_sent',{}))
        self.donations_rcvd = aPlayerStat(memberStats.get('donations_rcvd',{}))

        self.loot_gold = aPlayerStat(memberStats.get('loot_gold',{}))
        self.loot_elixir = aPlayerStat(memberStats.get('loot_elixir',{}))
        self.loot_darkelixir = aPlayerStat(memberStats.get('loot_darkelixir',{}))

        self.clangames = await aPlayerClanGames.create(ctx,player=self.player,input_json=memberStats.get('clangames',{}),season=self.season)

        self.capitalcontribution = aPlayerStat(memberStats.get('capitalcontribution',{}))

        try:
            if isinstance(memberStats.get('war_log',[]),dict):
                legacy_warlog = {wID:aPlayerWarLog.from_json(wID,wl) for (wID,wl) in memberStats['war_log'].items()}

                war_ids = []
                for war in legacy_warlog:
                    tag_id = war.clan.tag + war.opponent.tag
                    tag_id = tag_id.replace('#','')
                    tag_id = ''.join(sorted(tag_id))

                    new_id = tag_id + f"{str(int(float(war.wID)))}"
                    war_ids.append(new_id)

                self.warlog = {wid:await aClanWar.get(ctx,war_id=wid) for wid in war_ids}
            else:
                self.warlog = {wid:await aClanWar.get(ctx,war_id=wid) for wid in memberStats.get('war_log',[])}
        except:
            self.warlog = {}

        try:
            if isinstance(memberStats.get('raid_log',[]),dict):
                legacy_raidlog = {rID:aPlayerRaidLog.from_json(rID,self,rl) for (rID,rl) in memberStats['raid_log'].items()}

                raid_ids = []
                for raid in legacy_raidlog:
                    tag_id = raid.clan_tag
                    tag_id = tag_id.replace('#','')

                    new_id = tag_id + f"{str(int(float(raid.rID)))}"
                    raid_ids.append(new_id)

                self.raidlog = {rid:await aRaidWeekend.get(ctx,raid_id=rid) for rid in raid_ids}
            else:
                self.raidlog = {rid:await aRaidWeekend.get(ctx,raid_id=rid) for rid in memberStats.get('raid_log',[])}
        except:
            self.raidlog = {}

        self.war_stats = await aPlayerWarStats.compute(ctx=ctx,player=self.player,warlog=self.warlog)
        self.raid_stats = await aPlayerRaidStats.compute(ctx=ctx,player=self.player,raidlog=self.raidlog)
        return self

class aTownHall():
    def __init__(self,level=1,weapon=0):
        self.level = level
        self.weapon = weapon
        self.emote = emotes_townhall[self.level]
        self.emoji = self.emote
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
        elif self.season >= 100000:
            self.statdisplay = numerize.numerize(self.season,1)
        else:
            self.statdisplay = f"{self.season:,}"

    def update_stat(self,new_value):
        if new_value >= self.lastupdate:
            stat_increment = new_value - self.lastupdate
        else:
            stat_increment = new_value
        self.season += stat_increment
        self.lastupdate = new_value

    def set_baseline(self,base_value):
        self.lastupdate = base_value

    def to_json(self):
        statJson = {
            'season': self.season,
            'lastUpdate': self.lastupdate
            }
        return statJson

class aPlayerClanGames():
    def __init__(self,player,season):

        if season == 'current':
            sm = datetime.now(pytz.utc).month
            sy = datetime.now(pytz.utc).year
        else:
            season = season.split('-')
            sm = int(season[0])
            sy = int(season[1])

        self.player = player
        self.games_start = datetime(sy, sm, 22, 8, 0, 0, 0, tzinfo=pytz.utc).timestamp()
        self.games_end = datetime(sy, sm, 28, 8, 0, 0, 0, tzinfo=pytz.utc).timestamp()
        self.score = 0
        self.clan = None
        self.starting_time = 0
        self.ending_time = 0
        self.last_updated = 0

    @classmethod
    async def create(cls,ctx,player,**kwargs):
        input_json = kwargs.get('json',None)
        season = kwargs.get('season',None)

        self = aPlayerClanGames(player,season)

        if input_json:
            self.score = inputJson.get('score',0)
            self.clan = await aClan.create(ctx,tag=inputJson.get('clan',None))
            self.ending_time = inputJson.get('ending_time',0)
            self.last_updated = inputJson.get('last_updated',0)

        return self

    async def set_baseline(self):
        self.last_updated = [a.value for a in self.player.achievements if a.name == 'Games Champion'][0]

    async def calculate_clangames(self):
        max_score = 4000
        if self.player.timestamp >= self.games_start and self.player.timestamp < self.games_end:
            new_score = [a.value for a in self.player.achievements if a.name == 'Games Champion'][0]

            if (new_score - self.last_updated) > 0:

                if self.score == 0:
                    self.clan = self.player.clan
                    self.starting_time = time

                self.score += (new_score - self.last_updated)
                self.last_updated = new_score

                if self.score >= max_score:
                    self.ending_time = self.player.timestamp
                    self.score = max_score
        else:
            self.last_updated = [a.value for a in self.player.achievements if a.name == 'Games Champion'][0]

    def to_json(self):
        clangamesJson = {
            'clan': getattr(self.clan,'tag',None),
            'score': self.score,
            'last_updated': self.last_updated,
            'ending_time': self.ending_time
            }
        return clangamesJson

class aHero():
    def __init__(self,data,townhall_level,is_unlocked_at_this_level=False):

        self.id = getattr(data,'id',0)
        self.name = getattr(data,'name','')

        self.level = getattr(data,'level',0)
        if not isinstance(self.level,int):
            self.level = 0

        self.village = getattr(data,'village','')
        if self.village == '':
            self.village = 'home'

        maxlevel_for_townhall = data.get_max_level_for_townhall(max(townhall_level,3))
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        try:
            minlevel_for_townhall = data.get_max_level_for_townhall(max(townhall_level-1,3))
            self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)
        except:
            self.minlevel_for_townhall = 0

        if is_unlocked_at_this_level:
            self.minlevel_for_townhall = 0

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        else:
            self.is_rushed = False

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
    def __init__(self,data=None,minimum_level=None):
        self.id = getattr(data,'id',0)
        self.name = getattr(data,'name','')
        self.level = getattr(data,'level',0)
        self.minlevel_for_townhall = minimum_level
        self.maxlevel_for_townhall = getattr(data,'max_level',0)

    @classmethod
    def not_yet_unlocked(cls,pet_name,minimum_level):
        self = aHeroPet()
        self.id = 0
        self.name = pet_name
        self.level = 0
        self.minlevel_for_townhall = minimum_level
        self.maxlevel_for_townhall = 10
        return self

    def to_json(self):
        pJson = {
            'id': self.id,
            'name': self.name,
            'level': self.level,
            'minlevel_for_townhall': self.minlevel_for_townhall,
            'maxlevel_for_townhall': self.maxlevel_for_townhall,
            }
        return pJson

class aTroop():
    def __init__(self,data,townhall_level,is_unlocked_at_this_level=False):
        self.id = getattr(data,'id',0)
        self.name = getattr(data,'name','')

        self.level = getattr(data,'level',0)
        if not isinstance(self.level,int):
            self.level = 0

        self.village = getattr(data,'village','')
        if self.village == '':
            self.village = 'home'

        self.is_elixir_troop = getattr(data,'is_elixir_troop',False)
        self.is_dark_troop = getattr(data,'is_dark_troop',False)
        self.is_siege_machine = getattr(data,'is_siege_machine',False)
        self.is_super_troop = getattr(data,'is_super_troop',False)
        self.original_troop = getattr(data,'original_troop',None)

        maxlevel_for_townhall = data.get_max_level_for_townhall(max(townhall_level,3))
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        minlevel_for_townhall = data.get_max_level_for_townhall(max(townhall_level-1,3))
        self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)

        if is_unlocked_at_this_level:
            self.minlevel_for_townhall = 0

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        else:
            self.is_rushed = False

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
    def __init__(self,data,townhall_level,is_unlocked_at_this_level=False):
        self.id = getattr(data,'id',0)
        self.name = getattr(data,'name','')
        if not data.level:
            self.level = 0
        else:
            self.level = getattr(data,'level',0)
        self.village = getattr(data,'village','')

        self.is_elixir_spell = getattr(data,'is_elixir_spell',False)
        self.is_dark_spell = getattr(data,'is_dark_spell',False)

        maxlevel_for_townhall = data.get_max_level_for_townhall(max(townhall_level,3))
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        minlevel_for_townhall = data.get_max_level_for_townhall(max(townhall_level-1,3))
        self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)

        if is_unlocked_at_this_level:
            self.minlevel_for_townhall = 0

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        else:
            self.is_rushed = False

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
    def __init__(self):

        self.wars_participated = 0
        self.attack_count = 0

        self.offense_stars = 0
        self.offense_destruction = 0

        self.defense_count = 0
        self.defense_stars = 0
        self.defense_destruction = 0

        self.triples = 0
        self.unused_attacks = 0

        self.average_attack_duration = 0

    @classmethod
    async def compute(self,ctx,player,warlog):
        self = aPlayerWarStats()

        total_duration = 0

        for war in warlog:
            warmember = [m for m in war.members if m.tag == player.tag][0]
            clan = await aClan.create(ctx,tag=warmember.clan_tag)

            if war.type == 'random' and clan.is_alliance_clan:
                self.wars_participated += 1
                self.attack_count += len(warmember.attacks)

                self.offense_stars += sum([a.stars for a in warmember.attacks])
                self.offense_destruction += sum([a.destruction for a in warmember.attacks])

                self.defense_count += warmember.defense_count
                self.defense_stars += getattr(warmember.best_opponent_attack,'stars',0)
                self.defense_destruction += getattr(warmember.best_opponent_attack,'destruction',0)

                self.triples += len([a for a in warmember.attacks if a.is_triple])
                self.unused_attacks += warmember.unused_attacks

                total_duration += sum([a.duration for a in warmember.attacks])

        if self.attack_count > 0:
            self.average_attack_duration = total_duration / self.attack_count

        return self

class aPlayerRaidStats():
    def __init__(self):
        self.raids_participated = 0
        self.raid_attacks = 0
        self.resources_looted = 0
        self.medals_earned = 0

    @classmethod
    async def compute(self,ctx,player,raidlog):
        self = aPlayerRaidStats()

        for raid in raidlog:
            raidmember = [m for m in raid.members if m.tag == player.tag][0]
            clan = await aClan.create(ctx,tag=raid.clan_tag)

            if clan.is_alliance_clan:
                self.raids_participated += 1
                self.raid_attacks += raidmember.attack_count
                self.resources_looted += raidmember.capital_resources_looted

########################################

### CLAN OBJECT

########################################

class aClan(coc.Clan):
    def __init__(self,**kwargs):

        tag = kwargs.get('tag',None)
        load = kwargs.get('load',False)

        if tag or load:
            super().__init__(**kwargs)
        else:
            self.tag = None
            self.name = "No Clan"

        self.timestamp = time.time()

        #Alliance Attributes
        self.is_alliance_clan = False
        self.abbreviation = ''
        self.description = None
        self.level = 0
        self.capital_hall = 0
        self.emoji = ''
        self.leader = 0
        self.co_leaders = []
        self.elders = []
        self.member_count = 0
        self.recruitment_level = []
        self.notes = []

        self.member_role = 0
        self.elder_role = 0
        self.coleader_role = 0

        self.announcement_channel = 0
        self.reminder_channel = 0
        self.send_war_reminder = False
        self.send_raid_reminder = False

        self.war_reminder_intervals = []
        self.raid_reminder_intervals = []

        self.war_reminder_tracking = []
        self.raid_reminder_tracking = []

        #Clan Statuses
        self.war_state = ''
        self.war_state_change = False

        self.raid_weekend_state = ''
        self.raid_state_change = False

        self.war_log = {}
        self.raid_log = {}

        self.current_war = None
        self.current_raid_weekend = None

        self.desc_title = ""
        self.desc_full_text = ""
        self.desc_summary_text = ""

    def __repr__(self):
        return f"Clan {self.tag} {self.name} generated on {datetime.fromtimestamp(self.timestamp).strftime('%m%d%Y%H%M%S')}"

    @classmethod
    async def create(cls,ctx,tag,**kwargs):
        refresh = kwargs.get('refresh',False)
        reset = kwargs.get('reset',False)
        init = False
        build = False

        #return empty clan
        if not tag:
            self = aClan()
            return self

        tag = coc.utils.correct_tag(tag)
        if not coc.utils.is_valid_tag(tag):
            raise InvalidTag(tag)
            return None

        if not reset and tag in list(ctx.bot.clan_cache.keys()):
            self = ctx.bot.clan_cache[tag]

            #override refresh if last 60 secs
            if (time.time() - self.timestamp) < 60:
                refresh = False

            #if more than 10mins, force refresh
            if (time.time() - self.timestamp) > 600:
                refresh = True
        else:
            init = True

        if init or refresh:
            build = True
        else:
            return self
        if not build:
            return self

        try:
            self = await ctx.bot.coc_client.get_clan(tag=tag,cls=aClan,load=True)
        except Exception as exc:
            raise TerminateProcessing(exc) from exc
            return None

        #add to cache
        ctx.bot.clan_cache[tag] = self

        clanInfo = await alliance_file_handler(
            ctx=ctx,
            entry_type='clans',
            tag=self.tag)
        memberInfo = await alliance_file_handler(
            ctx=ctx,
            entry_type='members',
            tag="**")
        warLog = await data_file_handler(
            ctx=ctx,
            file='warlog',
            tag=self.tag)
        raidLog = await data_file_handler(
            ctx=ctx,
            file='capitalraid',
            tag=self.tag)

        try:
            self.capital_hall = [district.hall_level for district in self.capital_districts if district.name=="Capital Peak"][0]
        except:
            self.capital_hall = 0

        self.current_war = await aClanWar.get(ctx,clan=self)
        self.current_raid_weekend = await aRaidWeekend.get(ctx,clan=self)

        #Alliance Attributes
        if clanInfo:
            self.is_alliance_clan = True
            self.abbreviation = clanInfo.get('abbr','')
            self.emoji = clanInfo.get('emoji','')
            if clanInfo.get('description',None):
                self.description = clanInfo['description']

            self.leader = clanInfo.get('leader',0)
            self.co_leaders = clanInfo.get('co_leaders',[])
            self.elders = clanInfo.get('elders',[])
            self.recruitment_level = clanInfo.get('recruitment',[])
            self.recruitment_level.sort()

            notes = [aNote.from_json(ctx,n) for n in clanInfo.get('notes',[])]
            self.notes = sorted(notes,key=lambda n:(n.timestamp),reverse=True)

            self.member_role = clanInfo.get('member_role',0)
            self.elder_role = clanInfo.get('elder_role',0)
            self.coleader_role = clanInfo.get('coleader_role',0)

            self.announcement_channel = clanInfo.get('announcement_channel',0)
            self.reminder_channel = clanInfo.get('reminder_channel',0)
            self.send_war_reminder = clanInfo.get('send_war_reminder',False)
            self.send_raid_reminder = clanInfo.get('send_raid_reminder',False)

            self.war_reminder_intervals = clanInfo.get('war_reminder_intervals',[])
            self.raid_reminder_intervals = clanInfo.get('raid_reminder_intervals',[])

            self.war_reminder_tracking = clanInfo.get('war_reminder_tracking',[])
            self.raid_reminder_tracking = clanInfo.get('raid_reminder_tracking',[])

            self.war_state = clanInfo.get('war_state','')
            self.raid_weekend_state = clanInfo.get('raid_weekend_state','')

        if memberInfo:
            memberTags = list(memberInfo.keys())

            self.arix_members = [p for p in [await aPlayer.create(ctx,tag=tag) for tag in memberTags] if p.is_member and p.home_clan.tag == self.tag]
            self.arix_members = sorted(self.arix_members,key=lambda x:(clanRanks.index(x.arix_rank),x.exp_level,x.town_hall.level),reverse=True)
            self.arix_member_count = len(self.arix_members)

        try:
            if isinstance(warLog,dict):
                self.war_log = {wid:await aClanWar.get(ctx,clan=self,json=data) for (wid,data) in warLog.items()}
            else:
                self.war_log = {wid:await aClanWar.get(ctx,clan=self,war_id=wid) for wid in clanInfo.get('war_log',[])}
        except:
            self.war_log = {}

        try:
            if isinstance(raidLog,dict):
                self.raid_log = {rid:await aRaidWeekend.get(ctx,clan=self,json=data) for (rid,data) in raidLog.items()}
            else:
                self.raid_log = {rid:await aRaidWeekend.get(ctx,clan=self,raid_id=rid) for rid in clanInfo.get('raid_log',[])}
        except:
            self.raid_log = []

        if self.tag:
            self.desc_title = f"{self.name} ({self.tag})"

            war_league_str = ""
            if self.war_league:
                war_league_str = f"{emotes_league[self.war_league.name]} {self.war_league.name}"

            self.desc_full_text = (
                    f"<:Clan:825654825509322752> Level {self.level}\u3000{emotes_capitalhall[self.capital_hall]} CH {self.capital_hall}\u3000<:Members:1040672942524215337> {self.member_count}"
                +   f"\n{war_league_str}\n<:ClanWars:825753092230086708> W{self.war_wins}/D{self.war_ties}/L{self.war_losses} (Streak: {self.war_win_streak})"
                +   f"\n[Clan Link: {self.tag}]({self.share_link})")

            self.desc_summary_text = f"<:Clan:825654825509322752> Level {self.level}\u3000{emotes_capitalhall[self.capital_hall]} CH {self.capital_hall}\u3000{war_league_str}"

        return self


    async def save_to_json(self,ctx):
        allianceJson = {
            'name':self.name,
            'abbr':self.abbreviation,
            'emoji':self.emoji,
            'description': self.description,
            'level': self.level,
            'capital_hall': self.capital_hall,
            'leader':self.leader,
            'co_leaders': self.co_leaders,
            'elders': self.elders,
            'recruitment': self.recruitment_level,
            'notes': [n.to_json() for n in self.notes],
            'member_role': self.member_role,
            'elder_role': self.elder_role,
            'coleader_role': self.coleader_role,
            'announcement_channel': self.announcement_channel,
            'reminder_channel': self.reminder_channel,
            'send_war_reminder': self.send_war_reminder,
            'send_raid_reminder': self.send_raid_reminder,
            'war_reminder_intervals': self.war_reminder_intervals,
            'raid_reminder_intervals': self.raid_reminder_intervals,
            'war_reminder_tracking': self.war_reminder_tracking,
            'raid_reminder_tracking': self.raid_reminder_tracking,
            'war_state': self.war_state,
            'war_log': [wid for (wid,war) in self.war_log.items()],
            'raid_weekend_state': self.raid_weekend_state,
            'raid_log': [rid for (rid,raid) in self.raid_log.items()],
            }

        await alliance_file_handler(
            ctx=ctx,
            entry_type='clans',
            tag=self.tag,
            new_data=allianceJson)

    async def update_clan_war(self,ctx):
        update_summary = ""

        self.war_state_change = False

        if not self.current_war:
            self.war_state = 'notInWar'
            return None

        if self.current_war.state != self.war_state:
            self.war_state_change = True

        self.war_state = self.current_war.state

        self.war_log[self.current_war.war_id] = self.current_war

        await self.save_to_json(ctx)

        if self.current_war.type == 'random':
            if self.war_state_change and self.current_war.state == 'inWar':
                self.war_reminder_tracking = self.war_reminder_intervals
                update_summary += f"\n> - War vs {self.current_war.opponent.name} has started!"

            if self.current_war.state == 'inWar' and self.send_war_reminder and len(self.war_reminder_tracking) > 0:
                ch = ctx.bot.get_channel(self.reminder_channel)
                remaining_time = self.current_war.end_time - time.time()

                if remaining_time <= (self.war_reminder_tracking[0] * 3600):
                    next_reminder = self.war_reminder_tracking.pop(0)

                    ping_members = [await aPlayer.create(ctx,tag=m.tag) for m in [m for m in self.current_war.clan.members if m.unused_attacks > 0]]
                    ping_list = [m for m in ping_members if m.discord_user.discord_member]

                    ping_dict = {}
                    for m in ping_list:
                        if m.discord_user.user_id not in list(ping_dict.keys()):
                            ping_dict[m.discord_user.user_id] = []

                        ping_dict[m.discord_user.user_id].append(m)

                    if remaining_time < 3600:
                        ping_str = f"There is **less than 1 hour** left in Clan Wars and you have **NOT** used all your attacks.\n\n"

                    else:
                        dd, hh, mm, ss = await convert_seconds_to_str(ctx,remaining_time)
                        ping_str = f"Clan War ends in **{int(hh)} hours, {int(mm)} minutes**. You have **NOT** used all your attacks.\n\n"

                    for (uid,accounts) in ping_dict.items():
                        account_str = [f"{emotes_townhall[a.town_hall.level]} {a.name}" for a in accounts]
                        ping_str += f"<@{uid}> ({', '.join(account_str)})\n"

                    #override to war channel for PR
                    if self.abbreviation == 'PR':
                        ch = ctx.bot.get_channel(733000312180441190)
                        await ch.send(ping_str)
                    else:
                        await ch.send(ping_str)

                    update_summary += f"\n> - War reminders sent for {len(ping_list)} members."

        return update_summary

    async def update_raid_weekend(self,ctx):
        update_summary = ""

        self.raid_state_change = False

        if self.current_raid_weekend.state != self.raid_weekend_state:
            self.raid_state_change = True

        self.raid_weekend_state = self.current_raid_weekend.state

        self.raid_log[self.current_raid_weekend.raid_id] = self.current_raid_weekend

        await self.save_to_json(ctx)

        #new raid weekend
        if self.raid_state_change:
            if self.current_raid_weekend.state == 'ongoing':
                self.raid_reminder_tracking = self.raid_reminder_intervals
                update_summary += f"\n> - Raid Weekend has started!"

            if self.announcement_channel and self.current_raid_weekend.state == 'ended':
                results_embed = await self.current_raid_weekend.get_results_embed(ctx)
                ch = ctx.bot.get_channel(self.announcement_channel)
                await ch.send(embed=results_embed)
                update_summary += f"\n> - Raid Weekend is now over."

        #raid reminders
        if len(self.raid_reminder_tracking) > 0 and self.current_raid_weekend.state == 'ongoing':

            remaining_time = self.current_raid_weekend.end_time - time.time()

            if remaining_time <= (self.raid_reminder_tracking[0] * 3600):
                next_reminder = self.raid_reminder_tracking.pop(0)

                if next_reminder == 24 and self.announcement_channel:
                    ch = ctx.bot.get_channel(self.announcement_channel)

                    raid_weekend_1day_embed = await clash_embed(ctx,
                        message="**There is 1 Day left in Raid Weekend.**\nAlternate accounts are now allowed to fill up the remaining slots.",
                        show_author=False)

                    if self.member_role:
                        role = ctx.bot.alliance_server.get_role(self.member_role)
                        rm = discord.AllowedMentions(roles=True)
                        await ch.send(content=f"{role.mention}",embed=raid_weekend_1day_embed,allowed_mentions=rm)
                    else:
                        await ch.send(embed=raid_weekend_1day_embed)

                    update_summary += f"\n> - 24 hours left in Raid Weekend."


                if self.send_raid_reminder and self.reminder_channel:
                    ch = ctx.bot.get_channel(self.reminder_channel)

                    dd, hh, mm, ss = await convert_seconds_to_str(ctx,remaining_time)

                    remaining_time_str = ""
                    if dd > 0:
                        remaining_time_str += f"{int(dd)} day(s) "
                    if hh > 0:
                        remaining_time_str += f"{int(hh)} hour(s) "
                    if mm > 0:
                        remaining_time_str += f"{int(mm)} minute(s) "

                    ping_members = [await aPlayer.create(ctx,tag=m.tag) for m in [m for m in self.current_raid_weekend.members if m.attack_count < 6]]
                    ping_list = [m for m in ping_members if m.discord_user.discord_member]

                    ping_dict = {}
                    for m in ping_list:
                        if m.discord_user.user_id not in list(ping_dict.keys()):
                            ping_dict[m.discord_user.user_id] = []

                        ping_dict[m.discord_user.user_id].append(m)

                    if len(list(ping_dict.keys())) > 0:
                        if remaining_time < 3600:
                            unfinished_raid_str = f"There is **less than 1 hour** left in Raid Weekend and you **HAVE NOT** used all your Raid Attacks.\n\n"
                        else:
                            unfinished_raid_str = f"You started your Raid Weekend but **HAVE NOT** used all your Raid Attacks. Raid Weekend ends in **{remaining_time_str}**.\n\n"

                        for (uid,accounts) in ping_dict.items():
                            account_str = [f"{emotes_townhall[a.town_hall.level]} {a.name}" for a in accounts]
                            unfinished_raid_str += f"<@{uid}> ({', '.join(account_str)})\n"

                        await ch.send(unfinished_raid_str)

                        update_summary += f"\n> - Raid Reminders sent for {len(ping_list)} members."

        return update_summary


    async def add_to_alliance(self,ctx,leader:discord.User,abbreviation,emoji,coleader_role,elder_role,member_role):
        self.is_alliance_clan = True
        self.leader = leader.id
        self.abbreviation = abbreviation
        self.emoji = emoji
        self.coleader_role = coleader_role.id
        self.elder_role = elder_role.id
        self.member_role = member_role.id

        await self.save_to_json(ctx)

    async def update_member_rank(self,ctx,user,rank):
        if rank == 'Member':
            if user.id in self.elders:
                self.elders.remove(user.id)
            if user.id in self.co_leaders:
                self.co_leaders.remove(user.id)

        if rank == 'Elder':
            if user.id not in self.elders:
                self.elders.append(user.id)
            if user.id in self.co_leaders:
                self.co_leaders.remove(user.id)

        if rank in 'Co-Leader':
            if user.id not in self.co_leaders:
                self.co_leaders.append(user.id)
            if user.id in self.elders:
                self.elders.remove(user.id)

        if rank == 'Leader':
            #demote existing leader to Co
            if self.leader not in self.co_leaders:
                self.co_leaders.append(self.leader)

            self.leader = user.id

        member = await aMember.create(ctx,user_id=user.id,refresh=True)
        await member.sync_roles()

        await self.save_to_json(ctx)

    async def set_abbreviation(self,ctx,new_abbr:str):
        self.abbreviation = new_abbr
        await self.save_to_json(ctx)

    async def set_description(self,ctx,new_desc:str):
        self.description = new_desc
        await self.save_to_json(ctx)

    async def set_emoji(self,ctx,emoji):
        self.emoji = emoji
        await self.save_to_json(ctx)

    async def set_recruitment_level(self,ctx,th_levels:list):
        self.recruitment_level = []
        for th in th_levels:
            if int(th) not in self.recruitment_level:
                self.recruitment_level.append(int(th))

        self.recruitment_level.sort()
        await self.save_to_json(ctx)

    async def set_announcement_channel(self,ctx,channel_id):
        self.announcement_channel = channel_id
        await self.save_to_json(ctx)

    async def set_reminder_channel(self,ctx,channel_id):
        self.reminder_channel = channel_id
        await self.save_to_json(ctx)

    async def toggle_war_reminders(self,ctx):
        if self.send_war_reminder:
            self.send_war_reminder = False
        else:
            self.send_war_reminder = True

            if len(self.war_reminder_intervals) == 0:
                self.war_reminder_intervals = [12,4,1]
        await self.save_to_json(ctx)


########################################

### MEMBER OBJECT

########################################
class aMember():
    def __init__(self,user_id):
        self.timestamp = time.time()
        self.user_id = user_id
        self.discord_member = None

        self.elder_clans = []
        self.coleader_clans = []
        self.leader_clans = []

        self.home_clans = []
        self.accounts = []

    @classmethod
    async def create(cls,ctx,user_id,**kwargs):

        refresh = kwargs.get('refresh',False)
        init = False
        build = False

        if user_id in list(ctx.bot.user_cache.keys()):
            self = ctx.bot.user_cache[user_id]

            #override refresh if last 60 secs
            if (time.time() - self.timestamp) < 60:
                refresh = False

            #if more than 10mins, force refresh
            if (time.time() - self.timestamp) > 600:
                refresh = True
        else:
            init = True

        if init or refresh:
            build = True
        else:
            return self

        self = aMember(user_id)
        ctx.bot.user_cache[user_id] = self

        memberInfo = await alliance_file_handler(
            ctx=ctx,
            entry_type='members',
            tag="**")

        try:
            self.discord_member = await ctx.bot.alliance_server.fetch_member(user_id)
        except:
            self.discord_member = None

        memberTags = list(memberInfo.keys())

        self.accounts = [a for a in [await aPlayer.create(ctx,tag=tag) for tag in memberTags] if a.discord_user == self.user_id]

        if len(self.accounts) == 0:
            other_accounts = await ctx.bot.discordlinks.get_linked_players(self.user_id)
            self.accounts = [await aPlayer.create(ctx,tag=tag) for tag in other_accounts]

        [self.home_clans.append(a.home_clan) for a in self.accounts if a.is_member and a.home_clan not in self.home_clans]

        self.leader_clans = [hc for hc in self.home_clans if self.user_id == hc.leader]
        self.coleader_clans = [hc for hc in self.home_clans if self.user_id in hc.co_leaders]
        self.elder_clans = [hc for hc in self.home_clans if self.user_id in hc.elders]

    async def set_nickname(self,ctx,selection=False):
        try:
            self.discord_member = await ctx.bot.alliance_server.fetch_member(user_id)
        except:
            self.discord_member = None

        self.accounts = sorted(self.accounts,key=lambda x:(x.town_hall.level, x.exp_level),reverse=True)

        if len(self.accounts) == 0 or not self.discord_member:
            return None

        if len(self.accounts) == 1 or not selection:
            a = self.accounts[0]
            selected_account = {
                'id': f"{a.tag}",
                'title': f"{a.name} {a.tag}",
                'description': f"{a.town_hall.emote} {a.town_hall.description}\u3000{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}\u3000{emotes_league[a.league.name]} {a.trophies}"
                }
        else:
            selection_list = []
            selection_str = ""
            for a in p_user_accounts:
                a_dict = {
                    'id': f"{a.tag}",
                    'title': f"{a.name} ({a.tag})",
                    'description': f"{a.town_hall.emote} {a.town_hall.description}\u3000{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}\u3000{emotes_league[a.league.name]} {a.trophies}"
                    }
                selection_list.append(a_dict)

            selection_list = await multiple_choice_menu_generate_emoji(ctx,selection_list)

            for i in selection_list:
                selection_str += f"\n{i['emoji']} **{i['title']}**\n{i['description']}"

                if selection_list.index(i) < (len(selection_list)-1):
                    selection_str += "\n\n"

            nick_embed = await clash_embed(ctx,
                title=f"Nickname Change: {user.name}#{user.discriminator}",
                thumbnail=f"{user.avatar_url}")

            nick_embed.add_field(
                name="Select an account from the list below to be the new server nickname.",
                value=selection_str,
                inline=False)

            select_msg = await ctx.send(content=ctx.author.mention,embed=nick_embed)
            selected_account = await multiple_choice_menu_select(ctx,select_msg,selection_list)
            await select_msg.delete()

            if not selected_account:
                return None

        new_nickname_account = [a for a in self.accounts if a.tag == selected_account['id']][0]

        if new_nickname_account.readable_name:
            new_nickname = new_nickname_account.readable_name
        else:
            new_nickname = new_nickname_account.name

        new_nickname = new_nickname.replace('[AriX]','')
        new_nickname = new_nickname.strip()

        clan_ct = 0
        clan_str = ""

        abb_clans = []
        if len(self.leader_clans) > 0:
            [abb_clans.append(c.abbreviation) for c in self.leader_clans if c.abbreviation not in abb_clans and c.abbreviation != '']

        elif len(self.home_clans) > 0:
            [abb_clans.append(c.abbreviation) for c in self.home_clans if c.abbreviation not in abb_clans and c.abbreviation != '']

        if len(abb_clans) > 0:
            new_nickname += f" | {' + '.join(abb_clans)}"


        await self.discord_member.edit(nick=new_nickname)
        return new_nickname

    async def sync_roles(self,ctx):
        try:
            self.discord_member = await ctx.bot.alliance_server.fetch_member(user_id)
        except:
            self.discord_member = None

        if not self.discord_member:
            return

        roles_added = []
        roles_removed = []

        is_arix_member = False
        is_arix_elder = False
        is_arix_leader = False

        allianceClans = await alliance_file_handler(
            ctx=ctx,
            entry_type='clans',
            tag="**")

        allianceClans = [await aClan.create(ctx,tag=c) for c in list(allianceClans.keys())]

        if len(self.home_clans) > 0:
            is_arix_member = True

        if len(self.elder_clans) > 0:
            is_arix_member = True
            is_arix_elder = True

        if len(self.coleader_clans) > 0 or len(self.leader_clans) > 0:
            is_arix_member = True
            is_arix_elder = True
            is_arix_leader = True

        if is_arix_member:
            if ctx.bot.member_role not in self.discord_member.roles:
                await self.discord_member.add_roles(ctx.bot.member_role)
                roles_added.append(ctx.bot.member_role)
        else:
            if ctx.bot.member_role in self.discord_member.roles:
                await self.discord_member.remove_roles(ctx.bot.member_role)
                roles_removed.append(ctx.bot.member_role)

        if is_arix_elder:
            if ctx.bot.elder_role not in self.discord_member.roles:
                await self.discord_member.add_roles(ctx.bot.elder_role)
                roles_added.append(ctx.bot.elder_role)
        else:
            if ctx.bot.elder_role in self.discord_member.roles:
                await self.discord_member.remove_roles(ctx.bot.elder_role)
                roles_removed.append(ctx.bot.elder_role)

        if is_arix_leader:
            if ctx.bot.coleader_role not in self.discord_member.roles:
                await self.discord_member.add_roles(ctx.bot.coleader_role)
                roles_added.append(ctx.bot.coleader_role)
        else:
            if ctx.bot.coleader_role in self.discord_member.roles:
                await self.discord_member.remove_roles(ctx.bot.coleader_role)
                roles_removed.append(ctx.bot.coleader_role)

        for hc in self.home_clans:
            is_elder = False
            is_leader = False

            if self.user_id == hc.leader or self.user_id in hc.co_leaders:
                is_elder = True
                is_leader = True

            elif self.user_id in hc.elders:
                is_member = True
                is_elder = True

            member_role = ctx.bot.alliance_server.get_role(int(hc.member_role))
            elder_role = ctx.bot.alliance_server.get_role(int(hc.elder_role))
            coleader_role = ctx.bot.alliance_server.get_role(int(hc.coleader_role))

            if member_role not in self.discord_member.roles:
                await self.discord_member.add_roles(member_role)
                roles_added.append(member_role)

            if is_elder:
                if elder_role not in self.discord_member.roles:
                    await self.discord_member.add_roles(elder_role)
                    roles_added.append(elder_role)
            else:
                if elder_role in self.discord_member.roles:
                    await self.discord_member.remove_roles(elder_role)
                    roles_removed.append(elder_role)

            if is_leader:
                if coleader_role not in self.discord_member.roles:
                    await self.discord_member.add_roles(coleader_role)
                    roles_added.append(coleader_role)
            else:
                if coleader_role in self.discord_member.roles:
                    await self.discord_member.remove_roles(coleader_role)
                    roles_removed.append(coleader_role)

        for clan in [c for c in allianceClans if c.tag not in [hc.tag for hc in self.home_clans]]:
            member_role = ctx.bot.alliance_server.get_role(int(clan.member_role))
            elder_role = ctx.bot.alliance_server.get_role(int(clan.elder_role))
            coleader_role = ctx.bot.alliance_server.get_role(int(clan.coleader_role))

            if member_role in self.discord_member.roles:
                await self.discord_member.remove_roles(member_role)
                roles_removed.append(member_role)
            if elder_role in self.discord_member.roles:
                await self.discord_member.remove_roles(elder_role)
                roles_removed.append(elder_role)
            if coleader_role in self.discord_member.roles:
                await self.discord_member.remove_roles(coleader_role)
                roles_removed.append(coleader_role)

        if roles_added or roles_removed:
            ch = ctx.bot.get_channel(1047747107248939078)

            embed = await clash_embed(ctx,
                title=f"Role(s) Updated for: {self.discord_member.name}#{self.discord_member.discriminator}",
                message=f"User ID: `{self.discord_member.id}`\n\u200b",
                thumbnail=self.discord_member.avatar_url)

            account_summary = ""
            for a in self.accounts:
                account_summary += f"__{a.name} ({a.tag})__"
                account_summary += f"\n{a.town_hall.emoji} {a.member_description}"
                account_summary += "\n\n"

            embed.add_field(
                name="**Member Accounts**",
                value=account_summary)

            if roles_added:
                text_roles_added = ""
                for r in roles_added:
                    text_roles_added += f"{r.name} `{r.id}`\n"

                embed.add_field(
                    name=f"**Roles Added**",
                    value=text_roles_added)

            if roles_removed:
                text_roles_removed = ""
                for r in roles_removed:
                    text_roles_removed += f"{r.name} `{r.id}`\n"

                embed.add_field(
                    name=f"**Roles Added**",
                    value=text_roles_removed)

            await ch.send(embed=embed)

        return roles_added, roles_removed
