import os
import discord
import coc
import json
import asyncio
import random
import time
import pytz

from os import path
from dotenv import load_dotenv
from redbot.core import Config, commands
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

th_emotes = {
    1:"<:TH7:825570842616397884>",
    2:"<:TH7:825570842616397884>",
    3:"<:TH7:825570842616397884>",
    4:"<:TH7:825570842616397884>",
    5:"<:TH7:825570842616397884>",
    6:"<:TH7:825570842616397884>",
    7:"<:TH7:825570842616397884>",
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

async def get_current_alliance(self):
    allianceJson = await datafile_retrieve(self,'alliance')
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

    title = f"{pObject.player.name} ({pObject.player.tag})"
    fieldStr = f"<:Exp:825654249475932170>{pObject.player.exp_level}\u3000{th_emotes.get(pObject.player.town_hall,'TH')} {pObject.thDescription}\u3000{hero_description}"

    return title,fieldStr

async def player_embed(self,ctx,pObject):
    pEmbed = await clash_embed(ctx,
        title=f"{pObject.player.name} ({pObject.player.tag})",
        message=f"<:Exp:825654249475932170>{pObject.player.exp_level}\u3000<:Clan:825654825509322752> {pObject.clanDescription}",
        url=f"https://www.clashofstats.com/players/{pObject.player.tag.replace('#','')}",
        thumbnail=pObject.player.league.icon.url)

    maxTroops = maxHomeLevels[pObject.player.town_hall]

    hero_description = ""
    if pObject.player.town_hall >= 7:
        hero_description = f"\n**Heroes**\n{hero_emotes['Barbarian King']} {pObject.barbarianKing}"
    if pObject.player.town_hall >= 9:
        hero_description += f"\u3000{hero_emotes['Archer Queen']} {pObject.archerQueen}"
    if pObject.player.town_hall >= 11:
        hero_description += f"\u3000{hero_emotes['Grand Warden']} {pObject.grandWarden}"
    if pObject.player.town_hall >= 13:
        hero_description += f"\u3000{hero_emotes['Royal Champion']} {pObject.royalChampion}"

    troopStrength = f"<:TotalTroopStrength:827730290491129856> {pObject.homeTroopStrength}/{maxTroops[0]} ({round((pObject.homeTroopStrength/maxTroops[0])*100)}%)"
    if pObject.player.town_hall >= 5:
        troopStrength += f"\u3000<:TotalSpellStrength:827730290294259793> {pObject.homeSpellStrength}/{maxTroops[1]} ({round((pObject.homeSpellStrength/maxTroops[1])*100)}%)"                        
    if pObject.player.town_hall >= 7:
        troopStrength += f"\n<:TotalHeroStrength:827730291149635596> {pObject.homeHeroStrength}/{maxTroops[2]} ({round((pObject.homeHeroStrength/maxTroops[2])*100)}%)"

    pEmbed.add_field(
        name="**Home Village**",
        value=f"{th_emotes.get(pObject.player.town_hall,'TH')} {pObject.thDescription}\u3000<:HomeTrophies:825589905651400704> {pObject.player.trophies} (best: {pObject.player.best_trophies})"
            + f"{hero_description}"
            + "\n**Strength**"
            + f"\n{troopStrength}"
            + "\n\u200b",
        inline=False)

    if pObject.player.builder_hall > 0:
        pEmbed.add_field(
            name="**Builder Base**",
            value=f"<:BuilderHall:825640713215410176> {pObject.player.builder_hall}\u3000<:BuilderTrophies:825713625586466816> {pObject.player.versus_trophies} (best: {pObject.player.best_versus_trophies})"
                + "\n**Strength**"
                + f"\n<:BH_TroopStrength:827732057554812939> {pObject.builderTroopStrength}\u3000{hero_emotes['Battle Machine']} {pObject.battleMachine}"
                + "\n\u200b",
            inline=False)
    return pEmbed

class ClashPlayerError(Exception):
    def __init__(self,tag):
        self.errTag = tag

class ClashClanError(Exception):
    def __init__(self,tag):
        self.errTag = tag

async def getPlayer(self,ctx,tag,force_member=False):
    if not coc.utils.is_valid_tag(tag):
        raise ClashPlayerError(tag)
        return None
    try:
        player = await self.cClient.get_player(tag)
    except coc.NotFound:
        raise ClashPlayerError(tag)
        return None
    
    allianceJson = await datafile_retrieve(self,'alliance')
    memberJson = allianceJson['members'].get(player.tag,None)

    if memberJson:
        membershipStatus = memberJson['status']
    else:
        memberJson = {}
        membershipStatus = "Non-Member"

    if memberJson.get('is_member',False) or force_member:
        memberStatsJson = await datafile_retrieve(self,'members')
        memberStats = memberStatsJson.get(player.tag,{})
        memberObject = aMember(ctx,player,memberJson,memberStats)
        return memberObject
    else:
        playerObject = aPlayer(ctx,player,memberJson)
        return playerObject

async def getClan(self,ctx,tag):
    if not coc.utils.is_valid_tag(tag):
        raise ClashClanError(tag)
        return None
    try:
        clan = await self.cClient.get_clan(tag)
    except coc.NotFound:
        raise ClashClanError(tag)
        return None
    
    allianceJson = await datafile_retrieve(self,'alliance')
    clanJson = allianceJson['clans'].get(clan.tag,{})

    if memberJson:
        membershipStatus = memberJson['status']
    else:
        membershipStatus = "Non-Member"

    if memberJson.get('is_member',False) or force_member:
        memberStatsJson = await datafile_retrieve(self,'members')
        memberStats = memberStatsJson.get(player.tag,{})
        memberObject = aMember(ctx,player,memberJson,memberStats)
        return memberObject
    else:
        playerObject = aPlayer(ctx,player,memberJson)
        return playerObject

class MemberClassError(Exception):
    def __init__(self):
        pass

class MemberPromoteError(Exception):
    def __init__(self,mObject):
        self.mObject = mObject

    async def get_embed(self,mObject):
        errEmbed = await clash_embed(ctx,
            message=f"Unable to promote **{mObject.player.tag} {mObject.player.name}**. Player is currently a {mObject.memberStatus}.",
            color="fail")
        self.eEmbed = errEmbed

class aClan():
    def __init__(self,ctx,clan,allianceJson):
        self.ctx = ctx
        self.clan = clan

        #from AllianceJson
        self.abbrievation = allianceJson.get('abbr',"")
        self.description = allianceJson.get('description',self.clan.description)

class aPlayer():
    def __init__(self,ctx,player,allianceJson):
        self.ctx = ctx
        self.player = player

        #from AllianceJson
        self.homeClan = allianceJson.get('home_clan',"Non-Member")
        self.isMember = allianceJson.get('is_member',False)
        self.memberStatus = allianceJson.get('status',"Non-Member")
        self.discordUser = allianceJson.get('discord_user',0)
        self.notes = allianceJson.get('notes',[])
        
        if self.player.town_hall >= 12:
            th_desc = f"**{self.player.town_hall}**-{self.player.town_hall_weapon}"
        else:
            th_desc = f"**{self.player.town_hall}**"
        self.thDescription = th_desc

        if self.player.clan:
            self.clanDescription = f"{self.player.role} of **{self.player.clan.name}**"
        else:
            self.clanDescription = f"No Clan"

        self.homeTroopStrength = 0
        self.homeSpellStrength = 0
        self.homeHeroStrength = 0
        self.builderTroopStrength = 0

        self.barbarianKing = 0
        self.archerQueen = 0
        self.grandWarden = 0
        self.royalChampion = 0
        self.battleMachine = 0

        for hero in self.player.heroes:
            if hero.name == "Barbarian King":                        
                self.barbarianKing = hero.level
                self.homeHeroStrength += hero.level
            if hero.name == "Archer Queen":                        
                self.archerQueen = hero.level
                self.homeHeroStrength += hero.level
            if hero.name == "Grand Warden":                        
                self.grandWarden = hero.level
                self.homeHeroStrength += hero.level
            if hero.name == "Royal Champion":                        
                self.royalChampion = hero.level
                self.homeHeroStrength += hero.level
            if hero.name == "Battle Machine":
                self.battleMachine = hero.level

        for troop in self.player.troops:
            if troop.name in coc.HOME_TROOP_ORDER:
                self.homeTroopStrength += troop.level
            if troop.name in coc.HERO_PETS_ORDER:
                self.homeTroopStrength += troop.level
            if troop.name in coc.BUILDER_TROOPS_ORDER:
                self.builderTroopStrength += troop.level

        for spell in self.player.spells:
            if spell.name in coc.SPELL_ORDER:
                self.homeSpellStrength += spell.level

class aMember(aPlayer):
    #AriX Member Class to coordinate information exchange.
    def __init__(self,ctx,player,memberJson,memberStats):
        self.ctx = ctx
        aPlayer.__init__(self,self.ctx,player,memberJson)

        self.timestamp = time.time()

        clanMembershipDict = { 
            'timeInHomeClan': 0,
            'otherClans': []
            }
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
        clanCapitalDict = {
            'capitalContributed': {
                'season': 0,
                'lastUpdate': 0
                },
            'capitalLooted': {
                'season': 0,
                'lastUpdate': 0
                }
            }
        warDict = {
            'warsParticipated': 0,
            'offenseStars': 0,
            'defenseStars': 0,
            'totalAttacks':0,
            'triples': 0,
            'missedAttacks': 0
            }

        self.arixLastUpdate = memberStats.get('lastUpdate',0)
        self.arixTownHallLv = memberStats.get('townHallLevel',1)
        self.arixClanCastleLv = memberStats.get('clanCastleLevel',0)
        self.arixClanMembership = memberStats.get('clanMembership',clanMembershipDict)
        self.arixDonations = memberStats.get('donations',donationsDict)
        self.arixLoot = memberStats.get('loot',lootDict)
        self.arixClanCapital = memberStats.get('clanCapital',clanCapitalDict)
        self.arixWarStats = memberStats.get('warStats',warDict)
        self.arixWarLog = memberStats.get('warLog',[])

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
            'name': self.player.name,
            'lastUpdate': self.timestamp,
            'townHallLevel': self.arixTownHallLv,
            'clanCastleLevel': self.arixClanCastleLv,
            'clanMembership': self.arixClanMembership,
            'donations': self.arixDonations,
            'loot': self.arixLoot,
            'clanCapital': self.arixClanCapital,
            'warStats': self.arixWarStats,
            'warLog': self.arixWarLog
            }
        return allianceJson,memberJson

    def newMember(self,discordUser,homeClan):
        self.homeClan = homeClan
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
            if achievement.name == "Aggressive Capitalism":
                capitalgold_looted_total = achievement.value

        #reset these to 0 as COC resets donation counts to 0 when someone changes clans
        self.arixDonations['received']['lastUpdate'] = 0
        self.arixDonations['sent']['lastUpdate'] = 0

        #set new baselines for loot totals
        self.arixLoot['gold']['lastUpdate'] = gold_total
        self.arixLoot['elixir']['lastUpdate'] = elixir_total
        self.arixLoot['darkElixir']['lastUpdate'] = darkelixir_total
        self.arixClanCapital['capitalContributed']['lastUpdate'] = capitalgold_contributed_total
        self.arixClanCapital['capitalLooted']['lastUpdate'] = capitalgold_looted_total

    def removeMember(self):
        self.isMember = False
        self.memberStatus = "Non-Member"

    def updateRank(self,new_rank):
        valid_ranks = ["Member","Elder","Co-Leader","Leader"]
        if new_rank not in valid_ranks:
            raise MemberPromoteError(self)
        else:
            self.memberStatus = new_rank

    def updateStats(self):
        self.arixTownHallLv = self.player.town_hall

        if self.player.clan.tag == self.homeClan:
            self.arixClanMembership['timeInHomeClan'] += (self.timestamp - self.arixLastUpdate)
        elif self.player.clan.tag not in self.arixClanMembership['otherClans']:
            self.arixClanMembership['otherClans'].append(self.player.clan.tag)

        for achievement in self.player.achievements:
            if achievement.name == "Empire Builder":
                self.arixClanCastleLv = achievement.value
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

        self.arixClanCapital['capitalLooted']['season'] += capitalgold_looted_total - self.arixClanCapital['capitalLooted']['lastUpdate']
        self.arixClanCapital['capitalLooted']['lastUpdate'] = capitalgold_looted_total