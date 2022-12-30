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
from discord.ext import tasks
from datetime import datetime
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from tabulate import tabulate
from art import text2art

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select
from aa_resourcecog.constants import confirmation_emotes, json_file_defaults, clanRanks
from aa_resourcecog.notes import aNote
from aa_resourcecog.file_functions import get_current_season, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler
from aa_resourcecog.player import aPlayer, aClan, aMember
from aa_resourcecog.clan_war import aClanWar
from aa_resourcecog.raid_weekend import aRaidWeekend
from aa_resourcecog.errors import TerminateProcessing, InvalidTag

class AriXClashDataMgr(commands.Cog):
    """AriX Clash of Clans Data Module."""

    def __init__(self,bot):
        self.bot = bot
        self.config = Config.get_conf(self,identifier=2170311125702803,force_registration=True)
        default_global = {
            "last_status_update": 0,
            "last_data_update":0,
            "last_data_log":0,
            "update_runtimes":[],
            "logchannel":0,
            "memberlog":0,
            }
        default_guild = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.loop_data_update.start()

    async def initialize_config(self,bot):
        class EmptyContext(commands.Context):
            def __init__(self,**attrs):
                self.bot = bot

        ctx = EmptyContext()

        resource_cog = bot.get_cog("AriXClashResources")

        alliance_server_id = await resource_cog.config.alliance_server()
        alliance_leader_role = await resource_cog.config.alliance_leader_role()
        alliance_coleader_role = await resource_cog.config.alliance_coleader_role()
        alliance_elder_role = await resource_cog.config.alliance_elder_role()
        alliance_member_role = await resource_cog.config.alliance_member_role()
        base_vault_role = await resource_cog.config.alliance_base_role()

        base_channel = await resource_cog.config.alliance_base_channel()
        update_channel = await resource_cog.config.alliance_update_channel()

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

        try:
            bot.member_role = bot.alliance_server.get_role(int(alliance_member_role))
        except:
            bot.member_role = None

        try:
            bot.base_vault_role = bot.alliance_server.get_role(int(base_vault_role))
        except:
            bot.base_vault_role = None

        try:
            bot.base_channel = bot.get_channel(int(base_channel))
        except:
            bot.base_channel = None

        try:
            bot.update_channel = bot.get_channel(int(update_channel))
        except:
            bot.update_channel = None

        with bot.clash_file_lock.read_lock():
            with open(bot.clash_dir_path+'/seasons.json','r') as file:
                s_json = json.load(file)

        bot.tracked_seasons = s_json['tracked']

        alliance_clans_json = await alliance_file_handler(
            ctx=ctx,
            entry_type='clans',
            tag="**")

        member_json = await alliance_file_handler(
            ctx=ctx,
            entry_type='members',
            tag="**")

        if len(list(bot.clan_cache.keys())) == 0:
            [await aClan.create(ctx,tag=tag) for tag in list(alliance_clans_json.keys())]

        if len(list(bot.member_cache.keys())) == 0:
            [await aPlayer.create(ctx,tag=tag) for tag in list(member_json.keys())]


    @commands.command(name="initdata")
    @commands.is_owner()
    async def initialize_data_cache(self,ctx):
        with ctx.bot.clash_file_lock.read_lock():
            with open(ctx.bot.clash_dir_path+'/seasons.json','r') as file:
                s_json = json.load(file)

        bot.tracked_seasons = s_json['tracked']

        alliance_clans_json = await alliance_file_handler(
            ctx=ctx,
            entry_type='clans',
            tag="**")

        member_json = await alliance_file_handler(
            ctx=ctx,
            entry_type='members',
            tag="**")

        [await aClan.create(ctx,tag=tag) for tag in list(alliance_clans_json.keys())]
        [await aPlayer.create(ctx,tag=tag) for tag in list(member_json.keys())]

    @commands.command(name="drefresh")
    @commands.is_owner()
    async def data_toggle(self,ctx):
        m = await ctx.send("Please wait...")

        if not ctx.bot.refresh_status:
            ctx.bot.refresh_status = True

            await ctx.send("Bot Data Refresh is now activated.")

        elif ctx.bot.refresh_status:
            ctx.bot.refresh_status = False
            self.loop_data_update.stop()

            await ctx.send("Bot Data Refresh is now stopped.")

        await m.delete()

    @commands.group(name="data",aliases=["status"],autohelp=False)
    @commands.is_owner()
    async def data_control(self,ctx):
        """Manage the bot's Clash of Clans data."""
        if not ctx.invoked_subcommand:

            last_update = await self.config.last_data_update()
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
                    + f"\n> **Leader Role**: {getattr(ctx.bot.leader_role,'name','Not Set')} `({getattr(ctx.bot.leader_role,'id',0)})`"
                    + f"\n> **Co-Leader Role**: {getattr(ctx.bot.coleader_role,'name','Not Set')} `({getattr(ctx.bot.coleader_role,'id',0)})`"
                    + f"\n> **Elder Role**: {getattr(ctx.bot.elder_role,'name','Not Set')} `({getattr(ctx.bot.elder_role,'id',0)})`"
                    + f"\n> **Member Role**: {getattr(ctx.bot.member_role,'name','Not Set')} `({getattr(ctx.bot.member_role,'id',0)})`"
                    + f"\n\n> **Base Vault Access**: {getattr(ctx.bot.base_channel,'name','Not Set')} `({getattr(ctx.bot.base_channel,'id',0)})`"
                    + f"\n> **Bot Updates**: {getattr(ctx.bot.update_channel,'name','Not Set')} `({getattr(ctx.bot.update_channel,'id',0)})`",
                inline=False)

            embed.add_field(
                name="__Data Cache__",
                value=f"> Seasons: {', '.join(ctx.bot.tracked_seasons)}"
                    + f"\n> Players: {len(ctx.bot.member_cache)}"
                    + f"\n> Clans: {len(ctx.bot.clan_cache)}"
                    + f"\n> Users: {len(ctx.bot.user_cache)}"
                    + f"\n> Challenge Pass: {len(ctx.bot.pass_cache)}",
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
                value=f"> **Current Setting**: {ctx.bot.refresh_status}"
                    + f"\n> **Loop Number**: {ctx.bot.refresh_loop}"
                    + f"\n> **Task Status**: {self.loop_data_update.is_running}"
                    #+ f"\n> **Next Iteration**: <t:{self.loop_data_update.next_iteration.timestamp}:F>"
                    + f"\n> **Last Updated**: {update_str} ago"
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
        
        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
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


    @tasks.loop(seconds=30.0)
    async def loop_data_update(self):

        bot = self.bot
        save_state = self.bot.refresh_status
        test_ch = self.bot.get_channel(856433806142734346)

        await test_ch.send('hello')

        class DataError():
            def __init__(self,**kwargs):
                self.category = kwargs.get('category',None)
                self.tag = kwargs.get('tag',None)
                self.error = kwargs.get('error',None)

        class EmptyContext(commands.Context):
            def __init__(self,bot):
                self.bot = bot

        ctx = EmptyContext(bot=bot)

        if not self.bot.refresh_status:
            await test_ch.send(f'bye {self.bot.refresh_status}')
            return

        else:
            await test_ch.send(f'hi again')

            self.bot.refresh_status = False
            await test_ch.send(f'turned off')

            try:
                st = time.time()
                helsinkiTz = pytz.timezone("Europe/Helsinki")

                data_embed = discord.Embed(
                    title="Data Update Report",
                    color=0x0000)

                data_embed.set_footer(
                    text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
                    icon_url="https://i.imgur.com/TZF5r54.png")

                is_new_season = False
                send_logs = False

                await test_ch.send(f'hi again 2')

                last_status_update = await self.config.last_status_update()
                last_data_update = await self.config.last_data_update()
                run_time_hist = await self.config.update_runtimes()

                active_events = []
                passive_events = []

                await test_ch.send(f'hi again 3')

                try:
                    update_channel = self.bot.update_channel
                except:
                    update_channel = None

                role_sync = {}
                war_reminders = {}
                success_log = []
                error_log = []

                alliance_clans = []
                alliance_members = []
                discord_members = []

                season = await get_current_season()
                alliance_clans_json = await alliance_file_handler(
                    ctx=ctx,
                    entry_type='clans',
                    tag="**")

                member_json = await alliance_file_handler(
                    ctx=ctx,
                    entry_type='members',
                    tag="**")

                for c_tag in list(alliance_clans_json.keys()):
                    try:
                        c = await aClan.create(ctx,tag=c_tag,refresh=True)
                    except Exception as e:
                        err = DataError(category='clan',tag=c_tag,error=e)
                        error_log.append(err)
                    else:
                        alliance_clans.append(c)

                await test_ch.send(f'i found all clans')


                for m_tag in list(member_json.keys()):
                    try:
                        m = await aPlayer.create(ctx,tag=m_tag,refresh=True)
                    except Exception as e:
                        err = DataError(category='player',tag=m_tag,error=e)
                        error_log.append(err)
                    else:
                        alliance_members.append(c)

                await test_ch.send(f'i found all members')

                is_cwl = False
                if datetime.now(helsinkiTz).day <= 9:
                    is_cwl = True

                ## SEASON UPDATE
                is_new_season, current_season, new_season = await season_file_handler(ctx,season,alliance_clans)

                if is_new_season:
                    send_logs = True

                    data_embed.add_field(
                        name=f"**New Season Initialized: {new_season}**",
                        value=f"__Files Saved__"
                            + f"\n**{current_season}/members.json**: {os.path.exists(self.bot.clash_dir_path+'/'+current_season+'/members.json')}"
                            + f"\n"
                            + f"__Files Created__"
                            + f"\n**members.json**: {os.path.exists(self.bot.clash_dir_path+'/members.json')}",
                        inline=False)
                    season = new_season

                    await update_channel.send(f"**The new season {season} has started!**")

                    alliance_clans = [await aClan.create(ctx,tag=c,refresh=True,reset=True) for c in list(alliance_clans_json.keys())]
                    alliance_members = [await aPlayer.create(ctx,tag=p,refresh=True,reset=True) for p in list(member_json.keys())]

                    [await m.set_baselines(ctx) for m in alliance_members]

                await test_ch.send(f'season is ok')

                ## CLAN UPDATE
                clan_update = ''
                for c in alliance_clans:
                    clan_update += f"__{c.name} {c.tag}__"

                    try:
                        war_update = await c.update_clan_war(ctx)
                    except Exception as e:
                        err = DataError(category='clwar',tag=c.tag,error=e)
                        error_log.append(err)
                    else:
                        if c.current_war:
                            clan_update += f"\n> - War: {c.current_war.state} (Type: {c.current_war.type})"
                            if war_update:
                                clan_update += war_update
                                send_logs = True

                            if c.current_war.type == 'random':
                                result_dict = {
                                    'winning':'winning',
                                    'tied':'tie',
                                    'losing':'losing',
                                    'won':'winning',
                                    'tie':'tie',
                                    'lost':'losing',
                                    '':'',
                                    }

                                if c.war_state_change:
                                    if c.war_state == 'inWar':
                                        active_events.append(f"{c.abbreviation} declare war!")

                                    if c.war_state == 'warEnded':
                                        if c.current_war.result in ['winning','won']:
                                            active_events.append(f"{c.abbreviation} win {c.war_wins} times.")

                                        if c.current_war.result in ['losing','lost']:
                                            active_events.append(f"{c.abbreviation} get crushed {c.war_losses} times.")

                                        if c.war_win_streak >= 3:
                                            active_events.append(f"{c.abbreviation} on a {c.war_win_streak} streak!")

                                else:
                                    if c.war_state == 'inWar':
                                        passive_events.append(f"{c.abbreviation} {result_dict[c.current_war.result]} in war!")

                    try:
                        raid_update = await c.update_raid_weekend(ctx)
                    except Exception as e:
                        err = DataError(category='clraid',tag=c.tag,error=e)
                        error_log.append(err)
                    else:
                        clan_update += f"\n> - Raid Weekend: {c.current_raid_weekend.state}"

                        if raid_update:
                            clan_update += raid_update
                            send_logs = True

                        if c.raid_state_change:
                            detected_raid_change = True

                            if c.current_raid_weekend.state == 'ongoing':
                                active_events.append(f"Raid Weekend has started!")

                            if c.current_raid_weekend.state == 'ended':
                                active_events.append(f"{(c.current_raid_weekend.offense_rewards * 6) + c.current_raid_weekend.defense_rewards:,} Raid Medals in {c.abbreviation}")

                        if c.current_raid_weekend.state == 'ongoing':
                            passive_events.append(f"Raid Weekend with {len(c.current_raid_weekend.members)} {c.abbreviation} members")

                    try:
                        await c.save_to_json(ctx)
                    except Exception as e:
                        err = DataError(category='cljson',tag=c.tag,error=e)
                        error_log.append(err)


                data_embed.add_field(
                    name=f"**Clan Updates**",
                    value=clan_update,
                    inline=False)

                await test_ch.send(f'finished clan')

                ## MEMBER UPDATE
                count_member_update = 0
                for m in alliance_members:
                    try:
                        if is_cwl:
                            await m.set_baselines(ctx)
                        else:
                            if m.is_member:
                                stats = m.current_season
                                await stats.clangames.calculate_clangames()
                                await m.update_warlog(ctx)
                                await m.update_raid_weekend(ctx)

                                if m.clan.is_alliance_clan:
                                    await m.update_stats(ctx)
                            else:
                                await m.set_baselines(ctx)
                    except Exception as e:
                        err = DataError(category='meupdt',tag=m.tag,error=e)
                        error_log.append(err)
                        continue

                    try:
                        await m.save_to_json(ctx)
                    except Exception as e:
                        err = DataError(category='mejson',tag=m.tag,error=e)
                        error_log.append(err)
                        continue

                    count_member_update += 1

                data_embed.add_field(
                    name=f"**Member Updates**",
                    value=f"Number of Tags: {len(list(member_json.keys()))}"
                        + f"\nAccounts Found: {len(alliance_members)}"
                        + f"\nSuccessful Updates: {count_member_update}",
                    inline=False)

                await test_ch.send(f'finished member')

                for m in alliance_members:
                    if m.discord_user.discord_member and m.discord_user.user_id not in [u.user_id for u in discord_members]:
                        discord_members.append(m.discord_user)

                [await m.sync_roles(ctx) for m in discord_members]

                await test_ch.send(f'finished roles')

                et = time.time()
                ctx.bot.refresh_loop += 1

                if len(error_log) > 0:
                    send_logs = True
                    error_title = "Error Log"
                    error_text = ""
                    for e in error_log:
                        error_text += f"{e.category}{e.tag}: {e.error}\n"

                    if len(errStr) > 1024:
                        error_title = "Error Log (Truncated)"
                        error_text = errStr[0:500]

                    data_embed.add_field(
                        name=f"**{error_title}**",
                        value=error_text,
                        inline=False)

                processing_time = round(et-st,2)
                run_time_hist.append(processing_time)

                if len(run_time_hist) > 100:
                    del run_time_hist[0]

                if ctx.bot.refresh_loop == 1 or (ctx.bot.refresh_loop % 100) == 0:
                    send_logs = True

                await self.config.last_data_update.set(st)
                await self.config.update_runtimes.set(run_time_hist)

                if send_logs:
                    try:
                        log_channel = self.bot.get_channel(1033390608506695743)
                    except:
                        log_channel = None

                    if log_channel:
                        average_run_time = round(sum(run_time_hist) / len(run_time_hist),2)

                        run_time_plot = ctx.bot.clash_dir_path+"/runtimeplot.png"

                        plt.figure()
                        plt.plot(run_time_hist)
                        plt.savefig(run_time_plot)
                        plt.clf()

                        run_time_plot_file = discord.File(run_time_plot,filename='run_time_plot.png')
                        data_embed.set_image(url=f"attachment://run_time_plot.png")

                        data_embed.add_field(
                            name=f"**Processing Time**",
                            value=f"{round(et-st,2)} seconds. *Average: {average_run_time} seconds.*",
                            inline=False)

                        await log_channel.send(embed=data_embed,file=run_time_plot_file)

                activity_types = [
                    discord.ActivityType.playing,
                    discord.ActivityType.streaming,
                    discord.ActivityType.listening,
                    discord.ActivityType.watching
                    ]
                activity_select = random.choice(activity_types)

                if is_new_season:
                    await ctx.bot.change_presence(
                    activity=discord.Activity(
                        type=activity_select,
                        name=f"start of the {new_season} Season! Clash on!"))

                #update after 3 hours
                elif len(active_events) > 0 or (last_status_update - st) > 10800:
                    if len(active_events) > 0:
                        event = random.choice(active_events)
                        await ctx.bot.change_presence(
                            activity=discord.Activity(
                                type=activity_select,
                                name=event))
                        await self.config.last_status_update.set(st)

                    elif len(passive_events) > 0:
                        event = random.choice(passive_events)
                        await ctx.bot.change_presence(
                            activity=discord.Activity(
                                type=activity_select,
                                name=event))
                        await self.config.last_status_update.set(st)

                    else:
                        await ctx.bot.change_presence(
                            activity=discord.Activity(
                                type=activity_select,
                                name=f"{len(alliance_members)} AriX members"))
                        await self.config.last_status_update.set(st)

                await test_ch.send(f'i made it here')

                self.bot.refresh_status = True

            except Exception as e:
                await test_ch.send(e)

        self.bot.refresh_status = save_state

