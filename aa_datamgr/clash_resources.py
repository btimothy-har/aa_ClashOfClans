import os
import discord
import coc
import json
import asyncio
import random
import time
import pytz
import requests

from dotenv import load_dotenv
from redbot.core import Config, commands
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from numerize import numerize
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

th_emotes = {
    1:"<:TH8:825570963533463612>",
    2:"<:TH8:825570963533463612>",
    3:"<:TH8:825570963533463612>",
    4:"<:TH8:825570963533463612>",
    5:"<:TH8:825570963533463612>",
    6:"<:TH8:825570963533463612>",
    7:"<:TH8:825570963533463612>",
    8:"<:TH8:825570963533463612>",
    9:"<:TH9:825571026326781963>",
    10:"<:TH10:825571431131119666>",
    11:"<:TH11:825571502643871754>",
    12:"<:TH12:825571612325052427>",
    13:"<:TH13:825662803901415444>",
    14:"<:TH14:831443497994289153>",
    15:"<:TH15:1028948643828486215>"
    }

maxHomeLevels = {
    1:[0,0,0],
    2:[3,0,0],
    3:[8,0,0],
    4:[12,0,0],
    5:[17,4,0],
    6:[22,7,0],
    7:[36,12,5],
    8:[56,19,10],
    9:[77,30,60],
    10:[99,48,80],
    11:[124,59,120],
    12:[160,67,170],
    13:[191,75,225],
    14:[254,78,245],
    15:[309,84,265]
    }

hero_emotes = {
    "Barbarian King":"<:BarbarianKing:825723990088613899>",
    "Archer Queen":"<:ArcherQueen:825724358512607232>",
    "Grand Warden":"<:GrandWarden:825724495896510464>",
    "Royal Champion":"<:RoyalChampion:825724608987529226>",
    "Battle Machine":"<:BH_HeroStrength:827731911849279507>"
}

fileLocks = {
    'alliance': asyncio.Lock(),
    'members': asyncio.Lock(),
    'warlog': asyncio.Lock(),
    'clangames': asyncio.Lock(),
    'capitalraid': asyncio.Lock()
    }

membershipGrid = ["Member", "Elder", "Co-Leader", "Leader"]

warTypeGrid = {
    'random':'classic',
    'friendly':'friendly',
    'cwl':'cwl'
    }

warResultGrid = {
    'winning':'won',
    'tied':'tie',
    'losing':'lost',
    'won':'won',
    'tie':'tie',
    'lost':'lost',
    '':'',
    }

def get_th_emote(th:int):
    return th_emotes[th]

def response_check(ctx, m):
    if m.author.id == ctx.author.id:
        if m.channel.id == ctx.channel.id:
            return True
        elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
            return True
        else:
            return False
    else:
        return False

async def token_confirmation(self, ctx: commands.Context) -> bool:
    def chk_token(m):
        return response_check(ctx=ctx,m=m)
    confirm_token = "".join(random.choices((*ascii_letters, *digits), k=16))
    await ctx.send(f"`{confirm_token}`")
    try:
        message = await ctx.bot.wait_for("message",timeout=60,check=chk_token)
    except asyncio.TimeoutError:
        await ctx.send("Confirmation sequence timed out. Please try again.")
        return False
    else:
        if message.content.strip() == confirm_token:
            return True
        else:
            await ctx.send("Did not receive a valid confirmation token. Sequence cancelled.")
            return False

async def standard_confirmation(self, ctx: commands.Context) -> bool:
    def chk_standard(m):
        return response_check(ctx=ctx,m=m)
    try:
        message = await ctx.bot.wait_for("message",timeout=60,check=chk_standard)
    except asyncio.TimeoutError:
        await ctx.send("Confirmation sequence timed out. Please try again.")
        return False
    else:
        if message.content.strip().lower() == "yes":
            return True
        else:
            await ctx.send("Did not receive a confirmation. Sequence cancelled.")
            return False

async def react_confirmation(self,ctx,cMsg):
    emojiList = ['<:green_check:838461472324583465>','<:red_cross:838461484312428575>']

    def chk_reaction(r,u):
        if str(r.emoji) in emojiList and r.message.id == cMsg.id and u.id == ctx.author.id:
            return True
        else:
            return False

    for emoji in emojiList:
        await cMsg.add_reaction(emoji)

    try:
        reaction, user = await ctx.bot.wait_for("reaction_add",timeout=20,check=chk_reaction)
    except asyncio.TimeoutError:
        await ctx.send("Confirmation sequence timed out. Please try again.")
        await cMsg.remove_reaction('<:green_check:838461472324583465>',ctx.bot.user)
        await cMsg.remove_reaction('<:red_cross:838461484312428575>',ctx.bot.user)
        return False
    else:
        if str(reaction.emoji) == '<:green_check:838461472324583465>':
            await cMsg.remove_reaction('<:green_check:838461472324583465>',ctx.bot.user)
            await cMsg.remove_reaction('<:red_cross:838461484312428575>',ctx.bot.user)
            return True
        else:
            await ctx.send("Cancelling...")
            await cMsg.remove_reaction('<:green_check:838461472324583465>',ctx.bot.user)
            await cMsg.remove_reaction('<:red_cross:838461484312428575>',ctx.bot.user)
            return False

