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

async def function_season_update(cog,ctx):
    if ctx.invoked_with in ['simulate']:
        send_logs = True
    else:
        send_logs = False
        if ctx.bot.refresh_loop < 0:
            return None

    season_update_last = await cog.config.season_update_last()
    season_update_runtime = await cog.config.season_update_runtime()

    st = time.time()
    update_season = False

    await cog.config.season_update_last.set(st)

    season_embed = discord.Embed(
        title="**Season Update**",
        color=0x0000)

    season_embed.set_footer(
        text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
        icon_url="https://i.imgur.com/TZF5r54.png")

    season = aClashSeason.get_current_season()

    if season.id != ctx.bot.current_season.id:
        update_season = True
        send_logs = True

        season_embed.add_field(
            name=f"__New Season Detected__",
            value=f"> Current Season: {ctx.bot.current_season.season_description}"
                + f"\n> New Season: {season.season_description}",
            inline=False)

    if update_season:
        log_str = ""
        for c_tag in list(ctx.bot.clan_cache):

            clan = ctx.bot.clan_cache[c_tag]
            if clan.is_alliance_clan:
                if clan.war_state == 'inWar':
                    update_season = False
                if clan.raid_weekend_state == 'ongoing':
                    update_season = False

                log_str += f"**{clan.name} ({clan.tag})**"
                log_str += f"\n> Clan War: {clan.war_state}"
                log_str += f"\n> Capital Raid: {clan.raid_weekend_state}"

                log_str += "\n\n"

        season_embed.add_field(
            name=f"__Clan Activities__",
            value=log_str,
            inline=False)

    if update_season:
        #lock processes
        await cog.master_lock.acquire()

        await cog.clan_lock.acquire()
        await cog.member_lock.acquire()
        await cog.war_lock.acquire()
        await cog.raid_lock.acquire()

        await save_war_cache(ctx)
        await save_raid_cache(ctx)
        await save_clan_cache(ctx)
        await save_member_cache(ctx)

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                new_path = ctx.bot.clash_dir_path+'/'+ctx.bot.current_season.id
                os.makedirs(new_path)

                with open(ctx.bot.clash_dir_path+'/seasons.json','r+') as file:
                    s_json = json.load(file)
                    s_json['tracked'].append(ctx.bot.current_season.id)
                    s_json['current'] = season.id
                    file.seek(0)
                    json.dump(s_json,file,indent=2)
                    file.truncate()

                shutil.copy2(ctx.bot.clash_dir_path+'/clans.json',new_path)
                shutil.copy2(ctx.bot.clash_dir_path+'/membership.json',new_path)
                shutil.copy2(ctx.bot.clash_dir_path+'/players.json',new_path)
                with open(ctx.bot.clash_dir_path+'/players.json','w+') as file:
                    json.dump({},file,indent=2)

        for c_tag in list(ctx.bot.clan_cache):
            try:
                c = await aClan.create(ctx,tag=c_tag,refresh=True,reset=True)
            except Exception as e:
                err = DataError(category='clan',tag=c_tag,error=e)
                error_log.append(err)
                continue

        for m_tag in list(ctx.bot.member_cache):
            try:
                m = await aPlayer.create(ctx,tag=m_tag,refresh=True,reset=True)
            except Exception as e:
                err = DataError(category='player',tag=m_tag,error=e)
                error_log.append(err)
                continue

        season_embed.add_field(
            name=f"**New Season Initialized: {season.id}**",
            value=f"__Files Saved__"
                + f"\n**{ctx.bot.current_season.id}/players.json**: {os.path.exists(ctx.bot.clash_dir_path+'/'+ctx.bot.current_season.id+'/players.json')}"
                + f"\n"
                + f"__Files Created__"
                + f"\n**players.json**: {os.path.exists(ctx.bot.clash_dir_path+'/players.json')}",
            inline=False)

        ctx.bot.current_season = season
        ctx.bot.tracked_seasons = [aClashSeason(ssn) for ssn in s_json['tracked']]

        cog.clan_lock.release()
        cog.member_lock.release()
        cog.war_lock.release()
        cog.raid_lock.release()

        cog.master_lock.release()

        et = time.time()
        processing_time = round(et-st,2)
        season_update_runtime.append(processing_time)

        if len(season_update_runtime) > 100:
            del season_update_runtime[0]

        await cog.config.season_update_runtime.set(season_update_runtime)

        try:
            await ctx.bot.update_channel.send(f"**The new season {ctx.bot.current_season.id} has started!**")
        except:
            pass

        activity_types = [
            discord.ActivityType.playing,
            discord.ActivityType.listening,
            discord.ActivityType.watching
            ]
        activity_select = random.choice(activity_types)

        await ctx.bot.change_presence(
            activity=discord.Activity(
            type=activity_select,
            name=f"start of the {new_season} Season! Clash on!"))
        cog.last_status_update = st

    if send_logs:
        ch = ctx.bot.get_channel(1033390608506695743)
        await ch.send(embed=season_embed)

    cog.season_update_count += 1


