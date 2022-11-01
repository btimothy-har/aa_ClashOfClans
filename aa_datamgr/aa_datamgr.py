import os
import sys

import discord
import coc

import json
import asyncio
import random
import time
import requests
import fasteners

from redbot.core import Config, commands
from discord.utils import get
from datetime import datetime
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.constants import confirmation_emotes
from aa_resourcecog.notes import aNote
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog

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
            "logchannel":0,
            }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    @commands.group(name="datafiles",autohelp=False)
    @commands.is_owner()
    async def datafiles(self,ctx):
        """Checks if data files are present in the environment data path."""
        if not ctx.invoked_subcommand:
            embed = await clash_embed(ctx=ctx,
                                        title="Data File Status",
                                        message=f"**seasons.json: {os.path.exists(self.cDirPath+'/seasons.json')}"
                                                +f"**alliance.json**: {os.path.exists(self.cDirPath+'/alliance.json')}"
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
                                        "\n\nIf you wish to continue, enter the token below as your next message.\nYou have 60 seconds to respond.")
        cMsg = await ctx.send(content=ctx.author.mention,embed=embed)

        if not await resc.user_confirmation(ctx,cMsg,confirm_method='token_only'):
            return
        
        with ctx.bot.clash_file_lock.write_lock():
            with open(ctx.bot.clash_dir_path+'/seasons.json','w') as file:
                season_default = json_file_defaults['seasons']
                season_default['current'] = get_current_season()
                json.dump(season_default,file,indent=2)

            with open(ctx.bot.clash_dir_path+'/alliance.json','w') as file:
                json.dump(json_file_defaults['alliance'],file,indent=2)

            with open(ctx.bot.clash_dir_path+'/members.json','w') as file:
                json.dump({},file,indent=2)

            with open(ctx.bot.clash_dir_path+'/warlog.json','w') as file:
                json.dump({},file,indent=2)

            with open(ctx.bot.clash_dir_path+'/capitalraid.json','w') as file:
                json.dump({},file,indent=2)
            
        embed = await clash_embed(ctx=ctx,
            title="All Data Files Reset.",
            message=f"**seasons.json**: {os.path.exists(ctx.bot.clash_dir_path+'/seasons.json')}"
                    +f"**alliance.json**: {os.path.exists(ctx.bot.clash_dir_path+'/alliance.json')}"
                    +f"\n**members.json**: {os.path.exists(ctx.bot.clash_dir_path+'/members.json')}"
                    +f"\n**warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/warlog.json')}"
                    +f"\n**capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/capitalraid.json')}",
            color="success")
        return await ctx.send(embed=embed)

    @commands.command(name="logchannel")
    @commands.is_owner()
    async def log_channel(self, ctx, channel:discord.TextChannel=None):
        """Configure channel to send log messages in."""

        if ctx.channel.type == discord.ChannelType.private:
            embed = await clash_embed(ctx=ctx,message=f"This command cannot be used in DMs.",color="fail")
            return await ctx.send(embed=embed)

        if not channel:
            try:
                current_channel = await self.config.guild(ctx.guild).logchannel()
                channel_object = ctx.guild.get_channel(current_channel)
                channel_mention = f"<#{channel_object.id}>"
            except:
                channel_mention = f"No Channel Set"

            embed = await clash_embed(ctx=ctx,
                message=f"Logs are currently being sent in {channel_mention}.")

            return await ctx.send(embed=embed)

        else:
            try:
                await self.config.guild(ctx.guild).logchannel.set(channel.id)
            except:
                return await ctx.send(content='error encountered')
            else:
                current_channel = await self.config.guild(ctx.guild).logchannel()
                try:
                    channel_object = ctx.guild.get_channel(current_channel)
                    channel_mention = f"<#{channel_object.id}>"
                except:
                    channel_mention = f"No Channel Set"

                embed = await clash_embed(ctx=ctx,
                    message=f"Logs will now be sent in {channel_mention}.",color='success')
                return await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command(name="drefresh")
    async def data_update(self, ctx):

        send_logs = False
        is_new_season = False
        detected_war_change = False
        detected_raid_change = False
        last_log_sent = await self.config.last_data_log()
        last_data_update = await self.config.last_data_update()
        run_time_hist = await self.config.update_runtimes()

        try:
            log_channel_id = await self.config.guild(ctx.guild).logchannel()
        except:
            log_channel_id = ctx.channel.id
        finally:
            log_channel = ctx.guild.get_channel(log_channel_id)

        success_log = []
        err_log = []
        st = time.time()

        season = await get_current_season()
        clans, members = await get_current_alliance()

        sEmbed = await clash_embed(ctx,
                title="Data Update Report",
                show_author=False)

        sEmbed.set_footer(text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",icon_url="https://i.imgur.com/TZF5r54.png")

        #get file lock
        with ctx.bot.clash_file_lock.write_lock():
            is_new_season, current_season, new_season = await season_file_handler(season)

            if is_new_season:
                sEmbed.add_field(
                    name=f"**New Season Initialized: {new_season}**",
                    value=f"__Files Saved__"
                        + f"\n**{new_season}/members.json**: {os.path.exists(ctx.bot.clash_dir_path+'/'+new_season+'/members.json')}"
                        + f"\n**{new_season}/warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/'+new_season+'/warlog.json')}"
                        + f"\n**{new_season}/capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/'+new_season+'/capitalraid.json')}"
                        + f"\n\u200b\n"
                        + f"__Files Created__"
                        + f"\n**members.json**: {os.path.exists(ctx.bot.clash_dir_path+'/members.json')}"
                        + f"\n**warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/warlog.json')}"
                        + f"\n**capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/capitalraid.json')}",
                    inline=False)

            str_war_update = ''
            dict_war_update = {}
            str_raid_update = ''
            dict_raid_update = {}
            for ctag in clans:
                war_member_count = 0
                raid_member_count = 0
                try:
                    c = await aClan.create(ctx,ctag)
                except Exception as err:
                    c = None
                    err_dict = {
                        'tag':tag,
                        'reason':err
                        }
                    err_log.append(err_dict)
                    continue

                await c.update_clan_war()
                await c.update_raid_weekend()
                await c.save_to_json()

                if c.war_state_change:
                    detected_war_change = True

                if c.war_state_change or c.war_state == "inWar":
                    str_war_update += f"__{c.tag} {c.name}__"
                    if c.war_state_change and c.war_state == 'inWar':
                        str_war_update += f"\n**War vs {c.current_war.opponent.name} has begun!**"
                    if c.war_state == 'warEnded':
                        str_war_update += f"\n**War vs {c.current_war.opponent.name} was {c.current_war.result}.**"

                    str_war_update += f"\n- State: {c.war_state}\n- Type: {c.current_war.type} war"

                    if c.war_state != "notInWar" and c.current_war.type == 'classic':
                        for m in c.current_war.clan.members:
                            if m.tag in members:
                                war_member_count += 1
                                dict_war_update[m.tag] = m

                        warUpdateStr += f"\n- Tracking stats for {war_member_count} members in War."

                if c.raid_state_change:
                    detected_raid_change = True

                if c.raid_state_change or c.current_raid_weekend.state == "ongoing":
                    str_raid_update += f"__{c.tag} {c.name}__"

                    if c.raid_state_change and c.current_raid_weekend.state == 'ongoing':
                        str_raid_update += f"\n**Raid Weekend has begun!**"
                    if c.current_raid_weekend.state == 'ended':
                        str_raid_update += f"\n**Raid Weekend is now over.**"

                    str_raid_update += f"\n- State: {c.raidWeekend.state}"

                    for m in c.current_raid_weekend.members:
                        if m.tag in members:
                            raid_member_count += 1
                            dict_raid_update[m.tag] = m

                    str_raid_update += f"\n- Tracking stats for {raid_member_count} members in Capital Raids."

            if str_war_update == '':
                str_war_update = "No war updates."

            if str_raid_update == '':
                str_raid_update = "No raid weekend updates."

            sEmbed.add_field(
                name=f"**Clan War**",
                value=str_war_update,
                inline=False)

            sEmbed.add_field(
                name=f"**Capital Raids**",
                value=str_raid_update,
                inline=False)

            for mtag in members:
                try:
                    p = await aPlayer.create(ctx,mtag)
                except Exception as err:
                    p = None
                    err_dict = {
                        'tag':tag,
                        'reason':err,
                        }
                    err_log.append(err_dict)
                    continue

                if p.is_member and p.clan.tag in clans:
                    await p.retrieve_data()
                    await p.update_stats()
                    success_log.append(p)

                if p.tag in list(dict_war_update.keys()):
                    await p.update_war(dict_war_update[p.tag])

                if p.tag in list(dict_raid_update.keys()):
                    await p.update_raidweekend(dict_raid_update[p.tag])

                await p.save_to_json()
        #Lock releases here

        et = time.time()

        sEmbed.add_field(
            name=f"**Members**",
            value=f"{len(success_log)} records updated. {len(err_log)} errors encountered.",
            inline=False)

        if len(err_log)>0:
            errTitle = "Error Log"
            errStr = "\n"
            for e in err_log:
                errStr += f"{e['tag']}: {e['reason']}\n"

            if len(errStr) > 1024:
                errTitle = "Error Log (Truncated)"
                errStr = errStr[0:500]

            sEmbed.add_field(
                name=f"**{errTitle}**",
                value=errStr,
                inline=False)

        processing_time = round(et-st,2)
        run_time_hist.append(processing_time)
        if len(run_time_hist) > 100:
            del run_time_hist[0]
        average_run_time = round(sum(run_time_hist) / len(run_time_hist),2)

        sEmbed.add_field(
            name=f"**Processing Time**",
            value=f"{round(et-st,2)} seconds. *Average: {average_run_time} seconds.*",
            inline=False)
        
        if is_new_season or detected_war_change or detected_raid_change or len(err_log)>0 or datetime.fromtimestamp(st).strftime('%M')=='00':
            await log_channel.send(embed=sEmbed)
            await self.config.last_data_log.set(st)

        await self.config.last_data_update.set(st)
        await self.config.update_runtimes.set(run_time_hist)