def clashFileLock(locktype):
    if locktype not in list(fileLocks.keys()):
        fileLocks[locktype] = asyncio.Lock()
    return fileLocks[locktype]

async def datafile_retrieve(self,ftype,season=None):
    async with clashFileLock('alliance'):
        with open(self.cDirPath+'/alliance.json','r') as file:
            allianceJson = json.load(file)
    if ftype == 'alliance':
        return allianceJson

    if season and season in allianceJson['trackedSeasons']:
        dPath = self.cDirPath+'/'+season
    else:
        dPath = self.cDirPath

    if ftype == 'members':
        async with clashFileLock('members'):
            with open(dPath+'/members.json','r') as file:
                membersJson = json.load(file)
        return membersJson
    if ftype == 'warlog':
        async with clashFileLock('warlog'):
            with open(dPath+'/warlog.json','r') as file:
                warlogJson = json.load(file)
        return warlogJson
    if ftype == 'clangames':
        async with clashFileLock('clangames'):
            with open(dPath+'/clangames.json','r') as file:
                clangamesJson = json.load(file)
        return clangamesJson
    if ftype == 'capitalraid':
        async with clashFileLock('capitalraid'):
            with open(dPath+'/capitalraid.json','r') as file:
                clangamesJson = json.load(file)
        return clangamesJson

async def datafile_save(self,file,new_data):
    if file == 'alliance':
        async with clashFileLock('alliance'):
            with open(self.cDirPath+'/alliance.json','w') as file:
                json.dump(new_data,file,indent=2)
        return
    if file == 'members':
        async with clashFileLock('members'):
            with open(self.cDirPath+'/members.json','w') as file:
                json.dump(new_data,file,indent=2)
        return
    if file == 'warlog':
        async with clashFileLock('warlog'):
            with open(self.cDirPath+'/warlog.json','w') as file:
                json.dump(new_data,file,indent=2)
        return
    if file == 'clangames':
        async with clashFileLock('clangames'):
            with open(self.cDirPath+'/clangames.json','w') as file:
                json.dump(new_data,file,indent=2)
        return
    if file == 'capitalraid':
        async with clashFileLock('capitalraid'):
            with open(self.cDirPath+'/capitalraid.json','w') as file:
                json.dump(new_data,file,indent=2)
        return

async def get_current_alliance(self,rdict=False):
    allianceJson = await datafile_retrieve(self,'alliance')
    if rdict:
        clansList = allianceJson['clans']
        memberList = allianceJson['members']
    else:
        clansList = list(allianceJson['clans'].keys())
        memberList = list(allianceJson['members'].keys())
    return clansList,memberList

async def get_current_season():
    helsinkiTz = pytz.timezone("Europe/Helsinki")
    currSeason = f"{datetime.now(helsinkiTz).month}-{datetime.now(helsinkiTz).year}"
    return currSeason

async def clash_embed(ctx, title=None, message=None, url=None, show_author=True, color=None, thumbnail=None, image=None):
    if not title:
        title = ""
    if not message:
        message = ""
    if color == "success":
        color = 0x00FF00
    elif color == "fail":
        color = 0xFF0000
    else:
        color = await ctx.embed_color()
    if url:
        embed = discord.Embed(title=title,url=url,description=message,color=color)
    else:
        embed = discord.Embed(title=title,description=message,color=color)
    if show_author:
        embed.set_author(name=f"{ctx.author.display_name}#{ctx.author.discriminator}",icon_url=ctx.author.avatar_url)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text="AriX Alliance | Clash of Clans",icon_url="https://i.imgur.com/TZF5r54.png")
    return embed

async def player_shortfield(self,ctx,pObject):
    hero_description = ""
    if pObject.player.town_hall >= 7:
        hero_description = f"{hero_emotes['Barbarian King']} {pObject.barbarianKing}"
    if pObject.player.town_hall >= 9:
        hero_description += f"\u2000{hero_emotes['Archer Queen']} {pObject.archerQueen}"
    if pObject.player.town_hall >= 11:
        hero_description += f"\u2000{hero_emotes['Grand Warden']} {pObject.grandWarden}"
    if pObject.player.town_hall >= 13:
        hero_description += f"\u2000{hero_emotes['Royal Champion']} {pObject.royalChampion}"

    title = f"{pObject.name} ({pObject.tag})"
    fieldStr = f"<:Exp:825654249475932170>{pObject.exp_level}\u3000{th_emotes.get(pObject.town_hall,'TH')} {pObject.thDesc}\u3000{hero_description}"

    return title,fieldStr