async def function_save_data(cog,ctx):
    if ctx.invoked_with not in ['simulate','nstop']:
        if ctx.bot.refresh_loop < 0:
            return None
        if not cog.master_refresh:
            return None

    await cog.master_lock.acquire()

    await cog.clan_lock.acquire()
    await cog.member_lock.acquire()
    await cog.war_lock.acquire()
    await cog.raid_lock.acquire()

    await save_war_cache(ctx)
    await save_raid_cache(ctx)
    await save_clan_cache(ctx)
    await save_member_cache(ctx)

    cog.clan_lock.release()
    cog.member_lock.release()
    cog.war_lock.release()
    cog.raid_lock.release()

    cog.master_lock.release()

    cog.last_data_save = time.time()


async def function_clan_update(cog,ctx):
    if ctx.invoked_with in ['simulate']:
        send_logs = True
    else:
        send_logs = False
        if ctx.bot.refresh_loop < 0:
            return None
        if not cog.master_refresh:
            return None

    if cog.clan_refresh_status:
        return None
    if cog.master_lock.locked():
        return None
    if cog.clan_lock.locked():
        return None

    async with cog.clan_lock:
        cog.clan_refresh_status = True

        st = time.time()

        data_embed = discord.Embed(
            title="Clan Update Report",
            color=0x0000)
        data_embed.set_footer(
            text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
            icon_url="https://i.imgur.com/TZF5r54.png")

        try:
            clan_update_last = await cog.config.clan_update_last()
            clan_update_runtime = await cog.config.clan_update_runtime()

            active_events = []
            passive_events = []

            error_log = []

            ## CLAN UPDATE
            clan_update = ''
            mem_count = 0
            for c_tag in list(ctx.bot.clan_cache):
                try:
                    c = await aClan.create(ctx,tag=c_tag,refresh=True)
                except Exception as e:
                    err = DataError(category='clan',tag=c_tag,error=e)
                    error_log.append(err)
                    continue

                if c.is_alliance_clan:
                    clan_update += f"__{c.name} {c.tag}__"

                    try:
                        c, war_change, war_update = await c.update_clan_war(ctx)
                    except Exception as e:
                        err = DataError(category='clwar',tag=c.tag,error=e)
                        error_log.append(err)
                    else:
                        if c.current_war:
                            clan_update += f"\n> - War: {c.current_war.state} (Type: {c.current_war.type})"
                            if war_update:
                                clan_update += war_update
                                send_logs = True

                            if c.current_war.type in ['classic','random']:
                                result_dict = {
                                    'winning':'winning',
                                    'tied':'tie',
                                    'losing':'losing',
                                    'won':'winning',
                                    'tie':'tie',
                                    'lost':'losing',
                                    '':'',
                                    }

                                if war_change:
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
                        c, raid_change, raid_update = await c.update_raid_weekend(ctx)
                    except Exception as e:
                        err = DataError(category='clraid',tag=c.tag,error=e)
                        error_log.append(err)
                    else:
                        if c.current_raid_weekend:
                            clan_update += f"\n> - Raid Weekend: {c.current_raid_weekend.state}"
                            if raid_update:
                                clan_update += raid_update
                                send_logs = True

                            if raid_change:
                                if c.current_raid_weekend.state == 'ongoing':
                                    active_events.append(f"Raid Weekend has started!")

                                if c.current_raid_weekend.state == 'ended':
                                    active_events.append(f"{(c.current_raid_weekend.offensive_reward * 6) + c.current_raid_weekend.defensive_reward:,} Raid Medals in {c.abbreviation}")

                            if c.current_raid_weekend.state == 'ongoing':
                                passive_events.append(f"Raid Weekend with {len(c.current_raid_weekend.members)} {c.abbreviation} members")

                    try:
                        await c.compute_arix_membership(ctx)
                    except Exception as e:
                        err = DataError(category='clmem',tag=c.tag,error=e)
                        error_log.append(err)

                    mem_count += c.arix_member_count

                    if st - c.last_save > 3600:
                        await c.save_to_json(ctx)

                clan_update += f"\n"

            if clan_update == '':
                clan_update = "No Updates"

            data_embed.add_field(
                name=f"**Clan Updates**",
                value=clan_update,
                inline=False)

            et = time.time()
            ctx.bot.refresh_loop += 1
            cog.clan_update_count += 1
            cog.clan_refresh_status = False

        except Exception as e:
            await ctx.bot.send_to_owners(f"Error encountered during Clan Data Refresh:\n\n```{e}```")
            cog.clan_refresh_status = False
            return
    try:
        processing_time = round(et-st,2)
        clan_update_runtime.append(processing_time)

        if len(clan_update_runtime) > 100:
            del clan_update_runtime[0]

        await cog.config.clan_update_last.set(st)
        await cog.config.clan_update_runtime.set(clan_update_runtime)

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

        if send_logs:
            ch = ctx.bot.get_channel(1033390608506695743)
            await ch.send(embed=data_embed)

        activity_types = {
            'playing': discord.ActivityType.playing,
            'listening': discord.ActivityType.listening,
            'watching': discord.ActivityType.watching
            }
        activity_select = random.choice(list(activity_types))

        #update active events after 1 hours
        if (st - cog.last_status_update > 3600 or cog.last_status_update == 0) and len(active_events) > 0:
            event = random.choice(active_events)

            ch = ctx.bot.get_channel(1033390608506695743)
            await ch.send(f"Changed status to {activity_select} {event}: <t:{int(time.time())}:f>.")

            await ctx.bot.change_presence(
                activity=discord.Activity(
                    type=activity_types[activity_select],
                    name=event))
            cog.last_status_update = st

        #update passive events after 2 hours
        elif (st - cog.last_status_update > 7200 or cog.last_status_update == 0) and len(passive_events) > 0:
            event = random.choice(passive_events)

            ch = ctx.bot.get_channel(1033390608506695743)
            await ch.send(f"Changed status to {activity_select} {event}: <t:{int(time.time())}:f>.")

            await ctx.bot.change_presence(
                activity=discord.Activity(
                type=activity_types[activity_select],
                name=event))
            cog.last_status_update = st

        elif st - cog.last_status_update > 14400 or cog.last_status_update == 0:
            ch = ctx.bot.get_channel(1033390608506695743)
            await ch.send(f"Changed status to {activity_select} {mem_count} AriX members: <t:{int(time.time())}:f>.")

            await ctx.bot.change_presence(
                activity=discord.Activity(
                type=activity_types[activity_select],
                name=f"{mem_count} AriX members"))
            cog.last_status_update = st

    except Exception as e:
        await ctx.bot.send_to_owners(f"Clan Data Refresh completed successfully, but an error was encountered while wrapping up.\n\n```{e}```")


