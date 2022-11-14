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
from numerize import numerize

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, eclipse_embed, user_confirmation, multiple_choice_select
from aa_resourcecog.constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league
from aa_resourcecog.notes import aNote
from aa_resourcecog.file_functions import get_current_season, get_current_alliance, get_alliance_clan, get_alliance_members, get_user_accounts, get_staff_position
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing

from aa_resourcecog.eclipse_bases import eWarBase

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

    @commands.command(name="nickname")
    async def user_setnickname(self,ctx):
        """
        Change your server nickname.

        Your server nickname can be changed to match one of your registered accounts.
        """

        new_nickname = await resc.user_nickname_handler(ctx,ctx.author)

        if not new_nickname:
            return

        try:
            discord_member = ctx.guild.get_member(ctx.author.id)
            await discord_member.edit(nick=new_nickname)
            success_embed = await clash_embed(ctx,
                message=f"{ctx.author.mention} your nickname has been set to {new_nickname}.",
                color='success')
            return await ctx.send(embed=success_embed)
        except:
            end_embed = await clash_embed(ctx,
                message=f"{ctx.author.mention}, I don't have permissions to change your nickname.",
                color='fail')
            return await ctx.send(embed=end_embed)

    @commands.command(name="register")
    async def user_add_guest_account(self,ctx):
        """
        Register a Guest account to the Alliance.

        This lets our Leaders know who you are should you visit our clans.
        """

        user_account_tags = await get_user_accounts(ctx,ctx.author.id)


        embed = await clash_embed(ctx,message="I will DM you to continue the linking process. Please ensure your DMs are open!")
        await ctx.send(content=ctx.author.mention,embed=embed)

        embed = await clash_embed(ctx,message="Let's link your non-Member Clash accounts to AriX as Guest accounts. This will let you bring these accounts into our clans.\n\n**Please send any message to continue.**")
        await ctx.author.send(f"Hello, {ctx.author.mention}!",embed=embed)

        def dm_check(m):
            return m.author == ctx.author and m.guild is None
        
        try:
            startmsg = await ctx.bot.wait_for("message",timeout=60,check=dm_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,
                message="Sorry, you timed out. Please restart the process by re-using the `register` command from the AriX server.",
                color='fail')
            return await ctx.author.send(embed=timeout_embed)

        embed = await clash_embed(ctx,
            message="What is the **Player Tag** of the account you'd like to link?")
        await ctx.author.send(embed=embed)
        try:
            msg_player_tag = await ctx.bot.wait_for("message",timeout=120,check=dm_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,
                message="Sorry, you timed out. Please restart the process by re-using the `register` command from the AriX server.",
                color='fail')

        new_tag = coc.utils.correct_tag(msg_player_tag.content)
        if not coc.utils.is_valid_tag(new_tag):
            embed = await clash_embed(ctx,
                message="This tag seems to be invalid. Please try again by using the `register` command from the AriX server.",
                color="fail")
            return await ctx.author.send(embed=embed)

        if new_tag in user_account_tags:
            embed = await clash_embed(ctx,
                message="This account is already registered with AriX!",
                color="fail")
            return await ctx.author.send(embed=embed)

        embed = await clash_embed(ctx,
            message="Please provide your **in-game API Token.**\n\nTo locate your token, please follow the instructions in the image below.")
        embed.set_image(url='https://i.imgur.com/Q1JwMzK.png')
        await ctx.author.send(embed=embed)
        try:
            msg_api_token = await ctx.bot.wait_for("message",timeout=120,check=dm_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,
                message="Sorry, you timed out. Please restart the process by re-using the `register` command from the AriX server.",
                color='fail')
            return await ctx.author.send(embed=timeout_embed)

        player_tag = str(msg_player_tag.content)
        api_token = str(msg_api_token.content)

        embed = await clash_embed(ctx,
            message="Verifying... please wait.")
        waitmsg = await ctx.author.send(embed=embed)

        try:
            verify = await ctx.bot.coc_client.verify_player_token(player_tag=player_tag,token=api_token)
        except Exception as e:
            await waitmsg.delete()
            err_embed = await clash_embed(ctx,message=f"An error occurred while verifying: {e}.",color='fail')
            return await ctx.author.send(embed=err_embed)

        if not verify:
            embed = await clash_embed(ctx,
                message="The token you provided seems to be invalid. Please try again.",
                color="fail")
            await waitmsg.delete()
            return await ctx.author.send(embed=embed)
        else:
            try:
                p = await aPlayer.create(ctx,new_tag)
                await p.retrieve_data()
            except Exception as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while fetching this account.",
                    err=e)

            if p.is_member:
                err_embed = await clash_embed(ctx,message=f"The account {p.tag} {p.name} is already an AriX Member!",color='fail')
                return await ctx.author.send(embed=err_embed)
            else:
                async with ctx.bot.async_file_lock:
                    with ctx.bot.clash_file_lock.write_lock():
                        try:
                            await p.new_member(ctx,ctx.author)
                            await p.set_baselines()
                            await p.save_to_json()
                        except Exception as e:
                            err_embed = await clash_embed(ctx,message=f"I ran into a problem while saving your account. I've contacted my masters.",color='fail')
                            await ctx.author.send(embed=err_embed)
                            return await ctx.bot.send_to_owners(f"I ran into an error while adding {p.tag} {p.name} as a Guest account for {ctx.author.mention}.\n\nError: {e}")

                title, text, summary = await resc.player_description(ctx,p)

                player_embed = await clash_embed(ctx,
                    message=f"The account {p.tag} {p.name} was successfully added as a Guest account!",
                    color='success')

                return await ctx.send(embed=player_embed)

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
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving clan {tag}",
                    err=e)
            alliance_clans.append(c)

        if len(alliance_clans) == 0:
            eEmbed = await clash_embed(ctx=ctx,message=f"There are no clans registered.",color="fail")
            return await ctx.send(embed=eEmbed)

        rEmbed = await clash_embed(ctx=ctx,
            title="AriX Alliance | Clash of Clans",
            thumbnail="https://i.imgur.com/TZF5r54.png",
            show_author=False)

        for c in alliance_clans:
            th_str = ""
            for th in c.recruitment_level:
                th_str += f"{emotes_townhall[th]} "

            title, text, summary = await resc.clan_description(ctx,c)

            rEmbed.add_field(
                name=f"{c.emoji} **{c.name}**",
                value=f"\nLeader: <@{c.leader}>"
                    + f"\n{text}"
                    + f"\n\n> **Recruiting: {th_str}**"
                    + f"\n\n{c.description}\n\u200b",
                inline=False)

        await ctx.send(embed=rEmbed)

    # @commands.command(name="getclan")
    # async def clan_information(self,ctx,tag):
    #     """
    #     Gets information about a specified clan tag.
    #     """
    #     try:    
    #         c = await aClan.create(ctx,tag)
    #     except Exception as e:
    #         return await error_end_processing(ctx,
    #             preamble=f"Error encountered while retrieving clan {tag}",
    #             err=e)

    #     title, text, summary = await resc.clan_description(ctx,c)

    #     th_str = "Recruiting: "
    #     for th in c.recruitment_level:
    #         th_str += f"{emotes_townhall[th]} "

    #     clan_str = ""
    #     clan_str += f"{text}"
    #     if len(c.recruitment_level) > 0:
    #         clan_str += f"\n\n{th_str}"
    #     clan_str += f"\n\n{c.description}"

    #     rEmbed = await clash_embed(ctx=ctx,
    #         title=f"{c.emoji} {title}",
    #         message=clan_str,
    #         thumbnail=c.c.badge.medium,
    #         show_author=False)

    #     await ctx.send(embed=rEmbed)

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
                eEmbed = await clash_embed(ctx,message=e,color='fail')
                return await ctx.send(embed=eEmbed)
            user_accounts.append(p)

        discord_member = ctx.guild.get_member(user.id)

        profile_embed = await clash_embed(ctx,
            title=f"{discord_member.display_name}",
            thumbnail=user.avatar_url)

        user_accounts = sorted(user_accounts,key=lambda a:(a.exp_level, a.town_hall.level),reverse=True)

        main_accounts = [a for a in user_accounts if a.arix_rank not in ['Guest']]
        alt_accounts = [a for a in user_accounts if a.arix_rank in ['Guest']]

        if len(main_accounts) == 0:
            eEmbed = await clash_embed(ctx,message=f"{user.mention} is not an AriX Member.")
            return await ctx.send(embed=eEmbed)

        if len(main_accounts) > 0:
            for p in main_accounts:
                title, text, summary = await resc.player_description(ctx,p)

                profile_embed.add_field(
                    name=f"**{title}**",
                    value=f"{text}\n\u200b",
                    inline=False)

        if len(alt_accounts) > 0:
            alt_str = ""
            for p in alt_accounts:

                profile_embed.add_field(
                    name=f"**{title}**",
                    value=f"{text}\n\u200b",
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
                eEmbed = await clash_embed(ctx,message=e,color='fail')
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
                member_status = f"***{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}***\n"
            if a.arix_rank == 'Guest':
                member_status = f"***AriX Guest Account***\n"
                

            discord_msg = ""
            if a.discord_user:
                discord_msg += f"\n<:Discord:1040423151760314448> <@{a.discord_user}>"
            elif a.discord_link:
                discord_msg += f"\n<:Discord:1040423151760314448> <@{a.discord_link}>"

            if a.league.name == 'Unranked':
                league_img = "https://i.imgur.com/TZF5r54.png"
            else:
                league_img = a.league.icon.medium

            pEmbed = await clash_embed(
                ctx=ctx,
                title=f"{a.name} ({a.tag})",
                message=f"{member_status}"
                    + f"<:Exp:825654249475932170>{a.exp_level}\u3000<:Clan:825654825509322752> {a.clan_description}"
                    + f"{discord_msg}",
                url=f"{a.share_link}",
                thumbnail=league_img)

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
                    d, h, m, s = await convert_seconds_to_str(ctx,a.time_in_home_clan)
                    home_clan_str += f"\n{a.home_clan.emoji} {int(d)} days spent in {a.home_clan.name}"

                last_update_str = ""
                ltime = time.time() - a.last_update
                d, h, m, s = await convert_seconds_to_str(ctx,ltime)
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
                        + f"\n\n**Attacks Won**"
                        + f"\n<:Attack:828103854814003211> {a.attack_wins.statdisplay}"
                        + f"\n**Defenses Won**"
                        + f"\n<:Defense:828103708956819467> {a.defense_wins.statdisplay}"
                        + f"\n**Donations**"
                        + f"\n<:donated:825574412589858886> {a.donations_sent.statdisplay}\u3000<:received:825574507045584916> {a.donations_rcvd.statdisplay}"
                        + f"\n**Loot**"
                        + f"\n<:gold:825613041198039130> {a.loot_gold.statdisplay}\u3000<:elixir:825612858271596554> {a.loot_elixir.statdisplay}\u3000<:darkelixir:825640568973033502> {a.loot_darkelixir.statdisplay}"
                        + f"\n**Clan Capital**"
                        + f"\n<:CapitalGoldContributed:971012592057339954> {a.capitalcontribution.statdisplay}\u3000<:CapitalRaids:1034032234572816384> {a.raid_stats.raids_participated}\u3000<:RaidMedals:983374303552753664> {a.raid_stats.medals_earned:,}"
                        + f"\n**War Performance**"
                        + f"\n<:TotalWars:827845123596746773> {a.war_stats.wars_participated}\u3000<:WarStars:825756777844178944> {a.war_stats.offense_stars}\u3000<:Triple:1034033279411687434> {a.war_stats.triples}\u3000<:MissedHits:825755234412396575> {a.war_stats.missed_attacks}"
                        + f"\n**Clan Games**"
                        + f"\n<:ClanGames:834063648494190602> {a.clangames.statdisplay}",
                    inline=False)

            else:
                pEmbed.add_field(
                    name=f"**Season Activity**",
                    value=f"**Attacks Won**"
                        + f"\n<:Attack:828103854814003211> {a.p.attack_wins}"
                        + f"\n**Defenses Won**"
                        + f"\n<:Defense:828103708956819467> {a.p.defense_wins}"
                        + f"\n**Donations**"
                        + f"\n<:donated:825574412589858886> {a.p.donations}\u3000<:received:825574507045584916> {a.p.received}\n\u200b",
                    inline=False)

                for achievement in a.p.achievements:
                    if achievement.name == 'Gold Grab':
                        gold_value = achievement.value
                    if achievement.name == 'Elixir Escapade':
                        elixir_value = achievement.value
                    if achievement.name == 'Heroic Heist':
                        darkelixir_value = achievement.value
                    if achievement.name == 'Aggressive Capitalism':
                        capitalraided_value = achievement.value
                    if achievement.name == 'Games Champion':
                        clangames_value = achievement.value
                    if achievement.name == 'War League Legend':
                        warleague_value = achievement.value

                pEmbed.add_field(
                    name=f"**Lifetime Stats**",
                    value=f"**Loot**"
                        + f"\n<:gold:825613041198039130> {numerize.numerize(gold_value,1)}\u3000<:elixir:825612858271596554> {numerize.numerize(elixir_value,1)}\u3000<:darkelixir:825640568973033502> {numerize.numerize(darkelixir_value,1)}"
                        + f"\n**Clan Capital**"
                        + f"\n<:CapitalGoldContributed:971012592057339954> {numerize.numerize(a.p.clan_capital_contributions,1)}\u3000<:CapitalRaids:1034032234572816384> {numerize.numerize(capitalraided_value,1)}"
                        + f"\n**War Stats**"
                        + f"\n<:WarStars:825756777844178944> {a.p.war_stars:,}\u3000<:ClanWarLeagues:825752759948279848> {warleague_value:,}"
                        + f"\n**Clan Games**"
                        + f"\n<:ClanGames:834063648494190602> {clangames_value:,}")

            output_embed.append(pEmbed)

        if len(output_embed)>1:
            paginator = BotEmbedPaginator(ctx,output_embed)
            await paginator.run()
        elif len(output_embed)==1:
            await ctx.send(embed=output_embed[0])

    @commands.group(name="eclipse")
    async def eclipse_group(self,ctx):
        """
        Access E.C.L.I.P.S.E.

        An **E**xtraordinarily **C**ool **L**ooking **I**nteractive & **P**rofessional **S**earch **E**ngine.
        Your Clash of Clans database of attack strategies, guides and war bases.
        """

        if not ctx.invoked_subcommand:
            pass

    @eclipse_group.command(name="addbase")
    async def eclipse_add_base(self,ctx):
        """
        Add a base to Eclipse.
        """

        def baselink_check(m):
            msg_check = False
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    msg_check = True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    msg_check = True
            if msg_check:
                return m.content.startswith("https://link.clashofclans.com") and m.content.startswith("action=OpenLayout",33)

        def armylink_check(m):
            msg_check = False
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    msg_check = True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    msg_check = True
            if msg_check:
                return m.content.startswith("https://link.clashofclans.com") and m.content.startswith("action=CopyArmy",33)

        def response_check(m):
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    return True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    return True
                else:
                    return False

        #BASE LINK & TOWNHALL LEVEL

        base_link_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 1",
            message=f"Please provide the Base Link.\n\nI will get the Base Townhall level from the link provided.")

        base_link_msg = await ctx.send(embed=base_link_embed)
        try:
            base_link_response = await ctx.bot.wait_for("message",timeout=60,check=baselink_check)
        except asyncio.TimeoutError:
            timeout_embed = await eclipse_embed(ctx,message=f"Operation timed out.")
            await base_link_msg.edit(embed=timeout_embed)
            return
        else:
            base_link = base_link_response.content
            base_townhall = int(base_link.split('id=TH',1)[1][:2])
            base_id = base_link.split('id=',1)[1]
            await base_link_msg.delete()
            await base_link_response.delete()


        # SOURCE
        base_supplier_list = [
            {
                'id': 'rh',
                'emoji': "<:RHBB:1041627382018211900>",
                'title': "RH Base Building",
                'description': None
                },
            {
                'id': 'other',
                'emoji': "<a:aa_AriX:1031773589231374407>",
                'title': "Others",
                'description': None
                }
            ]
        base_source_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 2",
            message=f"Where is this Base from?")

        select_source = await multiple_choice_select(
            ctx=ctx,
            sEmbed=base_source_embed,
            selection_list=base_supplier_list)
        if not select_source:
            return
        base_source = f"{select_source['emoji']} {select_source['title']}"


        # BASE BUILDER
        base_builder_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 3",
            message=f"Provide the Name of the Builder. If no Builder is specified, please respond with an asterisk [`*`].")
        base_builder_msg = await ctx.send(embed=base_builder_embed)

        try:
            builder_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await eclipse_embed(ctx,message=f"Operation timed out.")
            await base_builder_msg.edit(embed=timeout_embed)
            return
        else:
            base_builder = builder_response.content
            await base_builder_msg.delete()
            await builder_response.delete()


        #BASE TYPE
        base_type_list = [
            {
                'id': 'home',
                'title': 'Trophy/Farm Base',
                'description': None
                },
            {
                'id': 'legends',
                'title': 'Legends Base',
                'description': None
                },
            {
                'id': 'anti2',
                'title': 'War Base: Anti-2 Star',
                'description': None
                },
            {   
                'id': 'anti3',
                'title': 'War Base: Anti-3 Star',
                'description': None
                }
            ]
        base_type_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 4",
            message=f"Select the type of base this is.")

        select_type = await multiple_choice_select(
            ctx=ctx,
            sEmbed=base_type_embed,
            selection_list=base_type_list)

        if not select_type:
            return
        base_type = f"{select_type['title']}"



        #DEFENSIVE CC
        defensive_cc_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 5",
            message=f"Provide the Army Link for the Defensive Clan Castle.")
        defensive_cc_msg = await ctx.send(embed=defensive_cc_embed)
        try:
            army_link_response = await ctx.bot.wait_for("message",timeout=60,check=armylink_check)
        except asyncio.TimeoutError:
            timeout_embed = await eclipse_embed(ctx,message=f"Operation timed out.")
            await defensive_cc_msg.edit(embed=timeout_embed)
            return
        else:
            defensive_cc = army_link_response.content
            await defensive_cc_msg.delete()
            await army_link_response.delete()


        #BASE IMAGE
        base_image_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 6",
            message=f"Upload the Base Image.")

        base_image_msg = await ctx.send(embed=base_image_embed)
        try:
            base_image_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await eclipse_embed(ctx,message=f"Operation timed out.")
            await base_image_msg.edit(embed=timeout_embed)
            return
        else:
            base_image = base_image_response.attachments[0]
            await base_image_msg.delete()
            await base_image_response.delete()


        new_base = await eWarBase.new_base(ctx=ctx,
            base_link=base_link,
            source=base_source,
            base_builder=base_builder,
            base_type=base_type,
            defensive_cc=defensive_cc,
            image_attachment=base_image)

        await new_base.save_to_json()

        embed = await new_base.base_embed()

        return await ctx.send(content="Base Added!",embed=embed)
