async def player_embed(self,ctx,pObject):
    if pObject.isMember:
        mStatus = f"***{pObject.memberStatus} of {pObject.homeClan['name']}***\n\n"
    else:
        mStatus = ""

    league = await self.cClient.get_league_named(pObject.league)

    pEmbed = await clash_embed(ctx,
        title=f"{pObject.name} ({pObject.tag})",
        message=f"{mStatus}<:Exp:825654249475932170>{pObject.exp_level}\u3000<:Clan:825654825509322752> {pObject.clanDesc}",
        url=f"https://www.clashofstats.com/players/{pObject.tag.replace('#','')}",
        thumbnail=league.icon.url)

    maxTroops = maxHomeLevels[pObject.town_hall]
    rushedTroops = maxHomeLevels[(pObject.town_hall-1)]

    hero_description = ""
    if pObject.player.town_hall >= 7:
        hero_description = f"\n**Heroes**\n{hero_emotes['Barbarian King']} {pObject.barbarianKing}"
    if pObject.player.town_hall >= 9:
        hero_description += f"\u3000{hero_emotes['Archer Queen']} {pObject.archerQueen}"
    if pObject.player.town_hall >= 11:
        hero_description += f"\u3000{hero_emotes['Grand Warden']} {pObject.grandWarden}"
    if pObject.player.town_hall >= 13:
        hero_description += f"\u3000{hero_emotes['Royal Champion']} {pObject.royalChampion}"

    troopStrength = f"<:TotalTroopStrength:827730290491129856> {pObject.homeTroopStrength}/{maxTroops[0]} *(Rushed: {round(max((1-(pObject.homeTroopStrength/rushedTroops[0])),0)*100)}%)*"
    if pObject.player.town_hall >= 5:
        troopStrength += f"\n<:TotalSpellStrength:827730290294259793> {pObject.homeSpellStrength}/{maxTroops[1]} *(Rushed: {round(max((1-(pObject.homeTroopStrength/rushedTroops[1])),0)*100)}%)*"                        
    if pObject.player.town_hall >= 7:
        troopStrength += f"\n<:TotalHeroStrength:827730291149635596> {pObject.homeHeroStrength}/{maxTroops[2]} *(Rushed: {round(max((1-(pObject.homeTroopStrength/rushedTroops[2])),0)*100)}%)*"

    pEmbed.add_field(
        name="**Home Village**",
        value=f"{th_emotes.get(pObject.town_hall,'TH')} {pObject.thDesc}\u3000<:HomeTrophies:825589905651400704> {pObject.trophies}\u3000<:TotalStars:825756777844178944> {pObject.warStars}"
            + f"{hero_description}"
            + "\n**Strength**"
            + f"\n{troopStrength}"
            + "\n\u200b",
        inline=False)

    #if pObject.player.builder_hall > 0:
    #    pEmbed.add_field(
    #        name="**Builder Base**",
    #        value=f"<:BuilderHall:825640713215410176> {pObject.player.builder_hall}\u3000<:BuilderTrophies:825713625586466816> {pObject.player.versus_trophies} (best: {pObject.player.best_versus_trophies})"
    #            + "\n**Strength**"
    #            + f"\n<:BH_TroopStrength:827732057554812939> {pObject.builderTroopStrength}\u3000{hero_emotes['Battle Machine']} {pObject.battleMachine}"
    #            + "\n\u200b",
    #        inline=False)

    if pObject.isMember:
        if isinstance(pObject.arixLastUpdate,str):
            lastseen_tdelta = datetime.datetime.now() - datetime.datetime.strptime(player.arixLastUpdate,"%Y-%m-%d %H:%M:%S.%f")
            lastseen_seconds = lastseen_tdelta.total_seconds()
            lastseen_days,lastseen_seconds = divmod(lastseen_seconds,86400)
            lastseen_hours,lastseen_seconds = divmod(lastseen_seconds,3600)
            lastseen_minutes,lastseen_seconds = divmod(lastseen_seconds,60)
        elif isinstance(pObject.arixLastUpdate,float):
            cnow = time.time()
            dtime = cnow - pObject.arixLastUpdate                            
            dtime_days,dtime = divmod(dtime,86400)
            dtime_hours,dtime = divmod(dtime,3600)
            dtime_minutes,dtime = divmod(dtime,60)

        lastseen_text = ''
        if dtime_days > 0:
            lastseen_text += f"{int(dtime_days)} days "
        if dtime_hours > 0:
            lastseen_text += f"{int(dtime_hours)} hours "
        if dtime_minutes > 0:
            lastseen_text += f"{int(dtime_minutes)} mins "
        if lastseen_text == '':
            lastseen_text = "a few seconds "

        lootGold = numerize.numerize(pObject.arixLoot['gold']['season'],1)
        lootElixir = numerize.numerize(pObject.arixLoot['elixir']['season'],1)
        lootDarkElixir = numerize.numerize(pObject.arixLoot['darkElixir']['season'],1)

        if pObject.arixLoot['gold']['lastUpdate'] >= 2000000000:
            lootGold = "max"
        if pObject.arixLoot['elixir']['lastUpdate'] >= 2000000000:
            lootElixir = "max"
        if pObject.arixLoot['darkElixir']['lastUpdate'] >= 2000000000:
            lootDarkElixir = "max"

        clanCapitalGold = numerize.numerize(pObject.arixClanCapital['capitalContributed']['season'],1)
        capitalGoldLooted = numerize.numerize(pObject.arixClanCapital['capitalRaids']['resources'],1)
        raidMedalsEarned = pObject.arixClanCapital['capitalRaids']['medals']

        pEmbed.add_field(
            name=f"**Current Season Stats with AriX**",
            value=f":stopwatch: Last updated: {lastseen_text}ago"
                + f"\n<a:aa_AriX:1031773589231374407> {int(pObject.clanMembership['timeInHomeClan']/86400)} day(s) spent in {pObject.homeClan['name']}"
                + "\n**Donations**"
                + f"\n<:donated:825574412589858886> {pObject.arixDonations['sent']['season']:,}\u3000<:received:825574507045584916> {pObject.arixDonations['received']['season']:,}"
                + "\n**Loot**"
                + f"\n<:gold:825613041198039130> {lootGold}\u3000<:elixir:825612858271596554> {lootElixir}\u3000<:darkelixir:825640568973033502> {lootDarkElixir}"
                + "\n**Clan Capital**"
                + f"\n<:CapitalGoldContributed:971012592057339954> {clanCapitalGold}\u3000<:CapitalRaids:1034032234572816384> {capitalGoldLooted}\u3000<:RaidMedals:983374303552753664> {raidMedalsEarned}"
                + "\n**War Performance**"
                + f"\n<:TotalWars:827845123596746773> {pObject.arixWarStats['warsParticipated']}\u3000<:TotalStars:825756777844178944> {pObject.arixWarStats['offenseStars']}\u3000<:Triple:1034033279411687434> {pObject.arixWarStats['triples']}\u3000<:MissedHits:825755234412396575> {pObject.arixWarStats['missedAttacks']}"
                + "\n*Use `;mywarlog` to view your War Log.*"
                + "\n\u200b",
            inline=False)
    return pEmbed

