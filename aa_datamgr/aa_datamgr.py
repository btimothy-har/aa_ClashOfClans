import os
import sys

import discord
import coc

import json
import asyncio
import random
import time
import pytz
import requests
import fasteners
import matplotlib.pyplot as plt

from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from datetime import datetime
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from tabulate import tabulate

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select
from aa_resourcecog.constants import confirmation_emotes, json_file_defaults, clanRanks
from aa_resourcecog.notes import aNote
from aa_resourcecog.file_functions import get_current_season, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from aa_resourcecog.errors import TerminateProcessing, InvalidTag

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


    async def initialize_config(self,bot):
        resource_cog = bot.get_cog("AriXClashResources")

        alliance_server_id = await resource_cog.config.alliance_server()
        alliance_leader_role = await resource_cog.config.alliance_leader_role()
        alliance_coleader_role = await resource_cog.config.alliance_coleader_role()
        alliance_elder_role = await resource_cog.config.alliance_elder_role()
        alliance_member_role = await resource_cog.config.alliance_member_role()

        try:
            bot.alliance_server = bot.get_guild(int(alliance_server_id))
        except:
            bot.alliance_server = None

        try:
            bot.leader_role = bot.alliance_server.get_role(int(alliance_leader_role))
        except:
            bot.leader_role = None

        try:
            bot.coleader_role = bot.alliance_server.get_role(int(alliance_coleader_role))
        except:
            bot.coleader_role = None

        try:
            bot.elder_role = bot.alliance_server.get_role(int(alliance_elder_role))
        except:
            bot.elder_role = None

        try:
            bot.member_role = bot.alliance_server.get_role(int(alliance_member_role))
        except:
            bot.member_role = None


    @commands.group(name="data",aliases=["status"],autohelp=False)
    @commands.is_owner()
    async def data_control(self,ctx):
        """Manage the bot's Clash of Clans data."""
        if not ctx.invoked_subcommand:

            if ctx.channel.type == discord.ChannelType.private:
                log_channel = "Not available in DMs."
            else:
                try:
                    c_log_channel = await self.config.guild(ctx.guild).logchannel()
                    c_log_channel = ctx.guild.get_channel(c_log_channel)
                    log_channel = f"<#{c_log_channel.id}>"
                except:
                    log_channel = f"Log Channel Not Set"

            last_update = await self.config.last_data_update()
            last_log_sent = await self.config.last_data_log()
            run_time = await self.config.update_runtimes()

            try:
                average_run_time = round(sum(run_time)/len(run_time),2)
            except:
                average_run_time = 0

            logdays, loghours, logminutes, logsecs = await convert_seconds_to_str(ctx,time.time() - last_update)

            update_str = ""
            if logdays > 0:
                update_str += f"{int(round(logdays,0))} day(s) "
            if loghours > 0:
                update_str += f"{int(round(loghours,0))} hour(s) "
            if logminutes > 0:
                update_str += f"{int(round(logminutes,0))} min(s) "
            if logsecs > 0:
                update_str += f"{int(round(logsecs,0))} sec(s) "

            embed = await clash_embed(ctx=ctx,title="System Status Report")
            embed.add_field(
                name="__Discord Configuration__",
                value=f"> **Alliance Server**: {getattr(ctx.bot.alliance_server,'name','Not Set')} `({getattr(ctx.bot.alliance_server,'id',0)})`"
                    + f"\n> **Leader Role**: {getattr(ctx.bot.leader_role,'mention','Not Set')}"
                    + f"\n> **Co-Leader Role**: {getattr(ctx.bot.coleader_role,'mention','Not Set')}"
                    + f"\n> **Elder Role**: {getattr(ctx.bot.elder_role,'mention','Not Set')}"
                    + f"\n> **Member Role**: {getattr(ctx.bot.member_role,'mention','Not Set')}",
                inline=False)

            embed.add_field(
                name="__System Cache__",
                value=f"> Players: {len(ctx.bot.member_cache)}"
                    f"\n> Clans: {len(ctx.bot.clan_cache)}",
                inline=False)

            embed.add_field(
                name="__File Path Config__",
                value=f"\n> **File Path**: {ctx.bot.clash_dir_path}"
                    + f"\n> **Report Path**: {ctx.bot.clash_report_path}"
                    + f"\n> **Eclipse Path**: {ctx.bot.eclipse_path}",)

            embed.add_field(
                name="__Core Data Files__",
                value=f"> **seasons.json**: {os.path.exists(ctx.bot.clash_dir_path+'/seasons.json')}"
                    + f"\n> **alliance.json**: {os.path.exists(ctx.bot.clash_dir_path+'/alliance.json')}"
                    + f"\n> **members.json**: {os.path.exists(ctx.bot.clash_dir_path+'/members.json')}"
                    + f"\n> **warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/warlog.json')}"
                    + f"\n> **capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/capitalraid.json')}",
                    inline=False)

            embed.add_field(
                name="__Eclipse Data Files__",
                value=f"> **warbases.json**: {os.path.exists(ctx.bot.eclipse_path+'/warbases.json')}",
                    inline=False)

            embed.add_field(
                name="__Refresh Status__",
                value=f"> **Last Updated**: {update_str} ago"
                    + f"\n> **Average Run Time**: {average_run_time} seconds",
                    inline=False)
            await ctx.send(embed=embed)


    @data_control.command(name="resetall")
    @commands.is_owner()
    async def data_control_resetall(self, ctx):
        """Erases all data and resets all data files to default."""

        embed = await clash_embed(ctx=ctx,
            title="Confirmation Required.",
            message=f"**This action erases __ALL__ data from the bot.**"+
                "\n\nIf you wish to continue, enter the token below as your next message.\nYou have 60 seconds to respond.")
        cMsg = await ctx.send(content=ctx.author.mention,embed=embed)

        if not await user_confirmation(ctx,cMsg,confirm_method='token_only'):
            return
        
        with ctx.bot.clash_file_lock.acquire():
            with open(ctx.bot.clash_dir_path+'/seasons.json','w') as file:
                season_default = json_file_defaults['seasons']
                season_default['current'] = await get_current_season()
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
                    +f"\n**alliance.json**: {os.path.exists(ctx.bot.clash_dir_path+'/alliance.json')}"
                    +f"\n**members.json**: {os.path.exists(ctx.bot.clash_dir_path+'/members.json')}"
                    +f"\n**warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/warlog.json')}"
                    +f"\n**capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/capitalraid.json')}",
            color="success")
        return await ctx.send(embed=embed)


    @data_control.command(name="reset")
    @commands.is_owner()
    async def data_control_reset(self, ctx):
        """Erases data stored for Members, Clan Wars, and Capital Raids."""

        embed = await clash_embed(ctx=ctx,
            title="Confirmation Required.",
            message=f"**This action erases data stored for Members, Clan Wars, and Capital Raids.**"+
                "\n\nIf you wish to continue, enter the token below as your next message.\nYou have 60 seconds to respond.")
        cMsg = await ctx.send(content=ctx.author.mention,embed=embed)

        if not await user_confirmation(ctx,cMsg,confirm_method='token_only'):
            return
        
        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(ctx.bot.clash_dir_path+'/members.json','w') as file:
                    json.dump({},file,indent=2)

                with open(ctx.bot.clash_dir_path+'/warlog.json','w') as file:
                    json.dump({},file,indent=2)

                with open(ctx.bot.clash_dir_path+'/capitalraid.json','w') as file:
                    json.dump({},file,indent=2)
            
        embed = await clash_embed(ctx=ctx,
            title="All Data Files Reset.",
            message=f"**seasons.json**: {os.path.exists(ctx.bot.clash_dir_path+'/seasons.json')}"
                    +f"\n**alliance.json**: {os.path.exists(ctx.bot.clash_dir_path+'/alliance.json')}"
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
    async def data_update(self, ctx, send_logs=False):

        st = time.time()
        helsinkiTz = pytz.timezone("Europe/Helsinki")

        sEmbed = await clash_embed(ctx,
            title="Data Update Report",
            show_author=False)
        sEmbed.set_footer(
            text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
            icon_url="https://i.imgur.com/TZF5r54.png")

        is_new_season = False
        detected_war_change = False
        detected_raid_change = False

        last_log_sent = await self.config.last_data_log()
        last_data_update = await self.config.last_data_update()
        run_time_hist = await self.config.update_runtimes()

        try:
            log_channel_id = await self.config.guild(ctx.guild).logchannel()
            log_channel = ctx.guild.get_channel(log_channel_id)
        except:
            pass

        if not log_channel:
            log_channel = ctx.channel

        role_sync = {}
        war_reminders = {}
        success_log = []
        err_log = []

        season = await get_current_season()

        with ctx.bot.clash_file_lock.read_lock():
            with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
                file_json = json.load(file)

        clan_keys = list(file_json['clans'].keys())
        member_keys = list(file_json['members'].keys())
        alliance_clans = []
        alliance_members = []

        await ctx.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching,
            name=f"{len(clan_keys)} clans, {len(member_keys)} members in AriX"))

        is_cwl = False
        if datetime.now(helsinkiTz).day <= 9:
            is_cwl = True

        for key in clan_keys:
            try:
                c = await aClan.create(ctx,key,fetch=True)
            except TerminateProcessing as e:
                eEmbed = await clash_embed(ctx,message=e,color='fail')
                eEmbed.set_footer(
                    text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
                    icon_url="https://i.imgur.com/TZF5r54.png")
                return await log_channel.send(embed=eEmbed)
            except Exception as e:
                c = None
                err_dict = {'tag':f'c{ctag}','reason':e}
                err_log.append(err_dict)
                continue

            alliance_clans.append(c)


        ## SEASON UPDATE
        is_new_season, current_season, new_season = await season_file_handler(ctx,season,alliance_clans)

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
        str_raid_update = ''

        ## MEMBER UPDATE
        for mtag in member_keys:
            try:
                p = await aPlayer.create(ctx,mtag,fetch=True)
            except TerminateProcessing as e:
                 eEmbed = await clash_embed(ctx,message=e,color='fail')
                 eEmbed.set_footer(
                     text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
                     icon_url="https://i.imgur.com/TZF5r54.png")
                 return await log_channel.send(eEmbed)
            except Exception as e:
                p = None
                err_dict = {'tag':f'm{mtag}','reason':e}
                err_log.append(err_dict)
                continue

            if p.is_member:
                alliance_members.append(p)

            if is_new_season:
                await p.set_baselines(ctx)

            if is_cwl:
                await p.set_baselines(ctx)
                success_log.append(p)

            else:
                if p.is_member and p.clan.is_alliance_clan:
                    await p.update_stats(ctx)
                    success_log.append(p)
                else:
                    await p.set_baselines(ctx)
                    success_log.append(p)

            await p.save_to_json(ctx)

            if p.discord_user not in list(role_sync.keys()):
                role_sync[p.discord_user] = {}

            if p.home_clan.tag:
                if p.home_clan.tag in list(role_sync[p.discord_user].keys()):
                    n_rank = clanRanks.index(p.arix_rank)
                    e_rank = clanRanks.index(role_sync[p.discord_user][p.home_clan.tag]['rank'])

                    if n_rank > e_rank:
                        role_sync[p.discord_user][p.home_clan.tag]['rank'] = p.arix_rank
                else:
                    role_sync[p.discord_user][p.home_clan.tag] = {
                        'clan': p.home_clan,
                        'rank': p.arix_rank
                        }


        for c in alliance_clans:
            clan_announcement_channel = None
            clan_reminder_channel = None

            war_reminder = False
            war_member_count = 0
            raid_member_count = 0

            c.member_count = len([a for a in alliance_members if a.home_clan.tag == c.tag])

            if c.announcement_channel:
                clan_announcement_channel = ctx.bot.alliance_server.get_channel(c.announcement_channel)

            if c.reminder_channel:
                clan_reminder_channel = ctx.bot.alliance_server.get_channel(c.reminder_channel)

            await c.update_clan_war(ctx)

            if c.war_state_change:
                detected_war_change = True

            if c.current_war and (c.war_state_change or c.war_state == "inWar"):
                str_war_update += f"__{c.tag} {c.name}__"
                if c.war_state_change and c.war_state == 'inWar':
                    c.war_reminder_tracking = c.war_reminder_intervals

                    str_war_update += f"\n**War vs {c.current_war.opponent.name} has begun!**"


                if c.send_war_reminder and clan_reminder_channel and len(c.war_reminder_tracking) > 0:
                    next_reminder = c.war_reminder_tracking[0]

                    if (c.current_war.end_time - st) <= (next_reminder*3600):
                        war_reminder = True
                        next_reminder = c.war_reminder_tracking.pop(0)


                if c.war_state == 'warEnded':
                    str_war_update += f"\n**War vs {c.current_war.opponent.name} was {c.current_war.result}.**"

                str_war_update += f"\n- State: {c.war_state}\n- Type: {c.current_war.type} war"


                if c.war_state != "notInWar" and c.current_war.type == 'classic':
                    war_reminder_ping = []

                    for m in c.current_war.clan.members:
                        member = [am for am in alliance_members if am.tag == m.tag]
                        if len(member) > 0:
                            war_member_count += 1
                            member = member[0]
                            await member.update_war(ctx,m)

                            if len(m.attacks) < c.current_war.attacks_per_member and member.discord_user not in war_reminder_ping:
                                war_reminder_ping.append(member.discord_user)

                    str_war_update += f"\n- Tracking stats for {war_member_count} members in War.\n"


                if war_reminder:
                    remaining_time = c.current_war.end_time - st
                    if remaining_time < 3600:
                        ping_str = f"There is **less than 1 hour** left in Clan Wars and you have **NOT** used all your attacks.\n\n"

                    else:
                        dd, hh, mm, ss = await convert_seconds_to_str(ctx,remaining_time)
                        ping_str = f"Clan War ends in **{hh} hours, {mm} minutes**. You have **NOT** used all your attacks.\n\n"

                    ping_str += f"{humanize_list([f'<@{mid}>' for mid in war_reminder_ping])}"

                    await clan_reminder_channel.send(ping_str)


            await c.update_raid_weekend(ctx)

            if c.raid_state_change:
                detected_raid_change = True

            if c.raid_state_change or c.current_raid_weekend.state == "ongoing":
                str_raid_update += f"__{c.tag} {c.name}__"

                if c.raid_state_change and c.current_raid_weekend.state == 'ongoing':
                    c.war_reminder_tracking = c.war_reminder_intervals

                    if 24 not in c.war_reminder_tracking:
                        c.war_reminder_tracking.append(24)

                    c.war_reminder_tracking.sort(reverse=True)

                    str_raid_update += f"\n**Raid Weekend has begun!**"

                    if clan_announcement_channel:
                        raid_weekend_start_embed = await clash_embed(ctx,
                            message="**Raid Weekend has begun!**")
                        
                        if c.member_role:
                            role = ctx.bot.alliance_server.get_role(c.member_role)
                            rm = discord.AllowedMentions(roles=True)
                            await channel.send(content=f"{role.mention}",embed=raid_weekend_start_embed,allowed_mentions=rm)
                        else:
                            await channel.send(embed=raid_weekend_start_embed)


                if len(c.raid_reminder_tracking) > 0:
                    next_reminder = c.raid_reminder_tracking[0]

                    if ((c.current_raid_weekend.end_time - st) <= (next_reminder*3600)):
                        next_reminder = c.raid_reminder_tracking.pop(0)

                        if next_reminder == 24 and clan_announcement_channel:
                            raid_weekend_1day_embed = await clash_embed(ctx,
                                message="**There is 1 Day left in Raid Weekend.** Alternate accounts are now allowed to fill up the remaining slots.")

                            if c.member_role:
                                role = ctx.bot.alliance_server.get_role(c.member_role)
                                rm = discord.AllowedMentions(roles=True)
                                await channel.send(content=f"{role.mention}",embed=raid_weekend_1day_embed,allowed_mentions=rm)
                            else:
                                await channel.send(embed=raid_weekend_1day_embed)

                        if c.send_raid_reminder and clan_reminder_channel:

                            remaining_time = c.current_raid_weekend.end_time - st
                            dd, hh, mm, ss = await convert_seconds_to_str(ctx,remaining_time)

                            remaining_time_str = ""
                            if dd > 0:
                                remaining_time_str += f"{dd} day(s)"

                            if hh > 0:
                                remaining_time_str += f"{hh} hour(s)"

                            if mm > 0:
                                remaining_time_str += f"{mm} minute(s)"

                            members_not_in_raid = [m for m in alliance_members if m.home_clan.tag == c.tag and m.tag not in [z.tag for z in c.current_raid_weekend.members]]
                            members_unfinished_raid = [m for m in alliance_members if m.tag in [z.tag for z in c.current_raid_weekend.members if z.attack_count < 6]]

                            if (c.current_raid_weekend.end_time - st) < 3600:
                                not_in_raid_str = f"There is **less than 1 hour** left in Raid Weekend and you have **NOT** participated.\n\n"
                            else:
                                not_in_raid_str = f"Raid Weekend ends in **{remaining_time_str}** and you have **NOT** participated.\n\n"

                            not_in_raid_str += f"{humanize_list([f'<@{m.discord_user}>' for m in members_not_in_raid])}"

                            if (c.current_raid_weekend.end_time - st) < 3600:
                                unfinished_raid_str = f"There is **less than 1 hour** left in Raid Weekend and you **DID NOT** use all your Raid Attacks.\n\n"
                            else:
                                unfinished_raid_str = f"You started your Raid Weekend but **DID NOT** use all your Raid Attacks. Raid Weekend ends in **{remaining_time_str}**.\n\n"

                            unfinished_raid_str += f"{humanize_list([f'<@{m.discord_user}>' for m in members_unfinished_raid])}"

                            await clan_reminder_channel.send(not_in_raid_str)
                            await clan_reminder_channel.send(unfinished_raid_str)


                if c.current_raid_weekend.state == 'ended':
                    str_raid_update += f"\n**Raid Weekend is now over.**"

                    if clan_announcement_channel:

                        members_ranked = sorted(c.current_raid_weekend.members, key=lambda x: (x.resources_looted),reverse=True)
                        rank = 0
                        rank_table = []
                        for m in members_ranked[0:5]:
                            rank += 1
                            m_table = {
                                "P": rank,
                                "Name": m.name,
                                "Looted": f"{m.resources_looted:,}",
                                "Attacks": m.attack_count,
                                }
                            rank_table.append(m_table)

                        raid_end_embed = await clash_embed(ctx=ctx,
                            title=f"Raid Weekend Results: {c.name} ({c.tag})",
                            message=f"\n**Maximum Reward: {(c.current_raid_weekend.offense_rewards * 6) + c.current_raid_weekend.defense_rewards:,}** <:RaidMedals:983374303552753664>"
                                + f"\n\nOffensive Rewards: {c.current_raid_weekend.offense_rewards * 6} <:RaidMedals:983374303552753664>"
                                + f"\nDefensive Rewards: {c.current_raid_weekend.defense_rewards} <:RaidMedals:983374303552753664>"
                                ,
                            thumbnail=c.c.badge.url,
                            show_author=False)

                        raid_end_embed.add_field(
                            name="Start Date",
                            value=f"{datetime.fromtimestamp(c.current_raid_weekend.start_time).strftime('%d %b %Y')}",
                            inline=True)

                        raid_end_embed.add_field(
                            name="End Date",
                            value=f"{datetime.fromtimestamp(c.current_raid_weekend.end_time).strftime('%d %b %Y')}",
                            inline=True)

                        raid_end_embed.add_field(
                            name="Number of Participants",
                            value=f"{len(c.current_raid_weekend.members)}",
                            inline=False)

                        raid_end_embed.add_field(
                            name="Total Loot Gained",
                            value=f"{c.current_raid_weekend.total_loot:,} <:CapitalGoldContributed:971012592057339954>",
                            inline=True)

                        raid_end_embed.add_field(
                            name="Number of Attacks",
                            value=f"{c.current_raid_weekend.raid_attack_count}",
                            inline=True)

                        raid_end_embed.add_field(
                            name="Districts Destroyed",
                            value=f"{c.current_raid_weekend.districts_destroyed}",
                            inline=True)

                        raid_end_embed.add_field(
                            name="Offensive Raids Completed",
                            value=f"{c.current_raid_weekend.offense_raids_completed}",
                            inline=True)

                        raid_end_embed.add_field(
                            name="Defensive Raids Completed",
                            value=f"{c.current_raid_weekend.defense_raids_completed}",
                            inline=True)

                        raid_end_embed.add_field(
                            name='**Raid Leaderboard**',
                            value=f"{box(tabulate(rank_table,headers='keys',tablefmt='pretty'))}",
                            inline=False)

                        channel = ctx.bot.alliance_server.get_channel(c.announcement_channel)
                        rm = discord.AllowedMentions(roles=True)

                        await channel.send(embed=raid_end_embed)

                str_raid_update += f"\n- State: {c.current_raid_weekend.state}"

                for m in c.current_raid_weekend.members:
                    member = [am for am in alliance_members if am.tag == m.tag]

                    if len(member) > 0:
                        raid_member_count += 1
                        member = member[0]
                        await member.update_raid_weekend(ctx,m)

                str_raid_update += f"\n- Tracking stats for {raid_member_count} members in Capital Raids.\n"

            await c.save_to_json(ctx)

        if str_war_update == '':
            str_war_update = "No war updates."

        if str_raid_update == '':
            str_raid_update = "No raid weekend updates."

        sEmbed.add_field(
            name=f"**Clan War**",
            value=f"CWL State: {is_cwl}\n{str_war_update}",
            inline=False)

        sEmbed.add_field(
            name=f"**Capital Raids**",
            value=str_raid_update,
            inline=False)

        role_count = 0
        for user, rank_info in role_sync.items():
            role_clan_tags = [c.tag for c in alliance_clans]
            discord_member = ctx.bot.alliance_server.get_member(int(user))
            alliance_ranks = []

            if discord_member:
                role_change = False
                try:
                    for clan_tag, rank_info in rank_info.items():
                        
                        if clan_tag in role_clan_tags:
                            role_clan_tags.remove(clan_tag)

                        member_role = ctx.bot.alliance_server.get_role(int(rank_info['clan'].member_role))
                        elder_role = ctx.bot.alliance_server.get_role(int(rank_info['clan'].elder_role))
                        coleader_role = ctx.bot.alliance_server.get_role(int(rank_info['clan'].coleader_role))

                        alliance_ranks.append(rank_info['rank'])

                        if rank_info['rank'] in ['Leader','Co-Leader']:
                            if member_role not in discord_member.roles:
                                await discord_member.add_roles(member_role)
                                role_change = True
                            if elder_role not in discord_member.roles:
                                await discord_member.add_roles(elder_role)
                                role_change = True
                            if coleader_role not in discord_member.roles:
                                await discord_member.add_roles(coleader_role)
                                role_change = True

                        elif rank_info['rank'] in ['Elder']:
                            if member_role not in discord_member.roles:
                                await discord_member.add_roles(member_role)
                                role_change = True
                            if elder_role not in discord_member.roles:
                                await discord_member.add_roles(elder_role)
                                role_change = True
                            if coleader_role in discord_member.roles:
                                await discord_member.remove_roles(coleader_role)
                                role_change = True

                        elif rank_info['rank'] in ['Member']:
                            if member_role not in discord_member.roles:
                                await discord_member.add_roles(member_role)
                                role_change = True
                            if elder_role in discord_member.roles:
                                await discord_member.remove_roles(elder_role)
                                role_change = True
                            if coleader_role in discord_member.roles:
                                await discord_member.remove_roles(coleader_role)
                                role_change = True

                        else:
                            if member_role in discord_member.roles:
                                await discord_member.remove_roles(member_role)
                                role_change = True
                            if elder_role in discord_member.roles:
                                await discord_member.remove_roles(elder_role)
                                role_change = True
                            if coleader_role in discord_member.roles:
                                await discord_member.remove_roles(coleader_role)
                                role_change = True

                    if len(role_clan_tags) > 0:
                        for c in [c for c in alliance_clans if c.tag in role_clan_tags]:
                            member_role = ctx.bot.alliance_server.get_role(int(c.member_role))
                            elder_role = ctx.bot.alliance_server.get_role(int(c.elder_role))
                            coleader_role = ctx.bot.alliance_server.get_role(int(c.coleader_role))

                            if member_role in discord_member.roles:
                                await discord_member.remove_roles(member_role)
                                role_change = True
                            if elder_role in discord_member.roles:
                                await discord_member.remove_roles(elder_role)
                                role_change = True
                            if coleader_role in discord_member.roles:
                                await discord_member.remove_roles(coleader_role)
                                role_change = True

                    if 'Leader' in alliance_ranks or 'Co-Leader' in alliance_ranks:
                        if ctx.bot.member_role not in discord_member.roles:
                            await discord_member.add_roles(ctx.bot.member_role)
                            role_change = True
                        if ctx.bot.elder_role not in discord_member.roles:
                            await discord_member.add_roles(ctx.bot.elder_role)
                            role_change = True
                        if ctx.bot.coleader_role not in discord_member.roles:
                            await discord_member.add_roles(ctx.bot.coleader_role)
                            role_change = True

                    elif 'Elder' in alliance_ranks:
                        if ctx.bot.member_role not in discord_member.roles:
                            await discord_member.add_roles(ctx.bot.member_role)
                            role_change = True
                        if ctx.bot.elder_role not in discord_member.roles:
                            await discord_member.add_roles(ctx.bot.elder_role)
                            role_change = True
                        if ctx.bot.coleader_role in discord_member.roles:
                            await discord_member.remove_roles(ctx.bot.coleader_role)
                            role_change = True

                    elif 'Member' in alliance_ranks:
                        if ctx.bot.member_role not in discord_member.roles:
                            await discord_member.add_roles(ctx.bot.member_role)
                            role_change = True
                        if ctx.bot.elder_role in discord_member.roles:
                            await discord_member.remove_roles(ctx.bot.elder_role)
                            role_change = True
                        if ctx.bot.coleader_role in discord_member.roles:
                            await discord_member.remove_roles(ctx.bot.coleader_role)
                            role_change = True

                    else:
                        if ctx.bot.member_role in discord_member.roles:
                            await discord_member.remove_roles(ctx.bot.member_role)
                            role_change = True

                        if ctx.bot.elder_role in discord_member.roles:
                            await discord_member.remove_roles(ctx.bot.elder_role)
                            role_change = True

                        if ctx.bot.coleader_role in discord_member.roles:
                            await discord_member.remove_roles(ctx.bot.coleader_role)
                            role_change = True

                except Exception as e:
                    err_dict = {'tag':f'u{int(user)}','reason':f"Error syncing roles: {e}"}
                    err_log.append(err_dict)
                    continue

                if role_change:
                    role_count += 1

        for tag,c_member in ctx.bot.member_cache.items():
            if st - c_member.timestamp > 86400:
                del ctx.bot.member_cache[tag]

        for tag,c_clan in ctx.bot.clan_cache.items():
            if st - c_clan.timestamp > 86400:
                del ctx.bot.clan_cache[tag]

        et = time.time()

        sEmbed.add_field(
            name=f"**Members**",
            value=f"{len(success_log)} records updated.\nUpdated roles for {role_count} members.\n{len(err_log)} errors encountered.",
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

        run_time_plot = ctx.bot.clash_dir_path+"/runtimeplot.png"

        plt.figure()
        plt.plot(run_time_hist)
        plt.savefig(run_time_plot)
        plt.clf()

        run_time_plot_file = discord.File(run_time_plot,filename='run_time_plot.png')
        sEmbed.set_image(url=f"attachment://run_time_plot.png")

        sEmbed.add_field(
            name=f"**Processing Time**",
            value=f"{round(et-st,2)} seconds. *Average: {average_run_time} seconds.*",
            inline=False)

        
        if send_logs or is_new_season or detected_war_change or detected_raid_change or len(err_log)>0 or datetime.fromtimestamp(st).strftime('%M')=='00':
            await log_channel.send(embed=sEmbed,file=run_time_plot_file)
            await self.config.last_data_log.set(st)

        await self.config.last_data_update.set(st)
        await self.config.update_runtimes.set(run_time_hist)