async def function_member_update(cog,ctx):
    if ctx.invoked_with in ['simulate']:
        send_logs = True
    else:
        send_logs = False
        if ctx.bot.refresh_loop < 0:
            return None
        if not cog.master_refresh:
            return None

    if cog.member_refresh_status:
        return None
    if cog.master_lock.locked():
        return None
    if cog.member_lock.locked():
        return None

    role_sync = False
    warlog_sync = False
    raidlog_sync = False

    async with cog.member_lock:
        cog.member_refresh_status = True

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
            last_role_sync = await cog.config.last_role_sync()
            last_warlog_sync = await cog.config.last_warlog_sync()
            last_raidlog_sync = await cog.config.last_raidlog_sync()

            member_update_last = await cog.config.member_update_last()
            member_update_runtime = await cog.config.member_update_runtime()

            #sync roles every 10mins
            if last_role_sync == 0 or (st - last_role_sync > 600):
                role_sync = True

            #war & raid logs sync every 6 hours
            if last_warlog_sync == 0 or (st - last_warlog_sync > 21600):
                warlog_sync = True
            if last_raidlog_sync == 0 or (st - last_raidlog_sync > 21600):
                raidlog_sync = True

            role_sync_completed = []
            error_log = []

            count_members = 0
            count_member_update = 0

            member_tags = list(ctx.bot.member_cache)
            for m_tag in member_tags:
                try:
                    m = await aPlayer.create(ctx,tag=m_tag,refresh=True)
                except Exception as e:
                    err = DataError(category='player',tag=m_tag,error=e)
                    error_log.append(err)
                    continue

                if m.is_arix_account:
                    count_members += 1
                    try:
                        await m.update_stats(ctx)

                        if warlog_sync:
                            await m.update_warlog(ctx)

                        if raidlog_sync and datetime.fromtimestamp(st).isoweekday() in [5,6,7,1]:
                            await m.update_raid_weekend(ctx)

                    except Exception as e:
                        err = DataError(category='meupdt',tag=m.tag,error=e)
                        error_log.append(err)
                        continue

                    save_int = random.randint(1,10)
                    if save_int < 2:
                        await m.save_to_json(ctx)
                    elif (st - m.last_save) > 1800 and save_int < 5:
                        await m.save_to_json(ctx)
                    elif (st - m.last_save) > 3600 and save_int < 8:
                        await m.save_to_json(ctx)

                    if m.discord_user and role_sync:
                        try:
                            memo = await aMember.create(ctx,user_id=m.discord_user,refresh=True)
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
                value=f"Number of Tags: {len(member_tags)}"
                    + f"\nAccounts Found: {count_members}"
                    + f"\nSuccessful Updates: {count_member_update}",
                inline=False)

            et = time.time()
            ctx.bot.refresh_loop += 1
            cog.member_update_count += 1

            cog.member_refresh_status = False

        except Exception as e:
            await bot.send_to_owners(f"Error encountered during Member Data Refresh:\n\n```{e}```")
            cog.member_refresh_status = False
            return

    try:
        processing_time = round(et-st,2)
        member_update_runtime.append(processing_time)

        if len(member_update_runtime) > 100:
            del member_update_runtime[0]

        await cog.config.member_update_last.set(st)
        await cog.config.member_update_runtime.set(member_update_runtime)

        if role_sync:
            await cog.config.last_role_sync.set(st)

        if warlog_sync:
            await cog.config.last_warlog_sync.set(st)

        if raidlog_sync:
            await cog.config.last_raidlog_sync.set(st)

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

        if send_logs:
            ch = ctx.bot.get_channel(1033390608506695743)
            await ch.send(embed=data_embed)

    except Exception as e:
        await bot.send_to_owners(f"Member Data Refresh completed successfully, but an error was encountered while wrapping up.\n\n```{e}```")