class ClashPlayerError(Exception):
    def __init__(self,tag):
        self.errTag = tag

class ClashClanError(Exception):
    def __init__(self,tag):
        self.errTag = tag

    async def clanErrEmbed(self):
        errEmbed = await clash_embed(ctx,
            message=f"Unable to find a clan with the tag {self.errTag}.",
            color="fail")
        return errEmbed

async def getClan(self,ctx,tag,war=False):
    if not coc.utils.is_valid_tag(tag):
        raise ClashClanError(tag)
        return None
    try:
        clan = await self.cClient.get_clan(tag)
    except coc.NotFound:
        raise ClashClanError(tag)
        return None
    
    clanData, memberData = await get_current_alliance(self,rdict=True)
    clanJson = clanData.get(clan.tag,{})

    warlogJson = await datafile_retrieve(self,'warlog')
    clanWarLog = warlogJson.get(clan.tag,{})

    clanObject = aClan(
        ctx=ctx,
        clan=clan,
        allianceJson=clanJson,
        warlogJson=clanWarLog)
    return clanObject

async def getPlayer(self,ctx,tag,jsonOverride=None,noApi=False):
    clanData, memberData = await get_current_alliance(self,rdict=True)
    if not coc.utils.is_valid_tag(tag):
        raise ClashPlayerError(tag)
        return None
    if noApi:
        player = None
    else:
        try:
            player = await self.cClient.get_player(tag)
        except coc.NotFound:
            raise ClashPlayerError(tag)
            return None
        except:
            if tag not in list(memberData.keys()):
                raise ClashPlayerError(tag)
                return None
            else:
                player = None
    
    if jsonOverride:
        memberStatsJson = jsonOverride
    else:
        memberStatsJson = await datafile_retrieve(self,'members')
    
    memberJson = memberData.get(player.tag,{})
    memberStats = memberStatsJson.get(player.tag,{})
        
    memberObject = aMember(
        ctx=ctx,
        tag=tag,
        player=player,
        allianceJson=memberJson,
        memberStats=memberStats)
    return memberObject

class MemberClassError(Exception):
    def __init__(self):
        pass

class MemberPromoteError(Exception):
    def __init__(self):
        pass

