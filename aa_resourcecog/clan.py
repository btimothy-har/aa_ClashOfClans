import coc
import discord
import time
import json

from datetime import datetime

from .constants import emotes_capitalhall, emotes_league
from .file_functions import get_current_season, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler
from .notes import aNote
from .clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from .raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from .errors import TerminateProcessing, InvalidTag

class ClashClanError(Exception):
    def __init__(self,message):
        self.message = message

class aClan():
    def __init__(self,ctx,tag=None):
        self.timestamp = time.time()
        self.tag = tag

        self.c = None
        self.name = "No Clan"

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

        self.war_log = None
        self.raid_log = None

        self.current_war = None
        self.current_raid_weekend = None

        self.desc_title = ""
        self.desc_full_text = ""
        self.desc_summary_text = ""

    def __repr__(self):
        return f"Clan {self.tag} {self.name} generated on {datetime.fromtimestamp(self.timestamp).strftime('%m%d%Y%H%M%S')}"

    @classmethod
    async def create(cls,ctx,tag=None,fetch=False):

        if tag:
            tag = coc.utils.correct_tag(tag)
            if not coc.utils.is_valid_tag(tag):
                raise InvalidTag(tag)
                return None

            if tag in list(ctx.bot.clan_cache.keys()):
                self = ctx.bot.clan_cache[tag]
            else:
                self = aClan(ctx,tag)
                ctx.bot.clan_cache[tag] = self

        else:
            self = aClan(ctx,tag)
            return self

        if not fetch and self.c and (time.time() - self.timestamp) < 300:
            return self

        else:
            self.timestamp = time.time()
            try:
                self.c = await ctx.bot.coc_client.get_clan(self.tag)
            except (coc.HTTPException, coc.InvalidCredentials, coc.Maintenance, coc.GatewayError) as exc:
                raise TerminateProcessing(exc) from exc
                return None

            clanInfo = await alliance_file_handler(
                ctx=ctx,
                entry_type='clans',
                tag=self.tag)
            warLog = await data_file_handler(
                ctx=ctx,
                file='warlog',
                tag=self.tag)
            raidLog = await data_file_handler(
                ctx=ctx,
                file='capitalraid',
                tag=self.tag)

            self.name = self.c.name
            self.level = self.c.level

            try:
                self.capital_hall = [d.hall_level for d in self.c.capital_districts if d.name=="Capital Peak"][0]
            except:
                self.capital_hall = 0

            self.member_count = self.c.member_count
            self.description = self.c.description

            #Alliance Attributes
            if clanInfo:
                self.is_alliance_clan = True
                self.abbreviation = clanInfo.get('abbr','')
                self.emoji = clanInfo.get('emoji','')
                #self.description = clanInfo.get('description',None)
                #if not self.description:
                #self.description = self.c.description

                self.leader = clanInfo.get('leader',0)
                self.co_leaders = clanInfo.get('co_leaders',[])
                self.elders = clanInfo.get('elders',[])
                self.member_count = clanInfo.get('member_count',0)
                self.recruitment_level = clanInfo.get('recruitment',[])

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

            self.war_log = {wid:aClanWar.from_json(ctx,wid,data) for (wid,data) in warLog.items()}
            self.raid_log = {rid:aRaidWeekend.from_json(ctx,self,rid,data) for (rid,data) in raidLog.items()}

            if self.tag:
                self.desc_title = f"{self.name} ({self.tag})"

                self.desc_full_text = (
                        f"<:Clan:825654825509322752> Level {self.level}\u3000{emotes_capitalhall[self.capital_hall]} CH {self.capital_hall}\u3000<:Members:1040672942524215337> {self.member_count}"
                    +   f"\n{emotes_league[self.c.war_league.name]} {self.c.war_league.name}\n<:ClanWars:825753092230086708> W{self.c.war_wins}/D{self.c.war_ties}/L{self.c.war_losses} (Streak: {self.c.war_win_streak})"
                    +   f"\n[Clan Link: {self.tag}]({self.c.share_link})")

                self.desc_summary_text = f"<:Clan:825654825509322752> Level {self.level}\u3000{emotes_capitalhall[self.capital_hall]} CH {self.capital_hall}\u3000{emotes_league[self.c.war_league.name]} {self.c.war_league.name}"

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
            'member_count': self.member_count,
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
            ctx=ctx,
            entry_type='clans',
            tag=self.tag,
            new_data=allianceJson)
        
        await data_file_handler(
            ctx=ctx,
            file='warlog',
            tag=self.tag,
            new_data=warlogJson)
        
        await data_file_handler(
            ctx=ctx,
            file='capitalraid',
            tag=self.tag,
            new_data=raidweekendJson)


    async def update_member_count(self,ctx):
        with ctx.bot.clash_file_lock.read_lock():
            with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
                file_json = json.load(file)

        members = file_json['members']

        clan_members = [tag for (tag,member) in members.items() if member['is_member']==True and member['home_clan']['tag']==self.tag]
        self.member_count = len(clan_members)

        await self.save_to_json(ctx)


    async def update_clan_war(self,ctx):
        try:
            current_war = await ctx.bot.coc_client.get_clan_war(self.tag)
        except (coc.HTTPException, coc.InvalidCredentials, coc.Maintenance, coc.GatewayError) as exc:
            raise TerminateProcessing(exc) from exc
            return None

        if current_war.state == 'notInWar':
            self.war_state = current_war.state
            return None
        
        self.current_war = aClanWar.from_game(ctx,current_war)
        if self.current_war.state != self.war_state:
            self.war_state = self.current_war.state
            self.war_state_change = True

        if self.current_war.state in ['inWar','warEnded']:
            self.war_log[self.current_war.wID] = self.current_war

        await self.save_to_json(ctx)


    async def update_raid_weekend(self,ctx):
        try:
            raid_log_gen = await ctx.bot.coc_client.get_raidlog(clan_tag=self.tag,page=False,limit=1)
        except (coc.HTTPException, coc.InvalidCredentials, coc.Maintenance, coc.GatewayError) as exc:
            raise TerminateProcessing(exc) from exc
            return None
            
        self.current_raid_weekend = aRaidWeekend.from_game(ctx,self,raid_log_gen[0])

        if self.current_raid_weekend.state != self.raid_weekend_state:
            self.raid_weekend_state = self.current_raid_weekend.state
            self.raid_state_change = True

        self.raid_log[self.current_raid_weekend.rID] = self.current_raid_weekend
        await self.save_to_json(ctx)


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
        coleader_role = ctx.bot.alliance_server.get_role(int(self.coleader_role))
        elder_role = ctx.bot.alliance_server.get_role(int(self.elder_role))
        member_role = ctx.bot.alliance_server.get_role(int(self.member_role))

        discord_member = await ctx.bot.alliance_server.fetch_member(user.id)

        if rank == 'Member':
            if user.id in self.elders:
                self.elders.remove(user.id)
            if user.id in self.co_leaders:
                self.co_leaders.remove(user.id)

            if discord_member:
                try:
                    if ctx.bot.member_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.member_role)

                    if member_role not in discord_member.roles:
                        await discord_member.add_roles(member_role)

                    if coleader_role:
                        await discord_member.remove_roles(coleader_role)

                    if elder_role:
                        await discord_member.remove_roles(elder_role)
                except:
                    pass

        if rank == 'Elder':
            if user.id not in self.elders:
                self.elders.append(user.id)
            if user.id in self.co_leaders:
                self.co_leaders.remove(user.id)

            if discord_member:    
                try:
                    if ctx.bot.member_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.member_role)

                    if ctx.bot.elder_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.elder_role)

                    if elder_role:
                        await discord_member.add_roles(elder_role)

                    if coleader_role:
                        await discord_member.remove_roles(coleader_role)
                except:
                    pass

        if rank in 'Co-Leader':
            if user.id not in self.co_leaders:
                self.co_leaders.append(user.id)
            if user.id in self.elders:
                self.elders.remove(user.id)

            if discord_member:
                try:
                    if ctx.bot.member_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.member_role)

                    if ctx.bot.elder_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.elder_role)

                    if ctx.bot.coleader_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.coleader_role)

                    if coleader_role:
                        await discord_member.add_roles(coleader_role)

                    if elder_role:
                        await discord_member.add_roles(elder_role)
                except:
                    pass

        if rank == 'Leader':
            #demote existing leader to Co
            if self.leader not in self.co_leaders:
                self.co_leaders.append(self.leader)

            self.leader = user.id

            if discord_member:
                try:
                    if ctx.bot.member_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.member_role)

                    if ctx.bot.elder_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.elder_role)

                    if ctx.bot.coleader_role not in discord_member.roles:
                        await discord_member.add_roles(ctx.bot.coleader_role)

                    if coleader_role:
                        await discord_member.add_roles(coleader_role)

                    if elder_role:
                        await discord_member.add_roles(elder_role)
                except:
                    pass

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

    async def set_war_reminder_interval(self,ctx,new_interval):
        for i in new_interval:
            i = int(i)
            if i > 24:
                pass

            if i not in self.war_reminder_intervals:
                self.war_reminder_intervals.append(i)

        if 1 not in self.war_reminder_intervals:
            self.war_reminder_intervals.append(1)

        self.war_reminder_intervals.sort(reverse=True)

        await self.save_to_json(ctx)

    async def set_raid_reminder_interval(self,ctx,new_interval):
        for i in new_interval:
            i = int(i)
            if i > 48:
                pass

            if i not in self.raid_reminder_intervals:
                self.raid_reminder_intervals.append(i)

        self.raid_reminder_intervals.sort(reverse=True)

        await self.save_to_json(ctx)

    async def toggle_raid_reminders(self,ctx):
        if self.send_raid_reminder:
            self.send_raid_reminder = False
        else:
            self.send_raid_reminder = True

            if len(self.raid_reminder_intervals) == 0:
                self.raid_reminder_intervals = [36,24,12,4]
        await self.save_to_json(ctx)

    async def add_note(self,ctx,message):
        new_note = aNote.create_new(ctx,message)
        self.notes.append(new_note)

        sorted_notes = sorted(self.notes,key=lambda n:(n.timestamp),reverse=False)
        self.notes = sorted_notes
        await self.save_to_json(ctx)
