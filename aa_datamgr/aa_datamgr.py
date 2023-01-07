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
import copy
import matplotlib.pyplot as plt

from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from discord.ext import tasks
from datetime import datetime
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from tabulate import tabulate
from art import text2art

from .data_functions import function_season_update, function_save_data, function_clan_update, function_member_update, function_war_update, function_raid_update

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
            "last_role_sync":0,
            "season_update_last":0,
            "season_update_runtime":[],
            "clan_update_last":0,
            "clan_update_runtime":[],
            "member_update_last":0,
            "member_update_runtime":[],
            "war_update_last":0,
            "war_update_runtime":[],
            "raid_update_last":0,
            "raid_update_runtime":[]
            }
        default_guild = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

        self.placeholder_context = None

        self.master_lock = asyncio.Lock()
        self.clan_lock = asyncio.Lock()
        self.member_lock = asyncio.Lock()
        self.war_lock = asyncio.Lock()
        self.raid_lock = asyncio.Lock()

        self.master_refresh = False
        self.clan_refresh_status = False
        self.member_refresh_status = False
        self.war_refresh_status = False
        self.raid_refresh_status = False

        self.last_status_update = 0
        self.last_data_save = 0

        self.clan_update_count = 0
        self.member_update_count = 0
        self.war_update_count = 0
        self.raid_update_count = 0
        self.season_update_count = 0

    @commands.command(name="nstart")
    @commands.is_owner()
    async def start_nebula(self,ctx,partial=False):
        bot = self.master_bot
        msg = await ctx.send("**Initializing N.E.B.U.LA.** ...")

        self.placeholder_context = ctx

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

        ctx.bot.member_cache = {}
        ctx.bot.clan_cache = {}
        ctx.bot.pass_cache = {}
        ctx.bot.war_cache = {}
        ctx.bot.raid_cache = {}

        if not partial:
            with ctx.bot.clash_file_lock.read_lock():
                with open(ctx.bot.clash_dir_path+'/clans.json','r+') as file:
                    clan_json = json.load(file)

            with ctx.bot.clash_file_lock.read_lock():
                with open(ctx.bot.clash_dir_path+'/membership.json','r') as file:
                    membership_json = json.load(file)

            with ctx.bot.clash_file_lock.read_lock():
                with open(ctx.bot.clash_dir_path+'/players.json','r') as file:
                    player_json = json.load(file)

            for tag in list(clan_json):
                cjson = clan_json[tag]
                await aClan.create(ctx,tag=tag,json=cjson)

            for tag in list(membership_json):
                member = membership_json[tag]

                if tag in list(player_json):
                    a = await aPlayer.create(ctx,tag=tag,a_json=member,s_json=player_json[tag])
                else:
                    a = await aPlayer.create(ctx,tag=tag,a_json=member)

            ctx.bot.refresh_loop = 0

            self.season_update.start()
            self.clan_update.start()
            self.member_update.start()
            self.war_update.start()
            self.raid_update.start()

        await msg.delete()
        await ctx.send("**Setup complete.**")

    @commands.command(name="nstop")
    @commands.is_owner()
    async def stop_nebula(self,ctx):

        await ctx.send("**Stopping...**")

        await self.master_lock.acquire()
        await self.clan_lock.acquire()
        await self.member_lock.acquire()
        await self.war_lock.acquire()
        await self.raid_lock.acquire()

        self.master_refresh = False

        self.season_update.stop()
        self.clan_update.stop()
        self.member_update.stop()
        self.war_update.stop()
        self.raid_update.stop()

        #save data
        await save_war_cache(ctx)
        await save_raid_cache(ctx)
        await save_clan_cache(ctx)
        await save_member_cache(ctx)

        await ctx.send("**Data saved!**")

        self.master_bot.remove_cog('AriXMemberCommands')
        self.master_bot.remove_cog('AriXLeaderCommands')
        self.master_bot.remove_cog('AriXClashDataMgr')

        await ctx.bot.coc_client.close()
        await ctx.bot.discordlinks.close()

        self.clan_lock.release()
        self.member_lock.release()
        self.war_lock.release()
        self.raid_lock.release()

        self.master_lock.release()

        await ctx.send("**All done here! Goodbye!**")

    @commands.command(name="drefresh")
    @commands.is_owner()
    async def data_toggle(self,ctx):
        m = await ctx.send("Please wait...")

        if self.master_refresh:
            self.master_refresh = False
            await ctx.send("Bot Data Refresh is now stopped.")

        else:
            self.master_refresh = True
            await ctx.send("Bot Data Refresh is now activated.")

        await m.delete()

    @commands.group(name="data",aliases=["status"],autohelp=False)
    @commands.is_owner()
    async def data_control(self,ctx):
        """Manage the bot's Clash of Clans data."""
        if not ctx.invoked_subcommand:

            season_update_last = await self.config.season_update_last()
            clan_update_last = await self.config.clan_update_last()
            member_update_last = await self.config.member_update_last()
            war_update_last = await self.config.war_update_last()
            raid_update_last = await self.config.raid_update_last()
            last_role_sync = await self.config.last_role_sync()

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

            try:
                war_update_runtime = await self.config.war_update_runtime()
                war_update_average = round(sum(war_update_runtime)/len(war_update_runtime),2)
            except:
                war_update_average = 0

            try:
                raid_update_runtime = await self.config.raid_update_runtime()
                raid_update_average = round(sum(raid_update_runtime)/len(raid_update_runtime),2)
            except:
                raid_update_average = 0

            embed = await clash_embed(ctx=ctx,title="N.E.B.U.L.A. Status Report")
            embed.add_field(
                name="__Discord Configuration__",
                value=f"> **Alliance Server**: {getattr(ctx.bot.alliance_server,'name','Not Set')} `({getattr(ctx.bot.alliance_server,'id',0)})`"
                    + f"\n> **Leader Role**: {getattr(ctx.bot.leader_role,'name','Not Set')} `({getattr(ctx.bot.leader_role,'id',0)})`"
                    + f"\n> **Co-Leader Role**: {getattr(ctx.bot.coleader_role,'name','Not Set')} `({getattr(ctx.bot.coleader_role,'id',0)})`"
                    + f"\n> **Elder Role**: {getattr(ctx.bot.elder_role,'name','Not Set')} `({getattr(ctx.bot.elder_role,'id',0)})`"
                    + f"\n> **Member Role**: {getattr(ctx.bot.member_role,'name','Not Set')} `({getattr(ctx.bot.member_role,'id',0)})`"
                    + f"\n> \n> **Base Vault Access**: {getattr(ctx.bot.base_channel,'name','Not Set')} `({getattr(ctx.bot.base_channel,'id',0)})`"
                    + f"\n> **Bot Updates**: {getattr(ctx.bot.update_channel,'name','Not Set')} `({getattr(ctx.bot.update_channel,'id',0)})`",
                inline=False)

            embed.add_field(
                name=f"__Current Season: {ctx.bot.current_season.season_description}__",
                value=f"> **Started On**: <t:{int(ctx.bot.current_season.season_start)}:f>"
                    + f"\n> **CWL Start**: <t:{int(ctx.bot.current_season.cwl_start)}:f>"
                    + f"\n> **CWL End**: <t:{int(ctx.bot.current_season.cwl_end)}:f>"
                    + f"\n> **Clan Games Start**: <t:{int(ctx.bot.current_season.clangames_start)}:f>"
                    + f"\n> **Clan Games End**: <t:{int(ctx.bot.current_season.clangames_end)}:f>"
                    + f"\n> \n> **Other Seasons**: {', '.join([s.season_description for s in ctx.bot.tracked_seasons])}",
                inline=False)

            embed.add_field(
                name="__File Path Config__",
                value=f"\n> **File Path**: {ctx.bot.clash_dir_path}"
                    + f"\n> **Report Path**: {ctx.bot.clash_report_path}"
                    + f"\n> **Eclipse Path**: {ctx.bot.eclipse_path}",)

            embed.add_field(
                name="__Core Data Files__",
                value=f"\n> **clans.json**: {os.path.exists(ctx.bot.clash_dir_path+'/clans.json')}"
                    + f"\n> **membership.json**: {os.path.exists(ctx.bot.clash_dir_path+'/membership.json')}"
                    + f"\n> **players.json**: {os.path.exists(ctx.bot.clash_dir_path+'/players.json')}"
                    + f"\n> **warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/warlog.json')}"
                    + f"\n> **capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/capitalraid.json')}",
                    inline=False)

            embed.add_field(
                name="__Eclipse Data Files__",
                value=f"> **warbases.json**: {os.path.exists(ctx.bot.eclipse_path+'/warbases.json')}",
                    inline=False)

            embed.add_field(
                name="__Data Cache__",
                value=f"\n> **Players**: {len(ctx.bot.member_cache)}"
                    + f"\n> **Clans**: {len(ctx.bot.clan_cache)}"
                    + f"\n> **Clan Wars**: {len(ctx.bot.war_cache)}"
                    + f"\n> **Capital Raids**: {len(ctx.bot.raid_cache)}"
                    + f"\n> **Challenge Pass**: {len(ctx.bot.pass_cache)}",
                inline=False)

            embed.add_field(
                name="__Data Update Status__",
                value=f"> **Master Switch**: {self.master_refresh}"
                    + f"\n> **Clan Update**: {self.clan_refresh_status}"
                    + f"\n> **Member Update**: {self.member_refresh_status}"
                    + f"\n> **War Update**: {self.war_refresh_status}"
                    + f"\n> **Raid Update**: {self.raid_refresh_status}"
                    + f"\n> **Last Data Save**: <t:{int(self.last_data_save)}:R>",
                inline=False)

            embed.add_field(
                name="__Most Recent Updates__",
                value=f"> **Season Check**: <t:{int(season_update_last)}:R>"
                    + f"\n> **Clans**: <t:{int(clan_update_last)}:R>"
                    + f"\n> **Members**: <t:{int(member_update_last)}:R>"
                    + f"\n> **Clan Wars**: <t:{int(war_update_last)}:R>"
                    + f"\n> **Capital Raids**: <t:{int(raid_update_last)}:R>"
                    + f"\n> **Role Sync**: <t:{int(last_role_sync)}:R>"
                    + f"\n> **Bot Status**: <t:{int(self.last_status_update)}:R>",
                inline=False)

            embed.add_field(
                name="__Data Update Runtime__",
                value=f"> **Clan Updates**: {clan_update_average}"
                    + f"\n> **Member Updates**: {member_update_average}"
                    + f"\n> **War Updates**: {war_update_average}"
                    + f"\n> **Raid Updates**: {raid_update_average}",
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
    async def data_simulation(self,ctx,update_type):

        st = time.time()
        message = await ctx.send("Running...")

        if update_type not in ['clan','member','season','war','raid','save']:
            await ctx.send("Invalid data type.")

        if update_type == 'clan':
            await function_clan_update(cog=self,ctx=ctx)

        if update_type == 'member':
            await function_member_update(cog=self,ctx=ctx)

        if update_type == 'season':
            await function_season_update(cog=self,ctx=ctx)

        if update_type == 'war':
            await function_war_update(cog=self,ctx=ctx)

        if update_type == 'raid':
            await function_raid_update(cog=self,ctx=ctx)

        if update_type == 'save':
            await function_save_data(cog=self,ctx=ctx)

        await ctx.send("Done")
        await message.delete()


    @tasks.loop(minutes=30.0)
    async def season_update(self):
        await function_season_update(cog=self,ctx=self.placeholder_context)

    @tasks.loop(minutes=5.0)
    async def clan_update(self):
        await function_clan_update(cog=self,ctx=self.placeholder_context)

    @tasks.loop(minutes=1.0)
    async def member_update(self):
        await function_member_update(cog=self,ctx=self.placeholder_context)

    @tasks.loop(minutes=15.0)
    async def war_update(self):
        await function_war_update(cog=self,ctx=self.placeholder_context)

    @tasks.loop(minutes=15.0)
    async def raid_update(self):
        await function_raid_update(cog=self,ctx=self.placeholder_context)

    @tasks.loop(hours=6.0)
    async def save_data(self):
        await function_save_data(cog=self,ctx=self.placeholder_context)