class aClan():
    def __init__(self,ctx,clan,allianceJson=None,warlogJson=None):
        self.ctx = ctx
        self.timestamp = time.time()
        self.clan = clan

        recruitmentDict = { 
            'townHall': [],
            'notes': ""
            }

        #from AllianceJson
        self.isAllianceClan = bool(allianceJson)
        self.abbrievation = allianceJson.get('abbr',"")

        try:
            jsonDesc = allianceJson['description']
        except:
            jsonDesc = None

        if bool(jsonDesc):
            self.description = jsonDesc
        else:
            self.description = self.clan.description
        self.arixDescription = jsonDesc

        self.recruitment = allianceJson.get('recruitment',recruitmentDict)

        self.warState = allianceJson.get('warState',None)
        self.warStateChange = False

        self.raidWeekendState = allianceJson.get('raidWeekendState',None)
        self.raidStateChange = False

        warlogChk = {wID:w for (wID,w) in warlogJson.items() if self.timestamp > w['endTime'] and w.get('state','')!='warEnded'}

        for wID, war in warlogChk.items():
            warlogJson[wID]['state'] = 'warEnded'
            warlogJson[wID]['results']['result'] = warResultGrid[war['results']['result']]

        self.warlog = warlogJson

    async def updateWar(self, client):
        currWar = await client.get_clan_war(self.clan.tag)
        self.currentWar = aClanWar(self.ctx,currWar)
        if self.currentWar.war.state != self.warState:
            self.warState = self.currentWar.war.state
            self.warStateChange = True

    async def updateRaidWeekend(self,apikey):
        apiHeader = {'Accept':'application/json','authorization':'Bearer '+apikey}
        apiUrl = f"https://api.clashofclans.com/v1/clans/%23{self.clan.tag.replace('#','')}/capitalraidseasons?limit=1"
        apiResult = requests.get(apiUrl,headers=apiHeader)

        if apiResult.status_code != 200:
            return

        raidJson = apiResult.json()
        self.raidWeekend = aRaidWeekend(self.ctx,raidJson['items'][0])

        if self.raidWeekend.state != self.raidWeekendState:
            self.raidWeekendState = self.raidWeekend.state
            self.raidStateChange = True

    def setAbbr(self,new_abbr:str):
        self.abbrievation = new_abbr

    def setDesc(self,new_desc:str):
        self.arixDescription = new_desc

    def setRecTH(self,*th_levels:int):
        for th in th_levels:
            if th not in self.recruitment['townHall']:
                self.recruitment['townHall'].append(th)

    def setRecNotes(self,note:str):
        self.recruitment['notes'] = note

    def toJson(self):
        allianceJson = {
            'name':self.clan.name,
            'abbr':self.abbrievation,
            'description': self.arixDescription,
            'recruitment': self.recruitment,
            'warState': self.warState,
            'raidWeekendState': self.raidWeekendState
            }
        warlogJson = self.warlog
        return allianceJson, warlogJson

class aClanWar():
    #AriX Class to handle Clan Wars.
    def __init__(self,ctx,war):
        self.ctx = ctx
        self.war = war

        self.warID = str(self.war.start_time.time.timestamp())
        self.warType = warTypeGrid[war.type]

        self.totalAttacks = self.war.attacks_per_member * self.war.team_size

        try:
            self.avgStars = round(sum([attack.stars for attack in self.war.clan.attacks]) / len([attack for attack in self.war.clan.attacks]),2)
        except:
            self.avgStars = 0

        self.triples = [attack for attack in self.war.clan.attacks if attack.stars==3 and attack.attacker.town_hall <= attack.defender.town_hall]

    def toJson(self):
        memberSummary = {}
        memberDetail = {}

        for member in self.war.clan.members:
            sJson = {
                'warType': self.warType,
                'result': warResultGrid[self.war.status], 
                'clan': {
                    'tag': self.war.clan.tag,
                    'name': self.war.clan.name,
                    },
                'opponent': {
                    'tag': self.war.opponent.tag,
                    'name': self.war.opponent.name,
                    },
                'totalAttacks': len(member.attacks),
                'triples': len([attack for attack in member.attacks if attack.stars==3 and attack.attacker.town_hall <= attack.defender.town_hall]),
                'attackStars': int(sum([getattr(a,'stars',0) for a in member.attacks])),
                'attackDestruction': float(sum([getattr(a,'destruction',0) for a in member.attacks])),
                'defenseStars': int(getattr(member.best_opponent_attack,"stars",0)),
                'defenseDestruction': float(getattr(member.best_opponent_attack,"destruction",0)),
                'missedAttacks': self.war.attacks_per_member - len(member.attacks)
                }
            memberSummary[member.tag] = sJson

        warLogJson = {
            'warType': self.warType,
            'warSize': self.war.team_size,
            'state': self.war.state,
            'startTime': self.war.start_time.time.timestamp(),
            'endTime': self.war.end_time.time.timestamp(),
            'opponent': {
                'tag': self.war.opponent.tag,
                'name': self.war.opponent.name,
                },
            'performance': {
                'totalAttacks':len([attack for attack in self.war.clan.attacks]),
                'triples': len(self.triples),
                'average': self.avgStars,
                'missed': self.totalAttacks - self.war.clan.attacks_used,
                },
            'results': {
                'result': self.war.status,
                'attackStars': self.war.clan.stars,
                'attackDestruction': self.war.clan.destruction,
                'defenseStars': self.war.opponent.stars,
                'defenseDestruction': self.war.opponent.destruction,
                }
            }
        return warLogJson, memberSummary

class aRaidMember():
    def __init__(self,ctx,memberJson,offRew,defRew):
        self.tag = memberJson.get('tag')
        self.name = memberJson.get('name')
        self.attacks = memberJson.get('attacks')
        self.attackLimit = memberJson.get('attackLimit')
        self.bonusLimit = memberJson.get('bonusAttackLimit')
        self.resourcesLooted = memberJson.get('capitalResourcesLooted')
        self.raidMedalsEarned = (self.attacks * offRew) + defRew

