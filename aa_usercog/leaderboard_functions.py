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
            self.hit_rate = round((self.total_triples / self.total_attacks) * 100,2)
        else:
            self.hit_rate = 0

async def leaderboard_warlord(ctx):
    current_season = await get_current_season()

    all_members = await get_clan_members(ctx)

    all_participants = [m for m in all_members if m.war_stats.wars_participated > 0]

    th_leaderboard = [9,10,11,12,13,14,15]

    warlord_leaderboard_embed = await clash_embed(ctx,
        title=f"AriX Warlord Leaderboard: {current_season}",
        message=f"The AriX Member with the most triples against higher or equal Townhalls during the AriX Season is annointed with the **Warlord** title."
            + f"\n\n> - Only regular Clan Wars are counted (friendly & CWL wars excluded)."
            + f"\n> - Warlords reset every month."
            + f"\n\nWarlords receive `10,000XP` per title, in addition to the TH Warlord role.")

    for th in th_leaderboard:

        leaderboard_members = [wp for wp in [WarLord_Player(ctx,m,th) for m in all_participants] if wp.wars_participated >= 0]
        leaderboard_sorted = sorted(leaderboard_members,key=lambda x:(x.total_triples,x.hit_rate),reverse=True)

        leaderboard_str = f"<:spacer:1054328465136037888> <:spacer:1054328465136037888>\u3000{'player':^15}\u3000<:NoOfTriples:1034033279411687434>\u3000<:TotalAttacks:827845123596746773>\u3000<:HitRate:1054325756618088498>"

        lb_rank = 0
        for m in leaderboard_sorted:
            lb_rank += 1
            leaderboard_str += f"\n{emotes_townhall[th]} {m.player.home_clan.emoji}\u3000{m.player.name}\u3000{m.total_triples}\u3000{m.total_attacks}\u3000{m.hit_rate}%"

        warlord_leaderboard_embed.add_field(
            name=f"TH{th} Warlords",
            value=f"{leaderboard_str}\n\u200b")

    return warlord_leaderboard_embed

async def leaderboard_heistlord(ctx):
    pass

async def leaderboard_clangames(ctx):
    pass


