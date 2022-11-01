import coc
import discord
import time

#from .aa_resourcecog import
#from .constants import 
from .file_functions import get_current_alliance, season_file_handler, alliance_file_handler, data_file_handler
from .notes import aNote
#from .player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from .clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from .raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog

class ClashClanError(Exception):
    def __init__(self,message):
        self.message = message

class aClan():
    def __init__(self,ctx,tag=None):
        self.timestamp = time.time()
        self.ctx = ctx
        
        self.tag = coc.utils.correct_tag(tag)

        if not coc.utils.is_valid_tag(tag):
            raise InvalidTagError(message=f"The tag {self.tag} is not a valid tag.")

        self.c = None
        self.name = None

        #Alliance Attributes
        self.is_alliance_clan = False
        self.abbreviation = ''
        self.description = None
        self.leader = 0
        self.recruitment_level = []
        self.notes = []

        self.announcement_channel = 0
        self.war_reminder_freq = 0
        self.raid_reminder_freq = 0

        #Clan Statuses
        self.war_state = ''
        self.war_state_change = False

        self.raid_weekend_state = ''
        self.raid_state_change = False

        self.war_log = None
        self.raid_log = None

        self.current_war = None
        self.current_raid_weekend = None

    @classmethod
    async def create(cls,ctx,tag=None):
        if not tag:
            return None
        self = aClan(ctx,tag)
        try:
            self.c = await ctx.bot.coc_client.get_clan(self.tag)
        except coc.NotFound:
            self.c = None
            raise ClashPlayerError(message=f"Unable to find a clan with the tag {tag}.")
            return None

        clanInfo = await alliance_file_handler(
            ctx=self.ctx,
            entry_type='clans',
            tag=self.tag)
        warLog = await data_file_handler(
            ctx=self.ctx,
            file='warlog',
            tag=self.tag)
        raidLog = await data_file_handler(
            ctx=self.ctx,
            file='capitalraid',
            tag=self.tag)

        self.name = getattr(self.c,'name',None)

        self.description = self.c.description

        #Alliance Attributes
        if clanInfo:
            self.is_alliance_clan = True
            self.abbreviation = clanInfo.get('abbr','')
            self.description = clanInfo.get('description',None)
            if not self.description:
                self.description = self.c.description

            self.leader = clanInfo.get('leader',0)
            self.recruitment_level = clanInfo.get('recruitment_level',[])
            self.notes = clanInfo.get('notes',[])

            self.announcement_channel = clanInfo.get('announcement_channel',0)
            self.war_reminder_freq = clanInfo.get('war_reminder_freq',[])
            self.raid_reminder_freq = clanInfo.get('raid_reminder_freq',[])

            self.war_state = clanInfo.get('war_state','')
            self.raid_weekend_state = clanInfo.get('raid_weekend_state','')

        self.war_log = {wid:aClanWar.from_json(self.ctx,wid,data) for (wid,data) in warLog.items()}
        self.raid_log = {rid:aRaidWeekend.from_json(self.ctx,self,rid,data) for (rid,data) in raidLog.items()}
        return self

    async def save_to_json(self):
        allianceJson = {
            'name':self.name,
            'abbr':self.abbreviation,
            'description': self.description,
            'recruitment': self.recruitment_level,
            'notes': self.notes,
            'announcement_channel': self.announcement_channel,
            'war_reminder_freq': self.war_reminder_freq,
            'raid_reminder_freq': self.raid_reminder_freq,
            'war_state': self.war_state,
            'raid_weekend_state': self.raid_weekend_state,
            }

        warlogJson = {}
        for wid,war in self.war_log.items():
            wID, wJson = war.to_json()
            warlogJson[wID] = wJson

        raidweekendJson = {}
        for rid,raid in self.raid_log.items():
            rID, rJson = raid.to_json()
            raidweekendJson[rID] = rJson

        await alliance_file_handler(
            ctx=self.ctx,
            entry_type='clans',
            tag=self.tag,
            new_data=allianceJson)
        
        await data_file_handler(
            ctx=self.ctx,
            file='warlog',
            tag=self.tag,
            new_data=warlogJson)
        
        await data_file_handler(
            ctx=self.ctx,
            file='capitalraid',
            tag=self.tag,
            new_data=raidweekendJson)

    async def update_clan_war(self):
        current_war = await self.ctx.bot.coc_client.get_clan_war(self.tag)
        if current_war.state == 'notInWar':
            return None
        
        self.current_war = aClanWar.from_game(self.ctx,current_war)
        if self.current_war.state != self.war_state:
            self.war_state = self.current_war.state
            self.war_state_change = True

        if self.current_war.state in ['inWar','warEnded']:
            self.war_log[self.current_war.wID] = self.current_war

    async def update_raid_weekend(self):
        raid_log_gen = await self.ctx.bot.coc_client.get_raidlog(clan_tag=self.tag,page=False,limit=1)
        self.current_raid_weekend = aRaidWeekend.from_game(self.ctx,self,raid_log_gen[0])

        if self.current_raid_weekend.state != self.raid_weekend_state:
            self.raid_weekend_state = self.current_raid_weekend.state
            self.raid_state_change = True

        self.raid_log[self.current_raid_weekend.rID] = self.current_raid_weekend

    async def add_to_alliance(self,abbreviation,leader:discord.User):
        self.is_alliance_clan = True
        self.abbreviation = abbreviation
        self.leader = leader.id

    async def set_abbreviation(self,new_abbr:str):
        self.abbreviation = new_abbr

    async def set_description(self,new_desc:str):
        self.description = new_desc

    async def set_recruitment_level(self,*th_levels:int):
        for th in th_levels:
            if th not in self.recruitment_level:
                self.recruitment_level.append(th)

    async def set_announcement_channel(self,channel_id):
        self.announcement_channel = channel_id

    async def add_note(self,ctx,message):
        new_note = await aNote.create_new(ctx,message)
        self.notes.append(new_note)

        sorted_notes = sorted(self.notes,key=lambda n:(n.timestamp),reverse=False)
        self.notes = sorted_notes