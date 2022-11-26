import coc
import discord
import time

from numerize import numerize
from itertools import chain

from coc.ext import discordlinks

from .constants import emotes_townhall, emotes_builderhall, emotes_capitalhall, emotes_league, emotes_army, hero_availability, troop_availability, spell_availability, pet_availability
from .file_functions import get_current_season, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler

from .notes import aNote
from .clan import aClan
from .clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from .raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from .errors import TerminateProcessing, InvalidTag, error_end_processing

class ClashPlayerError(Exception):
    def __init__(self,message):
        self.message = message

class aPlayer():
    def __init__(self,ctx,tag):
        self.timestamp = time.time()
        self.tag = tag

        self.p = None
        self.name = None

        self.share_link = ""
        self.discord_link = None

        self.is_arix_account = False

        #Membership Attributes
        self.home_clan = aClan(ctx,None)
        self.is_member = False
        self.arix_rank = 'Non-Member'
        self.discord_user = 0
        self.notes = []

        #Membership Statistics
        self.last_update = time.time()
        self.time_in_home_clan = 0
        self.other_clans = []

        #Player Attributes
        self.exp_level = 1

        self.clan = aClan(ctx,None)
        self.role = ''
        self.clan_description = ''

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
        self.hero_description = ''

        self.troop_strength = 0
        self.max_troop_strength = 0

        self.spell_strength = 0
        self.max_spell_strength = 0

        #Activity Stats
        self.attack_wins = aPlayerStat({})
        self.defense_wins = aPlayerStat({})

        self.donations_sent = aPlayerStat({})
        self.donations_rcvd = aPlayerStat({})

        self.loot_gold = aPlayerStat({})
        self.loot_elixir = aPlayerStat({})
        self.loot_darkelixir = aPlayerStat({})
        
        self.clangames = aPlayerStat({})

        self.capitalcontribution = aPlayerStat({})

        self.warlog = {}
        self.war_stats = aPlayerWarStats({})
 
        self.raidlog = {}
        self.raid_stats = aPlayerRaidStats({})

        self.desc_title = ""
        self.desc_full_text = ""
        self.desc_summary_text = ""

    @classmethod
    async def create(cls,ctx,tag,fetch=False):
        tag = coc.utils.correct_tag(tag)

        if not coc.utils.is_valid_tag(tag):
            raise InvalidTag(tag)
            return None

        #get from cache
        if tag in list(ctx.bot.member_cache.keys()):
            self = ctx.bot.member_cache[tag]
        else:
            self = aPlayer(ctx,tag)
            #add to cache
            ctx.bot.member_cache[tag] = self
            fetch = True

        self.share_link = f"https://link.clashofclans.com/en?action=OpenPlayerProfile&tag=%23{format(self.tag.strip('#'))}"

        #if tag already exists in cache, and current within last 5 minutes, use cached information
        if not fetch and self.p and (time.time() - self.timestamp) < 600:
            return self

        else:
            self.timestamp = time.time()
            try:
                self.p = await ctx.bot.coc_client.get_player(self.tag)
            except (coc.HTTPException, coc.InvalidCredentials, coc.Maintenance, coc.GatewayError, ClientConnectorError) as exc:
                raise TerminateProcessing(exc) from exc
                return None

            memberInfo = await alliance_file_handler(ctx,'members',self.tag)
            memberStats = await data_file_handler(ctx,'members',self.tag)

            self.name = self.p.name
            self.exp_level = self.p.exp_level

            clan = getattr(self.p,'clan',None)
            self.clan = await aClan.create(ctx,getattr(clan,'tag',None))
            self.role = str(getattr(self.p,'role',''))

            if self.clan.tag:
                self.clan_description = f"{self.role} of {self.clan.name}"
            else:
                self.clan_description = "No Clan"

            self.town_hall = aTownHall(level=getattr(self.p,'town_hall',1),weapon=getattr(self.p,'town_hall_weapon',0))
            self.clan_castle = sum([a.value for a in self.p.achievements if a.name=='Empire Builder'])
            self.league = getattr(self.p,'league',None)
            self.trophies = getattr(self.p,'trophies',0)
            self.best_trophies = getattr(self.p,'best_trophies',0)
            self.war_stars = getattr(self.p,'war_stars',0)
            self.war_optin = getattr(self.p,'war_opted_in',False)

            self.builder_hall = getattr(self.p,'builder_hall',0)
            self.versus_trophies = getattr(self.p,'versus_trophies',0)
            self.best_versus_trophies = getattr(self.p,'best_versus_trophies',0)

            self.heroes = []
            hero_d = [hero for (th,hero) in hero_availability.items() if th<=self.town_hall.level]
            for hero_name in list(chain.from_iterable(hero_d)):
                is_unlocked_at_this_level = False
                if hero_name in hero_availability[self.town_hall.level]:
                    is_unlocked_at_this_level = True
                hero = self.p.get_hero(name=hero_name)
                if not hero:
                    hero = ctx.bot.coc_client.get_hero(name=hero_name,townhall=self.town_hall.level)
                hero = aHero.from_data(hero,self.town_hall.level,is_unlocked_at_this_level)
                self.heroes.append(hero)

            self.troops = []
            troop_d = [troop for (th,troop) in troop_availability.items() if th<=self.town_hall.level]
            for troop_name in list(chain.from_iterable(troop_d)):
                is_unlocked_at_this_level = False
                if troop_name in troop_availability[self.town_hall.level]:
                    is_unlocked_at_this_level = True
                troop = self.p.get_troop(name=troop_name,is_home_troop=True)
                if not troop:
                    troop = ctx.bot.coc_client.get_troop(name=troop_name,townhall=self.town_hall.level)
                troop = aTroop.from_data(troop,self.town_hall.level,is_unlocked_at_this_level)
                self.troops.append(troop)

            self.spells = []
            spell_d = [spell for (th,spell) in spell_availability.items() if th<=self.town_hall.level]
            for spell_name in list(chain.from_iterable(spell_d)):
                is_unlocked_at_this_level = False
                if spell_name in spell_availability[self.town_hall.level]:
                    is_unlocked_at_this_level = True
                spell = self.p.get_spell(name=spell_name)
                if not spell:
                    spell = ctx.bot.coc_client.get_spell(name=spell_name,townhall=self.town_hall.level)
                spell = aSpell.from_data(spell,self.town_hall.level,is_unlocked_at_this_level)
                self.spells.append(spell)

            self.pets = []
            pets_d = {th:pets for (th,pets) in pet_availability.items() if th<=self.town_hall.level}
            for th, pets in pets_d.items():
                minlevel = 0
                if th < self.town_hall.level:
                    minlevel = 10
                for pet in pets:
                    get_pet = [p for p in self.p.hero_pets if p.name==pet]
                    if len(get_pet) == 0:
                        pet_object = aHeroPet.not_yet_unlocked(pet,minlevel)
                    else:
                        pet_object = aHeroPet.from_data(get_pet[0],minlevel)
                    self.pets.append(pet_object)

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
            else:
                self.hero_rushed_pct = 0

            self.troop_strength = sum([troop.level for troop in self.troops])
            self.max_troop_strength = (sum([troop.maxlevel_for_townhall for troop in self.troops]) + sum([pet.maxlevel_for_townhall for pet in self.pets]))
            self.min_troop_strength = (sum([troop.minlevel_for_townhall for troop in self.troops]) + sum([pet.minlevel_for_townhall for pet in self.pets]))

            rushed_troops = sum([(t.minlevel_for_townhall - t.level) for t in self.troops if t.is_rushed]) + sum([(p.minlevel_for_townhall - p.level) for p in self.pets if p.level < p.minlevel_for_townhall])
            if self.min_troop_strength > 0:
                self.troop_rushed_pct = round((rushed_troops / self.min_troop_strength)*100,2)
            else:
                self.troop_rushed_pct = 0

            self.spell_strength = sum([spell.level for spell in self.spells])
            self.max_spell_strength = (sum([spell.maxlevel_for_townhall for spell in self.spells]))
            self.min_spell_strength = (sum([spell.minlevel_for_townhall for spell in self.spells]))

            rushed_spells = sum([(s.minlevel_for_townhall - s.level) for s in self.spells if s.is_rushed])
            if self.min_spell_strength > 0:
                self.spell_rushed_pct = round((rushed_spells / self.min_spell_strength)*100,2)
            else:
                self.spell_rushed_pct = 0

            if self.min_hero_strength + self.min_troop_strength + self.min_spell_strength > 0:
                rushed_pct = (rushed_heroes + rushed_troops + rushed_spells) / (self.min_hero_strength + self.min_troop_strength + self.min_spell_strength)
                self.overall_rushed_pct = round(rushed_pct*100,2)
            else:
                self.overall_rushed_pct = 0

            #From AriX Data File
            if memberInfo:
                try:
                    home_clan_tag = memberInfo['home_clan']['tag']
                except:
                    home_clan_tag = None

                self.home_clan = await aClan.create(ctx,home_clan_tag)
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


            if memberStats:
                #Membership Statistics
                self.last_update = memberStats.get('last_update',time.time())
                self.time_in_home_clan = memberStats.get('time_in_home_clan',0)
                self.other_clans = memberStats.get('other_clans',[])

                self.attack_wins = aPlayerStat(memberStats.get('attack_wins',{}))
                self.defense_wins = aPlayerStat(memberStats.get('defense_wins',{}))

                self.donations_sent = aPlayerStat(memberStats.get('donations_sent',{}))
                self.donations_rcvd = aPlayerStat(memberStats.get('donations_rcvd',{}))

                self.loot_gold = aPlayerStat(memberStats.get('loot_gold',{}))
                self.loot_elixir = aPlayerStat(memberStats.get('loot_elixir',{}))
                self.loot_darkelixir = aPlayerStat(memberStats.get('loot_darkelixir',{}))

                self.clangames = aPlayerStat(memberStats.get('clangames',{}))

                self.capitalcontribution = aPlayerStat(memberStats.get('capitalcontribution',{}))

                try:
                    self.warlog = {wID:aPlayerWarLog.from_json(wID,wl) for (wID,wl) in memberStats.get('war_log',{}).items()}
                except:
                    self.warlog = {}
                try:
                    self.raidlog = {rID:aPlayerRaidLog.from_json(rID,self,rl) for (rID,rl) in memberStats.get('raid_log',{}).items()}
                except:
                    self.raidlog = {}

                self.war_stats = aPlayerWarStats(self.warlog)
                self.raid_stats = aPlayerRaidStats(self.raidlog)


            self.desc_title = f"{self.name} ({self.tag})"

            member_description = ""
            if self.is_member and self.arix_rank not in ['Guest','Non-Member']:
                member_description = f"***{self.home_clan.emoji} {self.arix_rank} of {self.home_clan.name}***"
            elif self.is_arix_account:
                member_description = f"***<a:aa_AriX:1031773589231374407> AriX Guest Account***"

            self.desc_full_text = f"{member_description}"
            if member_description:
                self.desc_full_text += "\n"

            self.desc_full_text += (
                f"<:Exp:825654249475932170> {self.exp_level}\u3000<:Clan:825654825509322752> {self.clan_description}"
                + f"\n{self.town_hall.emote} {self.town_hall.description}\u3000{emotes_league[self.league.name]} {self.trophies} (best: {self.best_trophies})")

            if self.town_hall.level >= 7:
                self.desc_full_text += f"\n{self.hero_description}"

            self.desc_full_text += f"\n[Player Link: {self.tag}]({self.share_link})"

            self.desc_summary_text = f"{self.town_hall.emote} {self.town_hall.description}\u3000"

            if self.is_member and self.arix_rank not in ['Guest','Non-Member']:
                self.desc_summary_text += member_description
            else:
                self.desc_summary_text += f"<:Clan:825654825509322752> {self.clan_description}"

            if not self.discord_user:
                get_links = await ctx.bot.discordlinks.get_links(self.tag)
                self.discord_user = get_links[0][1]

            return self


    async def save_to_json(self,ctx):
        allianceJson = {
            'name':self.name,
            'is_member':self.is_member,
            'home_clan': {
                'tag': self.home_clan.tag,
                'name': self.home_clan.name
                },
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
            'last_update': self.last_update,
            'time_in_home_clan': self.time_in_home_clan,
            'role': self.role,
            'current_clan': {
                'tag': self.clan.tag,
                'name': self.clan.name
                },
            'other_clans': self.other_clans,
            'exp_level': self.exp_level,
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

            self.last_update = self.timestamp


    async def set_baselines(self,ctx):
        if self.p:
            if self.clan.tag not in self.other_clans:
                self.other_clans.append(self.clan.tag)

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

            self.last_update = self.timestamp


    async def update_war(self,ctx,war_entry):
        player_log = aPlayerWarLog.from_war(war_entry)
        wID = player_log.wID
        self.warlog['wID'] = player_log

        await self.save_to_json(ctx)


    async def update_raid_weekend(self,ctx,raid_entry):
        player_log = aPlayerRaidLog.from_raid_member(raid_entry)
        rID = player_log.rID
        self.raidlog['rID'] = player_log

        await self.save_to_json(ctx)


    async def new_member(self,ctx,discord_user,home_clan=None):
        self.discord_user = discord_user.id
        try:
            discord_member = await ctx.bot.alliance_server.fetch_member(discord_user.id)
        except:
            discord_member = None

        if home_clan:
            coleader_role = ctx.bot.alliance_server.get_role(int(home_clan.coleader_role))
            elder_role = ctx.bot.alliance_server.get_role(int(home_clan.elder_role))
            member_role = ctx.bot.alliance_server.get_role(int(home_clan.member_role))
            
            self.home_clan = home_clan
            self.is_member = True

            if discord_user.id == home_clan.leader:
                self.arix_rank = 'Leader'
            elif discord_user.id in home_clan.co_leaders:
                self.arix_rank = 'Co-Leader'
            elif discord_user.id in home_clan.elders:
                self.arix_rank = 'Elder'
            else:
                self.arix_rank = 'Member'

            if discord_member:
                try:
                    if member_role not in discord_member.roles:
                        await discord_member.add_roles(member_role)
                    if ctx.bot.member_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.member_role)

                    if self.arix_rank in ['Leader','Co-Leader']:
                        if coleader_role not in discord_member.roles:
                            await discord_member.add_roles(coleader_role)

                        if ctx.bot.coleader_role not in discord_member.roles:
                            await discord_member.add_roles(ctx.bot.coleader_role)

                    if self.arix_rank in ['Leader','Co-Leader','Elder']:
                        if elder_role not in discord_member.roles:
                            await discord_member.add_roles(elder_role)

                        if ctx.bot.elder_role not in discord_member.roles:
                            await discord_member.add_roles(ctx.bot.elder_role)
                except:
                    pass

        else:
            self.home_clan = await aClan.create(ctx,None)
            self.is_member = False
            self.arix_rank = 'Non-Member'

        await self.set_baselines(ctx)
        await self.save_to_json(ctx)


    async def remove_member(self,ctx):
        home_clan_tag = None
        self.home_clan = await aClan.create(ctx,home_clan_tag)
        self.arix_rank = 'Non-Member'
        self.is_member = False
        await self.save_to_json(ctx)


    async def add_note(self,ctx,message):
        new_note = aNote.create_new(ctx,message)
        self.notes.append(new_note)

        sorted_notes = sorted(self.notes,key=lambda n:(n.timestamp),reverse=False)
        self.notes = sorted_notes

        await self.save_to_json(ctx)

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
        self.level = inputJson.get('level','')
        self.village = inputJson.get('village','')
        self.maxlevel_for_townhall = inputJson.get('maxlevel_for_townhall',0)
        self.minlevel_for_townhall = inputJson.get('minlevel_for_townhall',0)

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        else:
            self.is_rushed = False
        return self

    @classmethod
    def from_data(cls,gameData,th_level,is_unlocked_at_this_level):
        self = aHero()
        self.hero = gameData

        self.id = getattr(self.hero,'id',0)
        self.name = getattr(self.hero,'name','')
        if type(self.hero.level) == int:
            self.level = getattr(self.hero,'level',0)
        else:
            self.level = 0
        self.village = getattr(self.hero,'village','')
        if self.village == '':
            self.village = 'home'

        maxlevel_for_townhall = self.hero.get_max_level_for_townhall(max(th_level,3))
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        try:
            minlevel_for_townhall = self.hero.get_max_level_for_townhall(max(th_level-1,3))
            self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)
        except:
            self.minlevel_for_townhall = 0

        if is_unlocked_at_this_level:
            self.minlevel_for_townhall = 0

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
        self.minlevel_for_townhall = inputJson.get('minlevel_for_townhall',0)
        self.maxlevel_for_townhall = inputJson.get('maxlevel_for_townhall',0)
        return self

    @classmethod
    def from_data(cls,gameData,minlevel):
        self = aHeroPet()
        self.pet = gameData

        self.id = getattr(self.pet,'id',0)
        self.name = getattr(self.pet,'name','')
        self.level = getattr(self.pet,'level',0)
        self.minlevel_for_townhall = minlevel
        self.maxlevel_for_townhall = getattr(self.pet,'max_level',0)
        return self

    @classmethod
    def not_yet_unlocked(cls,pet_name,minlevel):
        self = aHeroPet()
        self.pet = None

        self.id = 0
        self.name = pet_name
        self.level = 0
        self.minlevel_for_townhall = 0
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
    def from_data(cls,gameData,th_level,is_unlocked_at_this_level=False):
        self = aTroop()
        self.troop = gameData

        self.id = getattr(self.troop,'id',0)
        self.name = getattr(self.troop,'name','')
        if type(self.troop.level) == int:
            self.level = getattr(self.troop,'level',0)
        else:
            self.level = 0

        self.village = getattr(self.troop,'village','')
        if self.village == '':
            self.village = 'home'

        self.is_elixir_troop = getattr(self.troop,'is_elixir_troop',False)
        self.is_dark_troop = getattr(self.troop,'is_dark_troop',False)
        self.is_siege_machine = getattr(self.troop,'is_siege_machine',False)
        self.is_super_troop = getattr(self.troop,'is_super_troop',False)
        self.original_troop = getattr(self.troop,'original_troop',None)

        maxlevel_for_townhall = self.troop.get_max_level_for_townhall(max(th_level,3))
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        minlevel_for_townhall = self.troop.get_max_level_for_townhall(max(th_level-1,3))
        self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)

        if is_unlocked_at_this_level:
            self.minlevel_for_townhall = 0

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
        if self.village == '':
            self.village = 'home'

        self.is_elixir_spell = inputJson.get('is_elixir_spell',False)
        self.is_dark_spell = inputJson.get('is_dark_spell',False)
        
        self.maxlevel_for_townhall = inputJson.get('maxlevel_for_townhall',0)
        self.minlevel_for_townhall = inputJson.get('minlevel_for_townhall',0)

        if self.level < self.minlevel_for_townhall:
            self.is_rushed = True
        return self

    @classmethod
    def from_data(cls,gameData,th_level,is_unlocked_at_this_level):
        self = aSpell()
        self.spell = gameData

        self.id = getattr(self.spell,'id',0)
        self.name = getattr(self.spell,'name','')
        if not self.spell.level:
            self.level = 0
        else:
            self.level = getattr(self.spell,'level',0)
        self.village = getattr(self.spell,'village','')

        self.is_elixir_spell = getattr(self.spell,'is_elixir_spell',False)
        self.is_dark_spell = getattr(self.spell,'is_dark_spell',False)

        maxlevel_for_townhall = self.spell.get_max_level_for_townhall(max(th_level,3))
        self.maxlevel_for_townhall = int(0 if maxlevel_for_townhall is None else maxlevel_for_townhall)

        minlevel_for_townhall = self.spell.get_max_level_for_townhall(max(th_level-1,3))
        self.minlevel_for_townhall = int(0 if minlevel_for_townhall is None else minlevel_for_townhall)

        if is_unlocked_at_this_level:
            self.minlevel_for_townhall = 0

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
            if war.result == '':
                self.missed_attacks += 0
            else:
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
