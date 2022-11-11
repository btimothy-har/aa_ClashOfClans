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
import shutil

from dotenv import load_dotenv
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits

from .discordutils import clash_embed, user_confirmation, multiple_choice_select
from .constants import confirmation_emotes, selection_emotes, emotes_army, emotes_capitalhall, emotes_league
from .file_functions import get_current_season, get_current_alliance, get_user_accounts, season_file_handler, alliance_file_handler, data_file_handler
from .notes import aNote
from .player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from .clan import aClan
from .clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from .raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog

load_dotenv()

class AriXClashResources(commands.Cog):
    """AriX Clash of Clans Resource Module."""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=4654586202897940,force_registration=True)
        default_global = {}
        default_guild = {}
        defaults_user = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**defaults_user)

    async def clan_description(ctx,c):
        #build title
        title = ""
        text_full = ""
        text_summary = ""
        title += f"{c.name} ({c.tag})"

        text_full += f"<:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} CH {c.capital_hall}\u3000Members: {c.c.member_count}"
        text_full += f"\n{emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
        text_full += f"\n:globe_with_meridians: {c.c.location.name}\u3000<:HomeTrophies:825589905651400704> {c.c.points}\u3000<:BuilderTrophies:825713625586466816> {c.c.versus_points}"
        text_full += f"\n[Open clan in-game]({c.c.share_link})"

        text_summary += f"<:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} CH {c.capital_hall}\u3000{emotes_league[c.c.war_league.name]} {c.c.war_league.name}"

        return title, text_full, text_summary


    async def player_description(ctx,p):
        #build title
        title = ""
        text_full = ""
        text_summary = ""
        title += f"{p.name} ({p.tag})"

        m_description = ""
        if p.is_member:
            if p.arix_rank not in ['alt']:
                m_description = f"***{p.home_clan.emoji} {p.arix_rank} of {p.home_clan.name}***\n"
            else:
                m_description = f"***<a:aa_AriX:1031773589231374407> AriX Guest Account***\n"

        text_full += f"{m_description}"
        text_full += f"<:Exp:825654249475932170> {p.exp_level}\u3000<:Clan:825654825509322752> {p.clan_description}"
        text_full += f"\n{p.town_hall.emote} {p.town_hall.description}\u3000{emotes_league[p.league.name]} {p.trophies} (best: {p.best_trophies})"
        text_full += f"\n{p.hero_description}"
        text_full += f"\n[Open player in-game]({p.share_link})"
        
        text_summary += f"<:Exp:825654249475932170> {p.exp_level}\u3000"
        if p.is_member and p.arix_rank not in ['alt']:
            text_summary += f"{m_description}"
        else:
            text_summary += f"<:Clan:825654825509322752> {p.clan_description}"
        text_summary += f"\u3000{emotes_league[p.league.name]} {p.trophies} (best: {p.best_trophies})"

        return title, text_full, text_summary


    async def get_welcome_embed(ctx,user):
        intro_embed = await clash_embed(ctx,
            title="Congratulations! You're an AriX Member!",
            message=f"Before going further, there are a few additional things you need to understand and do:"
                + f"\n\nThe **AriX Alliance** is made up of 4 active clans:\n- ArmyOf9YearOlds (AO9)\n- Phoenix Reborn (PR)\n- Project AriX (PA)\n- Assassins (AS)"
                + f"\n\nWe also have 3 event-only clans:\n- DawnOfPhoenix (DOP)\n- ArmyOf2YearOlds (AO2)\n- Don (DON)"
                + f"\n\nIn turn, AriX is also part of a larger alliance, the **Clash Without Limits Alliance (CWLA)**.\n\u200b")
        intro_embed.add_field(
            name="**About CWLA**",
            value=f"Through CWLA, our members are able to sign up for a specific league in the Clan War Leagues (CWL). During CWL week, you will be temporarily allocated a clan with which you can participate in CWL. "
                + f"Clans are available from <:GoldLeagueII:1037033274146570360> Gold II all the way to <:ChampionLeagueI:1037033289564815430> Champions I. "
                + f"\n\nNote: Allocations are made based on your town hall level and experience (e.g TH13 will probably let you be in Crystal 1 or Masters 3, TH12 will probably be Crystal etc.)."
                + f"\n\u200b",
            inline=False)
        intro_embed.add_field(
            name="**You are required to join the CWLA Server ASAP.**",
            value=f"The server link is below. Follow the steps below to get yourself set up in CWLA:"
                + f"\n\n1) Click on the :thumbsup: emoji in the Welcome channel (<#705036745619800154>)."
                + f"\n2) In the ticket that opens, post your Player Tag(s) and the Clan you are joining."
                + f"\n3) An Admin will approve you and set you up on the CWLA bot."
                + f"\n\nTo participate in CWL each month, you will have to sign up in the CWLA Server using the CWLA Bot. We'll remind you when that time comes!",
            inline=False)
        intro_embed.set_author(name=f"{user.name}#{user.discriminator}",icon_url=f"{user.avatar_url}")

        return intro_embed

    async def user_nickname_handler(ctx,user):
        menu = None
        accounts = []
        home_clans = []
        player_tags = await get_user_accounts(ctx,user.id)

        for tag in player_tags:
            try:
                p = await aPlayer.create(ctx,tag)
                if not p.is_member:
                    await p.retrieve_data()
            except Exception as e:
                eEmbed = await clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)

            if p.arix_rank != 'alt':
                if p.home_clan.tag not in [c.tag for c in home_clans]:
                    home_clans.append(p.home_clan)
                accounts.append(p)

        accounts = sorted(accounts,key=lambda p:(p.exp_level,p.town_hall.level),reverse=True)
        home_clans = sorted(home_clans,key=lambda c:(c.level,c.capital_hall),reverse=True)

        if len(accounts) < 1:
            end_embed = await clash_embed(ctx=c,
                message=f"{user.mention} is not an AriX Member.",
                color='fail')
            await ctx.send(embed=end_embed)
            return None

        elif len(accounts) == 1:
            a = accounts[0]
            selected_account = {
                'id': f"{a.tag}",
                'title': f"{a.name} {a.tag}",
                'description': f"{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}\n<:Exp:825654249475932170> {a.exp_level}\u3000{a.town_hall.emote} {a.town_hall.description}"
                }
        
        else:
            selection_list = []
            for a in accounts:
                a_dict = {
                    'id': f"{a.tag}",
                    'title': f"{a.name} ({a.tag})",
                    'description': f"{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}\n<:Exp:825654249475932170> {a.exp_level}\u3000{a.town_hall.emote} {a.town_hall.description}"
                    }
                selection_list.append(a_dict)

            nick_embed = await clash_embed(ctx,
                title=f"Nickname Change: {user.name}#{user.discriminator}",
                thumbnail=f"{user.avatar_url}")

            menu, selected_account = await multiple_choice_select(ctx,
                sEmbed=nick_embed,
                selection_list=selection_list,
                selection_text="Select an account from the list below to be your nickname.")

        if not selected_account:
            end_embed = await resc_cog.clash_embed(ctx,
                message=f"Did not receive a response. Operation cancelled.",
                color='fail')
            await menu.edit(embed=end_embed)
            return None

        if menu:
            await menu.delete()
        
        new_nickname = [a.name for a in accounts if a.tag == selected_account['id']][0]

        clan_ct = 0
        clan_str = ""
        for clan in home_clans:
            clan_ct += 1
            if clan_ct > 1:
                clan_str += " + "
            clan_str += clan.abbreviation

        new_nickname += f" | {clan_str}"
        return new_nickname