def function_war_update_wrapper(cog,ctx):
    if ctx.invoked_with in ['simulate']:
        send_logs = True
    else:
        send_logs = False
        if ctx.bot.refresh_loop < 0:
            return None
        if not cog.master_refresh:
            return None

    if cog.war_refresh_status:
        return None
    if cog.master_lock.locked():
        return None
    if cog.war_lock.locked():
        return None

    loop = asyncio.new_event_loop()
    embed, error_log = loop.run_until_complete(function_war_update(cog,ctx))
    loop.close()

    return embed, error_log

async def function_war_update(cog,ctx):
    async with cog.war_lock:
        cog.war_refresh_status = True

        st = time.time()
        error_log = []
        war_count = 0

        war_update_last = await cog.config.war_update_last()
        war_update_runtime = await cog.config.war_update_runtime()

        for war_id in list(ctx.bot.war_cache):
            try:
                war = ctx.bot.war_cache[war_id]

                if war:
                    if st > war.end_time:
                        war.state = 'warEnded'
                        await war.save_to_json(ctx)

                    wtype = war.type
                    wtag = war.war_tag

                    if (st - war.end_time) < 3600:
                        war_clan = await aClan.create(ctx,tag=war.clan)
                        if wtype == 'cwl':
                            war = await aClanWar.get(ctx,clan=war_clan,war_tag=wtag)
                        else:
                            war = await aClanWar.get(ctx,clan=war_clan)

                        if war:
                            await war.save_to_json(ctx)
                            war_count += 1

            except Exception as e:
                err = DataError(category='warupdate',tag=war_id,error=e)
                error_log.append(err)
                continue

        et = time.time()

        ctx.bot.refresh_loop += 1
        cog.war_update_count += 1
        cog.war_refresh_status = False

        processing_time = round(et-st,2)
        war_update_runtime.append(processing_time)

        if len(war_update_runtime) > 100:
            del war_update_runtime[0]

        await cog.config.war_update_last.set(st)
        await cog.config.war_update_runtime.set(war_update_runtime)

        data_embed = discord.Embed(
            title="Clan War Update",
            description=f"{len(list(ctx.bot.war_cache))} Wars in database. *Checked {war_count} wars for updates.*",
            color=0x0000)

        data_embed.set_footer(
            text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
            icon_url="https://i.imgur.com/TZF5r54.png")

    return data_embed, error_log


