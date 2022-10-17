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
from clash_resources import token_confirmation, standard_confirmation, react_confirmation, clashFileLock, datafile_retrieve, datafile_save, get_current_alliance, get_current_season, clash_embed, player_shortfield, player_embed, getPlayer
from clash_resources import ClashPlayerError

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
    """AriX Clash of Clans Data Management"""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=2170311125702803,force_registration=True)
        default_global = {
            "lastWarCheck":0
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

        if not await token_confirmation(self,ctx):
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
    @commands.admin_or_permissions(administrator=True)
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
    @commands.admin_or_permissions(administrator=True)
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
    @commands.admin_or_permissions(administrator=True)
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

    @commands.admin_or_permissions(administrator=True)
    @commands.command(name="drefresh")
    async def data_update(self, ctx):

        sendLogs = False
        newSeason = False

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
                logChannelO = None

        successLog = []
        errLog = []
        st = time.time()

        season = await get_current_season()
        allianceJson = await datafile_retrieve(self,'alliance')
        memberStatsJson = await datafile_retrieve(self,'members')
        warlogJson = await datafile_retrieve(self,'warlog')
        capitalraidJson = await datafile_retrieve(self,'capitalraid')

        sEmbed = await clash_embed(ctx,
                title="Data Update Status Report",
                show_author=False)

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

        for tag, member in allianceJson['members'].items():
            try:
                p = await getPlayer(self,ctx,tag,force_member=True)
            except ClashPlayerError as err:
                p = None
                errD = {
                    'tag':tag,
                    'reason':'Unable to find a user with this tag.'
                    }
                errLog.append(errD)
                continue
            except:
                p = None
                errD = {
                    'tag':tag,
                    'reason':'Unknown error.'
                    }
                errLog.append(errD)
                continue

            p.updateStats()
            aJson, mJson = p.toJson()

            memberStatsJson[tag] = mJson
            successLog.append(p)

        await datafile_save(self,'members',memberStatsJson)

        et = time.time()

        errStr = "\n"
        for e in errLog:
            errStr += f"{e['tag']}: {e['reason']}\n"

        sEmbed.add_field(
            name=f"**Member Updates Completed**",
            value=f"{len(successLog)} records updated. {len(errLog)} errors encountered."+errStr,
            inline=False)

        sEmbed.add_field(
            name=f"**Processing Time**",
            value=f"{round(et-st,2)} seconds",
            inline=False)
        
        if sendLogs or len(errLog)>0:
            await logChannelO.send(embed=sEmbed)

    # @commands.command(name="test")
    # async def test(self, ctx):
    #     #testwar = await self.cClient.get_clan_war('28VUPJRPU')

    #     #await ctx.send(f"{testwar.clan.name} {testwar.opponent.name} {testwar.state} {testwar.team_size}")

    #     #tag = testwar.clan.tag

    #     #for member in testwar.members:
    #     #    if member.clan.tag == tag:
    #     #        await ctx.send(f"{member.map_position} {member.name}")

    #     #for attack in testwar.attacks:
    #     #    await ctx.send(f"{attack.war} {attack.order} {attack.attacker_tag} vs {attack.defender_tag} {attack.stars} {attack.destruction} {attack.duration}")

    #     uid = int(644530507505336330)

    #     user = ctx.bot.get_user(uid)

    #     await ctx.send(f"{user.name} {user.discriminator}")