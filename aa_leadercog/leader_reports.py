import os
import sys

import discord
import coc

import json
import asyncio
import random
import time
import re
import fasteners
import xlsxwriter

from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from tabulate import tabulate

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select
from aa_resourcecog.constants import clanRanks, emotes_army, emotes_townhall, emotes_league, emotes_capitalhall
from aa_resourcecog.notes import aNote
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan, get_clan_members
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing


async def report_paginate(ctx,message,clan,output):

    nav_options = []
    nav_str = ""
    paginate_state = True

    back_dict = {
        'id': 'menu',
        'emoji': "<:backwards:1041976602420060240>",
        'title': "",
        }
    prev_dict = {
        'id': 'previous',
        'emoji': '<:to_previous:1041988094943035422>'
        }
    next_dict = {
        'id': 'next',
        'emoji': '<:to_next:1041988114308137010>'
        }

    nav_options.append(back_dict)
    nav_str += f"<:backwards:1041976602420060240> Back to the Main Menu"

    if len(output) > 1:
        for embed in output:
            embed.set_author(name=f"{clan.name} ({clan.tag})",icon_url=clan.c.badge.url)
            embed.set_footer(text=f"(Page {output.index(embed)+1} of {len(output)}) AriX Alliance | Clash of Clans",icon_url="https://i.imgur.com/TZF5r54.png")
        nav_options.append(prev_dict)
        nav_options.append(next_dict)

        nav_str += f"<:to_previous:1041988094943035422> Previous page"
        nav_str += f"<:to_next:1041988114308137010> Next page"

    browse_index = 0

    while paginate_state:

        if browse_index < 0:
            browse_index = (len(output)-1)

        if browse_index > (len(output)-1):
            browse_index = 0

        if message:
            await message.edit(content=ctx.author.mention,embed=output[browse_index])
        else:
            message = await ctx.send(content=ctx.author.mention,embed=output[browse_index])

        await message.clear_reactions()
        selection = await multiple_choice_menu_select(ctx,message,nav_options,timeout=300)

        if selection:
            response = selection['id']

            if response == 'previous':
                browse_index -= 1

            if response == 'next':
                browse_index += 1

            if response == 'menu':
                paginate_state = False
        else:
            response = None
            paginate_state = False

    return response