class aRaidDistrict():
    def __init__(self,districtJson):
        self.id = districtJson.get('id',0)
        self.name = districtJson.get('name','')
        self.districtHallLevel = districtJson.get('districtHallLevel',0)
        self.destructionPct = districtJson.get('destructionPercent',0)
        self.attackCount = districtJson.get('attackCount',0)
        self.totalLooted = districtJson.get('totalLooted',0)

class aRaidAttackLog():
    def __init__(self,ctx,logJson):
        self.ctx = ctx
        self.opponent = {
            'tag': logJson['defender']['tag'],
            'name': logJson['defender']['name']
            }
        self.attackCount = logJson.get('attackCount',0)
        self.districtCount = logJson.get('districtCount',0)
        self.districtDestroyed = logJson.get('districtsDestroyed',0)

        self.districts = []

        for district in logJson.get('districts',[]):
            district = aRaidDistrict(districtJson=district)
            self.districts.append(district)

class aRaidWeekend():
    def __init__(self,ctx,raidJson):
        self.ctx = ctx
        self.timestamp = time.time()

        self.json = raidJson

        self.state = raidJson.get('state','')

        def convertTime(timeStr):
            t1 = timeStr.split('.',1)
            t2 = time.strptime(t1[0],'%Y%m%dT%H%M%S')
            t3 = datetime(*t2[:6],tzinfo=pytz.utc)
            return t3

        startTime = convertTime(raidJson['startTime'])
        self.startTime = startTime.timestamp()

        endTime = convertTime(raidJson['endTime'])
        self.endTime = endTime.timestamp()

        self.rID = str(self.startTime)

        self.capitalTotalLoot = raidJson.get('capitalTotalLoot',0)
        self.raidsCompleted = raidJson.get('raidsCompleted',0)
        self.totalAttacks = raidJson.get('totalAttacks',0)
        self.districtsDestroyed = raidJson.get('enemyDistrictsDestroyed',0)
        self.offensiveRewards = raidJson.get('offensiveReward',0)
        self.defensiveReward = raidJson.get('defensiveReward',0)

        self.members = []
        for member in raidJson.get('members',[]):
            member = aRaidMember(
                ctx=self.ctx,
                memberJson=member,
                offRew=self.offensiveRewards,
                defRew=self.defensiveReward)
            self.members.append(member)

        self.totalMembers = len(self.members)

        self.attackLog = raidJson.get('attackLog',[])

    def toJson(self):
        memberSummary = {}
        memberDetail = {}

        for member in self.members:
            sJson = {
                'attacks': member.attacks,
                'resourcesLooted': member.resourcesLooted,
                'medalsEarned': member.raidMedalsEarned
                }
            memberSummary[member.tag] = sJson

        capitalRaidJson = self.json
        return capitalRaidJson, memberSummary

