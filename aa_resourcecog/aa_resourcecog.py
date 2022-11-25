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
        default_global = {
            "alliance_server": 0,
            "alliance_leader_role": 0,
            "alliance_coleader_role": 0,
            "alliance_elder_role": 0,
            "alliance_member_role": 0,
            }
        default_guild = {}
        defaults_user = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**defaults_user)

    @commands.command(name="setclashserver")
    @commands.is_owner()
    async def set_clash_alliance_server(self,ctx,server_id:int):
        """
        Sets the main Alliance server for use by the bot.
        """

        try:
            server = ctx.bot.get_guild(int(server_id))
        except:
            return await ctx.send(f"The Server ID {server_id} seems to be invalid.")

        else:
            await self.config.alliance_server.set(int(server.id))
            ctx.bot.alliance_server = server

            return await ctx.send(f"The Alliance Server has been set to `{ctx.bot.alliance_server.name}`.")

    @commands.command(name="setalliancerole")
    @commands.is_owner()
    async def set_clash_alliance_roles(self,ctx,role_type:str,role_id:int):
        """
        Sets Alliance roles.
        """

        valid_roles = ['leader','coleader','elder','member']

        if role_type not in valid_roles:
            return await ctx.send(f"The Role Type seems to be invalid. Acceptable types: {humanize_list(valid_roles)}")

        try:
            role = ctx.bot.alliance_server.get_role(int(role_id))
        except:
            return await ctx.send(f"The Role ID {role_id} seems to be invalid.")

        else:
            if role_type == 'leader':
                await self.config.alliance_leader_role.set(int(role.id))
                ctx.bot.leader_role = role
                return await ctx.send(f"The Alliance Leader Role has been set to `{ctx.bot.leader_role.name}`.")

            if role_type == 'coleader':
                await self.config.alliance_coleader_role.set(int(role.id))
                ctx.bot.coleader_role = role
                return await ctx.send(f"The Alliance Co-Leader Role has been set to `{ctx.bot.coleader_role.name}`.")

            if role_type == 'elder':
                await self.config.alliance_elder_role.set(int(role.id))
                ctx.bot.elder_role = role
                return await ctx.send(f"The Alliance Elder Role has been set to `{ctx.bot.elder_role.name}`.")

            if role_type == 'member':
                await self.config.alliance_member_role.set(int(role.id))
                ctx.bot.member_role = role
                return await ctx.send(f"The Alliance Member Role has been set to `{ctx.bot.member_role.name}`.")


    @commands.command(name="nebula",aliases=["n"])
    async def help_nebula(self,ctx):
        """
        Custom help command for N.E.B.U.L.A.
        """

        leader_state = False
        coleader_state = False
        elder_state = False
        member_state = False

        discord_member = ctx.bot.alliance_server.get_member(ctx.author.id)

        if ctx.bot.leader_role in discord_member.roles:
            leader_state = True

        if ctx.bot.coleader_role in discord_member.roles:
            coleader_state = True

        if ctx.bot.elder_role in discord_member.roles:
            elder_state = True

        if ctx.bot.member_role in discord_member.roles:
            member_state = True

        nebula_embed = await clash_embed(ctx,
            title="Hello, I am N.E.B.U.L.A.",
            message="**N**anotech **E**nhanced **B**ot **U**nit and **L**eader's **A**ssistant."
                + "\n\nMy commands are designed to be simple and easy to remember. "
                + "The commands displayed below are based on your access levels."
                + "\n\n**We don't use Slash commands yet. All commands must be prefixed with `$`.**\n\u200b",
            thumbnail="https://i.imgur.com/TZF5r54.png")

        nebula_embed.add_field(
            name="**__General Commands__**",
            value=f"> **arix**\n> Lists all the Clans in the AriX Alliance."
                + f"\n> \n> **profile** `[optional: @Discord User]`\n> View the AriX Profile of yourself, or another Discord Member."
                + f"\n> \n> **player** `[optional: COC Player Tags]`\n> Gets your Clash of Clans player stats.\n> You may provide multiple player tag(s), separated by a space."
                + f"\n\u200b",
            inline=False)

        if member_state:
            nebula_embed.add_field(
                name="**__Member Commands__**",
                value=f"> **register**\n> Register a non-member account with AriX, so you can bring it into our clans to visit."
                    + f"\n> \n> **nickname**\n> Change your Discord nickname based on your member accounts!"
                    + f"\n> \n> **eclipse**\n> Open E.C.L.I.P.S.E."
                    + f"\n\u200b",
                inline=False)

        if coleader_state or leader_state:
            nebula_embed.add_field(
                name="**__Leaders & Co-Leader Commands__**",
                value=f"> **recruitment**\n> Open the Recruiting Hub. This is where you can check the recruitment statuses of our clans."
                    + f"\n> \n> **getreport** `[clan abbreviation]`\n> Open the Report Hub. Get all sorts of data on Clans and/or Members."
                    + f"\n> \n> **promote** `[Discord User]`\n> Promote a Member. Use this command without mentioning a user to get additional instructions."
                    + f"\n> \n> **demote** `[Discord User]`\n> Demote a Member. Use this command without mentioning a user to get additional instructions."
                    + f"\n> \n> **clan**\n> Command group to manage Alliance clans. Use the command to get more information."
                    + f"\n> \n> **member**\n> Command group to manage Alliance members. Use the command to get more information."
                    + f"\n\u200b",
                inline=False)

        await ctx.send(embed=nebula_embed)

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
            message=f"We're really happy to have you with us. We *strongly encourage* you to review the information below, so you can understand everything that goes on in AriX."
                + f"\n\nThe **AriX Alliance** is made up of 4 active clans:\n- ArmyOf9YearOlds (AO9)\n- Phoenix Reborn (PR)\n- Project AriX (PA)\n- Assassins (AS)"
                + f"\n\nWe also have 3 event-only clans:\n- DawnOfPhoenix (DOP)\n- ArmyOf2YearOlds (AO2)\n- Don (DON)\n\u200b")

        intro_embed.add_field(
            name="**Getting Started in AriX**",
            value="We strongly encourage you to check out the following channels to get yourself set up in the community. If you have any questions, our Leaders will be around to assist."
                + f"\n\n> - Read <#973472492222046258> for info regarding the AriX Alliance Server"
                + f" \n> - Read <#970239273456500736> for info about our Hierarchy"
                + f"\n> - Read <#960096690394767380> for info about our War Rules"
                + f"\n> - Read <#998620795116986499> for info regarding our Raid Rules"
                + f"\n> - Take your Utility Roles from <#970394343133315192>"
                + f"\n\u200b")

        intro_embed.add_field(
            name="**About CWLA**",
            value=f"AriX is also part of a larger alliance, the **Clash Without Limits Alliance (CWLA)**."
                + f"\n\nThrough CWLA, our members are able to sign up for a specific league in the Clan War Leagues (CWL). During CWL week, you will be temporarily allocated a clan with which you can participate in CWL. "
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

        if not user_accounts:
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
