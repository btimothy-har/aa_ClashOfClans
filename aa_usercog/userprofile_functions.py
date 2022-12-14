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
from aa_resourcecog.constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league, clan_castle_size, army_campsize, warResultOngoing, warResultEnded, warResultDesc
from aa_resourcecog.notes import aNote
from aa_resourcecog.file_functions import get_current_season
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan, get_clan_members
from aa_resourcecog.player import aPlayer, aClan, aMember
from aa_resourcecog.clan_war import aClanWar
from aa_resourcecog.raid_weekend import aRaidWeekend
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing

from aa_resourcecog.eclipse_functions import eclipse_main_menu, eclipse_base_vault, eclipse_army_analyzer, eclipse_army_analyzer_main, get_eclipse_bases, eclipse_personal_vault, eclipse_personal_bases
from aa_resourcecog.eclipse_classes import EclipseSession, eWarBase

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
    'emoji': "????",
    'title': ""
    }

notes_dict = {
    'id': 'membernotes',
    'emoji': '????',
    'title': ""
    }

async def userprofile_warlog(ctx,account,message=None):
    nav_options = []
    a = account

    nav_str = ""
    nav_options.append(back_dict)
    nav_str += "<:backwards:1041976602420060240> Back to Accounts view\n"
    if a.is_member:
        nav_options.append(capitalraid_dict)
        nav_str += "<:CapitalRaids:1034032234572816384> To view AriX Raid Log\n"

    nav_options.append(trooplevels_dict)
    nav_str += "<:laboratory:1044904659917209651> To view current Troop Levels\n"
    #nav_options.append(laboratory_dict)
    #nav_str += "<:laboratory:1044904659917209651> To view remaining Lab Upgrades\n"
    nav_options.append(rushed_dict)
    nav_str += "???? To view Rushed Levels\n"

    current_season = ctx.bot.current_season

    warlog_embed = await clash_embed(ctx,
        title=f"**War Log: {a.name} ({a.tag})**",
        message=f"**Stats for: {current_season.season_description} Season**"
            + f"\n<:TotalWars:827845123596746773> `{a.current_season.war_stats.wars_participated:^3}`\u3000"
            + f"<:Triple:1034033279411687434> `{a.current_season.war_stats.triples:^3}`\u3000"
            + f"<:MissedHits:825755234412396575> `{a.current_season.war_stats.unused_attacks:^3}`"
            + f"\n<:Attack:828103854814003211>\u3000<:WarStars:825756777844178944> `{a.current_season.war_stats.offense_stars:<3}`\u3000:fire: `{a.current_season.war_stats.offense_destruction:>3}%`"
            + f"\n<:Defense:828103708956819467>\u3000<:WarStars:825756777844178944> `{a.current_season.war_stats.defense_stars:<3}`\u3000:fire: `{a.current_season.war_stats.defense_destruction:>3}%`"
            + f"\n\u200b")

    wars = [a.current_season.warlog[war_id] for war_id in list(a.current_season.warlog)]
    wars = sorted(wars,key=lambda x:(x.end_time),reverse=True)

    war_count = 0
    for war in [w for w in wars if w.start_time <= time.time()]:
        if war_count >= 5:
            break

        if war.result != '':
            attack_str = ""

            wm = [m for m in war.members if m.tag == a.tag][0]
            for att in wm.attacks:
                if wm.attacks.index(att) > 0:
                    attack_str += "\n"
                attack_str += f"<:Attack:828103854814003211>\u3000{emotes_townhall[att.attacker.town_hall]} vs {emotes_townhall[att.defender.town_hall]}\u3000<:WarStars:825756777844178944> `{att.stars:^3}`\u3000:fire: `{att.destruction:>3}%`"

            if len(wm.defenses) > 0:
                if len(wm.attacks) > 0:
                    attack_str += "\n"

                for defe in wm.defenses:
                    if wm.defenses.index(defe) > 0:
                        attack_str += "\n"
                    attack_str += f"<:Defense:828103708956819467>\u3000{emotes_townhall[defe.attacker.town_hall]} vs {emotes_townhall[defe.defender.town_hall]}\u3000<:WarStars:825756777844178944> `{defe.stars:^3}`\u3000:fire: `{defe.destruction:>3}%`"

            attack_str += "\n\u200b"

            if wm.is_opponent:
                war_clan = war.opponent
                war_opponent = war.clan
            else:
                war_clan = war.clan
                war_opponent = war.opponent

            war_emoji = ""
            if war.type == 'cwl':
                war_emoji = "<:ClanWarLeagues:825752759948279848> "

            elif war.type in ['classic','random']:
                c = await aClan.create(ctx,tag=war_clan.tag)
                if c.is_alliance_clan:
                    war_emoji = f"{c.emoji} "

            elif war.type in ['friendly']:
                war_emoji = ":handshake: "

            if war_clan.stars == war_opponent.stars:
                if war_clan.destruction > war_opponent.destruction:
                    wresult = 'won'
                elif war_clan.destruction < war_opponent.destruction:
                    wresult = 'lost'
                else:
                    wresult = 'tie'

            elif war_clan.stars > war_opponent.stars:
                wresult = 'won'
            elif war_clan.stars < war_opponent.stars:
                wresult = 'lost'
            else:
                wresult = 'tie'

            time_text = ""
            if time.time() < war.end_time:
                time_text = f"\n*Ends <t:{int(war.end_time)}:R> at <t:{int(war.end_time)}:f>.*"
                wresult = warResultOngoing[wresult]

            warlog_embed.add_field(
                name=f"{war_emoji}{war_clan.name} vs {war_opponent.name}",
                value=f"{warResultDesc[wresult]}\u3000<:Attack:828103854814003211> `{len(wm.attacks):^3}`\u3000<:MissedHits:825755234412396575> `{wm.unused_attacks:^3}`\u3000<:Defense:828103708956819467> `{len(wm.defenses):^3}`"
                    + f"{time_text}\n{attack_str}",
                inline=False
                )

            war_count += 1

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
        response = None
    return response


