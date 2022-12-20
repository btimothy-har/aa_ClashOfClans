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
import pytz

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

class WarLord_Player():
    def __init__(self,ctx,player,th_level):
        self.player = player

        self.wars_participated = 0
        self.total_attacks = 0
        self.total_triples = 0
        self.total_stars = 0
        self.total_destruction = 0.0

        war_ids = [wid for wid,war in self.player.warlog.items()]

        for wid in war_ids:
            war = self.player.warlog[wid]
            try:
                wid = float(wid)
            except:
                continue

            if war.town_hall == th_level:
                self.wars_participated += 1

                for att in [at for at in war.attacks if at.attacker_townhall <= at.defender_townhall]:
                    self.total_attacks += 1
                    self.total_stars += att.stars
                    self.total_destruction += att.destruction

                    if att.is_triple:
                        self.total_triples += 1

        if self.total_attacks > 0:
            self.hit_rate = int(round((self.total_triples / self.total_attacks) * 100,0))
        else:
            self.hit_rate = 0

async def leaderboard_warlord(ctx):
    current_season = await get_current_season(params='readable')
    all_members = await get_clan_members(ctx)
    all_participants = [m for m in all_members if m.war_stats.wars_participated > 0]
    th_leaderboard = [15,14,13,12,11,10,9]

    warlord_leaderboard_embed = await clash_embed(ctx,
        title=f"**AriX Warlord Leaderboard: {current_season}**",
        message=f"The AriX Member with the most triples against higher or equal Townhalls during the AriX Season is rewarded with the **Warlord** title."
            + f"\n\n> - Only regular Clan Wars with our Arix Clans are counted (friendly & CWL wars excluded)."
            + f"\n> - Each AriX Season runs from the 10th to the last day of every month."
            + f"\n> - TH levels are taken from the specific War you participated in."
            + f"\n\nWarlords receive `10,000XP` per title, in addition to the TH Warlord role."
            + f"\n\n`{'':<21}`<:NoOfTriples:1034033279411687434>`{'':<2}`<:TotalAttacks:827845123596746773>`{'':<1}{'':<2}`<:HitRate:1054325756618088498>`{'':<2}`")

    for th in th_leaderboard:

        leaderboard_members = [wp for wp in [WarLord_Player(ctx,m,th) for m in all_participants] if wp.wars_participated > 0]
        leaderboard_sorted = sorted(leaderboard_members,key=lambda x:(x.total_triples,x.hit_rate),reverse=True)

        leaderboard_str = ""

        lb_rank = 0
        for m in leaderboard_sorted:
            lb_rank += 1
            if lb_rank > 5:
                break
            leaderboard_str += f"\n"
            leaderboard_str += f"{emotes_townhall[th]}{m.player.home_clan.emoji}"
            leaderboard_str += f"`{m.player.name:<15}"
            leaderboard_str += f"{m.total_triples:^5}"
            leaderboard_str += f"{m.total_attacks:^5}"
            leaderboard_str += f"{'':<1}{str(m.hit_rate)+'%':>5}{'':<2}`\u3000"

        warlord_leaderboard_embed.add_field(
            name=f"**TH{th}**",
            value=f"{leaderboard_str}\u200b",
            inline=False)

    return warlord_leaderboard_embed


async def leaderboard_heistlord(ctx):
    current_season = await get_current_season(params='readable')
    all_members = await get_clan_members(ctx)
    all_participants = [m for m in all_members if m.loot_darkelixir.season > 0]
    th_leaderboard = [15,14,13,12,11,10,9]

    heistlord_leaderboard_embed = await clash_embed(ctx,
        title=f"**AriX Heistlord Leaderboard: {current_season}**",
        message=f"The AriX Member with most Dark Elixir <:DarkElixir:825640568973033502> looted during the AriX Season is rewarded with the **Heistlord** title."
            + f"\n\n> - Only activity while you're in our AriX Clans are counted."
            + f"\n> - Each AriX Season runs from the 10th to the last day of every month."
            + f"\n> - TH levels are based on your current TH level."
            + f"\n\nHeistlords receive `10,000XP` per title, in addition to the TH Heistlord role.")

    for th in th_leaderboard:

        leaderboard_members = [hp for hp in all_participants if hp.town_hall.level==th]
        leaderboard_sorted = sorted(leaderboard_members,key=lambda x:(x.loot_darkelixir.season),reverse=True)

        leaderboard_str = ""

        lb_rank = 0
        for m in leaderboard_sorted:
            lb_rank += 1
            if lb_rank > 5:
                break

            value = f"{m.loot_darkelixir.season:,}"

            leaderboard_str += f"\n"
            leaderboard_str += f"{emotes_townhall[th]}{m.home_clan.emoji}"
            leaderboard_str += f"`{m.name:<15}"
            leaderboard_str += f"{value:>9}`<:DarkElixir:825640568973033502>"

        heistlord_leaderboard_embed.add_field(
            name=f"**TH{th}**",
            value=f"{leaderboard_str}\u200b",
            inline=False)

    return heistlord_leaderboard_embed