class aMember():
    #AriX Member Class to coordinate information exchange.
    def __init__(self,ctx,tag,allianceJson,memberStats,player=None):
        clanMembershipDict = { 
            'timeInHomeClan': 0,
            'currentClan': {
                'tag':None,
                'name':None,
                'role':None,
                },
            'otherClans': [],
            }

        self.ctx = ctx
        self.timestamp = time.time()
        self.player = player
        
        self.tag = tag
        self.name = getattr(self.player,'name',memberStats.get('name','Unknown'))

        #from AllianceJson
        self.homeClan = allianceJson.get('home_clan',{'tag':"",'name':""})
        self.isMember = allianceJson.get('is_member',False)
        self.memberStatus = allianceJson.get('status',"Non-Member")
        self.discordUser = allianceJson.get('discord_user',0)
        self.notes = allianceJson.get('notes',[])

        #basic player stats
        self.exp_level = getattr(self.player,'exp_level',memberStats.get('explevel',0))
        self.town_hall = getattr(self.player,'town_hall',memberStats.get('townhall',1))
        self.town_hall_wpn = getattr(self.player,'town_hall_weapon',memberStats.get('townhall_weapon',0))
        self.league = getattr(getattr(self.player,'league',None),'name',memberStats.get('league','Unranked'))
        self.trophies = getattr(self.player,'trophies',memberStats.get('trophies',0))
        self.warStars = getattr(self.player,'war_stars',memberStats.get('warStars',0))
        self.warOptIn = getattr(self.player,'war_opted_in',memberStats.get('warOptIn',False))

        if self.player:
            self.clan = {
                'tag': getattr(self.player.clan,'tag',None),
                'name': getattr(self.player.clan,'name',None),
                'role': str(getattr(self.player,'role',''))
                }
        else:
            self.clan = {
                'tag': memberStats.get('clanMembership',clanMembershipDict)['currentClan']['tag'],
                'name': memberStats.get('clanMembership',clanMembershipDict)['currentClan']['name'],
                'role': memberStats.get('clanMembership',clanMembershipDict)['currentClan']['role'],
                }

        try:
            self.clan_castle = sum([a.value for a in self.player.achievements if a.name == 'Empire Builder'])
        except:
            self.clan_castle = memberStats.get('clanCastleLevel',0)
        
        if self.town_hall >= 12:
            self.thDesc = f"**{self.town_hall}**-{self.town_hall_wpn}"
        else:
            self.thDesc = f"**{self.town_hall}**"

        if self.clan['tag']:
            self.clanDesc = f"{self.clan['role']} of **{self.clan['name']}**"
        else:
            self.clanDesc = f"No Clan"

        self.homeTroopStrength = 0
        self.homeSpellStrength = 0

        if not self.player:
            self.barbarianKing = memberStats.get('heroes',None).get('barbarianKing',0)
            self.archerQueen = memberStats.get('heroes',None).get('archerQueen',0)
            self.grandWarden = memberStats.get('heroes',None).get('grandWarden',0)
            self.royalChampion = memberStats.get('heroes',None).get('royalChampion',0)

            self.homeTroopStrength = memberStats.get('troopStrength',0)
            self.homeSpellStrength = memberStats.get('spellStrength',0)

        else:
            self.barbarianKing = sum([h.level for h in self.player.heroes if h.name=='Barbarian King'])
            self.archerQueen = sum([h.level for h in self.player.heroes if h.name=='Archer Queen'])
            self.grandWarden = sum([h.level for h in self.player.heroes if h.name=='Grand Warden'])
            self.royalChampion = sum([h.level for h in self.player.heroes if h.name=='Royal Champion'])

            self.homeTroopStrength = sum([t.level for t in self.player.troops if t.name in coc.HOME_TROOP_ORDER]) + sum([p.level for p in self.player.hero_pets])
            self.homeSpellStrength = sum([s.level for s in self.player.spells if s.name in coc.SPELL_ORDER])
            
        self.homeHeroStrength = self.barbarianKing + self.archerQueen + self.grandWarden + self.royalChampion
        
        donationsDict = {
            'received': {
                'season': 0,
                'lastUpdate': 0
                },
            'sent': {
                'season': 0,
                'lastUpdate': 0
                }
            }
        lootDict = {
            'gold': {
                'season': 0,
                'lastUpdate': 0
                },
            'elixir': {
                'season': 0,
                'lastUpdate': 0
                },
            'darkElixir': {
                'season': 0,
                'lastUpdate': 0
                }
            }
        clanGamesDict ={
            'season':0,
            'lastUpdate':0
            }
        clanCapitalDict = {
            'capitalContributed': {
                'season': 0,
                'lastUpdate': 0
                },
            'capitalRaids': {
                'attacks': 0,
                'resources': 0,
                'medals':0
                },
            }
        warDict = {
            'warsParticipated': 0,
            'offenseStars': 0,
            'defenseStars': 0,
            'totalAttacks':0,
            'triples': 0,
            'missedAttacks': 0
            }

        self.clanMembership = memberStats.get('clanMembership',clanMembershipDict)
        self.arixLastUpdate = memberStats.get('lastUpdate',0)
        self.arixClanCastleLv = memberStats.get('clanCastleLevel',0)
        self.arixDonations = memberStats.get('donations',donationsDict)
        self.arixLoot = memberStats.get('loot',lootDict)
        self.arixClanGames = memberStats.get('clanGames',clanGamesDict)
        self.arixClanCapital = memberStats.get('clanCapital',clanCapitalDict)
        self.arixWarStats = memberStats.get('warStats',warDict)
        self.arixWarLog = memberStats.get('warLog',{})
        self.arixRaidLog = memberStats.get('raidLog',{})

    def toJson(self):
        allianceJson = {
            'name':self.player.name,
            'home_clan':self.homeClan,
            'is_member':self.isMember,
            'status':self.memberStatus,
            'discord_user':self.discordUser,
            'notes':self.notes,
            }
        memberJson = {
            'tag': self.tag,
            'name': self.name,
            'lastUpdate': self.timestamp,
            'clanMembership': self.clanMembership,
            'townHallLevel': self.town_hall,
            'townHallWeapon': self.town_hall_wpn,
            'clanCastleLevel': self.clan_castle,
            'league': self.league,
            'trophies': self.trophies,
            'warStars': self.warStars,
            'warOptIn': self.warOptIn,
            'heroes': {
                'barbarianKing':self.barbarianKing,
                'archerQueen':self.archerQueen,
                'grandWarden':self.grandWarden,
                'royalChampion':self.royalChampion,
                },
            'troopStrength': self.homeTroopStrength,
            'spellStrength': self.homeSpellStrength,
            'donations': self.arixDonations,
            'loot': self.arixLoot,
            'clanGames': self.arixClanGames,
            'clanCapital': self.arixClanCapital,
            'warStats': self.arixWarStats,
            'raidLog': self.arixRaidLog,
            'warLog': self.arixWarLog,
            }
        return allianceJson,memberJson

    def newMember(self,discordUser,homeClan):
        self.homeClan = {
            'tag':homeClan.tag,
            'name':homeClan.name,
            }
        self.isMember = True
        self.memberStatus = "Member"
        self.discordUser = discordUser

        for achievement in self.player.achievements:
            if achievement.name == "Gold Grab":
                gold_total = achievement.value
            if achievement.name == "Elixir Escapade": 
                elixir_total = achievement.value
            if achievement.name == "Heroic Heist":
                darkelixir_total = achievement.value
            if achievement.name == "Most Valuable Clanmate":
                capitalgold_contributed_total = achievement.value
            if achievement.name == "Games Champion":
                clangames_total = achievement.value

        #set new baselines for loot totals
        self.arixLoot['gold']['lastUpdate'] = gold_total
        self.arixLoot['elixir']['lastUpdate'] = elixir_total
        self.arixLoot['darkElixir']['lastUpdate'] = darkelixir_total
        self.arixClanCapital['capitalContributed']['lastUpdate'] = capitalgold_contributed_total
        self.arixClanGames['lastUpdate'] = clangames_total

        #reset these to 0 as COC resets donation counts to 0 when someone changes clans
        self.arixDonations['received']['lastUpdate'] = 0
        self.arixDonations['sent']['lastUpdate'] = 0

    def removeMember(self):
        self.isMember = False
        self.memberStatus = "Non-Member"

    def updateRank(self,new_rank):
        valid_ranks = ["Member","Elder","Co-Leader","Leader"]
        if new_rank not in valid_ranks:
            raise MemberPromoteError
        else:
            self.memberStatus = new_rank

    def updateStats(self):
        if not self.player:
            #cannot update stats if player object is not provided
            return
        self.clanMembership['currentClan'] = self.clan

        if self.player.clan:
            if self.player.clan.tag == self.homeClan['tag']:
                self.clanMembership['timeInHomeClan'] += (self.timestamp - self.arixLastUpdate)
            elif self.player.clan.tag not in self.clanMembership['otherClans']:
                self.clanMembership['otherClans'].append(self.player.clan.tag)

        for achievement in self.player.achievements:
            if achievement.name == "Gold Grab":
                gold_total = achievement.value
            if achievement.name == "Elixir Escapade": 
                elixir_total = achievement.value
            if achievement.name == "Heroic Heist":
                darkelixir_total = achievement.value
            if achievement.name == "Most Valuable Clanmate":
                capitalgold_contributed_total = achievement.value
            if achievement.name == "Aggressive Capitalism":
                capitalgold_looted_total = achievement.value
            if achievement.name == "Games Champion":
                clangames_total = achievement.value

        if self.player.received >= self.arixDonations['received']['lastUpdate']:
            newDonationsRcvd = self.player.received - self.arixDonations['received']['lastUpdate']
        else:
            newDonationsRcvd = self.player.received

        if self.player.donations >= self.arixDonations['sent']['lastUpdate']:
            newDonationsSent = self.player.donations - self.arixDonations['sent']['lastUpdate']
        else:
            newDonationsSent = self.player.donations

        self.arixDonations['received']['season'] += newDonationsRcvd
        self.arixDonations['received']['lastUpdate'] = self.player.received
        self.arixDonations['sent']['season'] += newDonationsSent
        self.arixDonations['sent']['lastUpdate'] = self.player.donations

        self.arixLoot['gold']['season'] += gold_total - self.arixLoot['gold']['lastUpdate']
        self.arixLoot['gold']['lastUpdate'] = gold_total

        self.arixLoot['elixir']['season'] += elixir_total - self.arixLoot['elixir']['lastUpdate']
        self.arixLoot['elixir']['lastUpdate'] = elixir_total
        
        self.arixLoot['darkElixir']['season'] += darkelixir_total - self.arixLoot['darkElixir']['lastUpdate']
        self.arixLoot['darkElixir']['lastUpdate'] = darkelixir_total

        self.arixClanCapital['capitalContributed']['season'] += capitalgold_contributed_total - self.arixClanCapital['capitalContributed']['lastUpdate']
        self.arixClanCapital['capitalContributed']['lastUpdate'] = capitalgold_contributed_total

        self.arixClanGames['season'] += clangames_total - self.arixClanGames['lastUpdate']
        self.arixClanGames['lastUpdate'] = clangames_total

        self.arixWarStats['warsParticipated'] = len(self.arixWarLog)
        self.arixWarStats['offenseStars'] = 0
        self.arixWarStats['defenseStars'] = 0
        self.arixWarStats['totalAttacks'] = 0
        self.arixWarStats['triples'] = 0
        self.arixWarStats['missedAttacks'] = 0

        for wID,war in self.arixWarLog.items():
            self.arixWarStats['offenseStars'] += war['attackStars']
            self.arixWarStats['defenseStars'] += war['defenseStars']
            self.arixWarStats['totalAttacks'] += war['totalAttacks']
            self.arixWarStats['triples'] += war['triples']
            self.arixWarStats['missedAttacks'] += war['missedAttacks']

        self.arixClanCapital['capitalRaids']['attacks'] = 0
        self.arixClanCapital['capitalRaids']['resources'] = 0
        self.arixClanCapital['capitalRaids']['medals'] = 0

        for rID,raid in self.arixRaidLog.items():
            self.arixClanCapital['capitalRaids']['attacks'] += raid['attacks']
            self.arixClanCapital['capitalRaids']['resources'] += raid['resourcesLooted']
            self.arixClanCapital['capitalRaids']['medals'] += raid['medalsEarned']