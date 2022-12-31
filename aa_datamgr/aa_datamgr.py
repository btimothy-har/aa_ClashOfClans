import os
import sys
import shutil

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
from aa_resourcecog.file_functions import get_current_season, alliance_file_handler, data_file_handler, eclipse_base_handler
from aa_resourcecog.player import aPlayer, aClan, aMember
from aa_resourcecog.clan_war import aClanWar
from aa_resourcecog.raid_weekend import aRaidWeekend
from aa_resourcecog.errors import TerminateProcessing, InvalidTag

class DataError():
    def __init__(self,**kwargs):
        self.category = kwargs.get('category',None)
        self.tag = kwargs.get('tag',None)
        self.error = kwargs.get('error',None)

class EmptyContext(commands.Context):
    def __init__(self,bot):
        self.bot = bot

class AriXClashDataMgr(commands.Cog):
    """AriX Clash of Clans Data Module."""

    def __init__(self,bot):
        self.master_bot = bot
        self.config = Config.get_conf(self,identifier=2170311125702803,force_registration=True)
        default_global = {
            "last_status_update": 0,
            "clan_update_last":0,
            "clan_update_runtime":[],
            "member_update_last":0,
            "member_update_runtime":[],
            }
        default_guild = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.season_update.start()
        self.clan_update.start()
        self.member_update.start()

    async def initialize_config(self,bot):
        ctx = EmptyContext(bot)

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

        bot.current_season = s_json['current']
        bot.tracked_seasons = s_json['tracked']

        alliance_clans_json = await alliance_file_handler(
            ctx=ctx,
            entry_type='clans',
            tag="**")

        member_json = await alliance_file_handler(
            ctx=ctx,
            entry_type='members',
            tag="**")

        if bot.load_cache:
            if len(list(bot.clan_cache.keys())) == 0:
                [await aClan.create(ctx,tag=tag) for tag in list(alliance_clans_json.keys())]

            if len(list(bot.member_cache.keys())) == 0:
                [await aPlayer.create(ctx,tag=tag) for tag in list(member_json.keys())]
            bot.refresh_loop = 0


    @commands.command(name="initdata")
    @commands.is_owner()
    async def initialize_data_cache(self,ctx):
        msg = await ctx.send("Initializing...")

        ctx.bot.user_cache = {}
        ctx.bot.member_cache = {}
        ctx.bot.clan_cache = {}
        ctx.bot.pass_cache = {}

        with ctx.bot.clash_file_lock.read_lock():
            with open(ctx.bot.clash_dir_path+'/seasons.json','r') as file:
                s_json = json.load(file)

        ctx.bot.current_season = s_json['current']
        ctx.bot.tracked_seasons = s_json['tracked']

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

        ctx.bot.refresh_loop = 0

        await msg.delete()

    @commands.command(name="fileconvert")
    @commands.is_owner()
    async def convert_warraidlog(self,ctx):

        file_path = ctx.bot.clash_dir_path + '/' + 'warlog.json'

        await ctx.send(f'started {file_path}')
        with ctx.bot.clash_file_lock.read_lock():
            with open(file_path,'r') as file:
                file_json = json.load(file)
        new_warlog = {}

        for (clan,warlog) in file_json.items():
            c = await aClan.create(ctx,tag=clan,conv=True)
            c.war_log = {}

            for (wid,war) in warlog.items():
                w = await aClanWar.get(ctx,clan=c,json=war)
                war_id = w.war_id

                c.war_log[war_id] = w
                new_warlog[war_id] = w.to_json()

            await c.save_to_json(ctx)

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(file_path,'r+') as file:
                    file.seek(0)
                    json.dump(new_warlog,file,indent=2)
                    file.truncate()

        file_path = ctx.bot.clash_dir_path + '/' + 'capitalraid.json'
        await ctx.send(f'now onto cap {file_path}')
        with ctx.bot.clash_file_lock.read_lock():
            with open(file_path,'r') as file:
                file_json = json.load(file)
        new_raidlog = {}

        for (clan,raidlog) in file_json.items():
            c = await aClan.create(ctx,tag=clan,conv=True)
            c.raid_log = {}

            for (wid,raid) in raidlog.items():
                r = await aRaidWeekend.get(ctx,clan=c,json=raid)
                raid_id = r.raid_id

                c.raid_log[raid_id] = r
                new_raidlog[raid_id] = r.to_json()

            await c.save_to_json(ctx)

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(file_path,'r+') as file:
                    file.seek(0)
                    json.dump(new_raidlog,file,indent=2)
                    file.truncate()

        file_path = ctx.bot.clash_dir_path + '/' + 'members.json'
        await ctx.send(f'members now {file_path}')
        with ctx.bot.clash_file_lock.read_lock():
            with open(file_path,'r') as file:
                file_json = json.load(file)

        for (tag,member) in file_json.items():
            new_warlog = []
            for (war_id,war) in member['war_log']:

                tag_id = war['clan']['tag'] + war['opponent']['tag']
                tag_id = tag_id.replace('#','')
                tag_id = ''.join(sorted(tag_id))

                new_id = tag_id + str(int(float(war_id)))
                new_warlog.append(new_id)

            new_raidlog = []
            for (raid_id,raid) in member['raid_log']:

                tag_id = raid['clan_tag']
                tag_id = tag_id.replace('#','')

                new_id = tag_id + str(int(float(raid_id)))
                new_raidlog.append(new_id)

            member['war_log'] = new_warlog
            member['raid_log'] = new_raidlog

            file_json[tag] = member

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(file_path,'r+') as file:
                    file.seek(0)
                    json.dump(file_json,file,indent=2)
                    file.truncate()

        await ctx.send('all done')

    @commands.command(name="drefresh")
    @commands.is_owner()
    async def data_toggle(self,ctx):
        m = await ctx.send("Please wait...")

        if ctx.bot.master_refresh:
            ctx.bot.master_refresh = False
            self.season_update.stop()
            self.clan_update.stop()
            self.member_update.stop()
            await ctx.send("Bot Data Refresh is now stopped.")

        else:
            ctx.bot.master_refresh = True
            await ctx.send("Bot Data Refresh is now activated.")

        await m.delete()

    @commands.group(name="data",aliases=["status"],autohelp=False)
    @commands.is_owner()
    async def data_control(self,ctx):
        """Manage the bot's Clash of Clans data."""
        if not ctx.invoked_subcommand:

            clan_update_last = await self.config.clan_update_last()
            member_update_last = await self.config.member_update_last()

            try:
                clan_update_runtime = await self.config.clan_update_runtime()
                clan_update_average = round(sum(clan_update_runtime)/len(clan_update_runtime),2)
            except:
                clan_update_average = 0

            try:
                member_update_runtime = await self.config.member_update_runtime()
                member_update_average = round(sum(member_update_runtime)/len(member_update_runtime),2)
            except:
                member_update_average = 0

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
                name="__Data Update Status__",
                value=f"> **Master Switch**: {ctx.bot.master_refresh}"
                    + f"\n> **Clan Update**: {ctx.bot.clan_refresh_status}"
                    + f"\n> **Last Clan Update**: <t:{int(clan_update_last)}:R>"
                    + f"\n> **Member Update**: {ctx.bot.member_refresh_status}"
                    + f"\n> **Last Member Update**: <t:{int(member_update_last)}:R>",
                inline=False)

            embed.add_field(
                name="__Data Update Performance__",
                value=f"> **Jobs Completed**: {ctx.bot.refresh_loop}"
                    + f"\n> **Clan Update Runtime**: avg {clan_update_average} seconds"
                    + f"\n> **Member Update Runtime**: avg {member_update_average} seconds",
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



    @tasks.loop(hours=1.0)
    async def season_update(self):

        bot = self.master_bot
        ctx = EmptyContext(bot=bot)
        send_logs = False

        clans = []
        members = []

        if bot.refresh_loop < 0:
            return None

        if not bot.master_refresh:
            return None

        st = time.time()
        update_season = False

        last_status_update = await self.config.last_status_update()

        season_embed = discord.Embed(
            title="**Season Update**",
            color=0x0000)

        season_embed.set_footer(
            text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
            icon_url="https://i.imgur.com/TZF5r54.png")

        season = await get_current_season()
        if season != bot.current_season:
            update_season = True
            send_logs = True

            season_embed.add_field(
                name=f"__New Season Detected__",
                value=f"> Current Season: {bot.current_season}"
                    + f"\n> New Season: {season}",
                inline=False)

        if update_season:
            log_str = ""

            alliance_clans_json = await alliance_file_handler(
                ctx=ctx,
                entry_type='clans',
                tag="**")

            for c_tag in list(alliance_clans_json.keys()):
                try:
                    c = await aClan.create(ctx,tag=c_tag)
                except Exception as e:
                    err = DataError(category='clan',tag=c_tag,error=e)
                    error_log.append(err)
                    continue

                if c.current_war.state == 'inWar':
                    update_season = False
                if c.current_raid_weekend.state == 'ongoing':
                    update_season = False

                log_str += f"**{c.name} ({c.tag})**"
                log_str += f"\n> Clan War: {c.current_war.state}"
                log_str += f"\n> Capital Raid: {c.current_raid_weekend.state}"

                log_str += "\n\n"

            season_embed.add_field(
                name=f"__Clan Activities__",
                value=log_str,
                inline=False)

        if update_season:
            #lock processes
            bot.clan_refresh_status = True
            bot.member_refresh_status = True

            new_season = season

            member_info_json = await alliance_file_handler(
                ctx=ctx,
                entry_type='members',
                tag="**")

            async with bot.async_file_lock:
                with bot.clash_file_lock.write_lock():
                    new_path = bot.clash_dir_path+'/'+current_season
                    os.makedirs(new_path)

                    with open(bot.clash_dir_path+'/seasons.json','r+') as file:
                        s_json = json.load(file)
                        s_json['tracked'].append(current_season)
                        s_json['current'] = new_season
                        file.seek(0)
                        json.dump(s_json,file,indent=2)
                        file.truncate()

                    shutil.copy2(bot.clash_dir_path+'/alliance.json',new_path)
                    shutil.copy2(bot.clash_dir_path+'/members.json',new_path)
                    with open(bot.clash_dir_path+'/members.json','w+') as file:
                        json.dump({},file,indent=2)

            for c_tag in list(alliance_clans_json.keys()):
                try:
                    c = await aClan.create(ctx,tag=c_tag,refresh=True,reset=True)
                except Exception as e:
                    err = DataError(category='clan',tag=c_tag,error=e)
                    error_log.append(err)
                    continue

            for m_tag in list(member_info_json.keys()):
                try:
                    m = await aPlayer.create(ctx,tag=m_tag,refresh=True,reset=True)
                    await m.set_baselines(ctx)
                except Exception as e:
                    err = DataError(category='player',tag=m_tag,error=e)
                    error_log.append(err)
                    continue

            season_embed.add_field(
                name=f"**New Season Initialized: {new_season}**",
                value=f"__Files Saved__"
                    + f"\n**{current_season}/members.json**: {os.path.exists(bot.clash_dir_path+'/'+current_season+'/members.json')}"
                    + f"\n"
                    + f"__Files Created__"
                    + f"\n**members.json**: {os.path.exists(bot.clash_dir_path+'/members.json')}",
                inline=False)

            try:
                await bot.update_channel.send(f"**The new season {season} has started!**")
            except:
                pass

            activity_types = [
                discord.ActivityType.playing,
                discord.ActivityType.streaming,
                discord.ActivityType.listening,
                discord.ActivityType.watching
                ]
            activity_select = random.choice(activity_types)

            await bot.change_presence(
                activity=discord.Activity(
                type=activity_select,
                name=f"start of the {new_season} Season! Clash on!"))
            await self.config.last_status_update.set(st)

        if send_logs:
            await self.data_log_channel.send(embed=season_embed)


    @tasks.loop(seconds=60.0)
    async def clan_update(self):

        bot = self.master_bot
        ctx = EmptyContext(bot=bot)
        send_logs = False

        if bot.refresh_loop < 0:
            return None

        if not bot.master_refresh:
            return None

        if bot.clan_refresh_status:
            return None

        bot.clan_refresh_status = True

        st = time.time()
        helsinkiTz = pytz.timezone("Europe/Helsinki")

        is_cwl = False
        if datetime.now(helsinkiTz).day <= 9:
            is_cwl = True

        data_embed = discord.Embed(
            title="Clan Update Report",
            color=0x0000)

        data_embed.set_footer(
            text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
            icon_url="https://i.imgur.com/TZF5r54.png")

        try:
            last_status_update = await self.config.last_status_update()
            clan_update_last = await self.config.clan_update_last()
            clan_update_runtime = await self.config.clan_update_runtime()

            active_events = []
            passive_events = []

            error_log = []

            alliance_clans_json = await alliance_file_handler(
                ctx=ctx,
                entry_type='clans',
                tag="**")

            ## CLAN UPDATE
            clan_update = ''
            mem_count = 0
            for c_tag in list(alliance_clans_json.keys()):
                try:
                    c = await aClan.create(ctx,tag=c_tag,refresh=True)
                except Exception as e:
                    err = DataError(category='clan',tag=c_tag,error=e)
                    error_log.append(err)
                    continue

                mem_count += c.arix_member_count

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

                clan_update += f"\n"

            if clan_update == '':
                clan_update = "No Updates"

            data_embed.add_field(
                name=f"**Clan Updates**",
                value=clan_update,
                inline=False)

            et = time.time()
            bot.refresh_loop += 1
            bot.clan_refresh_status = False

        except Exception as e:
            await bot.send_to_owners(f"Error encountered during Clan Data Refresh:\n\n{e}")
            bot.clan_refresh_status = False
            return


        try:
            processing_time = round(et-st,2)
            clan_update_runtime.append(processing_time)

            if len(clan_update_runtime) > 100:
                del clan_update_runtime[0]

            await self.config.clan_update_last.set(st)
            await self.config.clan_update_runtime.set(clan_update_runtime)

            if len(error_log) > 0:
                error_title = "Error Log"
                error_text = ""
                for e in error_log:
                    error_text += f"{e.category}{e.tag}: {e.error}\n"

                if len(error_text) > 1024:
                    error_title = "Error Log (Truncated)"
                    error_text = error_text[0:500]

                data_embed.add_field(
                    name=f"**{error_title}**",
                    value=error_text,
                    inline=False)

                await bot.data_log_channel.send(embed=data_embed)

            activity_types = [
                discord.ActivityType.playing,
                discord.ActivityType.streaming,
                discord.ActivityType.listening,
                discord.ActivityType.watching
                ]
            activity_select = random.choice(activity_types)

            #update active events after 1 hours
            if last_status_update - st > 3600 and len(active_events) > 0:
                event = random.choice(active_events)
                await bot.change_presence(
                    activity=discord.Activity(
                        type=activity_select,
                        name=event))
                await self.config.last_status_update.set(st)

            #update passive events after 2 hours
            elif last_status_update - st > 7200 and len(passive_events) > 0:
                event = random.choice(passive_events)
                await bot.change_presence(
                    activity=discord.Activity(
                    type=activity_select,
                    name=event))
                await self.config.last_status_update.set(st)

            elif last_status_update - st > 14400:
                await bot.change_presence(
                    activity=discord.Activity(
                    type=activity_select,
                    name=f"{mem_count} AriX members"))
                await self.config.last_status_update.set(st)

        except Exception as e:
            await bot.send_to_owners(f"Clan Data Refresh completed successfully, but an error was encountered while wrapping up.\n\n{e}")


    @tasks.loop(seconds=60.0)
    async def member_update(self):

        bot = self.master_bot
        ctx = EmptyContext(bot=bot)
        send_logs = False

        if bot.refresh_loop < 0:
            return None

        if not bot.master_refresh:
            return None

        if bot.member_refresh_status:
            return None

        bot.member_refresh_status = True

        st = time.time()
        helsinkiTz = pytz.timezone("Europe/Helsinki")

        is_cwl = False
        if datetime.now(helsinkiTz).day <= 9:
            is_cwl = True

        data_embed = discord.Embed(
            title="Member Update Report",
            color=0x0000)

        data_embed.set_footer(
            text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
            icon_url="https://i.imgur.com/TZF5r54.png")


        try:
            member_update_last = await self.config.member_update_last()
            member_update_runtime = await self.config.member_update_runtime()

            role_sync_completed = []
            error_log = []

            member_json = await alliance_file_handler(
                ctx=ctx,
                entry_type='members',
                tag="**")

            count_members = 0
            count_member_update = 0
            for m_tag in list(member_json.keys()):
                try:
                    m = await aPlayer.create(ctx,tag=m_tag,refresh=True)
                except Exception as e:
                    err = DataError(category='player',tag=m_tag,error=e)
                    error_log.append(err)
                    continue

                count_members += 1

                try:
                    await m.update_warlog(ctx)
                    await m.update_raid_weekend(ctx)

                    if is_cwl:
                        await m.set_baselines(ctx)
                    else:
                        await m.current_season.clangames.calculate_clangames()

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

                if m.discord_user:
                    try:
                        memo = await aMember.create(ctx,user_id=m.discord_user)
                    except Exception as e:
                        err = DataError(category='getme',tag=m.tag,error=e)
                        error_log.append(err)
                        continue

                    if memo:
                        if memo.discord_member and memo.user_id not in role_sync_completed:
                            if True:
                                await memo.sync_roles(ctx)
                            # except Exception as e:
                            #     err = DataError(category='mesync',tag=m.tag,error=e)
                            #     error_log.append(err)
                            #     continue
                            # else:
                            #     role_sync_completed.append(memo.user_id)

                count_member_update += 1

            data_embed.add_field(
                name=f"**Member Updates**",
                value=f"Number of Tags: {len(list(member_json.keys()))}"
                    + f"\nAccounts Found: {count_members}"
                    + f"\nSuccessful Updates: {count_member_update}",
                inline=False)

            et = time.time()
            bot.refresh_loop += 1
            bot.member_refresh_status = False

        except Exception as e:
            await bot.send_to_owners(f"Error encountered during Member Data Refresh:\n\n{e}")
            bot.member_refresh_status = False
            return


        try:
            processing_time = round(et-st,2)
            member_update_runtime.append(processing_time)

            if len(member_update_runtime) > 100:
                del member_update_runtime[0]

            await self.config.member_update_last.set(st)
            await self.config.member_update_runtime.set(member_update_runtime)

            if len(error_log) > 0:
                error_title = "Error Log"
                error_text = ""
                for e in error_log:
                    error_text += f"{e.category}{e.tag}: {e.error}\n"

                if len(error_text) > 1024:
                    error_title = "Error Log (Truncated)"
                    error_text = error_text[0:500]

                data_embed.add_field(
                    name=f"**{error_title}**",
                    value=error_text,
                    inline=False)

                await bot.data_log_channel.send(embed=data_embed)

        except Exception as e:
            await bot.send_to_owners(f"Member Data Refresh completed successfully, but an error was encountered while wrapping up.\n\n{e}")
