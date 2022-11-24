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
import urllib

from coc.ext import discordlinks
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from tabulate import tabulate
from numerize import numerize

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select, paginate_embed
from aa_resourcecog.constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league, clan_castle_size, army_campsize, warResultDesc
from aa_resourcecog.notes import aNote
from aa_resourcecog.file_functions import get_current_season
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan, get_clan_members
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing

from aa_resourcecog.eclipse_functions import eclipse_main_menu, eclipse_base_vault, eclipse_army_analyzer, eclipse_army_analyzer_main, get_eclipse_bases, eclipse_personal_vault, eclipse_personal_bases
from aa_resourcecog.eclipse_classes import EclipseSession, eWarBase


async def userprofile_main(ctx,output,accounts):

    userprofile_session = False

    back_dict = {
        'id': 'main',
        'emoji': "<:backwards:1041976602420060240>",
        'title': ""
        }

    prev_dict = {
        'id': 'previous',
        'emoji': "<:to_previous:1041988094943035422>",
        'title': ""
        }

    next_dict = {
        'id': 'next',
        'emoji': "<:to_next:1041988114308137010>",
        'title': ""
        }

    warlog_dict = {
        'id': 'warlog',
        'emoji': "<:ClanWars:825753092230086708>",
        'title': ""
        }

    capitalraid_dict = {
        'id': 'raidlog',
        'emoji': "<:CapitalRaids:1034032234572816384>",
        'title': ""
        }

    trooplevels_dict = {
        'id': 'trooplevels',
        'emoji': "<:laboratory:1044904659917209651>",
        'title': ""
        }

    laboratory_dict = {
        'id': 'remainingupgrades',
        'emoji': "<:laboratory:1044904659917209651>",
        'title': ""
        }

    rushed_dict = {
        'id': 'rushedtroops',
        'emoji': "<:barracks:1042336340072738847>",
        'title': ""
        }

    response = 'start'
    message = None
    userprofile_session = True
    page_index = 0

    while userprofile_session:

        if page_index < 0:
            page_index = (len(output)-1)

        if page_index > (len(output)-1):
            page_index = 0

        nav_options = []

        if response in ['start','main']:
            if len(output) > 1:
                nav_options.append(prev_dict)

            if accounts[page_index].is_member:
                nav_options.append(warlog_dict)
                nav_options.append(capitalraid_dict)

            nav_options.append(trooplevels_dict)
            #nav_options.append(laboratory_dict)
            nav_options.append(rushed_dict)

            if len(output) > 1:
                nav_options.append(next_dict)

            if message:
                await message.edit(embed=output[page_index])
            else:
                message = await ctx.send(embed=output[page_index])

            await message.clear_reactions()
            selection = await multiple_choice_menu_select(ctx,message,nav_options,timeout=300)

            if selection:
                response = selection['id']

                if response == 'previous':
                    page_index -= 1
                    response = 'main'

                if response == 'next':
                    page_index += 1
                    response = 'main'

            else:
                userprofile_session = False


        if response == 'warlog':
            nav_options = []
            a = accounts[page_index]

            nav_str = ""
            nav_options.append(back_dict)
            nav_str += "<:backwards:1041976602420060240> Back to Accounts view\n"
            if a.is_member:
                nav_options.append(capitalraid_dict)
                nav_str += "<:CapitalRaids:1034032234572816384> To view AriX Raid Log\n"

            nav_options.append(trooplevels_dict)
            nav_str += "<:army_camp:1044905754471182409> To view current Troop Levels\n"
            #nav_options.append(laboratory_dict)
            #nav_str += "<:laboratory:1044904659917209651> To view remaining Lab Upgrades\n"
            nav_options.append(rushed_dict)
            nav_str += "<:barracks:1042336340072738847> To view Rushed Troops/Spells/Heroes\n"

            current_season = await get_current_season()

            # won = [w for wid,w in a.warlog.items() if w.result in ['won','winning']]
            # lost = [w for wid,w in a.warlog.items() if w.result in ['lost','losing']]
            # tied = [w for wid,w in a.warlog.items() if w.result in ['tied']]

            warlog_embed = await clash_embed(ctx,
                title=f"**War Log: {a.name} ({a.tag})**",
                message=f"**Stats for: {current_season} Season**"
                    + f"\n<:TotalWars:827845123596746773> {a.war_stats.wars_participated}\u3000"
                    + f"<:Triple:1034033279411687434> {a.war_stats.triples}\u3000"
                    + f"<:MissedHits:825755234412396575> {a.war_stats.missed_attacks}"
                    + f"\n<:Attack:828103854814003211>\u3000<:WarStars:825756777844178944> {a.war_stats.offense_stars}\u3000:fire: {a.war_stats.offense_destruction}%"
                    + f"\n<:Defense:828103708956819467>\u3000<:WarStars:825756777844178944> {a.war_stats.defense_stars}\u3000:fire: {a.war_stats.defense_destruction}%"
                    + f"\n\u200b")

            war_id_sort = [wid for wid,war in a.warlog.items()]
            war_id_sort.sort(reverse=True)

            for wid in war_id_sort:
                war = a.warlog[wid]

                attack_str = ""
                for att in war.attacks:
                    attack_str += f"<:Attack:828103854814003211>\u3000{emotes_townhall[att.attacker_townhall]} vs {emotes_townhall[att.defender_townhall]}\u3000<:WarStars:825756777844178944> {att.stars}\u3000:fire: {att.destruction}%\n"

                if war.best_opponent_attack.order:
                    attack_str += f"<:Defense:828103708956819467>\u3000{emotes_townhall[war.best_opponent_attack.attacker_townhall]} vs {emotes_townhall[war.best_opponent_attack.defender_townhall]}\u3000<:WarStars:825756777844178944> {war.best_opponent_attack.stars}\u3000:fire: {war.best_opponent_attack.destruction}%"

                attack_str += "\n\u200b"

                warlog_embed.add_field(
                    name=f"{war.clan.name} vs {war.opponent.name}",
                    value=f"{warResultDesc[war.result]}\u3000<:MissedHits:825755234412396575> {war.total_attacks - len(war.attacks)}"
                        + f"\n{attack_str}",
                    inline=False
                    )

            warlog_embed.add_field(
                name="Navigation",
                value=nav_str,
                inline=False)

            if message:
                await message.edit(embed=warlog_embed)
            else:
                message = await ctx.send(embed=warlog_embed)

            await message.clear_reactions()
            selection = await multiple_choice_menu_select(ctx,message,nav_options,timeout=300)

            if selection:
                response = selection['id']
            else:
                userprofile_session = False


        if response == 'raidlog':

            nav_options = []
            a = accounts[page_index]

            nav_str = ""
            nav_options.append(back_dict)
            nav_str += "<:backwards:1041976602420060240> Back to Accounts view\n"
            if a.is_member:
                nav_options.append(warlog_dict)
                nav_str += "<:ClanWars:825753092230086708> To view AriX War Log\n"

            nav_options.append(trooplevels_dict)
            nav_str += "<:army_camp:1044905754471182409> To view current Troop Levels\n"
            #nav_options.append(laboratory_dict)
            #nav_str += "<:laboratory:1044904659917209651> To view remaining Lab Upgrades\n"
            nav_options.append(rushed_dict)
            nav_str += "<:barracks:1042336340072738847> To view Rushed Troops/Spells/Heroes\n"

            current_season = await get_current_season()

            raidlog_embed = await clash_embed(ctx,
                title=f"**Raid Log: {a.name} ({a.tag})**",
                message=f"**Stats for: {current_season} Season**"
                    + f"\n<:CapitalRaids:1034032234572816384> {a.raid_stats.raids_participated}\u3000<:Attack:828103854814003211> {a.raid_stats.raid_attacks}\u3000<:MissedHits:825755234412396575> {(a.raid_stats.raids_participated * 6) - a.raid_stats.raid_attacks}"
                    + f"\n<:CapitalGoldLooted:1045200974094028821> {a.raid_stats.resources_looted:,}\u3000<:RaidMedals:983374303552753664> {a.raid_stats.medals_earned:,}"
                    + f"\n\u200b"
                    )

            raid_id_sort = [rid for rid,raid in a.raidlog.items()]
            raid_id_sort.sort(reverse=True)

            for rid in raid_id_sort:
                raid = a.raidlog[rid]

                raid_date = datetime.fromtimestamp(float(rid)).strftime('%d %b %Y')

                raidlog_embed.add_field(
                    name=f"Raid Weekend: {raid_date}",
                    value=f"<:Clan:825654825509322752> {raid.clan_name}\n<:Attack:828103854814003211> {raid.attack_count} / 6"
                        + f"\u3000<:CapitalGoldLooted:1045200974094028821> {raid.resources_looted:,}\u3000<:RaidMedals:983374303552753664> {raid.medals_earned:,}"
                        + f"\n\u200b",
                    inline=False
                    )

            raidlog_embed.add_field(
                name="Navigation",
                value=nav_str,
                inline=False)

            if message:
                await message.edit(embed=raidlog_embed)
            else:
                message = await ctx.send(embed=raidlog_embed)

            await message.clear_reactions()
            selection = await multiple_choice_menu_select(ctx,message,nav_options,timeout=300)

            if selection:
                response = selection['id']
            else:
                userprofile_session = False


        if response == 'trooplevels':

            nav_options = []
            a = accounts[page_index]

            nav_str = ""
            nav_options.append(back_dict)
            nav_str += "<:backwards:1041976602420060240> Back to Accounts view\n"
            if a.is_member:
                nav_options.append(warlog_dict)
                nav_str += "<:ClanWars:825753092230086708> To view AriX War Log\n"
                nav_options.append(capitalraid_dict)
                nav_str += "<:CapitalRaids:1034032234572816384> To view AriX Raid Log\n"

            #nav_options.append(laboratory_dict)
            #nav_str += "<:laboratory:1044904659917209651> To view remaining Lab Upgrades\n"
            nav_options.append(rushed_dict)
            nav_str += "<:barracks:1042336340072738847> To view Rushed Troops/Spells/Heroes\n"

            trooplevels_embed = await clash_embed(ctx,
                title=f"**Offense Levels: {a.name} ({a.tag})**",
                message=f"Hero & Troop Levels for: {emotes_townhall[a.town_hall.level]} TH {a.town_hall.level}"
                )

            elixir_troops = [t for t in a.troops if t.is_elixir_troop]
            darkelixir_troops = [t for t in a.troops if t.is_dark_troop]
            siege_machines = [t for t in a.troops if t.is_siege_machine]

            elixir_spells = [s for s in a.spells if s.is_elixir_spell]
            darkelixir_spells = [s for s in a.spells if s.is_dark_spell]

            if len(a.heroes) > 0:
                hero_str = ""
                for h in a.heroes:
                    hero_str += f"{emotes_army[h.name]} `{str(h.level) + ' / ' + str(h.maxlevel_for_townhall): ^8}\u3000"

                trooplevels_embed.add_field(
                    name=f"Heroes",
                    value=f"{hero_str}\n\u200b",
                    inline=False)

            if len(elixir_troops) > 0:
                elixir_troops_str = ""
                ct = 0
                for et in elixir_troops:
                    ct += 1
                    if ct % 2 == 0:
                        elixir_troops_str += "\u3000\u3000"
                    else:
                        elixir_troops_str += "\n"
                    elixir_troops_str += f"{emotes_army[et.name]} `{str(et.level) + ' / ' + str(et.maxlevel_for_townhall): ^8}`"

                trooplevels_embed.add_field(
                    name=f"Elixir Troops",
                    value=f"{elixir_troops_str}\n\u200b",
                    inline=False)

            if len(darkelixir_troops) > 0:
                darkelixir_troops_str = ""
                ct = 0
                for dt in darkelixir_troops:
                    ct += 1
                    if ct % 2 == 0:
                        darkelixir_troops_str += "\u3000\u3000"
                    else:
                        darkelixir_troops_str += "\n"
                    darkelixir_troops_str += f"{emotes_army[dt.name]} `{str(dt.level) + ' / ' + str(dt.maxlevel_for_townhall): ^8}`"

                trooplevels_embed.add_field(
                    name=f"Dark Elixir Troops",
                    value=f"{darkelixir_troops_str}\n\u200b",
                    inline=False)

            if len(siege_machines) > 0:
                siege_machines_str = ""
                ct = 0
                for sm in siege_machines:
                    ct += 1
                    if ct % 2 == 0:
                        siege_machines_str += "\u3000\u3000"
                    else:
                        siege_machines_str += "\n"
                    siege_machines_str += f"{emotes_army[sm.name]} `{str(sm.level) + ' / ' + str(sm.maxlevel_for_townhall): ^8}`"

                trooplevels_embed.add_field(
                    name=f"Siege Machines",
                    value=f"{siege_machines_str}\n\u200b",
                    inline=False)

            if len(elixir_spells) > 0:
                elixir_spells_str = ""
                ct = 0
                for es in elixir_spells:
                    ct += 1
                    if ct % 2 == 0:
                        elixir_spells_str += "\u3000\u3000"
                    else:
                        elixir_spells_str += "\n"
                    elixir_spells_str += f"{emotes_army[es.name]} `{str(es.level) + ' / ' + str(es.maxlevel_for_townhall): ^8}`"

                trooplevels_embed.add_field(
                    name=f"Elixir Spells",
                    value=f"{elixir_spells_str}\n\u200b",
                    inline=False)

            if len(darkelixir_spells) > 0:
                darkelixir_spells_str = ""
                ct = 0
                for ds in darkelixir_spells:
                    ct += 1
                    if ct % 2 == 0:
                        darkelixir_spells_str += "\u3000\u3000"
                    else:
                        darkelixir_spells_str += "\n"
                    darkelixir_spells_str += f"{emotes_army[ds.name]} `{str(ds.level) + ' / ' + str(ds.maxlevel_for_townhall): ^8}`"

                trooplevels_embed.add_field(
                    name=f"Dark Elixir Spells",
                    value=f"{darkelixir_spells_str}\n\u200b",
                    inline=False)

            trooplevels_embed.add_field(name="Navigation",value=nav_str,inline=False)

            if message:
                await message.edit(embed=trooplevels_embed)
            else:
                message = await ctx.send(embed=trooplevels_embed)

            await message.clear_reactions()
            selection = await multiple_choice_menu_select(ctx,message,nav_options,timeout=300)

            if selection:
                response = selection['id']
            else:
                userprofile_session = False




    if message:
        await message.clear_reactions()