async def userprofile_raidlog(ctx,account,message=None):
    nav_options = []
    a = account

    nav_str = ""
    nav_options.append(back_dict)
    nav_str += "<:backwards:1041976602420060240> Back to Accounts view\n"
    if a.is_member:
        nav_options.append(warlog_dict)
        nav_str += "<:ClanWars:825753092230086708> To view AriX War Log\n"

    nav_options.append(trooplevels_dict)
    nav_str += "<:laboratory:1044904659917209651> To view current Troop Levels\n"
    #nav_options.append(laboratory_dict)
    #nav_str += "<:laboratory:1044904659917209651> To view remaining Lab Upgrades\n"
    nav_options.append(rushed_dict)
    nav_str += "???? To view Rushed Levels\n"

    current_season = ctx.bot.current_season

    raidlog_embed = await clash_embed(ctx,
        title=f"**Raid Log: {a.name} ({a.tag})**",
        message=f"**Stats for: {current_season.season_description} Season**"
            + f"\n<:CapitalRaids:1034032234572816384> {a.current_season.raid_stats.raids_participated}\u3000<:Attack:828103854814003211> {a.current_season.raid_stats.raid_attacks}\u3000<:MissedHits:825755234412396575> {(a.current_season.raid_stats.raids_participated * 6) - a.current_season.raid_stats.raid_attacks}"
            + f"\n<:CapitalGoldLooted:1045200974094028821> {a.current_season.raid_stats.resources_looted:,}\u3000<:RaidMedals:983374303552753664> {a.current_season.raid_stats.medals_earned:,}"
            + f"\n\u200b"
            )

    raids = [a.current_season.raidlog[raid_id] for raid_id in list(a.current_season.raidlog)]
    raids = sorted(raids,key=lambda x:(x.end_time),reverse=True)

    for raid in raids:
        raid_date = datetime.fromtimestamp(raid.end_time).strftime('%d %b %Y')

        raid_member = [m for m in raid.members if m.tag == a.tag][0]

        raidlog_embed.add_field(
            name=f"Raid Weekend: {raid_date}",
            value=f"<:Clan:825654825509322752> {raid.clan_name}\n<:Attack:828103854814003211> {raid_member.attack_count} / 6"
                + f"\u3000<:CapitalGoldLooted:1045200974094028821> {raid_member.capital_resources_looted:,}\u3000<:RaidMedals:983374303552753664> {raid_member.medals_earned:,}"
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
        response = None
    return response


async def userprofile_trooplevels(ctx,account,message=None):
    nav_options = []
    a = account

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
    nav_str += "???? To view Rushed Levels\n"

    trooplevels_embed = await clash_embed(ctx,
        title=f"**Offense Levels: {a.name} ({a.tag})**",
        message=f"Hero & Troop Levels for: {emotes_townhall[a.town_hall.level]} TH {a.town_hall.level}"
            + f"\n*`Italicized levels indicate rushed levels.`*"
        )

    elixir_troops = [t for t in a.troops if t.is_elixir_troop and not t.is_super_troop]
    darkelixir_troops = [t for t in a.troops if t.is_dark_troop and not t.is_super_troop]
    siege_machines = [t for t in a.troops if t.is_siege_machine and not t.is_super_troop]

    elixir_spells = [s for s in a.spells if s.is_elixir_spell]
    darkelixir_spells = [s for s in a.spells if s.is_dark_spell]

    if len(a.heroes) > 0:
        hero_str = ""
        ct = 0
        for h in a.heroes:
            if ct % 2 == 0:
                hero_str += "\n"
            else:
                hero_str += "  "

            if h.is_rushed:
                hero_str += f"*{emotes_army[h.name]} `{str(h.level) + ' / ' + str(h.maxlevel_for_townhall): ^7}`*"
            else:
                hero_str += f"{emotes_army[h.name]} `{str(h.level) + ' / ' + str(h.maxlevel_for_townhall): ^7}`"
            ct += 1

        trooplevels_embed.add_field(
            name=f"Heroes",
            value=f"{hero_str}\n\u200b",
            inline=False)

    if len(a.hero_pets) > 0:
        pets_str = ""
        ct = 0
        for p in a.hero_pets:
            if ct % 2 == 0:
                pets_str += "\n"
            else:
                pets_str += "  "
            if p.level < p.minlevel_for_townhall:
                pets_str += f"*{emotes_army[p.name]} `{str(p.level) + ' / ' + str(p.maxlevel_for_townhall): ^7}`*"
            else:
                pets_str += f"{emotes_army[p.name]} `{str(p.level) + ' / ' + str(p.maxlevel_for_townhall): ^7}`"
            ct += 1

        trooplevels_embed.add_field(
            name=f"Hero Pets",
            value=f"{pets_str}\n\u200b",
            inline=False)

    if len(elixir_troops) > 0:
        elixir_troops_str = ""
        ct = 0
        for et in elixir_troops:
            if ct % 3 == 0:
                elixir_troops_str += "\n"
            else:
                elixir_troops_str += "  "

            if et.is_rushed:
                elixir_troops_str += f"*{emotes_army[et.name]} `{str(et.level) + ' / ' + str(et.maxlevel_for_townhall): ^7}`*"
            else:
                elixir_troops_str += f"{emotes_army[et.name]} `{str(et.level) + ' / ' + str(et.maxlevel_for_townhall): ^7}`"
            ct += 1

        trooplevels_embed.add_field(
            name=f"Elixir Troops",
            value=f"{elixir_troops_str}\n\u200b",
            inline=False)

    if len(darkelixir_troops) > 0:
        darkelixir_troops_str = ""
        ct = 0
        for dt in darkelixir_troops:
            if ct % 3 == 0:
                darkelixir_troops_str += "\n"
            else:
                darkelixir_troops_str += "  "

            if dt.is_rushed:
                darkelixir_troops_str += f"*{emotes_army[dt.name]} `{str(dt.level) + ' / ' + str(dt.maxlevel_for_townhall): ^7}`*"
            else:
                darkelixir_troops_str += f"{emotes_army[dt.name]} `{str(dt.level) + ' / ' + str(dt.maxlevel_for_townhall): ^7}`"
            ct += 1

        trooplevels_embed.add_field(
            name=f"Dark Elixir Troops",
            value=f"{darkelixir_troops_str}\n\u200b",
            inline=False)

    if len(siege_machines) > 0:
        siege_machines_str = ""
        ct = 0
        for sm in siege_machines:
            if ct % 3 == 0:
                siege_machines_str += "\n"
            else:
                siege_machines_str += "  "

            if sm.is_rushed:
                siege_machines_str += f"*{emotes_army[sm.name]} `{str(sm.level) + ' / ' + str(sm.maxlevel_for_townhall): ^7}`*"
            else:
                siege_machines_str += f"{emotes_army[sm.name]} `{str(sm.level) + ' / ' + str(sm.maxlevel_for_townhall): ^7}`"
            ct += 1

        trooplevels_embed.add_field(
            name=f"Siege Machines",
            value=f"{siege_machines_str}\n\u200b",
            inline=False)

    if len(elixir_spells) > 0:
        elixir_spells_str = ""
        ct = 0
        for es in elixir_spells:
            if ct % 3 == 0:
                elixir_spells_str += "\n"
            else:
                elixir_spells_str += "  "

            if es.is_rushed:
                elixir_spells_str += f"*{emotes_army[es.name]} `{str(es.level) + ' / ' + str(es.maxlevel_for_townhall): ^7}`*"
            else:
                elixir_spells_str += f"{emotes_army[es.name]} `{str(es.level) + ' / ' + str(es.maxlevel_for_townhall): ^7}`"
            ct += 1

        trooplevels_embed.add_field(
            name=f"Elixir Spells",
            value=f"{elixir_spells_str}\n\u200b",
            inline=False)

    if len(darkelixir_spells) > 0:
        darkelixir_spells_str = ""
        ct = 0
        for ds in darkelixir_spells:
            if ct % 3 == 0:
                darkelixir_spells_str += "\n"
            else:
                darkelixir_spells_str += "  "

            if ds.is_rushed:
                darkelixir_spells_str += f"*{emotes_army[ds.name]} `{str(ds.level) + ' / ' + str(ds.maxlevel_for_townhall): ^7}`*"
            else:
                darkelixir_spells_str += f"{emotes_army[ds.name]} `{str(ds.level) + ' / ' + str(ds.maxlevel_for_townhall): ^7}`"
            ct += 1

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
        response = None
    return response


async def userprofile_rushed(ctx,account,message=None):
    nav_options = []
    a = account

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
    nav_options.append(trooplevels_dict)
    nav_str += "<:laboratory:1044904659917209651> To view current Troop Levels\n"

    rushed_embed = await clash_embed(ctx,
        title=f"**Rushed Troops: {a.name} ({a.tag})**",
        message=f"*All levels based on: {emotes_townhall[a.town_hall.level]} TH {a.town_hall.level}*"
            + f"\n\n**Rushed Percentage**"
            + f"\nTroops: {a.troop_rushed_pct}%"
            + f"\nSpells: {a.spell_rushed_pct}%"
            + f"\nHeroes: {a.hero_rushed_pct}%"
            + f"\n\nOverall: **{a.overall_rushed_pct}%**"
            + f"\n*Percentages exclude Pets.*")

    heroes = [h for h in a.heroes if h.is_rushed]
    pets = [p for p in a.hero_pets if p.level < p.minlevel_for_townhall]
    elixir_troops = [t for t in a.troops if t.is_elixir_troop and t.is_rushed and not t.is_super_troop]
    darkelixir_troops = [t for t in a.troops if t.is_dark_troop and t.is_rushed and not t.is_super_troop]
    siege_machines = [t for t in a.troops if t.is_siege_machine and t.is_rushed and not t.is_super_troop]

    elixir_spells = [s for s in a.spells if s.is_elixir_spell and s.is_rushed]
    darkelixir_spells = [s for s in a.spells if s.is_dark_spell and s.is_rushed]

    if len(heroes) > 0:
        hero_str = ""
        ct = 0
        for h in heroes:
            if ct % 2 == 0:
                hero_str += "\n"
            else:
                hero_str += "  "
            hero_str += f"{emotes_army[h.name]} `{str(h.level) + ' / ' + str(h.maxlevel_for_townhall): ^7}`"
            ct += 1

        rushed_embed.add_field(
            name=f"Heroes ({len(heroes)})",
            value=f"{hero_str}\n\u200b",
            inline=False)

    if len(pets) > 0:
        pets_str = ""
        ct = 0
        for p in pets:
            if ct % 2 == 0:
                pets_str += "\n"
            else:
                pets_str += " "
            pets_str += f"{emotes_army[p.name]} `{str(p.level) + ' / ' + str(p.maxlevel_for_townhall): ^7}`"
            ct += 1

        rushed_embed.add_field(
            name=f"Hero Pets ({len(pets)})",
            value=f"{pets_str}\n\u200b",
            inline=False)

    if len(elixir_troops) > 0:
        elixir_troops_str = ""
        ct = 0
        for et in elixir_troops:
            if ct % 3 == 0:
                elixir_troops_str += "\n"
            else:
                elixir_troops_str += "  "
            elixir_troops_str += f"{emotes_army[et.name]} `{str(et.level) + ' / ' + str(et.maxlevel_for_townhall): ^7}`"
            ct += 1

        rushed_embed.add_field(
            name=f"Elixir Troops ({len(elixir_troops)})",
            value=f"{elixir_troops_str}\n\u200b",
            inline=False)

    if len(darkelixir_troops) > 0:
        darkelixir_troops_str = ""
        ct = 0
        for dt in darkelixir_troops:
            if ct % 3 == 0:
                darkelixir_troops_str += "\n"
            else:
                darkelixir_troops_str += "  "
            darkelixir_troops_str += f"{emotes_army[dt.name]} `{str(dt.level) + ' / ' + str(dt.maxlevel_for_townhall): ^7}`"
            ct += 1

        rushed_embed.add_field(
            name=f"Dark Elixir Troops ({len(darkelixir_troops)})",
            value=f"{darkelixir_troops_str}\n\u200b",
            inline=False)

    if len(siege_machines) > 0:
        siege_machines_str = ""
        ct = 0
        for sm in siege_machines:
            if ct % 3 == 0:
                siege_machines_str += "\n"
            else:
                siege_machines_str += "  "
            siege_machines_str += f"{emotes_army[sm.name]} `{str(sm.level) + ' / ' + str(sm.maxlevel_for_townhall): ^7}`"
            ct += 1

        rushed_embed.add_field(
            name=f"Siege Machines ({len(siege_machines)})",
            value=f"{siege_machines_str}\n\u200b",
            inline=False)

    if len(elixir_spells) > 0:
        elixir_spells_str = ""
        ct = 0
        for es in elixir_spells:
            if ct % 3 == 0:
                elixir_spells_str += "\n"
            else:
                elixir_spells_str += "  "
            elixir_spells_str += f"{emotes_army[es.name]} `{str(es.level) + ' / ' + str(es.maxlevel_for_townhall): ^7}`"
            ct += 1

        rushed_embed.add_field(
            name=f"Elixir Spells ({len(elixir_spells)})",
            value=f"{elixir_spells_str}\n\u200b",
            inline=False)

    if len(darkelixir_spells) > 0:
        darkelixir_spells_str = ""
        ct = 0
        for ds in darkelixir_spells:
            if ct % 3 == 0:
                darkelixir_spells_str += "\n"
            else:
                darkelixir_spells_str += "  "
            darkelixir_spells_str += f"{emotes_army[ds.name]} `{str(ds.level) + ' / ' + str(ds.maxlevel_for_townhall): ^7}`"
            ct += 1

        rushed_embed.add_field(
            name=f"Dark Elixir Spells ({len(darkelixir_spells)})",
            value=f"{darkelixir_spells_str}\n\u200b",
            inline=False)

    rushed_embed.add_field(name="Navigation",value=nav_str,inline=False)

    if message:
        await message.edit(embed=rushed_embed)
    else:
        message = await ctx.send(embed=rushed_embed)

    await message.clear_reactions()
    selection = await multiple_choice_menu_select(ctx,message,nav_options,timeout=300)

    if selection:
        response = selection['id']
    else:
        response = None
    return response


async def userprofile_notes(ctx,account,message=None):

    a = account

    info_embed = await clash_embed(ctx,
        message="I've sent the Notes to your DMs.")

    notes_embed = await clash_embed(ctx,
        title=f"Notes for: {a.name} ({a.tag})",
        message=f"{a.desc_summary_text}")

    for n in a.notes[:9]:
        dt = f"{datetime.fromtimestamp(n.timestamp).strftime('%d %b %Y')}"
        notes_embed.add_field(
            name=f"__{n.author.name} @ {dt}__",
            value=f">>> {n.content}",
            inline=False)

    await ctx.send(embed=info_embed,delete_after=30)

    await ctx.author.send(embed=notes_embed)


async def userprofile_main(ctx,output,accounts):

    tries = 10

    userprofile_session = False

    response = 'start'
    message = None
    userprofile_session = True
    page_index = 0

    discord_member = ctx.bot.alliance_server.get_member(ctx.author.id)

    while userprofile_session:

        tries -= 1

        if page_index < 0:
            page_index = (len(output)-1)

        if page_index > (len(output)-1):
            page_index = 0

        nav_options = []

        if response in ['start','main']:
            tries = 10
            if len(output) > 1:
                nav_options.append(prev_dict)

            if accounts[page_index].is_member:
                nav_options.append(warlog_dict)
                nav_options.append(capitalraid_dict)

            nav_options.append(trooplevels_dict)
            #nav_options.append(laboratory_dict)
            nav_options.append(rushed_dict)

            if (ctx.bot.leader_role in discord_member.roles or ctx.bot.coleader_role in discord_member.roles) and len(accounts[page_index].notes)>0:
                nav_options.append(notes_dict)

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
            tries = 10
            a = accounts[page_index]
            response = await userprofile_warlog(ctx,a,message)

        if response == 'raidlog':
            tries = 10
            a = accounts[page_index]
            response = await userprofile_raidlog(ctx,a,message)

        if response == 'trooplevels':
            tries = 10
            a = accounts[page_index]
            response = await userprofile_trooplevels(ctx,a,message)

        if response == 'rushedtroops':
            tries = 10
            a = accounts[page_index]
            response = await userprofile_rushed(ctx,a,message)

        if response == 'membernotes':
            tries = 10
            a = accounts[page_index]
            await userprofile_notes(ctx,a,message)
            response = 'main'

        if tries == 0 or response == None:
            userprofile_session = False


    if message:
        try:
            await message.clear_reactions()
        except:
            pass







