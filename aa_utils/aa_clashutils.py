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
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, eclipse_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select, paginate_embed
from aa_resourcecog.constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league, clan_castle_size, army_campsize, badge_emotes, xp_rank_roles
from aa_resourcecog.notes import aNote
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan, get_clan_members
from aa_resourcecog.player import aClashSeason, aPlayer, aClan, aMember
from aa_resourcecog.clan_war import aClanWar
from aa_resourcecog.raid_weekend import aRaidWeekend
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing

class AriXClashUtils(commands.Cog):
    """Utility stuff for Clash of Clans"""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=395346260580,force_registration=True)
        default_global = {}
        default_guild = {}
        defaults_user = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**defaults_user)

        self.placeholder_context = None

    @commands.command(name="lstart",hidden=True)
    @commands.is_owner()
    async def start_listener(self,ctx):
        self.placeholder_context = ctx
        await ctx.send("Done!")

    @commands.Cog.listener()
    async def on_guild_channel_create(self,channel):

        ctx = self.placeholder_context

        tag_submission = None

        await asyncio.sleep(3)

        async for message in channel.history(limit=2,oldest_first=True):
            for embed in message.embeds:
                if embed.title == "Player Tags":
                    tag_submission = embed.description

        if tag_submission:
            valid_tags = []
            players = []

            for tag in re.split('[^a-zA-Z0-9]', tag_submission):
                tag = coc.utils.correct_tag(tag)

                if coc.utils.is_valid_tag(tag):
                    a = await aPlayer.create(ctx,tag=tag)
                    if a:

                        discord_msg = ""
                        if a.discord_user:
                            discord_msg += f"\n<:Discord:1040423151760314448> <@{a.discord_user}>"
                        if a.league.name == 'Unranked':
                            league_img = "https://i.imgur.com/TZF5r54.png"
                        else:
                            league_img = a.league.icon.medium

                        for achievement in a.achievements:
                            if achievement.name == 'Aggressive Capitalism':
                                capitalraided_value = achievement.value
                            if achievement.name == 'War League Legend':
                                warleague_value = achievement.value

                        offense_str = f"<:TotalTroopStrength:827730290491129856> {a.troop_strength} / {a.max_troop_strength} *(rushed: {a.troop_rushed_pct}%)*"
                        if a.town_hall.level >= 5:
                            offense_str += f"\n<:TotalSpellStrength:827730290294259793> {a.spell_strength} / {a.max_spell_strength} *(rushed: {a.spell_rushed_pct}%)*"
                        if a.town_hall.level >= 7:
                            offense_str += f"\n<:TotalHeroStrength:827730291149635596> {a.hero_strength} / {a.max_hero_strength} *(rushed: {a.hero_rushed_pct}%)*"

                        pEmbed = await clash_embed(
                            ctx=ctx,
                            title=f"**{a.name}** ({a.tag})",
                            message=f"<:Exp:825654249475932170>{a.exp_level}\u3000<:Clan:825654825509322752> {a.clan_description}"
                                + f"{discord_msg}"
                                + f"\n\n{a.town_hall.emote} {a.town_hall.description}\u3000{emotes_league[a.league.name]} {a.trophies} (best: {a.best_trophies})"
                                + f"\n<:WarStars:825756777844178944> {a.war_stars:,}\u3000<:ClanWarLeagues:825752759948279848> {warleague_value:,}\u3000<:CapitalRaids:1034032234572816384> {numerize.numerize(capitalraided_value,1)}"
                                + f"\n\n{offense_str}"
                                + f"\n\nAn asterisk (*) below indicates rushed levels.",
                            url=f"{a.share_link}",
                            thumbnail=league_img,
                            show_author=False)

                        elixir_troops = [t for t in a.troops if t.is_elixir_troop and not t.is_super_troop]
                        darkelixir_troops = [t for t in a.troops if t.is_dark_troop and not t.is_super_troop]
                        siege_machines = [t for t in a.troops if t.is_siege_machine and not t.is_super_troop]

                        elixir_spells = [s for s in a.spells if s.is_elixir_spell]
                        darkelixir_spells = [s for s in a.spells if s.is_dark_spell]

                        if len(a.heroes) > 0:
                            hero_str = ""
                            ct = 0
                            rushed_ct = 0
                            for h in a.heroes:
                                if ct % 2 == 0:
                                    hero_str += "\n"
                                else:
                                    hero_str += "  "
                                if h.is_rushed:
                                    hero_str += f"{emotes_army[h.name]} `{str(h.level) + '*/ ' + str(h.maxlevel_for_townhall): ^7}`"
                                    rushed_ct += 1
                                else:
                                    hero_str += f"{emotes_army[h.name]} `{str(h.level) + ' / ' + str(h.maxlevel_for_townhall): ^7}`"
                                ct += 1
                            pEmbed.add_field(name=f"Heroes (rushed: {rushed_ct} / {ct})",value=f"{hero_str}\n\u200b",inline=False)

                        if len(a.hero_pets) > 0:
                            pets_str = ""
                            ct = 0
                            rushed_ct = 0
                            for p in a.hero_pets:
                                if ct % 2 == 0:
                                    pets_str += "\n"
                                else:
                                    pets_str += "  "
                                if p.level < p.minlevel_for_townhall:
                                    pets_str += f"{emotes_army[p.name]} `{str(p.level) + '*/ ' + str(p.maxlevel_for_townhall): ^7}`"
                                    rushed_ct += 1
                                else:
                                    pets_str += f"{emotes_army[p.name]} `{str(p.level) + ' / ' + str(p.maxlevel_for_townhall): ^7}`"
                                ct += 1
                            pEmbed.add_field(name=f"Hero Pets (rushed: {rushed_ct} / {ct})",value=f"{pets_str}\n\u200b",inline=False)

                        if len(elixir_troops) > 0:
                            elixir_troops_str = ""
                            ct = 0
                            rushed_ct = 0
                            for et in elixir_troops:
                                if ct % 3 == 0:
                                    elixir_troops_str += "\n"
                                else:
                                    elixir_troops_str += "  "
                                if et.is_rushed:
                                    elixir_troops_str += f"{emotes_army[et.name]} `{str(et.level) + '*/ ' + str(et.maxlevel_for_townhall): ^7}`"
                                    rushed_ct += 1
                                else:
                                    elixir_troops_str += f"{emotes_army[et.name]} `{str(et.level) + ' / ' + str(et.maxlevel_for_townhall): ^7}`"
                                ct += 1
                            pEmbed.add_field(name=f"Elixir Troops (rushed: {rushed_ct} / {ct})",value=f"{elixir_troops_str}\n\u200b",inline=False)

                        if len(darkelixir_troops) > 0:
                            darkelixir_troops_str = ""
                            ct = 0
                            rushed_ct = 0
                            for dt in darkelixir_troops:
                                if ct % 3 == 0:
                                    darkelixir_troops_str += "\n"
                                else:
                                    darkelixir_troops_str += "  "
                                if dt.is_rushed:
                                    darkelixir_troops_str += f"{emotes_army[dt.name]} `{str(dt.level) + '*/ ' + str(dt.maxlevel_for_townhall): ^7}`"
                                    rushed_ct += 1
                                else:
                                    darkelixir_troops_str += f"{emotes_army[dt.name]} `{str(dt.level) + ' / ' + str(dt.maxlevel_for_townhall): ^7}`"
                                ct += 1
                            pEmbed.add_field(name=f"Dark Elixir Troops (rushed: {rushed_ct} / {ct})",value=f"{darkelixir_troops_str}\n\u200b",inline=False)

                        if len(siege_machines) > 0:
                            siege_machines_str = ""
                            ct = 0
                            rushed_ct = 0
                            for sm in siege_machines:
                                if ct % 3 == 0:
                                    siege_machines_str += "\n"
                                else:
                                    siege_machines_str += "  "
                                if sm.is_rushed:
                                    siege_machines_str += f"{emotes_army[sm.name]} `{str(sm.level) + '*/ ' + str(sm.maxlevel_for_townhall): ^7}`"
                                    rushed_ct += 1
                                else:
                                    siege_machines_str += f"{emotes_army[sm.name]} `{str(sm.level) + ' / ' + str(sm.maxlevel_for_townhall): ^7}`"
                                ct += 1
                            pEmbed.add_field(name=f"Siege Machines (rushed: {rushed_ct} / {ct})",value=f"{siege_machines_str}\n\u200b",inline=False)

                        if len(elixir_spells) > 0:
                            elixir_spells_str = ""
                            ct = 0
                            rushed_ct = 0
                            for es in elixir_spells:
                                if ct % 3 == 0:
                                    elixir_spells_str += "\n"
                                else:
                                    elixir_spells_str += "  "
                                if es.is_rushed:
                                    elixir_spells_str += f"{emotes_army[es.name]} `{str(es.level) + '*/ ' + str(es.maxlevel_for_townhall): ^7}`"
                                    rushed_ct += 1
                                else:
                                    elixir_spells_str += f"{emotes_army[es.name]} `{str(es.level) + ' / ' + str(es.maxlevel_for_townhall): ^7}`"
                                ct += 1
                            pEmbed.add_field(name=f"Elixir Spells (rushed: {rushed_ct} / {ct})",value=f"{elixir_spells_str}\n\u200b",inline=False)

                        if len(darkelixir_spells) > 0:
                            darkelixir_spells_str = ""
                            ct = 0
                            rushed_ct = 0
                            for ds in darkelixir_spells:
                                if ct % 3 == 0:
                                    darkelixir_spells_str += "\n"
                                else:
                                    darkelixir_spells_str += "  "
                                if ds.is_rushed:
                                    darkelixir_spells_str += f"{emotes_army[ds.name]} `{str(ds.level) + '*/ ' + str(ds.maxlevel_for_townhall): ^7}`"
                                    rushed_ct += 1
                                else:
                                    darkelixir_spells_str += f"{emotes_army[ds.name]} `{str(ds.level) + ' / ' + str(ds.maxlevel_for_townhall): ^7}`"
                                ct += 1
                            pEmbed.add_field(name=f"Dark Elixir Spells (rushed: {rushed_ct} / {ct})",value=f"{darkelixir_spells_str}\n\u200b",inline=False)

                        await channel.send(embed=pEmbed)
