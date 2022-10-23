import os
import sys

import discord
import coc

import json
import asyncio
import random
import time

from dotenv import load_dotenv
from redbot.core import Config, commands
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

load_dotenv()

sys.path.append(os.getenv("RESOURCEPATH"))

import clash_resources
from clash_resources import token_confirmation, standard_confirmation, react_confirmation, datafile_retrieve, datafile_save, get_current_alliance, get_current_season, clash_embed
from clash_resources import getPlayer, player_shortfield, player_embed, ClashPlayerError
from clash_resources import getClan, ClashClanError

membershipGrid = ["Member", "Elder", "Co-Leader", "Leader"]

async def datafile_defaults():
    currSeason = await get_current_season()
    alliance = {'currentSeason': currSeason,
                'trackedSeasons': [],
                'clans':{},
                'members':{}
                }
    members = {}
    warlog = {}
    capitalraid = {}
    return alliance,members,warlog,capitalraid

class AriXClashDataMgr(commands.Cog):
    """AriX Clash of Clans Data Module."""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=2170311125702803,force_registration=True)
        default_global = {
            "last_data_update":0,
            "last_data_log":0,
            "update_runtimes":[],
            }
        default_guild = {
            "postlogs":False,
            "logchannel":0,
            }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def cog_initialize(self):
        #Initializes API Login and Data Directory.
        coc_client = coc.EventsClient()
        
        try:
            await coc_client.login(os.getenv("CLASH_DEV_EMAIL"), os.getenv("CLASH_DEV_PASSWORD"))
        except coc.InvalidCredentials as error:
            await ctx.send("error")
        
        self.cDirPath = os.getenv("DATAPATH")
        self.cClient = coc_client

        currSeason = await get_current_season()
        default_alliance, default_members, default_warlog, default_capitalraid = await datafile_defaults()

        if not os.path.exists(self.cDirPath+'/alliance.json'):
            await datafile_save(self,'alliance',default_alliance)
        if not os.path.exists(self.cDirPath+'/members.json'):
            await datafile_save(self,'members',default_members)
        if not os.path.exists(self.cDirPath+'/warlog.json'):
            await datafile_save(self,'warlog',default_warlog)
        if not os.path.exists(self.cDirPath+'/capitalraid.json'):
            await datafile_save(self,'capitalraid',default_capitalraid)

    @commands.group(name="datafiles",autohelp=False)
    @commands.is_owner()
    async def datafiles(self,ctx):
        """Checks if data files are present in the environment data path."""
        if not ctx.invoked_subcommand:
            embed = await clash_embed(ctx=ctx,
                                        title="Data File Status",
                                        message=f"**alliance.json**: {os.path.exists(self.cDirPath+'/alliance.json')}"
                                                +f"\n**members.json**: {os.path.exists(self.cDirPath+'/members.json')}"
                                                +f"\n**warlog.json**: {os.path.exists(self.cDirPath+'/warlog.json')}"
                                                +f"\n**capitalraid.json**: {os.path.exists(self.cDirPath+'/capitalraid.json')}"
                                                +f"\n\nRun `[p]datafiles init` to create any missing files.")
            await ctx.send(embed=embed)

    @datafiles.command(name="reset")
    @commands.is_owner()
    async def datafiles_reset(self, ctx):
        """Erases all current data and resets all data files."""

        embed = await clash_embed(ctx=ctx,
                                title="Confirmation Required.",
                                message=f"**This action erases __ALL__ data from the bot.**"+
                                        "\n\nIf you wish to continue, enter the token below as your next message.")
        await ctx.send(content=ctx.author.mention,embed=embed)

        if not await clash_resources.token_confirmation(self,ctx):
            return
        
        currSeason = await get_current_season()
        default_alliance, default_members, default_warlog, default_capitalraid = await datafile_defaults()
            
        await datafile_save(self,'alliance',default_alliance)
        await datafile_save(self,'members',default_members)
        await datafile_save(self,'warlog',default_warlog)
        await datafile_save(self,'capitalraid',default_capitalraid)
            
        embed = await clash_embed(ctx=ctx,
                    title="All Data Files Reset.",
                    message=f"**alliance.json**: {os.path.exists(self.cDirPath+'/alliance.json')}"
                            +f"\n**members.json**: {os.path.exists(self.cDirPath+'/members.json')}"
                            +f"\n**warlog.json**: {os.path.exists(self.cDirPath+'/warlog.json')}"
                            +f"\n**capitalraid.json**: {os.path.exists(self.cDirPath+'/capitalraid.json')}",
                    color="success")
            
        await ctx.send(embed=embed)

    @commands.group(name="serverset",autohelp=False)
    @commands.is_owner()
    async def serversettings(self,ctx):
        """Configure settings for the current server."""
        if not ctx.invoked_subcommand:
            if ctx.channel.type == discord.ChannelType.private:
                embed = await clash_embed(ctx=ctx,message=f"This command cannot be used in DMs.",color="fail")
                return await ctx.send(embed=embed)

            try:
                logsBool = await self.config.guild(ctx.guild).postlogs()
                logChannel = await self.config.guild(ctx.guild).logchannel()

                try:
                    channelObject = ctx.guild.get_channel(logChannel)
                    channelMention = f"<#{channelObject.id}>"
                except:
                    channelMention = "Invalid Channel"

            except:
                embed = await clash_embed(ctx=ctx,message=f"Error encountered in retrieving server settings.",color="fail")
                return await ctx.send(embed=embed)

            else:
                embed = await clash_embed(ctx=ctx,
                                    title=f"Settings for {ctx.guild.name}",
                                    message=f"**Send Logs?:** {logsBool}\n**Log Channel:** {channelMention}",
                                    thumbnail=ctx.guild.icon_url)
                return await ctx.send(embed=embed)

    @serversettings.command(name="sendlogs")
    @commands.is_owner()
    async def setlogs(self, ctx, boolset:bool):
        """Configure whether to send data logs in the current server."""

        if ctx.channel.type == discord.ChannelType.private:
            embed = await clash_embed(ctx=ctx,message=f"This command cannot be used in DMs.",color="fail")
            return await ctx.send(embed=embed)

        try:
            newSetting = boolset
            await self.config.guild(ctx.guild).postlogs.set(newSetting)

            logsBool = await self.config.guild(ctx.guild).postlogs()
            logChannel = await self.config.guild(ctx.guild).logchannel()
            
            try:
                channelObject = ctx.guild.get_channel(logChannel)
                channelMention = f"<#{channelObject.id}>"
            except:
                channelMention = "Invalid Channel"

            embed = await clash_embed(ctx=ctx,title="Settings updated.",message=f"**Send Logs?:** {logsBool}\n**Log Channel:** {channelMention}", color="success")
            return await ctx.send(embed=embed)
        except:
            embed = await clash_embed(ctx=ctx,message=f"Error updating settings.",color="fail")
            return await ctx.send(embed=embed)

    @serversettings.command(name="logchannel")
    @commands.is_owner()
    async def setchannel(self, ctx, channel:discord.TextChannel):
        """Configure channel to send log messages in."""

        if ctx.channel.type == discord.ChannelType.private:
            embed = await clash_embed(ctx=ctx,message=f"This command cannot be used in DMs.",color="fail")
            return await ctx.send(embed=embed)

        try:
            await self.config.guild(ctx.guild).logchannel.set(channel.id)

            logsBool = await self.config.guild(ctx.guild).postlogs()
            logChannel = await self.config.guild(ctx.guild).logchannel()
            
            try:
                channelObject = ctx.guild.get_channel(logChannel)
                channelMention = f"<#{channelObject.id}>"
            except:
                channelMention = "Invalid Channel"

            embed = await clash_embed(ctx=ctx,title="Settings updated.",message=f"**Send Logs?:** {logsBool}\n**Log Channel:** {channelMention}",color="success")
            return await ctx.send(embed=embed)
        except:
            embed = await clash_embed(ctx=ctx,message=f"Error updating settings.",color="fail")
            return await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command(name="drefresh")
    async def data_update(self, ctx):

        sendLogs = False
        newSeason = False
        warStateChange = False
        lastLogSent = await self.config.last_data_log()
        lastDataUpdate = await self.config.last_data_update()
        updateRunTime = await self.config.update_runtimes()

        try:
            logsBool = await self.config.guild(ctx.guild).postlogs()
            sendLogs = logsBool
        except:
            pass

        try:
            logChannel = await self.config.guild(ctx.guild).logchannel()
        except:
            pass
        else:
            try:
                logChannelO = ctx.guild.get_channel(logChannel)
            except:
                sendLogs = False
                logChannelO = ctx.channel

        successLog = []
        errLog = []
        st = time.time()

        season = await get_current_season()
        allianceJson = await datafile_retrieve(self,'alliance')
        memberStatsJson = await datafile_retrieve(self,'members')
        warlogJson = await datafile_retrieve(self,'warlog')
        capitalraidJson = await datafile_retrieve(self,'capitalraid')

        sEmbed = await clash_embed(ctx,
                title="Data Update Report",
                show_author=False)

        sEmbed.set_footer(text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",icon_url="https://i.imgur.com/TZF5r54.png")

        if str(season) != str(allianceJson['currentSeason']):
            newSeason = True
            nSeason = season
            pSeason = allianceJson['currentSeason']
            allianceJson['trackedSeasons'] = []
            allianceJson['trackedSeasons'].append(pSeason)

            os.makedirs(self.cDirPath+'/'+pSeason)
            with open(self.cDirPath+'/'+pSeason+'/members.json','x') as file:
                json.dump(memberStatsJson,file,indent=2)
            with open(self.cDirPath+'/'+pSeason+'/warlog.json','x') as file:
                json.dump(warlogJson,file,indent=2)
            with open(self.cDirPath+'/'+pSeason+'/capitalraid.json','x') as file:
                json.dump(capitalraidJson,file,indent=2)

            default_alliance, default_members, default_warlog, default_capitalraid = await datafile_defaults()
            memberStatsJson = default_members
            warlogJson = default_warlog
            capitalraidJson = default_capitalraid

            await datafile_save(self,'members',default_members)
            await datafile_save(self,'warlog',default_warlog)
            await datafile_save(self,'capitalraid',default_capitalraid)

            sEmbed.add_field(
                name=f"**New Season Initialized: {nSeason}**",
                value=f"__Files Saved__"
                    + f"\n**{pSeason}/members.json**: {os.path.exists(self.cDirPath+'/'+pSeason+'/members.json')}"
                    + f"\n**{pSeason}/warlog.json**: {os.path.exists(self.cDirPath+'/'+pSeason+'/warlog.json')}"
                    + f"\n**{pSeason}/capitalraid.json**: {os.path.exists(self.cDirPath+'/'+pSeason+'/capitalraid.json')}"
                    + f"\n\u200b\n"
                    + f"__Files Created__"
                    + f"\n**members.json**: {os.path.exists(self.cDirPath+'/members.json')}"
                    + f"\n**warlog.json**: {os.path.exists(self.cDirPath+'/warlog.json')}"
                    + f"\n**capitalraid.json**: {os.path.exists(self.cDirPath+'/capitalraid.json')}",
                inline=False)

        warUpdateStr = ''
        for tag, clan in allianceJson['clans'].items():
            mCount = 0
            try:
                c = await getClan(self,ctx,tag)
            except Exception as err:
                c = None
                errD = {
                    'tag':tag,
                    'reason':err
                    }
                errLog.append(errD)
                continue

            await c.updateWar(client=self.cClient)
            nClanJson, nWarlogJson = c.toJson()
            allianceJson['clans'][c.clan.tag] = nClanJson
            warlogJson[tag] = nWarlogJson

            if c.warStateChange or c.warState == "inWar":
                warStateChange = True
                warUpdateStr += f"__{c.clan.tag} {c.clan.name}__"
                if c.warStateChange and c.warState == 'inWar':
                    warUpdateStr += f"\n**War vs {c.currentWar.war.opponent.name} has begun!**"
                if c.warState == 'warEnded':
                    warUpdateStr += f"\n**War vs {c.currentWar.war.opponent.name} was {c.currentWar.war.status}.**"

                warUpdateStr += f"\n- State: {c.warState}\n- Type: {c.currentWar.warType} war"

                if c.warState != "notInWar" and c.currentWar.warType=='classic':
                    wJson, mJson = c.currentWar.toJson()
                    warlogJson[tag][c.currentWar.warID] = wJson

                    for member in c.currentWar.war.clan.members:
                        if member.tag in list(allianceJson['members'].keys()):
                            mCount += 1
                            memberStatsJson[member.tag]['warLog'][c.currentWar.warID] = mJson[member.tag]

                    warUpdateStr += f"\n- Recognized {mCount} members in War."

        if warUpdateStr == '':
            warUpdateStr = "No war updates."

        sEmbed.add_field(
            name=f"**Clan War**",
            value=warUpdateStr,
            inline=False)

        for tag, member in allianceJson['members'].items():
            try:
                p = await getPlayer(self,ctx,tag,jsonOverride=memberStatsJson)
            except Exception as err:
                p = None
                errD = {
                    'tag':tag,
                    'reason':err,
                    }
                errLog.append(errD)
                continue

            if p.isMember:
                p.updateStats()
                aJson, mJson = p.toJson()

                memberStatsJson[tag] = mJson
                successLog.append(p)

        await datafile_save(self,'warlog',warlogJson)
        await datafile_save(self,'members',memberStatsJson)
        await datafile_save(self,'alliance',allianceJson)

        et = time.time()

        sEmbed.add_field(
            name=f"**Members**",
            value=f"{len(successLog)} records updated. {len(errLog)} errors encountered.",
            inline=False)

        if len(errLog)>0:
            errTitle = "Error Log"
            errStr = "\n"
            for e in errLog:
                errStr += f"{e['tag']}: {e['reason']}\n"

            if len(errStr) > 1024:
                errTitle = "Error Log (Truncated)"
                errStr = errStr[0:500]

            sEmbed.add_field(
                name=f"**{errTitle}**",
                value=errStr,
                inline=False)

        procTime = round(et-st,2)
        updateRunTime.append(procTime)
        if len(updateRunTime) > 100:
            del updateRunTime[0]
        averageRunTime = round(sum(updateRunTime) / len(updateRunTime),2)

        sEmbed.add_field(
            name=f"**Processing Time**",
            value=f"{round(et-st,2)} seconds"
                + f"\n*Average of {averageRunTime} seconds.*",
            inline=False)
        
        if warStateChange or sendLogs or len(errLog)>0 or datetime.fromtimestamp(st).strftime('%M')=='00':
            await logChannelO.send(embed=sEmbed)
            await self.config.last_data_log.set(st)

        await self.config.last_data_update.set(st)
        await self.config.update_runtimes.set(updateRunTime)

    @commands.command(name="data_test")
    async def misc_command(self, ctx):

        cWar = await self.cClient.get_clan_war('92g9j8cg')