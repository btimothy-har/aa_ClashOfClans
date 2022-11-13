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
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_select
from aa_resourcecog.constants import confirmation_emotes, json_file_defaults, clanRanks
from aa_resourcecog.notes import aNote
from aa_resourcecog.file_functions import get_current_season, get_current_alliance, season_file_handler, alliance_file_handler, data_file_handler
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

    @commands.group(name="data",autohelp=False)
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
                name="__Summary__",
                value=f"> **File Path**: {ctx.bot.clash_dir_path}"
                    + f"\n> **Log Channel**: {log_channel}",
                inline=False)

            embed.add_field(
                name="__Data Files__",
                value=f"> **seasons.json**: {os.path.exists(ctx.bot.clash_dir_path+'/seasons.json')}"
                    + f"\n> **alliance.json**: {os.path.exists(ctx.bot.clash_dir_path+'/alliance.json')}"
                    + f"\n> **members.json**: {os.path.exists(ctx.bot.clash_dir_path+'/members.json')}"
                    + f"\n> **warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/warlog.json')}"
                    + f"\n> **capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/capitalraid.json')}",
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

        is_new_season = False
        detected_war_change = False
        detected_raid_change = False
        st = time.time()
        helsinkiTz = pytz.timezone("Europe/Helsinki")
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
        clans, members = await get_current_alliance(ctx)
        alliance_clans = []

        sEmbed = await clash_embed(ctx,
                title="Data Update Report",
                show_author=False)
        
        sEmbed.set_footer(text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",icon_url="https://i.imgur.com/TZF5r54.png")

        is_cwl = False
        if datetime.now(helsinkiTz).day <= 9:
            is_cwl = True

        #file lock for new season
        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                is_new_season, current_season, new_season = await season_file_handler(ctx,season)

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
            #lock separately for each clan
            async with ctx.bot.async_file_lock:
                with ctx.bot.clash_file_lock.write_lock():
                    war_member_count = 0
                    raid_member_count = 0

                    try:
                        c = await aClan.create(ctx,ctag)
                    except TerminateProcessing as e:
                        eEmbed = await clash_embed(ctx,message=e,color='fail')
                        eEmbed.set_footer(text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",icon_url="https://i.imgur.com/TZF5r54.png")
                        return await log_channel.send(eEmbed)
                    except Exception as e:
                        c = None
                        err_dict = {'tag':f'c{ctag}','reason':e}
                        err_log.append(err_dict)
                        continue

                    alliance_clans.append(c)
                    await c.update_member_count()
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

                    str_war_update += f"\n- Tracking stats for {war_member_count} members in War.\n"

            if c.raid_state_change:
                detected_raid_change = True

            if c.raid_state_change or c.current_raid_weekend.state == "ongoing":
                str_raid_update += f"__{c.tag} {c.name}__"

                if c.raid_state_change and c.current_raid_weekend.state == 'ongoing':
                    str_raid_update += f"\n**Raid Weekend has begun!**"
                    if c.announcement_channel:
                        channel = ctx.bot.alliance_server.get_channel(c.announcement_channel)
                        announcement_str = "Raid Weekend has begun!"
                        
                        if c.member_role:
                            role = ctx.bot.alliance_server.get_role(c.member_role)
                            announcement_str += f"\n\n{role.mention}"

                        rm = discord.AllowedMentions(roles=True)
                        await channel.send(content=announcement_str,allowed_mentions=rm)

                if c.current_raid_weekend.state == 'ended':
                    str_raid_update += f"\n**Raid Weekend is now over.**"

                    if c.announcement_channel:

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

                        test_embed.add_field(
                            name='**Raid Leaderboard**',
                            value=f"{box(tabulate(rank_table,headers='keys',tablefmt='pretty'))}",
                            inline=False)

                        channel = ctx.bot.alliance_server.get_channel(c.announcement_channel)
                        rm = discord.AllowedMentions(roles=True)

                        if c.member_role:
                            role = ctx.bot.alliance_server.get_role(c.member_role)
                            await channel.send(content=f"{role.mention}",embed=raid_end_embed,allowed_mentions=rm)
                        else:
                            await channel.send(embed=raid_end_embed)

                str_raid_update += f"\n- State: {c.current_raid_weekend.state}"

                for m in c.current_raid_weekend.members:
                    if m.tag in members:
                        raid_member_count += 1
                        dict_raid_update[m.tag] = m

                str_raid_update += f"\n- Tracking stats for {raid_member_count} members in Capital Raids.\n"

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

        for mtag in members:
            #lock separately for each member
            async with ctx.bot.async_file_lock:
                with ctx.bot.clash_file_lock.write_lock():
                    #try:
                    p = await aPlayer.create(ctx,mtag)
                    await p.retrieve_data()
                    #except TerminateProcessing as e:
                    #    eEmbed = await clash_embed(ctx,message=e,color='fail')
                    #    eEmbed.set_footer(text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",icon_url="https://i.imgur.com/TZF5r54.png")
                    #    return await log_channel.send(eEmbed)
                    #except Exception as e:
                    #    p = None
                    #    err_dict = {'tag':f'm{mtag}','reason':e}
                    #    err_log.append(err_dict)
                    #    continue

                    if is_new_season:
                        await p.set_baselines()

                    if is_cwl:
                        await p.set_baselines()
                        success_log.append(p)
                    else:
                        if p.is_member and p.clan.is_alliance_clan:
                            await p.update_stats()
                            success_log.append(p)
                        else:
                            await p.set_baselines()
                            success_log.append(p)

                    if p.tag in list(dict_war_update.keys()):
                        await p.update_war(dict_war_update[p.tag])

                    if p.tag in list(dict_raid_update.keys()):
                        await p.update_raidweekend(dict_raid_update[p.tag])

                    await p.save_to_json()

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

        role_count = 0
        for user, rank_info in role_sync.items():
            role_clan_tags = [c.tag for c in alliance_clans]
            discord_member = ctx.bot.alliance_server.get_member(int(user))

            if discord_member:
                role_change = False
                for clan_tag, rank_info in rank_info.items():
                    
                    if clan_tag in role_clan_tags:
                        role_clan_tags.remove(clan_tag)

                    member_role = ctx.bot.alliance_server.get_role(int(rank_info['clan'].member_role))
                    elder_role = ctx.bot.alliance_server.get_role(int(rank_info['clan'].elder_role))
                    coleader_role = ctx.bot.alliance_server.get_role(int(rank_info['clan'].coleader_role))

                    if rank_info['rank'] == 'Guest' or rank_info['rank'] == 'Non-Member':
                        try:
                            if member_role in discord_member.roles:
                                await discord_member.remove_roles(member_role)
                                role_change = True
                            if elder_role in discord_member.roles:
                                await discord_member.remove_roles(elder_role)
                                role_change = True
                            if coleader_role in discord_member.roles:
                                await discord_member.remove_roles(coleader_role)
                                role_change = True
                        except:
                            pass

                    if rank_info['rank'] == 'Member':
                        try:
                            if member_role not in discord_member.roles:
                                await discord_member.add_roles(member_role)
                                role_change = True
                            if elder_role in discord_member.roles:
                                await discord_member.remove_roles(elder_role)
                                role_change = True
                            if coleader_role in discord_member.roles:
                                await discord_member.remove_roles(coleader_role)
                                role_change = True
                        except:
                            pass
                        
                    if rank_info['rank'] == 'Elder':
                        try:
                            if member_role not in discord_member.roles:
                                await discord_member.add_roles(member_role)
                                role_change = True
                            if elder_role not in discord_member.roles:
                                await discord_member.add_roles(elder_role)
                                role_change = True
                            if coleader_role in discord_member.roles:
                                await discord_member.remove_roles(coleader_role)
                                role_change = True
                        except:
                            pass
                        
                    if rank_info['rank'] == 'Leader':
                        try:    
                            if member_role not in discord_member.roles:
                                await discord_member.add_roles(member_role)
                                role_change = True
                            if elder_role not in discord_member.roles:
                                await discord_member.add_roles(elder_role)
                                role_change = True
                            if coleader_role not in discord_member.roles:
                                await discord_member.add_roles(coleader_role)
                                role_change = True
                        except:
                            pass

                if len(role_clan_tags) > 0:
                    for c in [c for c in alliance_clans if c.tag in role_clan_tags]:
                        member_role = ctx.bot.alliance_server.get_role(int(c.member_role))
                        elder_role = ctx.bot.alliance_server.get_role(int(c.elder_role))
                        coleader_role = ctx.bot.alliance_server.get_role(int(c.coleader_role))

                        try:
                            if member_role in discord_member.roles:
                                await discord_member.remove_roles(member_role)
                                role_change = True
                            if elder_role in discord_member.roles:
                                await discord_member.remove_roles(elder_role)
                                role_change = True
                            if coleader_role in discord_member.roles:
                                await discord_member.remove_roles(coleader_role)
                                role_change = True
                        except:
                            pass

                if role_change:
                    role_count += 1

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