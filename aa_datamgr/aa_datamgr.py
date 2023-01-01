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
from aa_resourcecog.file_functions import get_current_season, save_war_cache, save_raid_cache, save_clan_cache, save_member_cache, read_file_handler, write_file_handler, eclipse_base_handler
from aa_resourcecog.player import aClashSeason, aPlayer, aClan, aMember
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
            "clan_update_last":0,
            "clan_update_runtime":[],
            "member_update_last":0,
            "member_update_runtime":[],
            "last_data_save":0,
            }
        default_guild = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

        self.master_lock = asyncio.Lock()
        self.clan_lock = asyncio.Lock()
        self.member_lock = asyncio.Lock()

        self.last_status_update = 0
        self.clan_update_count = 0
        self.member_update_count = 0
        self.season_update_count = 0
        self.backup_count = 0

    @commands.command(name="nstart")
    @commands.is_owner()
    async def start_nebula(self,ctx,partial=False):
        bot = self.master_bot
        msg = await ctx.send("**Initializing N.E.B.U.LA.** ...")

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

        ctx.bot.current_season = aClashSeason(s_json['current'])
        ctx.bot.tracked_seasons = [aClashSeason(ssn) for ssn in s_json['tracked']]

        ctx.bot.user_cache = {}
        ctx.bot.member_cache = {}
        ctx.bot.clan_cache = {}
        ctx.bot.pass_cache = {}

        if not partial:
            with ctx.bot.clash_file_lock.read_lock():
                with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
                    a_json = json.load(file)

            with ctx.bot.clash_file_lock.read_lock():
                with open(ctx.bot.clash_dir_path+'/players.json','r') as file:
                    m_json = json.load(file)

            with ctx.bot.clash_file_lock.read_lock():
                with open(ctx.bot.clash_dir_path+'/warlog.json','r') as file:
                    w_json = json.load(file)

            with ctx.bot.clash_file_lock.read_lock():
                with open(ctx.bot.clash_dir_path+'/capitalraid.json','r') as file:
                    cr_json = json.load(file)

            for (tag,clan) in a_json['clans'].items():
                await aClan.create(ctx,tag=tag,json=clan)

            for (tag,member) in a_json['members'].items():
                if tag in list(m_json.keys()):
                    a = await aPlayer.create(ctx,tag=tag,a_json=member,s_json=m_json[tag])
                else:
                    a = await aPlayer.create(ctx,tag=tag,a_json=member)

            ctx.bot.refresh_loop = 0

            self.data_backup_save.start()

        await msg.delete()
        await ctx.send("**Setup complete.**")

    @commands.command(name="nsave")
    @commands.is_owner()
    async def save_json_data(self,ctx):

        bot = self.master_bot
        send_logs = False

        if bot.refresh_loop < 0:
            return None

        master_lock = await self.master_lock.acquire()
        clan_lock = await self.clan_lock.acquire()
        member_lock = await self.member_lock.acquire()

        st = time.time()

        await self.config.last_data_save.set(st)

        self.clan_lock.release()
        self.member_lock.release()
        self.master_lock.release()

        await ctx.send("Save complete.")


    @commands.command(name="nstop")
    @commands.is_owner()
    async def stop_nebula(self,ctx):

        await ctx.send("**Stopping...**")

        master_lock = await self.master_lock.acquire()
        clan_lock = await self.clan_lock.acquire()
        member_lock = await self.member_lock.acquire()

        ctx.bot.master_refresh = False
        self.season_update.stop()
        self.clan_update.stop()
        self.member_update.stop()
        self.data_backup_save.stop()

        #save data
        await save_war_cache(ctx)
        await save_raid_cache(ctx)
        await save_clan_cache(ctx)
        await save_member_cache(ctx)
        await ctx.send("**Data saved, goodbye!**")

        self.master_bot.remove_cog('AriXMemberCommands')
        self.master_bot.remove_cog('AriXLeaderCommands')
        self.master_bot.remove_cog('AriXClashDataMgr')

        await ctx.bot.coc_client.close()
        await ctx.bot.discordlinks.close()

        self.clan_lock.release()
        self.member_lock.release()
        self.master_lock.release()


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
            if coc.utils.is_valid_tag(clan):
                c = await aClan.create(ctx,tag=clan,conv=True)
                c.war_log = {}

                for (wid,war) in warlog.items():
                    w = await aClanWar.get(ctx,clan=c,json=war)
                    war_id = w.war_id

                    c.war_log[war_id] = w
                    new_warlog[war_id] = w.to_json()

                await c.save_to_json(ctx)

            else:
                new_warlog[clan] = warlog

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(file_path,'w') as file:
                    json.dump(new_warlog,file,indent=2)

        file_path = ctx.bot.clash_dir_path + '/' + 'capitalraid.json'
        await ctx.send(f'now onto cap {file_path}')
        with ctx.bot.clash_file_lock.read_lock():
            with open(file_path,'r') as file:
                file_json = json.load(file)
        new_raidlog = {}

        for (clan,raidlog) in file_json.items():
            if coc.utils.is_valid_tag(clan):
                c = await aClan.create(ctx,tag=clan,conv=True)
                c.raid_log = {}

                for (wid,raid) in raidlog.items():
                    r = await aRaidWeekend.get(ctx,clan=c,json=raid)
                    raid_id = r.raid_id

                    c.raid_log[raid_id] = r
                    new_raidlog[raid_id] = r.to_json()

                await c.save_to_json(ctx)
            else:
                new_raidlog[clan] = raidlog

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(file_path,'w') as file:
                    json.dump(new_raidlog,file,indent=2)

        file_path = ctx.bot.clash_dir_path + '/' + 'members.json'
        await ctx.send(f'members now {file_path}')
        with ctx.bot.clash_file_lock.read_lock():
            with open(file_path,'r') as file:
                file_json = json.load(file)

        for (tag,member) in file_json.items():

            if 'attack_wins' in list(member.keys()):
                member['attacks'] = member['attack_wins']

            if 'defense_wins' in list(member.keys()):
                member['defenses'] = member['defense_wins']

            warlog = member['war_log']
            if isinstance(warlog,dict):
                new_warlog = []
                for (war_id,war) in warlog.items():

                    tag_a = war['clan']['tag'] + war['opponent']['tag']
                    tag_b = tag_a.replace('#','')
                    tag_id = ''.join(sorted(tag_b))

                    new_id = tag_id + str(int(float(war_id)))
                    new_warlog.append(new_id)
                member['war_log'] = new_warlog

            raidlog = member['raid_log']
            if isinstance(raidlog,dict):
                new_raidlog = []
                for (raid_id,raid) in member['raid_log'].items():

                    tag_a = raid['clan_tag']
                    tag_id = tag_a.replace('#','')

                    new_id = tag_id + str(int(float(raid_id)))
                    new_raidlog.append(new_id)
                member['raid_log'] = new_raidlog

            mm = await aPlayer.create(ctx,tag=tag,s_json=member,reset=True)

            await mm.save_to_json(ctx)

        #     aa_json, mm_json = mm.to_json()

        #     file_json[tag] = mm_json

        # file_path = ctx.bot.clash_dir_path + '/' + 'players.json'
        # async with ctx.bot.async_file_lock:
        #     with ctx.bot.clash_file_lock.write_lock():
        #         with open(file_path,'w') as file:
        #             json.dump(file_json,file,indent=2)

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
            self.season_update.start()
            self.clan_update.start()
            self.member_update.start()
            await ctx.send("Bot Data Refresh is now activated.")

        await m.delete()

    @commands.group(name="data",aliases=["status"],autohelp=False)
    @commands.is_owner()
    async def data_control(self,ctx):
        """Manage the bot's Clash of Clans data."""
        if not ctx.invoked_subcommand:

            clan_update_last = await self.config.clan_update_last()
            member_update_last = await self.config.member_update_last()
            last_data_save  = await self.config.last_data_save()

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
                value=f"> Current Season: {ctx.bot.current_season.season_description}"
                    + f"\n> Seasons: {', '.join([s.season_description for s in ctx.bot.tracked_seasons])}"
                    + f"\n> Players: {len(ctx.bot.member_cache)}"
                    + f"\n> Clans: {len(ctx.bot.clan_cache)}"
                    + f"\n> Users: {len(ctx.bot.user_cache)}"
                    + f"\n> Clan Wars: {len(ctx.bot.war_cache)}"
                    + f"\n> Capital Raids: {len(ctx.bot.raid_cache)}"
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
                    + f"\n> **players.json**: {os.path.exists(ctx.bot.clash_dir_path+'/players.json')}"
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
                    + f"\n> **Last Member Update**: <t:{int(member_update_last)}:R>"
                    + f"\n> **Last Data Save**: <t:{int(last_data_save)}:R>",
                inline=False)

            embed.add_field(
                name="__Data Update Performance__",
                value=f"> **Member Update Jobs**: {self.member_update_count}"
                    + f"\n> **Clan Update Jobs**: {self.clan_update_count}"
                    + f"\n> **Season Check Jobs**: {self.season_update_count}"
                    + f"\n> **Backup Jobs**: {self.backup_count}"
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
                    season_default['current'] = aClashSeason.get_current_season()
                    json.dump(season_default,file,indent=2)

                with open(ctx.bot.clash_dir_path+'/alliance.json','w') as file:
                    json.dump(json_file_defaults['alliance'],file,indent=2)

                with open(ctx.bot.clash_dir_path+'/member_info.json','w') as file:
                    json.dump({},file,indent=2)

                with open(ctx.bot.clash_dir_path+'/warlog.json','w') as file:
                    json.dump({},file,indent=2)

                with open(ctx.bot.clash_dir_path+'/capitalraid.json','w') as file:
                    json.dump({},file,indent=2)
            
        embed = await clash_embed(ctx=ctx,
            title="All Data Files Reset.",
            message=f"**seasons.json**: {os.path.exists(ctx.bot.clash_dir_path+'/seasons.json')}"
                    +f"\n**alliance.json**: {os.path.exists(ctx.bot.clash_dir_path+'/alliance.json')}"
                    +f"\n**member_info.json**: {os.path.exists(ctx.bot.clash_dir_path+'/member_info.json')}"
                    +f"\n**warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/warlog.json')}"
                    +f"\n**capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/capitalraid.json')}",
            color="success")
        return await ctx.send(embed=embed)


    @commands.command(name="simulate")
    @commands.is_owner()
    async def data_simulation(self,ctx,update_type,tag):

        st = time.time()

        if update_type not in ['clan','member','season']:
            await ctx.send("Invalid data type.")

        if update_type == 'member':
            is_cwl = False

            if st >= ctx.bot.current_season.cwl_start and st <= ctx.bot.current_season.cwl_end:
                is_cwl = True

            m = await aPlayer.create(ctx,tag=tag,refresh=True)

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

            await m.save_to_json(ctx)

            role_sync_completed = []
            if m.discord_user:
                memo = await aMember.create(ctx,user_id=m.discord_user)

                if memo:
                    if memo.discord_member and memo.user_id not in role_sync_completed:
                        await memo.sync_roles(ctx)
                        role_sync_completed.append(memo.user_id)

        if update_type == 'clan':
            c = await aClan.create(ctx,tag=tag,refresh=True)

            if c.is_alliance_clan:
                await c.compute_arix_membership(ctx)

            war_update = await c.update_clan_war(ctx)
            raid_update = await c.update_raid_weekend(ctx)

            clanwar_json = await data_file_handler(
                ctx=ctx,
                action='read',
                entry_type='warlog',
                tag="**")
            capitalraid_json = await data_file_handler(
                ctx=ctx,
                action='read',
                entry_type='capitalraid',
                tag="**")

            for war_id in list(clanwar_json.keys()):
                war = await aClanWar.get(ctx,war_id=war_id)

                if war.state not in ['warEnded']:
                    war_clan = await aClan.create(ctx,tag=war.clan.tag)
                    war = await aClanWar.get(ctx,clan=war_clan)

            for raid_id in list(capitalraid_json.keys()):
                raid = await aRaidWeekend.get(ctx,raid_id=raid_id)

                if raid.state not in ['ended']:
                    raid_clan = await aClan.create(ctx,tag=raid.clan_tag)
                    raid = await aRaidWeekend.get(ctx,clan=raid_clan)

        if update_type == 'season':
            bot = self.master_bot
            test_str = ""
            update_season = False

            season_embed = discord.Embed(
                title="**Season Update**",
                color=0x0000)

            season_embed.set_footer(
                text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
                icon_url="https://i.imgur.com/TZF5r54.png")

            season = aClashSeason.get_current_season()

            if season.id != bot.current_season.id:
                update_season = True
                send_logs = True

                test_str += f"> Current Season: {bot.current_season.season_description}"
                test_str += f"\n> New Season: {season.season_description}"

                season_embed.add_field(
                    name=f"__New Season Detected__",
                    value=f"> Current Season: {bot.current_season.season_description}"
                        + f"\n> New Season: {season.season_description}",
                    inline=False)

            if update_season:
                log_str = ""

                for (c_tag,clan) in ctx.bot.clan_cache.items():

                    if clan.is_alliance_clan:
                        if clan.war_state == 'inWar':
                            update_season = False
                        if clan.raid_weekend_state == 'ongoing':
                            update_season = False

                        log_str += f"**{clan.name} ({clan.tag})**"
                        log_str += f"\n> Clan War: {getattr(clan.current_war,'state',None)}"
                        log_str += f"\n> Capital Raid: {getattr(clan.current_raid_weekend,'state',None)}"

                        log_str += "\n\n"

                season_embed.add_field(
                    name=f"__Clan Activities__",
                    value=log_str,
                    inline=False)

                test_str += log_str

            if update_season:
                #lock processes
                await self.master_lock.acquire()
                await self.clan_lock.acquire()
                await self.member_lock.acquire()

                await save_war_cache(ctx)
                await save_raid_cache(ctx)
                await save_clan_cache(ctx)
                await save_member_cache(ctx)

                async with bot.async_file_lock:
                    with bot.clash_file_lock.write_lock():
                        new_path = bot.clash_dir_path+'/'+bot.current_season.id
                        os.makedirs(new_path)

                        with open(bot.clash_dir_path+'/seasons.json','r+') as file:
                            s_json = json.load(file)
                            s_json['tracked'].append(bot.current_season.id)
                            s_json['current'] = season.id
                            file.seek(0)
                            json.dump(s_json,file,indent=2)
                            file.truncate()

                        shutil.copy2(bot.clash_dir_path+'/alliance.json',new_path)
                        shutil.copy2(bot.clash_dir_path+'/players.json',new_path)
                        with open(bot.clash_dir_path+'/players.json','w+') as file:
                            json.dump({},file,indent=2)

                for (c_tag,clan) in ctx.bot.clan_cache.items():
                    try:
                        c = await aClan.create(ctx,tag=c_tag,refresh=True,reset=True)
                    except Exception as e:
                        err = DataError(category='clan',tag=c_tag,error=e)
                        error_log.append(err)
                        continue

                for (m_tag,member) in ctx.bot.member_cache.items():
                    try:
                        m = await aPlayer.create(ctx,tag=m_tag,refresh=True,reset=True)
                        await m.set_baselines(ctx)
                    except Exception as e:
                        err = DataError(category='player',tag=m_tag,error=e)
                        error_log.append(err)
                        continue

                season_embed.add_field(
                    name=f"**New Season Initialized: {season.id}**",
                    value=f"__Files Saved__"
                        + f"\n**{bot.current_season.id}/players.json**: {os.path.exists(bot.clash_dir_path+'/'+bot.current_season.id+'/players.json')}"
                        + f"\n"
                        + f"__Files Created__"
                        + f"\n**players.json**: {os.path.exists(bot.clash_dir_path+'/players.json')}",
                    inline=False)

                test_str += f"__Files Saved__"
                test_str += f"\n**{bot.current_season.id}/players.json**: {os.path.exists(bot.clash_dir_path+'/'+bot.current_season.id+'/players.json')}"
                test_str += f"\n"
                test_str += f"__Files Created__"
                test_str += f"\n**players.json**: {os.path.exists(bot.clash_dir_path+'/players.json')}"

                bot.current_season = season
                bot.tracked_seasons = [aClashSeason(ssn) for ssn in s_json['tracked']]

                await self.clan_lock.release()
                await self.member_lock.release()
                await self.master_lock.release()

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
                self.last_status_update = st

        if send_logs:
            ch = bot.get_channel(1033390608506695743)
            await ch.send(embed=season_embed)

        await ctx.send('update completed')

    @tasks.loop(minutes=28.0)
    async def data_backup_save(self):

        bot = self.master_bot
        ctx = EmptyContext(bot=bot)
        send_logs = False

        if bot.refresh_loop < 0:
            return None

        await self.master_lock.acquire()
        await self.clan_lock.acquire()
        await self.member_lock.acquire()

        st = time.time()

        try:
            await save_war_cache(ctx)
            await save_raid_cache(ctx)
            await save_clan_cache(ctx)
            await save_member_cache(ctx)

        except Exception as e:
            await bot.send_to_owners(f"Error encountered during File Save:\n\n```{e}```")
            self.clan_lock.release()
            self.member_lock.release()
            self.master_lock.release()
            return

        await self.config.last_data_save.set(st)

        self.clan_lock.release()
        self.member_lock.release()
        self.master_lock.release()

        self.backup_count += 1


    @tasks.loop(minutes=10.0)
    async def season_update(self):

        bot = self.master_bot
        ctx = EmptyContext(bot=bot)
        send_logs = False

        clans = []
        members = []

        if bot.refresh_loop < 0:
            return None

        st = time.time()
        update_season = False

        season_embed = discord.Embed(
            title="**Season Update**",
            color=0x0000)

        season_embed.set_footer(
            text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
            icon_url="https://i.imgur.com/TZF5r54.png")

        season = aClashSeason.get_current_season()

        if season.id != bot.current_season.id:
            update_season = True
            send_logs = True

            season_embed.add_field(
                name=f"__New Season Detected__",
                value=f"> Current Season: {bot.current_season.season_description}"
                    + f"\n> New Season: {season.season_description}",
                inline=False)

        if update_season:
            log_str = ""

            for (c_tag,clan) in ctx.bot.clan_cache.items():

                if clan.is_alliance_clan:
                    if clan.war_state == 'inWar':
                        update_season = False
                    if clan.raid_weekend_state == 'ongoing':
                        update_season = False

                    log_str += f"**{clan.name} ({clan.tag})**"
                    log_str += f"\n> Clan War: {getattr(clan.current_war,'state',None)}"
                    log_str += f"\n> Capital Raid: {getattr(clan.current_raid_weekend,'state',None)}"

                    log_str += "\n\n"

            season_embed.add_field(
                name=f"__Clan Activities__",
                value=log_str,
                inline=False)

        if update_season:
            #lock processes
            await self.master_lock.acquire()
            await self.clan_lock.acquire()
            await self.member_lock.acquire()

            await save_war_cache(ctx)
            await save_raid_cache(ctx)
            await save_clan_cache(ctx)
            await save_member_cache(ctx)

            async with bot.async_file_lock:
                with bot.clash_file_lock.write_lock():
                    new_path = bot.clash_dir_path+'/'+bot.current_season.id
                    os.makedirs(new_path)

                    with open(bot.clash_dir_path+'/seasons.json','r+') as file:
                        s_json = json.load(file)
                        s_json['tracked'].append(bot.current_season.id)
                        s_json['current'] = season.id
                        file.seek(0)
                        json.dump(s_json,file,indent=2)
                        file.truncate()

                    shutil.copy2(bot.clash_dir_path+'/alliance.json',new_path)
                    shutil.copy2(bot.clash_dir_path+'/players.json',new_path)
                    with open(bot.clash_dir_path+'/players.json','w+') as file:
                        json.dump({},file,indent=2)

            for (c_tag,clan) in ctx.bot.clan_cache.items():
                try:
                    c = await aClan.create(ctx,tag=c_tag,refresh=True,reset=True)
                except Exception as e:
                    err = DataError(category='clan',tag=c_tag,error=e)
                    error_log.append(err)
                    continue

            for (m_tag,member) in ctx.bot.member_cache.items():
                try:
                    m = await aPlayer.create(ctx,tag=m_tag,refresh=True,reset=True)
                    await m.set_baselines(ctx)
                except Exception as e:
                    err = DataError(category='player',tag=m_tag,error=e)
                    error_log.append(err)
                    continue

            season_embed.add_field(
                name=f"**New Season Initialized: {season.id}**",
                value=f"__Files Saved__"
                    + f"\n**{bot.current_season.id}/players.json**: {os.path.exists(bot.clash_dir_path+'/'+bot.current_season.id+'/players.json')}"
                    + f"\n"
                    + f"__Files Created__"
                    + f"\n**players.json**: {os.path.exists(bot.clash_dir_path+'/players.json')}",
                inline=False)

            bot.current_season = season
            bot.tracked_seasons = [aClashSeason(ssn) for ssn in s_json['tracked']]

            await self.clan_lock.release()
            await self.member_lock.release()
            await self.master_lock.release()

            try:
                await bot.update_channel.send(f"**The new season {bot.current_season.id} has started!**")
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
            self.last_status_update = st

        if send_logs:
            ch = bot.get_channel(1033390608506695743)
            await ch.send(embed=season_embed)

        self.season_update_count += 1


    @tasks.loop(seconds=120.0)
    async def clan_update(self):

        bot = self.master_bot
        ctx = EmptyContext(bot=bot)
        send_logs = False

        if bot.refresh_loop < 0:
            return None

        if not bot.master_refresh:
            return None

        if self.master_lock.locked():
            return None
        if self.clan_lock.locked():
            return None

        async with self.clan_lock:
            bot.clan_refresh_status = True

            st = time.time()

            data_embed = discord.Embed(
                title="Clan Update Report",
                color=0x0000)

            data_embed.set_footer(
                text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
                icon_url="https://i.imgur.com/TZF5r54.png")

            try:
                clan_update_last = await self.config.clan_update_last()
                clan_update_runtime = await self.config.clan_update_runtime()

                active_events = []
                passive_events = []

                error_log = []

                ## CLAN UPDATE
                clan_update = ''
                mem_count = 0
                for (c_tag,clan) in ctx.bot.clan_cache.items():
                    try:
                        c = await aClan.create(ctx,tag=c_tag,refresh=True)
                    except Exception as e:
                        err = DataError(category='clan',tag=c_tag,error=e)
                        error_log.append(err)
                        continue

                    if c.is_alliance_clan:
                        try:
                            await c.compute_arix_membership(ctx)
                        except Exception as e:
                            err = DataError(category='clmem',tag=c.tag,error=e)
                            error_log.append(err)

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

                    clan_update += f"\n"

                if clan_update == '':
                    clan_update = "No Updates"

                data_embed.add_field(
                    name=f"**Clan Updates**",
                    value=clan_update,
                    inline=False)

                for (war_id,war) in ctx.bot.war_cache.items():
                    if war.state not in ['warEnded']:
                        war_clan = await aClan.create(ctx,tag=war.clan.tag)
                        war = await aClanWar.get(ctx,clan=war_clan)

                for (raid_id,raid) in ctx.bot.raid_cache.items():
                    if raid.state not in ['ended']:
                        raid_clan = await aClan.create(ctx,tag=raid.clan_tag)
                        raid = await aRaidWeekend.get(ctx,clan=raid_clan)

                et = time.time()
                bot.refresh_loop += 1
                self.clan_update_count += 1
                bot.clan_refresh_status = False

            except Exception as e:
                await bot.send_to_owners(f"Error encountered during Clan Data Refresh:\n\n```{e}```")
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

                ch = bot.get_channel(1033390608506695743)
                await ch.send(embed=data_embed)

            activity_types = [
                discord.ActivityType.playing,
                discord.ActivityType.streaming,
                discord.ActivityType.listening,
                discord.ActivityType.watching
                ]
            activity_select = random.choice(activity_types)

            #update active events after 1 hours
            if (self.last_status_update - st > 3600 or self.last_status_update == 0) and len(active_events) > 0:
                event = random.choice(active_events)
                await bot.change_presence(
                    activity=discord.Activity(
                        type=activity_select,
                        name=event))
                self.last_status_update = st

            #update passive events after 2 hours
            elif (self.last_status_update - st > 7200 or self.last_status_update == 0) and len(passive_events) > 0:
                event = random.choice(passive_events)
                await bot.change_presence(
                    activity=discord.Activity(
                    type=activity_select,
                    name=event))
                self.last_status_update = st

            elif self.last_status_update - st > 14400 or self.last_status_update == 0:
                await bot.change_presence(
                    activity=discord.Activity(
                    type=activity_select,
                    name=f"{mem_count} AriX members"))
                self.last_status_update = st

        except Exception as e:
            await bot.send_to_owners(f"Clan Data Refresh completed successfully, but an error was encountered while wrapping up.\n\n```{e}```")


    @tasks.loop(seconds=30.0)
    async def member_update(self):

        bot = self.master_bot
        ctx = EmptyContext(bot=bot)
        send_logs = False

        if bot.refresh_loop < 0:
            return None

        if not bot.master_refresh:
            return None

        if self.master_lock.locked():
            return None
        if self.member_lock.locked():
            return None

        async with self.member_lock:

            bot.member_refresh_status = True

            st = time.time()

            is_cwl = False
            if st >= ctx.bot.current_season.cwl_start and st <= ctx.bot.current_season.cwl_end:
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

                count_members = 0
                count_member_update = 0
                for (m_tag, member) in ctx.bot.member_cache.items():
                    try:
                        m = await aPlayer.create(ctx,tag=m_tag,refresh=True)
                    except Exception as e:
                        err = DataError(category='player',tag=m_tag,error=e)
                        error_log.append(err)
                        continue

                    if m.is_arix_account:
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

                    if m.discord_user:
                        try:
                            memo = await aMember.create(ctx,user_id=m.discord_user)
                        except Exception as e:
                            err = DataError(category='getme',tag=m.tag,error=e)
                            error_log.append(err)
                            continue

                        if memo:
                            if memo.discord_member and memo.user_id not in role_sync_completed:
                                try:
                                    await memo.sync_roles(ctx)
                                except Exception as e:
                                    err = DataError(category='mesync',tag=m.tag,error=e)
                                    error_log.append(err)
                                    continue
                                else:
                                    role_sync_completed.append(memo.user_id)

                    count_member_update += 1

                data_embed.add_field(
                    name=f"**Member Updates**",
                    value=f"Number of Tags: {len(list(ctx.bot.member_cache.keys()))}"
                        + f"\nAccounts Found: {count_members}"
                        + f"\nSuccessful Updates: {count_member_update}",
                    inline=False)

                et = time.time()
                bot.refresh_loop += 1
                self.member_update_count += 1
                bot.member_refresh_status = False

            except Exception as e:
                await bot.send_to_owners(f"Error encountered during Member Data Refresh:\n\n```{e}```")
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

                ch = bot.get_channel(1033390608506695743)
                await ch.send(embed=data_embed)

        except Exception as e:
            await bot.send_to_owners(f"Member Data Refresh completed successfully, but an error was encountered while wrapping up.\n\n```{e}```")
