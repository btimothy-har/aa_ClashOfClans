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

from .discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select, paginate_embed
from .constants import confirmation_emotes, selection_emotes, emotes_army, emotes_capitalhall, emotes_league
from .file_functions import get_current_season, read_file_handler, write_file_handler, eclipse_base_handler
from .alliance_functions import get_user_profile, get_alliance_clan
from .notes import aNote
from .player import aPlayer, aClan, aMember
from .clan_war import aClanWar
from .raid_weekend import aRaidWeekend

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
            "alliance_base_role": 0,
            "alliance_base_channel": 0,
            "alliance_update_channel": 0,
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

        valid_roles = ['leader','coleader','elder','member','base']

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

            if role_type == 'base':
                await self.config.alliance_base_role.set(int(role.id))
                ctx.bot.base_vault_role = role
                return await ctx.send(f"The Alliance Base Role has been set to `{ctx.bot.base_role.name}`.")

    @commands.command(name="setalliancechannel")
    @commands.is_owner()
    async def set_clash_alliance_channel(self,ctx,channel_type:str,channel_id:int):
        """
        Sets Alliance channels.
        """

        valid_channels = ['base','updates']

        if channel_type not in valid_channels:
            return await ctx.send(f"The Channel Type seems to be invalid. Acceptable types: {humanize_list(valid_channels)}")

        try:
            channel = ctx.bot.get_channel(int(channel_id))
        except:
            return await ctx.send(f"The Channel ID {channel_id} seems to be invalid.")

        else:
            if channel_type == 'base':
                await self.config.alliance_base_channel.set(int(channel.id))
                ctx.bot.base_channel = channel
                return await ctx.send(f"The Alliance Base Vault Channel has been set to `{ctx.bot.base_channel.name}`.")

            if channel_type == 'updates':
                await self.config.alliance_update_channel.set(int(channel.id))
                ctx.bot.update_channel = channel
                return await ctx.send(f"The Alliance Update Channel has been set to `{ctx.bot.update_channel.name}`.")

    @commands.command(name="showembed")
    @commands.is_owner()
    async def show_static_embed(self,ctx):
        """
        Prints a static embed in the current channel.
        """

        base_embed = await clash_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"Need to refresh your base collection and get a brand new OP defense? The E.C.L.I.P.S.E. Base Vault contains bases from **<:09:1037001009207201832> TH9 to <:15:1045961696939872276> TH15**, covering a wide range of your needs."
                + f"\n\nTo get access to the Base Vault, run the `/eclipse` command in <#{ctx.bot.base_channel.id}>. *You need to be a member of our clans for at least 2 weeks to view this channel.*"
                + f"\n\nIf you already meet the above condition but are unable to view the base vault, please contact a <@&733023831366697080>.",
            show_author=False)

        await ctx.send(embed=base_embed)
        await ctx.message.delete()


    @commands.command(name="bakkuhelp")
    async def help_nebula(self,ctx,thing_to_get_help_for: str = None):
        """
        Custom help command for N.E.B.U.L.A.
        """

        await ctx.bot.send_help_for(ctx,thing_to_get_help_for,from_help_command=True)


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


    async def user_nickname_handler(ctx,user,selection=True):
        leader_clans = []

        for c in self.home_clans:
            if self.user_id in c:
                leader_clans.append(c)

        if len(p_user_accounts) == 0:
            p_user_accounts = user_accounts

        if len(p_user_accounts) == 1 or not selection:
            a = p_user_accounts[0]
            selected_account = {
                'id': f"{a.tag}",
                'title': f"{a.name} {a.tag}",
                'description': f"{a.town_hall.emote} {a.town_hall.description}\u3000{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}\u3000{emotes_league[a.league.name]} {a.trophies}"
                }
        else:
            selection_list = []
            selection_str = ""
            for a in p_user_accounts:
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

            await select_msg.delete()

            if not selected_account:
                return None
        
        new_nickname_account = [a for a in p_user_accounts if a.tag == selected_account['id']][0]

        if new_nickname_account.readable_name:
            new_nickname = new_nickname_account.readable_name
        else:
            new_nickname = new_nickname_account.name

        new_nickname = new_nickname.replace('[AriX]','')
        new_nickname = new_nickname.strip()

        clan_ct = 0
        clan_str = ""
        if len(leader_clans) > 0:
            home_clans = leader_clans

        if home_clans:
            abb_clans = []
            [abb_clans.append(c.abbreviation) for c in home_clans if c.abbreviation not in abb_clans and c.abbreviation!='']
            new_nickname += f" | {' + '.join(abb_clans)}"

        return new_nickname