async def leaderboard_clangames(ctx):
    current_season = await get_current_season(params='readable')

    alliance_clans = await get_alliance_clan(ctx)
    all_members = await get_clan_members(ctx)

    cg_participants = [m for m in all_members if m.clangames.score > 0]

    clangames_leaderboard_embed = await clash_embed(ctx,
        title=f"**AriX Clan Games Leaderboard: {current_season}**",
        message=f"Win one of the following awards by participating in the Clan Games!"
            + f"\n\n**Speedrunner**"
            + f"\n> Be the first to finish Clan Games for your Clan."
            + f"\n> Reward(s): `9,000XP` for 1st, `8,000XP` for 2nd, `7,000XP` for 3rd."
            + f"\n\n**Going the extra mile!**"
            + f"\n> Achieve 4,000 Clan Games Points."
            + f"\n> Reward(s): `4,000XP`"
            + f"\n\n**Due Diligence**"
            + f"\n> Achieve 1,000 Clan Games Points."
            + f"\n> Reward(s): `1,000XP`\n\u200b")

    cg_start = datetime(datetime.now(pytz.utc).year, datetime.now(pytz.utc).month, 22, 8, 0, 0, 0, tzinfo=pytz.utc)

    if time.time() < cg_start.timestamp():
        clangames_leaderboard_embed.add_field(
            name=f"Leaderboard Unavailable",
            value=f"The Clan Games Leaderboard is only available once the games begin!"
                + f"\n\nThe next Clan Games will start on <t:{int(cg_start.timestamp())}:f>. Time shown in your local timezone.",
            inline=False)

        return clangames_leaderboard_embed

    for c in alliance_clans:
        leaderboard_participants = [m for m in cg_participants if m.clangames.clan.tag == c.tag]
        leaderboard_sorted = sorted(leaderboard_participants,key=lambda x:(x.clangames.score,(x.clangames.ending_time*-1)),reverse=True)

        leaderboard_str = f"`{'':<24}{'Score':^6}{'Time':^10}`"

        lb_rank = 0
        prev_ts = 0

        for m in leaderboard_sorted:

            if m.clangames.ending_time > 0:
                if m.clangames.ending_time != prev_ts:
                    lb_rank += 1
            else:
                lb_rank += 1

            prev_ts = m.clangames.ending_time

            if lb_rank > 5:
                break

            sc = f"{m.clangames.score:,}"
            ct = ""

            if m.clangames.score >= 4000:
                cd, ch, cm, cs = await convert_seconds_to_str(ctx,(m.clangames.ending_time-m.clangames.starting_time))
                if cd > 0:
                    ct += f"{int(cd)}d "
                if ch > 0:
                    ct += f"{int(ch)}h "
                if cm > 0:
                    ct += f"{int(cm)}m"

            leaderboard_str += f"\n"
            leaderboard_str += f"{emotes_townhall[m.town_hall.level]}"
            leaderboard_str += f"`{lb_rank:<3}{m.name:<18}"
            leaderboard_str += f"{sc:^6}"
            leaderboard_str += f"{ct:^10}`"

        clangames_leaderboard_embed.add_field(
            name=f"**{c.name}**",
            value=f"{leaderboard_str}\u200b",
            inline=False)

    return clangames_leaderboard_embed

async def leaderboard_donations(ctx):
    current_season = await get_current_season(params='readable')

    alliance_clans = await get_alliance_clan(ctx)
    all_members = await get_clan_members(ctx)

    donations_leaderboard_embed = await clash_embed(ctx,
        title=f"**AriX Donations Leaderboard: {current_season}**",
        message=f"**Donate troops, spells and sieges to your Clan mates!**"
            + f"\n> XP will be given only to the users that have 1,000+ donations across their accounts."
            + f"\n> **Reward(s):** The amount of XP awarded will be determined by the sum of the donations rounded up to the nearest multiple of 100 across every account owned by the user inside one of the AriX Clans."
            + f"\n\u200b")

    for c in alliance_clans:
        donation_participants = [m for m in all_members if m.home_clan.tag == c.tag]
        leaderboard_sorted = sorted(donation_participants,key=lambda x:(x.donations_sent.season),reverse=True)

        leaderboard_str = f"`{'':<21}{'Sent':>8}{'':^2}{'Rcvd':>8}{'':^2}`"

        lb_rank = 0

        for m in leaderboard_sorted:
            lb_rank += 1

            if lb_rank > 5:
                break

            sent = f"{m.donations_sent.season:,}"
            rcvd = f"{m.donations_rcvd.season:,}"

            leaderboard_str += f"\n"
            leaderboard_str += f"{emotes_townhall[m.town_hall.level]}"
            leaderboard_str += f"`{m.name:<18}"
            leaderboard_str += f"{sent:>8}{'':^2}"
            leaderboard_str += f"{rcvd:>8}{'':^2}`"

        donations_leaderboard_embed.add_field(
            name=f"**{c.name}**",
            value=f"{leaderboard_str}\u200b",
            inline=False)

    return donations_leaderboard_embed