async def report_member_summary(ctx,message,clan):
    output_pages = []

    members = await get_clan_members(ctx,clan)

    #Users & Accounts
    user_count = {}

    for m in members:
        if m.discord_user not in list(user_count.keys()):
            user_count[m.discord_user] = 0
        user_count[m.discord_user] += 1

    users_accounts_output = []
    for user, accounts in user_count.items():
        try:
            d_user = ctx.bot.get_user(int(user))
            d_user_display = d_user.display_name
        except:
            d_user_display = "<< Unknown User >>"

        user_accounts_townhalls = [a.town_hall.level for a in members if a.discord_user==user]

        townhalls_only = []
        [townhalls_only.append(str(t)) for t in user_accounts_townhalls if t not in townhalls_only]

        townhalls_only.sort(reverse=True)

        output = {
            'User': f"{d_user_display}",
            '# Accs': f"{accounts}",
            'Townhalls': f"{','.join(townhalls_only)}"
            }
        users_accounts_output.append(output)

    users_accounts_embed = await clash_embed(ctx,
        title=f"{clan.emoji} User Summary Report",
        message=f"Total Members: {len(members)}"
            + f"\nUnique Members: {len(list(user_count.keys()))}"
            + f"\n\n{box(tabulate(users_accounts_output,headers='keys',tablefmt='pretty'))}")

    output_pages.append(users_accounts_embed)


    #TH Composition
    all_townhall_levels = [a.town_hall.level for a in members]
    average_townhall = sum(all_townhall_levels) / len(all_townhall_levels)

    individual_townhalls = []
    [individual_townhalls.append(t) for t in all_townhall_levels if t not in individual_townhalls]

    individual_townhalls.sort(reverse=True)

    composition_str = ""
    for th_level in individual_townhalls:
        composition_str += f"{emotes_townhall[th_level]} **{len([a for a in members if a.town_hall.level==th_level])}** "
        composition_str += f"({int(round((len([a for a in members if a.town_hall.level==th_level]) / len(members))*100,0))}%)"

        if individual_townhalls.index(th_level) < (len(individual_townhalls)-1):
            composition_str += "\n\n"

    townhall_composition_embed = await clash_embed(ctx,
        title=f"{clan.emoji} Clan Composition",
        message=f"Total Members: {len(members)}"
            + f"\nAverage: {emotes_townhall[int(average_townhall)]} {round(average_townhall,1)}"
            + f"\n\n{composition_str}")

    output_pages.append(townhall_composition_embed)


    #TH/Hero/Strength
    account_strength_output = []
    hero_strength_output = []
    for m in members:
        bk = ""
        aq = ""
        gw = ""
        rc = ""

        troop_strength = str(int((m.troop_strength / m.max_troop_strength)*100)) + "%"
        spell_strength = ""

        if m.town_hall.level >= 6:
            spell_strength = str(int((m.spell_strength / m.max_spell_strength)*100)) + "%"

        if m.town_hall.level >= 7:
            hero_strength = str(int((m.hero_strength / m.max_hero_strength)*100)) + "%"
            bk = [h.level for h in m.heroes if h.name=='Barbarian King'][0]
        if m.town_hall.level >= 9:
            aq = [h.level for h in m.heroes if h.name=='Archer Queen'][0]
        if m.town_hall.level >= 11:
            gw = [h.level for h in m.heroes if h.name=='Grand Warden'][0]
        if m.town_hall.level >= 13:
            rc = [h.level for h in m.heroes if h.name=='Royal Champion'][0]

        account_output = {
            'Name': m.name,
            'TH':m.town_hall.level,
            'Troops': troop_strength,
            'Spells': spell_strength,
            'Heroes': hero_strength,
            }

        hero_output = {
            'Name': m.name,
            'TH': m.town_hall.level,
            'BK':bk,
            'AQ':aq,
            'GW':gw,
            'RC':rc
            }
        account_strength_output.append(account_output)
        hero_strength_output.append(hero_output)

    account_strength_embed = await clash_embed(ctx,
        title=f"{clan.emoji} Base Strength",
        message=f"{box(tabulate(account_strength_output,headers='keys',tablefmt='pretty'))}")
    output_pages.append(account_strength_embed)

    hero_strength_embed = await clash_embed(ctx,
        title=f"{clan.emoji} Hero Strength",
        message=f"{box(tabulate(hero_strength_output,headers='keys',tablefmt='pretty'))}")
    output_pages.append(hero_strength_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_super_troops(ctx,message,clan):

    page_num = 0
    output_pages = []
    super_troop_str = []

    members = await get_clan_members(ctx,clan)

    for super_troop in coc.SUPER_TROOP_ORDER:
        troop_title = f"\n\n{emotes_army[super_troop]} **{super_troop}**"
        troop_str = ""
        boost_count = 0
        for m in members:
            if super_troop in [t.name for t in m.p.troops]:
                t = [t for t in m.p.troops][0]

                boost_count += 1
                troop_str += f"\n> {emotes_townhall[m.town_hall.level]} {m.name}"

                if t.duration.days > 0:
                    troop_str += f"{t.cooldown.days}d"
                if t.duration.hours > 0:
                    troop_str += f"{t.cooldown.minutes}h"

                if m.clan.tag != clan.tag:
                    troop_str += f"(<:Clan:825654825509322752> {m.clan.name})"

        if boost_count > 0:
            try:
                if len(super_troop_str[page_num]) > 3000:
                    page_num += 1
                super_troop_str[page_num] += troop_title
                super_troop_str[page_num] += troop_str
            except IndexError:
                t_str = troop_title + troop_str
                super_troop_str.append(t_str)

    page = 0
    for i in super_troop_str:
        page += 1
        super_troop_boost_embed = await clash_embed(ctx,
            title=f"{clan.emoji} Boosted Super Troops",
            message=i)
        output_pages.append(super_troop_boost_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_war_status(ctx,message,clan):
    output_pages = []

    members = await get_clan_members(ctx,clan)

    #War Status
    opted_in_clan = [m for m in members if m.waroptin and m.clan.tag == clan.tag]
    opted_not_in_clan = [m for m in members if m.waroptin and m.clan.tag != clan.tag]

    war_opted_in = opted_in_clan + opted_not_in_clan

    chunked_war_opted_in = []
    for z in range(0, len(war_opted_in), 10):
        chunked_war_opted_in.append(war_opted_in[z:z+10])

    page = 0
    for chunk in chunked_war_opted_in:
        mem_str = ""

        for m in chunk:
            mem_str += f"\n\n{emotes_townhall[m.town_hall.level]} {m.name}"
            mem_str += f"\n{m.hero_description}"
            mem_str += f"\n<:TotalWars:827845123596746773> {m.war_stats.wars_participated}\u3000"
            mem_str += f"<:WarStars:825756777844178944> {m.war_stats.offense_stars}\u3000"
            mem_str += f"<:Triple:1034033279411687434> {m.war_stats.triples}\u3000"
            mem_str += f"<:MissedHits:825755234412396575> {m.war_stats.missed_attacks}"

        war_status_embed = await clash_embed(ctx,
            title=f" {clan.emoji} War Opt-In Status",
            message=f"**Total Opted-In**"
                + f"\n*In Clan:* {len(opted_in_clan)}\u3000Not In Clan: {len(opted_not_in_clan)}"
                + f"{mem_str}")

        output_pages.append(war_status_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_all_members(ctx,message,clan):
    output_pages = []

    members = await get_clan_members(ctx,clan)

    chunked_members = []
    for z in range(0, len(members), 10):
        chunked_members.append(members[z:z+10])

    page = 0
    mem_count = 0
    for chunk in chunked_members:
        page += 1

        members_embed = await clash_embed(ctx,
            title=f"{clan.emoji} All Registered Members",
            message=f"Total: {len(members)} members")

        for m in chunk:
            mem_count += 1

            m_str = f"> {m.desc_summary_text}"
            if m.discord_user or m.clan.name != m.home_clan.name:
                m_str += f"\n> "

            if m.discord_user:
                m_str += f"<:Discord:1040423151760314448> <@{m.discord_user}>\u3000"

            if m.clan.name != m.home_clan.name:
                m_str += f"<:Clan:825654825509322752> {m.clan_description}"

            m_str += f"\n> [Open player in-game]({m.share_link})"

            members_embed.add_field(
                name=f"{mem_count} {m.name} ({m.tag})",
                value=m_str,
                inline=False)

        output_pages.append(members_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_missing_members(self,ctx,clan):
    output_pages = []

    members = await get_clan_members(ctx,clan)

    members_not_in_clan = [m for m in members if m.clan.tag != m.home_clan.tag]

    chunked_not_in_clan = []
    for z in range(0, len(members_not_in_clan), 10):
        chunked_not_in_clan.append(members_not_in_clan[z:z+10])

    page = 0
    mem_count = 0
    for chunk in chunked_not_in_clan:
        page += 1
        members_not_in_clan_embed = await clash_embed(ctx,
            title=f"{clan.emoji} Members Not in Clan",
            message=f"Total: {len(members_not_in_clan)} members")

        for m in chunk:
            mem_count += 1

            m_str = f"> {m.desc_summary_text}"
            if m.discord_user or m.clan.name != m.home_clan.name:
                m_str += f"\n> "

            if m.discord_user:
                m_str += f"<:Discord:1040423151760314448> <@{m.discord_user}>\u3000"

            if m.clan.name != m.home_clan.name:
                m_str += f"<:Clan:825654825509322752> {m.clan_description}"

            m_str += f"\n> [Open player in-game]({m.share_link})"

            members_not_in_clan_embed.add_field(
                name=f"{mem_count} {m.name} ({m.tag})",
                value=m_str,
                inline=False)

        output_pages.append(members_not_in_clan_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_unrecognized_members(self,ctx,clan):
    output_pages = []

    members = await get_clan_members(ctx,clan)

    unrecognized_members = [m for m in clan.c.members if m.tag not in [a.tag for a in members]]

    chunked_unrecognized = []
    for z in range(0, len(unrecognized_members), 10):
        chunked_unrecognized.append(unrecognized_members[z:z+10])

    page = 0
    for chunk in chunked_unrecognized:
        page += 1
        members_unrecognized_embed = await clash_embed(ctx,
            title=f"{clan.emoji} Non-Member Accounts in Clan",
            message=f"Total: {len(unrecognized_members)} members")

        for m in chunk:
            try:
                m = await aPlayer.create(ctx,m.tag)
            except TerminateProcessing as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for {m.tag}.",
                    err=e)
            except Exception as e:
                p = None
                errD = {'tag':m.tag,'reason':e}
                error_log.append(errD)
                continue

            m_str = f"> {m.desc_summary_text}"
            if m.discord_user or m.clan.name != m.home_clan.name:
                m_str += f"\n > "

            if m.discord_user:
                m_str += f"<:Discord:1040423151760314448> <@{m.discord_user}>\u3000"
            elif m.discord_link:
                m_str += f"<:Discord:1040423151760314448> <@{m.discord_link}\u3000"

            if m.clan.name != m.home_clan.name:
                m_str += f"<:Clan:825654825509322752> {m.clan_description}"

            m_str += f"\n> [Open player in-game]({m.share_link})"

            members_unrecognized_embed.add_field(
                name=f"{m.name} ({m.tag})",
                value=m_str,
                inline=False)

        output_pages.append(members_unrecognized_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_to_excel(ctx,clan):

    members = await get_clan_members(ctx,clan)

    dt = f"{datetime.fromtimestamp(time.time()).strftime('%m%d%Y%H%M%S')}"
    report_file = f"{ctx.bot.clash_report_path}/{ctx.author.name}_{clan.abbreviation}_{dt}.xlsx"

    rp_workbook = xlsxwriter.Workbook(report_file)
    bold = rp_workbook.add_format({'bold': True})

    mem_worksheet = rp_workbook.add_worksheet('Members')
    mem_headers = ['Tag',
        'Name',
        'Discord User',
        'Home Clan',
        'Rank',
        'Days in Home Clan',
        'Exp',
        'Townhall',
        'TH Weapon',
        'Current Clan',
        'Role in Clan',
        'League',
        'Trophies',
        'Barbarian King',
        'Archer Queen',
        'Grand Warden',
        'Royal Champion',
        'Hero Completion',
        'Troop Levels',
        'Troop Completion',
        'Spell Levels',
        'Spell Completion',
        'Attack Wins',
        'Defense Wins',
        'Donations Sent',
        'Donations Received',
        'Gold Looted',
        'Elixir Looted',
        'Dark Elixir Looted',
        'Clan Games Points',
        'Wars Participated',
        'Total Attacks',
        'Missed Attacks',
        'Triples',
        'Offense Stars',
        'Offense Destruction',
        'Defense Stars',
        'Defense Destruction',
        'Raids Participated',
        'Raid Attacks',
        'Capital Gold Looted',
        'Raid Medals Earned',
        'Capital Contribution']

    row = 0
    col = 0
    for h in mem_headers:
        mem_worksheet.write(row,col,h,bold)
        col += 1

    for m in members:
        col = 0
        row += 1

        m_data = []

        m_data.append(m.tag)
        m_data.append(m.name)

        try:
            m_user = ctx.bot.get_user(int(m.discord_user))
            m_user_display = m_user.display_name
        except:
            m_user_display = str(m.discord_user)
        m_data.append(m_user_display)

        m_data.append(m.home_clan.name)
        m_data.append(m.arix_rank)

        dd, hh, mm, ss = await convert_seconds_to_str(ctx,m.time_in_home_clan)
        m_data.append(dd)

        m_data.append(m.exp_level)
        m_data.append(m.town_hall.level)
        m_data.append(m.town_hall.weapon)

        m_data.append(f"{m.clan.name} ({m.clan.tag})")

        m_data.append(m.role)

        m_data.append(m.league.name)

        m_data.append(m.trophies)

        m_data.append(sum([h.level for h in m.heroes if h.name=='Barbarian King']))
        m_data.append(sum([h.level for h in m.heroes if h.name=='Archer Queen']))
        m_data.append(sum([h.level for h in m.heroes if h.name=='Grand Warden']))
        m_data.append(sum([h.level for h in m.heroes if h.name=='Royal Champion']))

        hero_completion = round((m.hero_strength/m.max_hero_strength)*100,1)
        m_data.append(hero_completion)

        troop_completion = round((m.troop_strength/m.max_troop_strength)*100,1)
        m_data.append(m.troop_strength)
        m_data.append(troop_completion)

        spell_completion = round((m.spell_strength/m.max_spell_strength)*100,1)
        m_data.append(m.spell_strength)
        m_data.append(spell_completion)

        m_data.append(m.attack_wins.season)
        m_data.append(m.defense_wins.season)

        m_data.append(m.donations_sent.season)
        m_data.append(m.donations_rcvd.season)

        m_data.append(m.loot_gold.season)
        m_data.append(m.loot_elixir.season)
        m_data.append(m.loot_darkelixir.season)

        m_data.append(m.clangames.season)

        m_data.append(m.war_stats.wars_participated)
        m_data.append(m.war_stats.total_attacks)
        m_data.append(m.war_stats.missed_attacks)

        m_data.append(m.war_stats.triples)
        m_data.append(m.war_stats.offense_stars)

        m_data.append(m.war_stats.offense_destruction)

        m_data.append(m.war_stats.defense_stars)
        m_data.append(m.war_stats.defense_destruction)

        m_data.append(m.raid_stats.raids_participated)

        m_data.append(m.raid_stats.raid_attacks)
        m_data.append(m.raid_stats.resources_looted)
        m_data.append(m.raid_stats.medals_earned)
        m_data.append(m.capitalcontribution.season)

        for d in m_data:
            mem_worksheet.write(row,col,d)
            col += 1

    war_worksheet = rp_workbook.add_worksheet('Clan Wars')
    war_headers = [
        'Clan',
        'Clan Tag',
        'Opponent',
        'Opponent Tag',
        'War Type',
        'Start Time',
        'End Time',
        'State',
        'Size',
        'Attacks per Member',
        'Result',
        'Clan Stars',
        'Clan Destruction',
        'Average Attack Duration',
        'Member Tag',
        'Member Name',
        'Member Townhall',
        'Member Map Position',
        'Attack Order',
        'Attack Defender',
        'Attack Stars',
        'Attack Destruction',
        'Attack Duration',
        'Defense Order',
        'Defense Attacker',
        'Defense Stars',
        'Defense Destruction',
        'Defense Duration',
        ]

    row = 0
    col = 0
    for h in war_headers:
        war_worksheet.write(row,col,h,bold)
        col += 1

    wid_sorted = sorted([wid for wid in list(clan.war_log.keys())],reverse=True)
    for wid in wid_sorted:
        war = clan.war_log[wid]
        for m in war.clan.members:
            for i in range(0,war.attacks_per_member):

                mwar_data = []
                mwar_data.append(war.clan.name)
                mwar_data.append(war.clan.tag)
                mwar_data.append(war.opponent.name)
                mwar_data.append(war.opponent.tag)
                mwar_data.append(war.type)
                mwar_data.append(datetime.fromtimestamp(war.start_time).strftime('%b %d %Y %H:%M:%S'))
                mwar_data.append(datetime.fromtimestamp(war.end_time).strftime('%b %d %Y %H:%M:%S'))
                mwar_data.append(war.state)
                mwar_data.append(war.size)
                mwar_data.append(war.attacks_per_member)
                mwar_data.append(war.result)

                mwar_data.append(war.clan.stars)
                mwar_data.append(war.clan.destruction)
                mwar_data.append(war.clan.average_attack_duration)

                mwar_data.append(m.tag)
                mwar_data.append(m.name)
                mwar_data.append(m.town_hall)
                mwar_data.append(m.map_position)
                try:
                    a = m.attacks[i]
                    mwar_data.append(a.order)
                    mwar_data.append(a.defender)
                    mwar_data.append(a.stars)
                    mwar_data.append(a.destruction)
                    mwar_data.append(a.duration)
                except:
                    mwar_data.append(None)
                    mwar_data.append(None)
                    mwar_data.append(None)
                    mwar_data.append(None)
                    mwar_data.append(None)

                if i == 0:
                    try:
                        mwar_data.append(m.best_opponent_attack.order)
                        mwar_data.append(m.best_opponent_attack.attacker)
                        mwar_data.append(m.best_opponent_attack.stars)
                        mwar_data.append(m.best_opponent_attack.destruction)
                        mwar_data.append(m.best_opponent_attack.duration)
                    except:
                        mwar_data.append(None)
                        mwar_data.append(None)
                        mwar_data.append(None)
                        mwar_data.append(None)
                        mwar_data.append(None)

                col = 0
                row += 1
                for d in mwar_data:
                    war_worksheet.write(row,col,d)
                    col += 1

    raid_worksheet = rp_workbook.add_worksheet('Raid Weekends')
    raid_headers = [
        'Clan',
        'Clan Tag',
        'Start Date',
        'End Date',
        'State',
        'Total Loot Gained',
        'Offensive Raids Completed',
        'Defensive Raids Completed',
        'Raid Attack Count',
        'Districts Destroyed',
        'Offense Rewards',
        'Defense Rewards',
        'Participant Tag',
        'Participant Name',
        'Number of Attacks',
        'Capital Gold Looted',
        'Raid Medals'
        ]

    row = 0
    col = 0
    for h in raid_headers:
        raid_worksheet.write(row,col,h,bold)
        col += 1

    rid_sorted = sorted([rid for rid in list(clan.raid_log.keys())],reverse=True)
    for rid in rid_sorted:
        r = clan.raid_log[rid]
        for m in r.members:
            raid_data = []

            raid_data.append(r.clan.name)
            raid_data.append(r.clan.tag)
            raid_data.append(datetime.fromtimestamp(r.start_time).strftime('%b %d %Y'))
            raid_data.append(datetime.fromtimestamp(r.end_time).strftime('%b %d %Y'))
            raid_data.append(r.state)
            raid_data.append(r.total_loot)
            raid_data.append(r.offense_raids_completed)
            raid_data.append(r.defense_raids_completed)
            raid_data.append(r.raid_attack_count)
            raid_data.append(r.districts_destroyed)
            raid_data.append(r.offense_rewards)
            raid_data.append(r.defense_rewards)
            #m_data = raid_data
            raid_data.append(m.tag)
            raid_data.append(m.name)
            raid_data.append(m.attack_count)
            raid_data.append(m.resources_looted)
            raid_data.append(m.medals_earned)

            col = 0
            row += 1
            for d in raid_data:
                raid_worksheet.write(row,col,d)
                col += 1

    rp_workbook.close()

    return report_file
