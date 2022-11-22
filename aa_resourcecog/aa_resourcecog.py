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

from .discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select
from .constants import confirmation_emotes, selection_emotes, emotes_army, emotes_capitalhall, emotes_league
from .file_functions import get_current_season, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler
from .alliance_functions import get_user_profile, get_alliance_clan
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


    @commands.command(name="status")
    @commands.is_owner()
    async def system_status(self,ctx):
        """Gets information on the system status."""

        if ctx.bot.alliance_server:
            try:
                a_server = ctx.bot.alliance_server.name
            except:
                a_server = ctx.guild.name
        else:
            a_server = ctx.guild.name

        embed = await clash_embed(ctx=ctx,title="System Status Report")
        embed.add_field(
            name="__Summary__",
            value=f"> **Alliance Server**: {a_server}"
                + f"\n> \n> **File Path**: {ctx.bot.clash_dir_path}"
                + f"\n> **Report Path**: {ctx.bot.clash_report_path}"
                + f"\n> **Eclipse Path**: {ctx.bot.eclipse_path}",
            inline=False)

        embed.add_field(
            name="__Data Files__",
            value=f"> **seasons.json**: {os.path.exists(ctx.bot.clash_dir_path+'/seasons.json')}"
                + f"\n> **alliance.json**: {os.path.exists(ctx.bot.clash_dir_path+'/alliance.json')}"
                + f"\n> **members.json**: {os.path.exists(ctx.bot.clash_dir_path+'/members.json')}"
                + f"\n> **warlog.json**: {os.path.exists(ctx.bot.clash_dir_path+'/warlog.json')}"
                + f"\n> **capitalraid.json**: {os.path.exists(ctx.bot.clash_dir_path+'/capitalraid.json')}",
                inline=False)
        await ctx.send(embed=embed)

    # @commands.command(name="meteor")
    # async def help_meteor(self,ctx):
    #     """
    #     Custom help command for M.E.T.E.O.R.
    #     """

    #     coleader_clans = await get_staff_position(ctx,ctx.author.id,"Co-Leader")
    #     elder_clans = await get_staff_position(ctx,ctx.author.id,"Elder")

    #     meteor_embed = await clash_embed(ctx,
    #         name="Hello, I am M.E.T.E.O.R. .",
    #         message="**M**ain **E**xecutive **T**erminal and **E**xtra-**O**rdinary **R**obot."
    #             + "\n\nI host several commands for AriX Members and Leaders, so that the alliance runs smoothly at all times."
    #             + " Below are some commands you may have access to.\n\u200b")

    #     meteor_embed.add_field(
    #         name="**General Commands**",
    #         value="These commands are usable by everyone."
    #             + f"\n\n**arix** Lists all the Clans in the AriX Alliance."
    #             + f"\n\n**player** Gets your Clash of Clans player stats. You may specify player tag(s) when using this command."
    #             + f"\n\n****")
    #eclipse

    async def player_description(ctx,p):
        #build title
        title = ""
        text_full = ""
        text_summary = ""
        title += f"{p.name}"

        m_description = ""
        if p.is_member:
            if p.arix_rank not in ['Guest']:
                m_description = f"***{p.home_clan.emoji} {p.arix_rank} of {p.home_clan.name}***"
            else:
                m_description = f"***<a:aa_AriX:1031773589231374407> AriX Guest Account***"

        text_full += f"{m_description}"
        if m_description:
            text_full += "\n"
        text_full += f"<:Exp:825654249475932170> {p.exp_level}\u3000<:Clan:825654825509322752> {p.clan_description}"
        text_full += f"\n{p.town_hall.emote} {p.town_hall.description}\u3000{emotes_league[p.league.name]} {p.trophies} (best: {p.best_trophies})"
        text_full += f"\n{p.hero_description}"
        text_full += f"\n[Player Link: {p.tag}]({p.share_link})"
        
        text_summary += f"{p.town_hall.emote} {p.town_hall.description}\u3000"
        if p.is_member and p.arix_rank not in ['Guest']:
            text_summary += f"{m_description}"
        else:
            text_summary += f"<:Clan:825654825509322752> {p.clan_description}"
        text_summary += f"\u3000{emotes_league[p.league.name]} {p.trophies}"

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
        leader_clans = []
        home_clans, user_accounts = await get_user_profile(ctx,user.id)

        user_accounts = [a for a in user_accounts if a.is_member]

        for a in user_accounts:
            if a.arix_rank == 'Leader' and a.home_clan.tag not in [c.tag for c in leader_clans]:
                leader_clans.append(a.home_clan)

        if len(user_accounts) < 1:
            if ctx.author.id == user.id:
                end_embed = await clash_embed(ctx,
                    message="You must be an AriX Member to use this command.",
                    color="fail")
            else:
                end_embed = await clash_embed(ctx,
                    message=f"{user.mention} is not an AriX Member.",
                    color='fail')
            await ctx.send(embed=end_embed)
            return None

        elif len(user_accounts) == 1:
            a = user_accounts[0]
            selected_account = {
                'id': f"{a.tag}",
                'title': f"{a.name} {a.tag}",
                'description': f"{a.town_hall.emote} {a.town_hall.description}\u3000{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}\u3000{emotes_league[a.league.name]} {a.trophies}"
                }
        
        else:
            selection_list = []
            selection_str = ""
            for a in user_accounts:
                a_dict = {
                    'id': f"{a.tag}",
                    'title': f"{a.name} ({a.tag})",
                    'description': f"{a.town_hall.emote} {a.town_hall.description}\u3000{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}\u3000{emotes_league[a.league.name]} {a.trophies}"
                    }
                selection_list.append(a_dict)

            selection_list = await multiple_choice_menu_generate_emoji(ctx,selection_list)

            for i in selection_list:
                selection_str += f"\n{i['emoji']} **{i['title']}**\n{i['description']}"

                if selection_list.index(i) < (len(selection_list)-1):
                    selection_str += "\n\n"

            nick_embed = await clash_embed(ctx,
                title=f"Nickname Change: {user.name}#{user.discriminator}",
                thumbnail=f"{user.avatar_url}")

            nick_embed.add_field(
                name="Select an account from the list below to be the new server nickname.",
                value=selection_str,
                inline=False)

            select_msg = await ctx.send(content=ctx.author.mention,embed=nick_embed)

            selected_account = await multiple_choice_menu_select(ctx,select_msg,selection_list)

            if not selected_account:
                return None
        
        new_nickname = [a.name for a in user_accounts if a.tag == selected_account['id']][0]

        new_nickname = new_nickname.replace('[AriX]','')
        new_nickname = new_nickname.strip()

        clan_ct = 0
        clan_str = ""
        if len(leader_clans) > 0:
            home_clans = leader_clans

        for clan in home_clans:
            clan_ct += 1
            if clan_ct > 1:
                clan_str += " + "
            clan_str += clan.abbreviation

        new_nickname += f" | {clan_str}"
        return new_nickname
