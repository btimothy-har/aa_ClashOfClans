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
import math

from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from tabulate import tabulate

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select
from aa_resourcecog.constants import clanRanks, emotes_army, emotes_townhall, emotes_league, emotes_capitalhall, clanRanks
from aa_resourcecog.notes import aNote
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan, get_clan_members
from aa_resourcecog.player import aClashSeason, aPlayer, aClan, aMember
from aa_resourcecog.clan_war import aClanWar
from aa_resourcecog.raid_weekend import aRaidWeekend
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
            embed.set_author(name=f"{clan.name} ({clan.tag})",icon_url=clan.badge.url)
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

        try:
            await message.clear_reactions()
            selection = await multiple_choice_menu_select(ctx,message,nav_options,timeout=300)
        except:
            selection = None

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
    clan_members = clan.arix_members

    if len(clan_members) == 0:
        return None

    #Users & Accounts
    user_count = {}
    for m in clan_members:
        if m.discord_user not in list(user_count.keys()):
            user_count[m.discord_user] = []
        user_count[m.discord_user].append(m)

    leaders = []
    coleaders = []
    elders = []
    members = []

    for user, accounts in user_count.items():
        user_member = await aMember.create(ctx,user_id=user)

        if user_member.discord_member:
            user_display = user_member.discord_member.display_name
        else:
            user_display = "<< Unknown User >>"

        townhalls_only = []
        [townhalls_only.append(str(t)) for t in [a.town_hall.level for a in accounts] if t not in townhalls_only]

        townhalls_only.sort(reverse=True)

        output = {
            'User': f"{user_display}",
            '# Accs': f"{len(accounts)}",
            'Townhalls': f"{','.join(townhalls_only)}"
            }

        if user == clan.leader:
            leaders.append(output)

        elif user in clan.coleaders:
            coleaders.append(output)

        elif user in clan.elders:
            elders.append(output)

        else:
            members.append(output)

    users_accounts_embed = await clash_embed(ctx,
        title=f"{clan.emoji} User Summary Report",
        message=f"Total Members: {len(clan_members)}"
            + f"\nUnique Members: {len(list(user_count.keys()))}\n\u200b")

    def get_table(text_input):
        output_str = f"{'User':^15}{'':^2}{'# AC':^3}{'':^2}{'Townhalls':<10}"
        for i in text_input:
            user_len = i['User'][0:15]
            output_str += f"\n"
            output_str += f"{user_len:<15}{'':^2}"
            output_str += f"{i['# Accs']:>3}{'':^2}"
            output_str += f"{i['Townhalls']:<10}"

        return output_str

    leader_output = get_table(leaders)
    users_accounts_embed.add_field(
        name="**Leader(s)**",
        value=f"```{leader_output}```\n\u200b")

    coleader_output = get_table(coleaders)
    users_accounts_embed.add_field(
        name="**Co-Leader(s)**",
        value=f"```{coleader_output}```\n\u200b")

    elder_output = get_table(elders)
    users_accounts_embed.add_field(
        name="**Elder(s)**",
        value=f"```{elder_output}```\n\u200b")

    member_output = get_table(members)
    users_accounts_embed.add_field(
        name="**Member(s)**",
        value=f"```{member_output}```\n\u200b")

    output_pages.append(users_accounts_embed)


    #TH Composition
    all_townhall_levels = [a.town_hall.level for a in clan_members]
    average_townhall = sum(all_townhall_levels) / len(all_townhall_levels)

    individual_townhalls = []
    [individual_townhalls.append(t) for t in all_townhall_levels if t not in individual_townhalls]

    individual_townhalls.sort(reverse=True)

    composition_str = ""
    for th_level in individual_townhalls:
        composition_str += f"{emotes_townhall[th_level]} **{len([a for a in clan_members if a.town_hall.level==th_level])}** "
        composition_str += f"({int(round((len([a for a in clan_members if a.town_hall.level==th_level]) / len(clan_members))*100,0))}%)"

        if individual_townhalls.index(th_level) < (len(individual_townhalls)-1):
            composition_str += "\n\n"

    townhall_composition_embed = await clash_embed(ctx,
        title=f"{clan.emoji} Clan Composition",
        message=f"Total Members: {len(clan_members)}"
            + f"\nAverage: {emotes_townhall[int(average_townhall)]} {round(average_townhall,1)}"
            + f"\n\n{composition_str}")

    output_pages.append(townhall_composition_embed)

    #TH/Hero/Strength
    account_strength_output = []
    hero_strength_output = []
    for m in clan_members:
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

    base_strength_str = f"{'Player':^15}{'':^2}{'TH':^2}{'':^1}{'Troops':^6}{'':^1}{'Spells':^6}{'':^1}{'Heroes':^6}"
    for i in account_strength_output:
        base_strength_str += "\n"
        base_strength_str += f"{i['Name']:<15}{'':^2}"
        base_strength_str += f"{i['TH']:^2}{'':^1}"
        base_strength_str += f"{i['Troops']:^6}{'':^1}"
        base_strength_str += f"{i['Spells']:^6}{'':^1}"
        base_strength_str += f"{i['Heroes']:^6}"

    account_strength_embed = await clash_embed(ctx,
        title=f"{clan.emoji} Base Strength",
        message=f"```{base_strength_str}```")
    output_pages.append(account_strength_embed)

    hero_strength_str = f"{'Player':^15}{'':^2}{'TH':^2}{'':^1}{'BK':^2}{'':^1}{'AQ':^2}{'':^1}{'GW':^2}{'':^1}{'RC':^2}"
    for i in hero_strength_output:
        hero_strength_str += "\n"
        hero_strength_str += f"{i['Name']:<15}{'':^2}"
        hero_strength_str += f"{i['TH']:^2}{'':^1}"
        hero_strength_str += f"{i['BK']:^2}{'':^1}"
        hero_strength_str += f"{i['AQ']:^2}{'':^1}"
        hero_strength_str += f"{i['GW']:^2}{'':^1}"
        hero_strength_str += f"{i['RC']:^2}"

    hero_strength_embed = await clash_embed(ctx,
        title=f"{clan.emoji} Hero Strength",
        message=f"```{hero_strength_str}```")
    output_pages.append(hero_strength_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_super_troops(ctx,message,clan):
    page_num = 0
    output_pages = []
    super_troop_str = []

    members = clan.arix_members
    if not members:
        return None

    for super_troop in coc.SUPER_TROOP_ORDER:
        troop_title = f"\n\n{emotes_army[super_troop]} **{super_troop}**"
        troop_str = ""
        boost_count = 0
        for m in members:
            player_troop = m.get_troop(name=super_troop,is_home_troop=True)

            if player_troop:
                boost_count += 1
                troop_str += f"\n> {emotes_townhall[m.town_hall.level]} {m.name}"

                if m.clan.tag != clan.tag:
                    troop_str += f" (<:Clan:825654825509322752> {m.clan.name})"

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

    members = clan.arix_members
    if not members:
        return None

    members = sorted(members,key=lambda x:(x.town_hall.level,x.current_season.war_stats.triples,x.current_season.war_stats.offense_stars),reverse=True)

    #War Status
    opted_in_clan = [m for m in members if m.war_opted_in and m.clan.tag == clan.tag]
    opted_not_in_clan = [m for m in members if m.war_opted_in and m.clan.tag != clan.tag]

    war_opted_in = opted_in_clan + opted_not_in_clan

    chunked_war_opted_in = []
    for z in range(0, len(war_opted_in), 10):
        chunked_war_opted_in.append(war_opted_in[z:z+10])

    page = 0
    for chunk in chunked_war_opted_in:
        mem_str = ""

        for m in chunk:
            mem_str += f"\n\n**{emotes_townhall[m.town_hall.level]} {m.name}**"
            mem_str += f"\n> {m.hero_description}"
            mem_str += f"\n> <:TotalWars:827845123596746773> {m.current_season.war_stats.wars_participated}\u3000"
            mem_str += f"<:WarStars:825756777844178944> {m.current_season.war_stats.offense_stars}\u3000"
            mem_str += f"<:Triple:1034033279411687434> {m.current_season.war_stats.triples}\u3000"
            mem_str += f"<:MissedHits:825755234412396575> {m.current_season.war_stats.unused_attacks}"

            if m.clan.tag != clan.tag:
                mem_str += f"\n> <:Clan:825654825509322752> {m.clan.name}"

        war_status_embed = await clash_embed(ctx,
            title=f" {clan.emoji} War Opt-In Status",
            message=f"**Total Opted-In**"
                + f"\n*In Clan:* {len(opted_in_clan)}\u3000*Not In Clan:* {len(opted_not_in_clan)}"
                + f"{mem_str}")

        output_pages.append(war_status_embed)

    if len(output_pages) == 0:
        war_status_embed = await clash_embed(ctx,
            title=f" {clan.emoji} War Opt-In Status",
            message=f"**Total Opted-In**"
                + f"\n*In Clan:* {len(opted_in_clan)}\u3000*Not In Clan:* {len(opted_not_in_clan)}")
        output_pages.append(war_status_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_all_members(ctx,message,clan):
    output_pages = []

    members = clan.arix_members
    if not members:
        return None

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

    if len(output_pages) == 0:
        members_embed = await clash_embed(ctx,
            title=f"{clan.emoji} All Registered Members",
            message=f"Total: {len(members)} members")
        output_pages.append(members_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_missing_members(ctx,message,clan):
    output_pages = []

    members = clan.arix_members
    if not members:
        return None

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

            m_str += f"<:Clan:825654825509322752> {m.clan_description}"

            m_str += f"\n> [Open player in-game]({m.share_link})"

            members_not_in_clan_embed.add_field(
                name=f"{mem_count} {m.name} ({m.tag})",
                value=m_str,
                inline=False)

        output_pages.append(members_not_in_clan_embed)

    if len(output_pages) == 0:
        members_not_in_clan_embed = await clash_embed(ctx,
            title=f"{clan.emoji} Members Not in Clan",
            message=f"Total: {len(members_not_in_clan)} members")
        output_pages.append(members_not_in_clan_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response


async def report_unrecognized_members(ctx,message,clan):
    output_pages = []

    members = clan.arix_members
    if not members:
        return None

    unrecognized_members = [m for m in clan.members if m.tag not in [a.tag for a in members]]

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
            except Exception as e:
                await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for {m.tag}.",
                    err=e)
                return None

            m_str = f"> {m.desc_summary_text}"
            if m.discord_user:
                m_str += f"\n > "

            if m.discord_user:
                m_str += f"<:Discord:1040423151760314448> <@{m.discord_user}>\u3000"

            # m_str += f"<:Clan:825654825509322752> {m.clan_description}"

            m_str += f"\n> [Open player in-game]({m.share_link})"

            members_unrecognized_embed.add_field(
                name=f"{m.name} ({m.tag})",
                value=m_str,
                inline=False)

        output_pages.append(members_unrecognized_embed)

    if len(output_pages) == 0:
        members_unrecognized_embed = await clash_embed(ctx,
            title=f"{clan.emoji} Non-Member Accounts in Clan",
            message=f"Total: {len(unrecognized_members)} members")
        output_pages.append(members_unrecognized_embed)

    response = await report_paginate(ctx,message,clan,output_pages)
    return response

async def get_xp_report(ctx,season):
    alliance_clans = [tag for (tag,clan) in ctx.bot.clan_cache.items() if clan.is_alliance_clan]
    members = ctx.bot.member_cache
    season = season

    dt = f"{datetime.fromtimestamp(time.time()).strftime('%m%d%Y%H%M%S')}"
    report_file = f"{ctx.bot.clash_report_path}/{ctx.author.name}_EXPREPORT_{dt}.xlsx"

    rp_workbook = xlsxwriter.Workbook(report_file)
    bold = rp_workbook.add_format({'bold': True})

    sheet_name = f"{season.season_description}"
    xp_worksheet = rp_workbook.add_worksheet(sheet_name)

    xp_dict = {}

    xp_headers = ['ID',
        'Discord Name',
        'Nickname',
        '# Accounts',
        'Account Tags',
        'Total XP',
        'Total Donations',
        'Donation XP',
        'Clan Games Score',
        'Clan Games XP',
        ]

    row = 0
    col = 0
    for h in xp_headers:
        xp_worksheet.write(row,col,h,bold)
        col += 1

    for (t,m) in members.items():
        if not m.discord_user:
            continue

        try:
            season_stats = m.season_data[season.id]
        except KeyError:
            continue

        if m.discord_user not in list(xp_dict.keys()):
            xp_dict[m.discord_user] = []

        if season_stats.is_member:
            xp_dict[m.discord_user].append(season_stats)

    for (user,accounts) in xp_dict.items():
        total_donations = 0
        cg_score = 0

        donation_xp = 0
        cg_xp = 0

        for a in accounts:
            total_donations += a.donations_sent.season

            if a.clangames.clan_tag in alliance_clans and a.clangames.score > cg_score:
                cg_score = a.clangames.score

        if total_donations >= 1000:
            donation_xp = math.ceil(total_donations / 100) * 100

        if cg_score >= 1000:
            cg_xp = 1000

        if cg_score >= 4000:
            cg_xp = 4000

        arix_member = await aMember.create(ctx,user_id=int(user))

        col = 0
        row += 1

        m_data = []
        m_data.append(str(arix_member.user_id))

        if arix_member.discord_member:
            m_data.append(f"{arix_member.discord_member.name}#{arix_member.discord_member.discriminator}")
            m_data.append(f"{arix_member.discord_member.display_name}")
        else:
            m_data.append(None)

        m_data.append(len(accounts))
        m_data.append(', '.join([a.player.tag for a in accounts]))
        m_data.append(donation_xp + cg_xp)
        m_data.append(total_donations)
        m_data.append(donation_xp)
        m_data.append(cg_score)
        m_data.append(cg_xp)

        for d in m_data:
            xp_worksheet.write(row,col,d)
            col += 1

    rp_workbook.close()
    return report_file


async def report_to_excel(ctx,clan):
    members = ctx.bot.member_cache

    dt = f"{datetime.fromtimestamp(time.time()).strftime('%m%d%Y%H%M%S')}"
    report_file = f"{ctx.bot.clash_report_path}/{ctx.author.name}_{clan.abbreviation}_{dt}.xlsx"

    rp_workbook = xlsxwriter.Workbook(report_file)
    bold = rp_workbook.add_format({'bold': True})

    mem_worksheet = rp_workbook.add_worksheet('Members - Current')
    mem_headers = ['Tag',
        'Name',
        'Home Clan',
        'Townhall',
        'Days in Home Clan',
        'Other Clans',
        'Attack Wins',
        'Defense Wins',
        'Donations Sent',
        'Donations Received',
        'Gold Looted',
        'Elixir Looted',
        'Dark Elixir Looted',
        'Capital Contribution',
        'Clan Games Points',
        'Clan Games Timer',
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
        'Discord User',
        'Rank',
        'Exp',
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
        ]

    row = 0
    col = 0
    for h in xp_headers:
        mem_worksheet.write(row,col,h,bold)
        col += 1

    for m in [m for (t,m) in members.items() if m.home_clan.tag == clan.tag]:
        col = 0
        row += 1

        stats = m.current_season

        m_data = []

        m_data.append(m.tag)
        m_data.append(m.name)

        m_data.append(f"{stats.home_clan.name}")

        m_data.append(stats.town_hall)

        dd, hh, mm, ss = await convert_seconds_to_str(ctx,stats.time_in_home_clan)
        m_data.append(dd)

        ocl = ""
        for c in stats.other_clans:
            if c.tag:
                ocl += f"{c.name} ({c.tag}), "
        m_data.append(ocl)

        m_data.append(stats.attacks.season)
        m_data.append(stats.defenses.season)

        m_data.append(stats.donations_sent.season)
        m_data.append(stats.donations_rcvd.season)

        m_data.append(stats.loot_gold.season)
        m_data.append(stats.loot_elixir.season)
        m_data.append(stats.loot_darkelixir.season)
        m_data.append(stats.capitalcontribution.season)

        m_data.append(stats.clangames.score)
        m_data.append(max(stats.clangames.ending_time - stats.clangames.games_start,0))

        m_data.append(stats.war_stats.wars_participated)
        m_data.append(stats.war_stats.attack_count)
        m_data.append(stats.war_stats.unused_attacks)

        m_data.append(stats.war_stats.triples)
        m_data.append(stats.war_stats.offense_stars)
        m_data.append(stats.war_stats.offense_destruction)

        m_data.append(stats.war_stats.defense_stars)
        m_data.append(stats.war_stats.defense_destruction)

        m_data.append(stats.raid_stats.raids_participated)

        m_data.append(stats.raid_stats.raid_attacks)
        m_data.append(stats.raid_stats.resources_looted)
        m_data.append(stats.raid_stats.medals_earned)

        try:
            m_user = await aMember.create(ctx,user_id=m.discord_user)
            if m_user.discord_member:
                m_user_display = f"{m_user.discord_member.name}#{m_user.discord_member.discriminator}"
        except:
            m_user_display = str(m.discord_user)
        m_data.append(m_user_display)

        m_data.append(m.arix_rank)
        m_data.append(m.exp_level)
        m_data.append(f"{m.clan.name} ({m.clan.tag})")
        m_data.append(str(m.role))
        m_data.append(m.league.name)
        m_data.append(m.trophies)

        m_data.append(sum([h.level for h in m.heroes if h.name=='Barbarian King']))
        m_data.append(sum([h.level for h in m.heroes if h.name=='Archer Queen']))
        m_data.append(sum([h.level for h in m.heroes if h.name=='Grand Warden']))
        m_data.append(sum([h.level for h in m.heroes if h.name=='Royal Champion']))

        hero_completion = round((m.hero_strength/m.max_hero_strength)*100,1)
        m_data.append(f"{hero_completion}%")

        troop_completion = round((m.troop_strength/m.max_troop_strength)*100,1)
        m_data.append(m.troop_strength)
        m_data.append(f"{troop_completion}%")

        spell_completion = round((m.spell_strength/m.max_spell_strength)*100,1)
        m_data.append(m.spell_strength)
        m_data.append(f"{spell_completion}%")

        for d in m_data:
            mem_worksheet.write(row,col,d)
            col += 1

    for season in ctx.bot.tracked_seasons:
        sheet_name = f"Members - {season.season_description}"
        mem_worksheet = rp_workbook.add_worksheet(sheet_name)

        mem_headers = ['Tag',
            'Name',
            'Home Clan',
            'Townhall',
            'Days in Home Clan',
            'Other Clans',
            'Attack Wins',
            'Defense Wins',
            'Donations Sent',
            'Donations Received',
            'Gold Looted',
            'Elixir Looted',
            'Dark Elixir Looted',
            'Capital Contribution',
            'Clan Games Points',
            'Clan Games Timer',
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
            ]

        row = 0
        col = 0
        for h in mem_headers:
            mem_worksheet.write(row,col,h,bold)
            col += 1

        for m in [m for (t,m) in members.items()]:

            try:
                stats = m.season_data[season.id]
            except:
                continue

            if stats.home_clan.tag != clan.tag:
                continue

            col = 0
            row += 1

            m_data = []

            m_data.append(m.tag)
            m_data.append(m.name)

            m_data.append(f"{stats.home_clan.name}")

            m_data.append(stats.town_hall)

            dd, hh, mm, ss = await convert_seconds_to_str(ctx,stats.time_in_home_clan)
            m_data.append(dd)

            ocl = ""
            for c in stats.other_clans:
                if c.tag:
                    ocl += f"{c.name} ({c.tag})"
            m_data.append(ocl)

            m_data.append(stats.attacks.season)
            m_data.append(stats.defenses.season)

            m_data.append(stats.donations_sent.season)
            m_data.append(stats.donations_rcvd.season)

            m_data.append(stats.loot_gold.season)
            m_data.append(stats.loot_elixir.season)
            m_data.append(stats.loot_darkelixir.season)
            m_data.append(stats.capitalcontribution.season)

            m_data.append(stats.clangames.score)
            m_data.append(max(stats.clangames.ending_time - stats.clangames.games_start,0))

            m_data.append(stats.war_stats.wars_participated)
            m_data.append(stats.war_stats.attack_count)
            m_data.append(stats.war_stats.unused_attacks)

            m_data.append(stats.war_stats.triples)
            m_data.append(stats.war_stats.offense_stars)
            m_data.append(stats.war_stats.offense_destruction)

            m_data.append(stats.war_stats.defense_stars)
            m_data.append(stats.war_stats.defense_destruction)

            m_data.append(stats.raid_stats.raids_participated)

            m_data.append(stats.raid_stats.raid_attacks)
            m_data.append(stats.raid_stats.resources_looted)
            m_data.append(stats.raid_stats.medals_earned)

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
        'Member Defense Count',
        'Attack Order',
        'Attack Defender',
        'Attack Defender TH',
        'Attack Stars',
        'Attack Destruction',
        'Attack Duration',
        'Defense Order',
        'Defense Attacker',
        'Defense Attacker TH',
        'Defense Stars',
        'Defense Destruction',
        'Defense Duration',
        ]

    row = 0
    col = 0
    for h in war_headers:
        war_worksheet.write(row,col,h,bold)
        col += 1

    clan_wars_list = [war for (wid,war) in clan.war_log.items() if war]
    clan_wars_sorted = sorted(clan_wars_list,key=lambda x:x.end_time,reverse=True)
    for war in clan_wars_sorted:
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
                mwar_data.append(war.team_size)
                mwar_data.append(war.attacks_per_member)
                mwar_data.append(war.result)

                mwar_data.append(war.clan.stars)
                mwar_data.append(round(war.clan.destruction,2))
                mwar_data.append(int(war.clan.average_attack_duration))

                mwar_data.append(m.tag)
                mwar_data.append(m.name)
                mwar_data.append(m.town_hall)
                mwar_data.append(m.map_position)
                mwar_data.append(m.defense_count)
                try:
                    a = m.attacks[i]
                    mwar_data.append(a.order)
                    mwar_data.append(f"{a.defender_tag} {a.defender.name}")
                    mwar_data.append(a.defender.town_hall)
                    mwar_data.append(a.stars)
                    mwar_data.append(a.destruction)
                    mwar_data.append(a.duration)
                except:
                    mwar_data.append(None)
                    mwar_data.append(None)
                    mwar_data.append(None)
                    mwar_data.append(None)
                    mwar_data.append(None)
                    mwar_data.append(None)

                if i == 0:
                    try:
                        mwar_data.append(m.best_opponent_attack.order)
                        mwar_data.append(f"{m.best_opponent_attack.attacker_tag} {m.best_opponent_attack.attacker.name}")
                        mwar_data.append(m.best_opponent_attack.attacker.town_hall)
                        mwar_data.append(m.best_opponent_attack.stars)
                        mwar_data.append(m.best_opponent_attack.destruction)
                        mwar_data.append(m.best_opponent_attack.duration)
                    except:
                        mwar_data.append(None)
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

    raids_list = [raid for (rid,raid) in clan.raid_log.items() if raid]
    raids_sorted = sorted(raids_list,key=lambda x:x.end_time,reverse=True)
    for r in raids_sorted:
        for m in r.members:
            raid_data = []

            raid_data.append(r.clan_name)
            raid_data.append(r.clan_tag)
            raid_data.append(datetime.fromtimestamp(r.start_time).strftime('%b %d %Y'))
            raid_data.append(datetime.fromtimestamp(r.end_time).strftime('%b %d %Y'))
            raid_data.append(r.state)
            raid_data.append(r.total_loot)
            raid_data.append(r.offense_raids_completed)
            raid_data.append(r.defense_raids_completed)
            raid_data.append(r.attack_count)
            raid_data.append(r.destroyed_district_count)
            raid_data.append(r.offensive_reward)
            raid_data.append(r.defensive_reward)
            #m_data = raid_data
            raid_data.append(m.tag)
            raid_data.append(m.name)
            raid_data.append(m.attack_count)
            raid_data.append(m.capital_resources_looted)
            raid_data.append(m.medals_earned)

            col = 0
            row += 1
            for d in raid_data:
                raid_worksheet.write(row,col,d)
                col += 1

    rp_workbook.close()

    return report_file