async def function_raid_update(cog,ctx):
    if ctx.invoked_with in ['simulate']:
        send_logs = True
    else:
        send_logs = False
        if ctx.bot.refresh_loop < 0:
            return None
        if not cog.master_refresh:
            return None

    if cog.raid_refresh_status:
        return None
    if cog.master_lock.locked():
        return None
    if cog.raid_lock.locked():
        return None

    if datetime.fromtimestamp(time.time()).isoweekday() not in [5,6,7,1]:
        return None

    async with cog.raid_lock:
        cog.raid_refresh_status = True

        st = time.time()
        error_log = []
        raid_count = 0

        raid_update_last = await cog.config.raid_update_last()
        raid_update_runtime = await cog.config.raid_update_runtime()

        for raid_id in list(ctx.bot.raid_cache):
            try:
                raid = ctx.bot.raid_cache[raid_id]

                if raid:
                    if st > raid.end_time:
                        raid.state = 'ended'
                        await raid.save_to_json(ctx)

                    if (st - raid.end_time) < 3600:
                        raid_clan = await aClan.create(ctx,tag=raid.clan_tag)
                        raid = await aRaidWeekend.get(ctx,clan=raid_clan)

                        if raid:
                            await raid.save_to_json(ctx)
                            raid_count += 1

            except Exception as e:
                err = DataError(category='raidupdate',tag=war_id,error=e)
                error_log.append(err)
                continue

        et = time.time()

        ctx.bot.refresh_loop += 1
        cog.raid_update_count += 1
        cog.raid_refresh_status = False

        processing_time = round(et-st,2)
        raid_update_runtime.append(processing_time)

        if len(raid_update_runtime) > 100:
            del raid_update_runtime[0]

        await cog.config.raid_update_last.set(st)
        await cog.config.raid_update_runtime.set(raid_update_runtime)

        data_embed = discord.Embed(
            title="Raid Weekend Update",
            description=f"*Checked {raid_count} Capital Raids for updates.*",
            color=0x0000)

        data_embed.set_footer(
            text=f"AriX Alliance | {datetime.fromtimestamp(st).strftime('%d/%m/%Y %H:%M:%S')}+0000",
            icon_url="https://i.imgur.com/TZF5r54.png")

    if len(error_log) > 0:
        send_logs = True
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

    if send_logs:
        ch = ctx.bot.get_channel(1033390608506695743)
        await ch.send(embed=data_embed)
