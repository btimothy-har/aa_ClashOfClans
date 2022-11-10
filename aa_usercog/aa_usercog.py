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

from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from tabulate import tabulate

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.constants import emotes_townhall, emotes_army, hero_availability, troop_availability, spell_availability, emotes_league
from aa_resourcecog.notes import aNote
from aa_resourcecog.file_functions import get_current_season, get_current_alliance, get_alliance_clan, get_alliance_members, get_user_accounts, get_staff_position
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from aa_resourcecog.errors import TerminateProcessing

class AriXMemberCommands(commands.Cog):
    """AriX Clash of Clans Members' Module."""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=2170311125702803,force_registration=True)
        default_global = {}
        default_guild = {}
        defaults_user = {
            "default_clan": []
            }       
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**defaults_user)

    @commands.command(name="arix")
    async def arix_information(self,ctx):
        """
        Lists all clans in the Alliance.
        """
        clans, members = await get_current_alliance(ctx)
        alliance_clans = []

        for tag in clans:
            try:    
                c = await aClan.create(ctx,tag)
            except Exception as e:
                eEmbed = await resc.clash_embed(ctx=ctx,message=f"{e}",color="fail")
                return await ctx.send(embed=eEmbed)
            alliance_clans.append(c)

        if len(alliance_clans) == 0:
            eEmbed = await resc.clash_embed(ctx=ctx,message=f"There are no clans registered.",color="fail")
            return await ctx.send(embed=eEmbed)

        rEmbed = await resc.clash_embed(ctx=ctx,
            title="AriX Alliance | Clash of Clans",
            image="https://i.imgur.com/TZF5r54.png")

        for c in alliance_clans:
            th_str = ""
            for th in c.recruitment_level:
                th_str += f"{emotes_townhall[th]} "

            rEmbed.add_field(
                name=f"{c.emoji} {c.name} ({c.tag})",
                value=f"\n> <:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} {c.capital_hall}\u3000Leader: <@{c.leader}>"
                    + f"\n> {emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
                    + f"\n> Members: {c.member_count}/50\u3000Recruiting: {th_str}"
                    + f"\n> [Click here to open in-game]({c.c.share_link})"
                    + f"\n\n{c.description}",
                inline=False)

        await ctx.send(embed=rEmbed)

    @commands.command(name="profile")
    async def arix_profile(self,ctx,user:discord.User=None):
        """
        Gets a User's AriX Profile.

        Returns only AriX-registered accounts.
        """

        if not user:
            user = ctx.author

        user_account_tags = await get_user_accounts(ctx,user.id)

        user_accounts = []
        for tag in user_account_tags:
            try:
                p = await aPlayer.create(ctx,tag)
            except Exception as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(embed=eEmbed)
            user_accounts.append(p)

        profile_embed = await resc.clash_embed(ctx,
            title=f"{user.name}#{user.discriminator}",
            thumbnail=user.avatar_url)

        user_accounts = sorted(user_accounts,key=lambda a:(a.exp_level, a.town_hall.level),reverse=True)

        main_accounts = [a for a in user_accounts if a.arix_rank not in ['alt']]
        alt_accounts = [a for a in user_accounts if a.arix_rank in ['alt']]

        if len(main_accounts) == 0:
            eEmbed = await resc.clash_embed(ctx,message=f"{user.mention} is not an AriX Member.")
            return await ctx.send(embed=eEmbed)

        if len(main_accounts) > 0:
            for p in main_accounts:
                main_str = ""
                
                if p.is_member:
                    main_str += f"\n> *{p.home_clan.emoji} {p.arix_rank} of {p.home_clan.name}*"
                main_str += f"\n> <:Exp:825654249475932170> {p.exp_level}\u3000{p.town_hall.emote} {p.town_hall.description}\u3000{emotes_league[p.league.name]} {p.trophies}"
                main_str += f"\n> {p.hero_description}"
                main_str += f"\n> [Open in-game]({p.share_link})"
                main_str += "\n\u200b"

                profile_embed.add_field(
                    name=f"**{p.name} {p.tag}**",
                    value=main_str,
                    inline=False)

        if len(alt_accounts) > 0:
            alt_str = ""
            for p in alt_accounts:
                alt_str += f"\n> *AriX alternate account*"
                alt_str += f"\n> <:Exp:825654249475932170> {p.exp_level}\u3000{p.town_hall.emote} {p.town_hall.description}\u3000{emotes_league[p.league.name]} {p.trophies}"
                alt_str += f"\n> {p.hero_description}"
                alt_str += f"\n> [Open in-game]({p.share_link})"
                alt_str += "\n\u200b"

                profile_embed.add_field(
                    name=f"**{p.name} {p.tag}**",
                    value=alt_str,
                    inline=False)

        return await ctx.send(embed=profile_embed)

    @commands.command(name="player")
    async def arix_player(self,ctx,*player_tags:str):
        """
        Get Player Stats for yourself or for a Clash of Clans account.

        You can provide multiple tags in a single command.
        If no tags are provided, will return all of your active accounts with AriX.
        """

        output_embed = []

        if not player_tags:
            player_tags = await get_user_accounts(ctx,ctx.author.id)

        accounts = []
        error_log = []
        for tag in player_tags:
            try:
                p = await aPlayer.create(ctx,tag)
                if not p.is_member:
                    await p.retrieve_data()
            except TerminateProcessing as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            except Exception as e:
                p = None
                err_dict = {'tag':tag,'reason':f"Error retrieving data: {e}"}
                error_log.append(err_dict)
                continue
            accounts.append(p)

        accounts = sorted(accounts,key=lambda p:(p.exp_level,p.town_hall.level),reverse=True)

        for a in accounts:
            member_status = ""
            if a.is_member:
                if a.arix_rank == 'alt':
                    member_status = f"***AriX alternate account***\n"
                else:
                    member_status = f"***{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}***\n"

            discord_msg = ""
            if a.discord_user:
                discord_msg += f"\nLinked to: <@{a.discord_user}>"
            elif a.discord_link:
                discord_msg += f"\nLinked to <@{a.discord_link}>"

            pEmbed = await resc.clash_embed(
                ctx=ctx,
                title=f"{a.name} ({a.tag})",
                message=f"{member_status}"
                    + f"<:Exp:825654249475932170>{a.exp_level}\u3000<:Clan:825654825509322752> {a.clan_description}"
                    + f"{discord_msg}",
                url=f"{a.share_link}",
                thumbnail=f"{a.league.icon.medium}")

            base_strength = f"<:TotalTroopStrength:827730290491129856> {a.troop_strength} / {a.max_troop_strength} *(rushed: {a.troop_rushed_pct}%)*"
            if a.town_hall.level >= 5:
                base_strength += f"\n<:TotalSpellStrength:827730290294259793> {a.spell_strength} / {a.max_spell_strength} *(rushed: {a.spell_rushed_pct}%)*"
            if a.town_hall.level >= 7:
                base_strength += f"\n<:TotalHeroStrength:827730291149635596> {a.hero_strength} / {a.max_hero_strength} *(rushed: {a.hero_rushed_pct}%)*"
            base_strength += "\n\u200b"

            pEmbed.add_field(
                name="**Home Village**",
                value=f"{a.town_hall.emote} {a.town_hall.description}\u3000{emotes_league[a.league.name]} {a.trophies} (best: {a.best_trophies})"
                    + f"\n**Heroes**"
                    + f"\n{a.hero_description}"
                    + f"\n**Strength**"
                    + f"\n{base_strength}",
                inline=False)

            if a.is_member:
                home_clan_str = ""
                if a.home_clan.tag:
                    d, h, m, s = await resc.convert_seconds_to_str(ctx,a.time_in_home_clan)
                    home_clan_str += f"\n{a.home_clan.emoji} {int(d)} days spent in {a.home_clan.name}"

                last_update_str = ""
                ltime = time.time() - a.last_update
                d, h, m, s = await resc.convert_seconds_to_str(ctx,ltime)
                if d > 0:
                    last_update_str += f"{int(d)} days "
                if h > 0:
                    last_update_str += f"{int(h)} hours "
                if m > 0:
                    last_update_str += f"{int(m)} minutes "
                if last_update_str == "":
                    last_update_str = "a few seconds "

                pEmbed.add_field(
                    name=f"**Current Season Stats with AriX**",
                    value=f":stopwatch: Last updated: {last_update_str}ago"
                        + f"{home_clan_str}"
                        + f"\n**Donations**"
                        + f"\n<:donated:825574412589858886> {a.donations_sent.statdisplay}\u3000<:received:825574507045584916> {a.donations_rcvd.statdisplay}"
                        + f"\n**Loot**"
                        + f"\n<:gold:825613041198039130> {a.loot_gold.statdisplay}\u3000<:elixir:825612858271596554> {a.loot_elixir.statdisplay}\u3000<:darkelixir:825640568973033502> {a.loot_darkelixir.statdisplay}"
                        + f"\n**Clan Capital**"
                        + f"\n<:CapitalGoldContributed:971012592057339954> {a.capitalcontribution.statdisplay}\u3000<:CapitalRaids:1034032234572816384> {a.raid_stats.raids_participated}\u3000<:RaidMedals:983374303552753664> {a.raid_stats.medals_earned:,}"
                        + f"\n**War Performance**"
                        + f"\n<:TotalWars:827845123596746773> {a.war_stats.wars_participated}\u3000<:TotalStars:825756777844178944> {a.war_stats.offense_stars}\u3000<:Triple:1034033279411687434> {a.war_stats.triples}\u3000<:MissedHits:825755234412396575> {a.war_stats.missed_attacks}",
                    inline=False)

            output_embed.append(pEmbed)

        if len(output_embed)>1:
            paginator = BotEmbedPaginator(ctx,output_embed)
            await paginator.run()
        elif len(output_embed)==1:
            await ctx.send(embed=output_embed[0])

    @commands.command(name="nickname")
    async def user_setnickname(self,ctx):
        """
        Change your server nickname.

        Your server nickname can be changed to match one of your registered accounts.
        """

        user = ctx.author

        accounts = []
        home_clans = []
        player_tags = await get_user_accounts(ctx,ctx.author.id)

        for tag in player_tags:
            try:
                p = await aPlayer.create(ctx,tag)
                if not p.is_member:
                    await p.retrieve_data()
            except Exception as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)

            if p.home_clan.tag not in [c.tag for c in home_clans]:
                home_clans.append(p.home_clan)
            accounts.append(p)

        accounts = sorted(accounts,key=lambda p:(p.exp_level,p.town_hall.level),reverse=True)
        home_clans = sorted(home_clans,key=lambda c:(c.level,c.capital_hall),reverse=True)

        selection_list = []
        for a in accounts:
            a_dict = {
                'id': f"{a.tag}",
                'title': f"{a.name} ({a.tag})",
                'description': f"{p.home_clan.emoji} {p.arix_rank} of {p.home_clan.name}\n<:Exp:825654249475932170> {p.exp_level}\u3000{a.town_hall.emote} {a.town_hall.description}"
                }
            selection_list.append(a_dict)

        nick_embed = await resc.clash_embed(ctx,
            title=f"Nickname Change: {user.name}#{user.discriminator}",
            thumbnail=user.avatar_url)

        menu, selected_account = await resc.multiple_choice_select(self,
            ctx=ctx,
            sEmbed=nick_embed,
            selection_list=selection_list,
            selection_text="Select an account from the list below to be your nickname.")

        if not selected_account:
            end_embed = await resc.clash_embed(ctx,
                message=f"Did not receive a response. Operation cancelled.",
                color='fail')
            return await menu.edit(embed=end_embed)

        await menu.delete()

        new_nickname = [a.name for a in accounts if a.tag == selected_account['id']][0]

        clan_ct = 0
        clan_str = ""
        for clan in home_clans:
            clan_ct += 1
            if clan_ct > 1:
                clan_str += ", "
            clan_str += clan.abbreviation

        new_nickname += f" | {clan_str}"

        try:
            await ctx.author.edit(nick=new_nickname)
            success_embed = await resc.clash_embed(ctx,
                message=f"{ctx.author.mention} your nickname has been set to {new_nickname}.",
                color='success')
        except:
            end_embed = await resc.clash_embed(ctx,
                message=f"I don't have permissions to change your nickname. New nickname: {new_nickname}",
                color='fail')
            return await ctx.send(embed=end_embed)

















