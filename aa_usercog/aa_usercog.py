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

from .userprofile_functions import userprofile_main
from .leaderboard_functions import leaderboard_warlord, leaderboard_heistlord, leaderboard_clangames, leaderboard_donations

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, eclipse_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select, paginate_embed
from aa_resourcecog.constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league, clan_castle_size, army_campsize, badge_emotes, xp_rank_roles
from aa_resourcecog.notes import aNote
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan, get_clan_members
from aa_resourcecog.player import aClashSeason, aPlayer, aClan, aMember
from aa_resourcecog.clan_war import aClanWar
from aa_resourcecog.raid_weekend import aRaidWeekend
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing

from aa_resourcecog.eclipse_functions import eclipse_main_menu, eclipse_base_vault, eclipse_army_analyzer, eclipse_army_analyzer_main, get_eclipse_bases, eclipse_personal_vault, eclipse_personal_bases
from aa_resourcecog.eclipse_classes import EclipseSession, eWarBase

class AriXMemberCommands(commands.Cog):
    """AriX Clash of Clans Members' Module."""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=2170311125702803,force_registration=True)
        default_global = {}
        default_guild = {}
        defaults_user = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**defaults_user)

    @commands.command(name="nickname")
    async def user_setnickname(self,ctx):
        """
        Change your server nickname.

        Your server nickname can be changed to match one of your registered accounts.
        """
        user_id = ctx.author.id

        member = await aMember.create(ctx,user_id=user_id)

        try:
            await member.set_nickname(ctx,selection=True)
        except Exception as e:
            embed = await clash_embed(ctx,
                message=f"Oops! I don't seem to have permissions to change your nickname.\n\n`{e}`")

    @commands.command(name="register")
    async def user_add_guest_account(self,ctx):
        """
        Register a Guest account to the Alliance.

        This lets our Leaders know who you are should you visit our clans.
        """

        def dm_check(m):
            return m.author == ctx.author and m.guild is None

        embed = await clash_embed(ctx,message="I will DM you to continue the linking process. Please ensure your DMs are open!")
        init_msg = await ctx.send(content=ctx.author.mention,embed=embed)

        try:
            embed = await clash_embed(ctx,
                message="Let's link your non-Member Clash accounts to AriX as Guest accounts. "
                    + "This will let you bring these accounts into our clans.\n\n"
                    + "**Please send any message to continue.**")
            await ctx.author.send(f"Hello, {ctx.author.mention}!",embed=embed)
        except Exception as e:
            embed = await clash_embed(ctx,
                message="I couldn't DM you to start the linking process. Please ensure your DMs are open.",
                color='fail')

            await init_msg.edit(content=ctx.author.mention,embed=embed)
            return

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
            return await ctx.author.send(embed=timeout_embed)

        new_tag = coc.utils.correct_tag(msg_player_tag.content)
        if not coc.utils.is_valid_tag(new_tag):
            embed = await clash_embed(ctx,
                message="This tag seems to be invalid. Please try again by using the `register` command from the AriX server.",
                color="fail")
            return await ctx.author.send(embed=embed)

        try:
            new_account = await aPlayer.create(ctx,tag=new_tag)
        except Exception as e:
            return await error_end_processing(ctx,
                preamble=f"Error encountered while fetching this account.",
                err=e)

        if new_account.is_member:
            embed = await clash_embed(ctx,
                message="**This account is already an AriX Member** and cannot be registered as a Guest Account."
                    + f"\n\nInstead, I will overwrite the Discord Link on other Clash Bots. Please confirm if I should proceed."
                    + f"\n\nYou tried to register: **{new_account.tag} {new_account.name}**")

            c_msg = await ctx.author.send(embed=embed)

            if not await user_confirmation(ctx,c_msg):
                return

            await c_msg.delete()

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

        api_token = str(msg_api_token.content)

        embed = await clash_embed(ctx,
            message="Verifying... please wait.")
        waitmsg = await ctx.author.send(embed=embed)

        try:
            verify = await ctx.bot.coc_client.verify_player_token(player_tag=new_account.tag,token=api_token)
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
            linked = False
            try:
                await ctx.bot.discordlinks.add_link(new_account.tag,ctx.author.id)
                linked = True
            except:
                pass

            if new_account.is_member:
                player_embed = await clash_embed(ctx,
                    message=f"The account **{new_account.tag} {new_account.name}** is now linked to {ctx.author.mention}.",
                    color='success')
            else:
                try:
                    await new_account.new_member(ctx,ctx.author)
                except Exception as e:
                    err_embed = await clash_embed(ctx,message=f"I ran into a problem while saving your account. I've contacted my masters.",color='fail')
                    await ctx.author.send(embed=err_embed)
                    return await ctx.bot.send_to_owners(f"I ran into an error while adding {new_account.tag} {new_account.name} as a Guest account for {ctx.author.mention}.\n\nError: ```{e}```")

                player_embed = await clash_embed(ctx,
                    message=f"You've successfully linked the account **{new_account.tag} {new_account.name}** to AriX!",
                    color='success')

            await waitmsg.delete()
            return await ctx.author.send(embed=player_embed)

    @commands.command(name="arix")
    async def arix_information(self,ctx):
        """
        Lists all clans in the Alliance.
        """

        alliance_clans = [c for c in [ctx.bot.clan_cache[c_tag] for c_tag in list(ctx.bot.clan_cache)] if c.is_alliance_clan]

        if not alliance_clans:
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

            rEmbed.add_field(
                name=f"{c.emoji} **{c.name}**",
                value=f"\nLeader: <@{c.leader}>"
                    + f"\n{c.desc_full_text}"
                    + f"\n\n> **Recruiting: {th_str}**"
                    + f"\n\n{c.description}\n\u200b",
                inline=False)

        return await ctx.send(embed=rEmbed)

    @commands.command(name="getclan",aliases=['as','pa','ao9','pr','don','dop','ao2','ae'])
    async def clan_information(self,ctx,*tags):
        """
        Gets information about a specified clan.
        """

        tag_run = []
        tag_run.append(ctx.invoked_with)

        if tags:
            for tag in tags:
                if tag not in tag_run:
                    tag_run.append(tag)

        clans = []

        for t in tag_run:
            if t in ['as','pa','ao9','pr']:
                c1 = await get_alliance_clan(ctx,t.upper())
                clans.append(c1[0])

            elif t in ['don','dop','ao2','ae']:
                tag_dict = {
                    'don': '#8089PGLQ',
                    'dop': '#2Y0VPJUVJ',
                    'ao2': '#2P90Y0JLP',
                    'ae': '#2QGGRUPYU',
                    }
                c2 = await aClan.create(ctx,tag_dict[t])
                clans.append(c2)

            else:
                t2 = coc.utils.correct_tag(t)
                if not coc.utils.is_valid_tag(t2):
                    continue
                try:
                    c = await aClan.create(ctx,t2)
                except Exception as e:
                    continue
                clans.append(c)

        for c in clans:
            clan_str = ""
            clan_str += c.desc_summary_text

            if len(c.recruitment_level) > 0:
                clan_str += "\n\nRecruiting: "
                for th in c.recruitment_level:
                    clan_str += f"{emotes_townhall[th]} "

            clan_str += f"\n\n**[Clan Link: {c.tag}]({c.share_link})**"
            clan_str += f"\n\n{c.description}"

            rEmbed = await clash_embed(ctx=ctx,
                title=f"{c.emoji} {c.desc_title}",
                message=clan_str,
                thumbnail=c.badge,
                show_author=False)

            await ctx.send(embed=rEmbed)


    @commands.command(name="profile")
    async def arix_profile(self,ctx,Discord_User:discord.User=None):
        """
        Gets a User's AriX Profile.
        """

        output_embed = []

        user = Discord_User
        if not user:
            user = ctx.author

        member = await aMember.create(ctx,user_id=user.id)

        is_staff = False

        leader_msg = ""
        coleader_msg = ""
        elder_msg = ""

        if len(member.leader_clans) > 0:
            is_staff = True
            for c in member.leader_clans:
                leader_msg += f"\n<:Leader:1047060798192754688> **Leader of {c.name}**"

        if len(member.coleader_clans) > 0:
            is_staff = True
            for c in member.coleader_clans:
                coleader_msg += f"\n{c.emoji} *Co-Leader of {c.name}*"

        if len(member.elder_clans) > 0:
            is_staff = True
            for c in member.elder_clans:
                elder_msg += f"\n{c.emoji} Elder of {c.name}"

        staff_msg = leader_msg + coleader_msg + elder_msg

        has_badge = False
        badge_msg = ""

        if not member.discord_member:
            await member.fetch_discord_user(ctx)

        roles_sorted = sorted(member.discord_member.roles,key=lambda x:(x.position),reverse=True)

        for i in list(badge_emotes.keys()):
            if i in [role.id for role in roles_sorted]:
                has_badge = True
                badge_msg += f"{badge_emotes[i]} "

        try:
            for c in member.home_clans:
                has_badge = True
                badge_msg += f"{c.emoji} "
        except:
            pass

        profile_msg = ""
        if has_badge:
            profile_msg += f"{badge_msg}\n"

        rank_role = [role for role in member.discord_member.roles if role.id in xp_rank_roles]
        if len(rank_role) > 0:
            profile_msg += f" \n`{rank_role[0].name}`"

        if is_staff:
            profile_msg += f"\n{staff_msg}"

        #profile_msg += "\n\n**Joined AriX (Server)**"
        #profile_msg += f"\n<a:aa_AriX:1031773589231374407> {discord_member.joined_at.strftime('%d %b %Y')}"

        if member.discord_member.premium_since:
            profile_msg += f"\n<:ServerBooster:1047016978759553056> Boosting AriX since {member.discord_member.premium_since.strftime('%d %b %Y')}"

        embed_color_role = [r for r in roles_sorted if r.color.value]

        if len(embed_color_role)>0:
            embed_color = embed_color_role[0].color
        else:
            embed_color = None

        member_embed = await clash_embed(ctx,
            title=f"{member.discord_member.display_name}",
            message=f"{profile_msg}\n\u200b",
            thumbnail=member.discord_member.avatar_url,
            color=embed_color)

        try:
            accounts_ct = 0
            for a in member.accounts:
                accounts_ct += 1
                member_embed.add_field(
                    name=f"{a.desc_title}",
                    value=f"{a.home_clan.emoji} {a.town_hall.emote} {a.town_hall.description}\u3000{emotes_league[a.league.name]} {a.trophies} (best: {a.best_trophies})\n{a.hero_description}\n[Player Link: {a.tag}]({a.share_link})\n\u200b",
                    inline=False)
        except:
            pass

        await ctx.send(embed=member_embed)


    @commands.command(name="player")
    async def arix_player(self,ctx,*tags_or_user_mention):
        """
        Get Player Stats for yourself or for a Clash of Clans account.

        You can provide multiple tags in a single command.
        If no tags are provided, will return all of your accounts registered with AriX.
        """

        member = None
        player_tags = []
        output_embed = []
        accounts = []

        if len(tags_or_user_mention) == 0:
            member = await aMember.create(ctx,user_id=ctx.author.id)
        else:
            try:
                check_for_discord_mention = int(re.search('@(.*)>',tags_or_user_mention[0]).group(1))
                member = await aMember.create(ctx,user_id=check_for_discord_mention)
            except:
                member = None

        if not member:
            for t in tags_or_user_mention:
                t = coc.utils.correct_tag(t)
                if not coc.utils.is_valid_tag(t):
                    continue

                try:
                    p = await aPlayer.create(ctx,tag=t)
                except Exception as e:
                    eEmbed = await clash_embed(ctx,message=e,color='fail')
                    return await ctx.send(embed=eEmbed)
                accounts.append(p)

        elif member:
            accounts = member.accounts

        if not accounts:
            no_account_embed = await clash_embed(ctx,message="I couldn't find any accounts to show. Check your input, maybe?")
            return await ctx.send(embed=no_account_embed)

        for a in accounts:
            member_status = ""
            if a.is_member:
                member_status = f"***{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}***\n"
            elif a.is_arix_account:
                member_status = f"***<a:aa_AriX:1031773589231374407> AriX Guest Account***\n"

            discord_msg = ""
            if a.discord_user:
                discord_msg += f"\n<:Discord:1040423151760314448> <@{a.discord_user}>"

            if a.league.name == 'Unranked':
                league_img = "https://i.imgur.com/TZF5r54.png"
            else:
                league_img = a.league.icon.medium

            pEmbed = await clash_embed(
                ctx=ctx,
                title=f"**{a.name}** ({a.tag})",
                message=f"{member_status}"
                    + f"<:Exp:825654249475932170>{a.exp_level}\u3000<:Clan:825654825509322752> {a.clan_description}"
                    + f"{discord_msg}",
                url=f"{a.share_link}",
                thumbnail=league_img)

            if len(accounts) > 1:
                pEmbed.set_footer(text=f"({accounts.index(a)+1} of {len(accounts)}) -- AriX Alliance | Clash of Clans",icon_url="https://i.imgur.com/TZF5r54.png")

            base_strength = f"<:TotalTroopStrength:827730290491129856> {a.troop_strength} / {a.max_troop_strength} *(rushed: {a.troop_rushed_pct}%)*"
            if a.town_hall.level >= 5:
                base_strength += f"\n<:TotalSpellStrength:827730290294259793> {a.spell_strength} / {a.max_spell_strength} *(rushed: {a.spell_rushed_pct}%)*"
            if a.town_hall.level >= 7:
                base_strength += f"\n<:TotalHeroStrength:827730291149635596> {a.hero_strength} / {a.max_hero_strength} *(rushed: {a.hero_rushed_pct}%)*"
            base_strength += "\n\u200b"

            currently_boosting = [f"{emotes_army[t.name]}" for t in a.troops if t.is_super_troop]

            home_village_str = f"{a.town_hall.emote} {a.town_hall.description}\u3000{emotes_league[a.league.name]} {a.trophies} (best: {a.best_trophies})"
            home_village_str +=f"\n**Heroes**\n{a.hero_description}"

            space = "\u3000"

            if len(currently_boosting) > 0:
                home_village_str += f"\n**Super Troops Active**\n{space.join(currently_boosting)}"

            home_village_str += f"\n**Strength**"
            home_village_str += f"\n{base_strength}"

            pEmbed.add_field(
                name="**Home Village**",
                value=home_village_str,
                inline=False)

            if a.is_member:
                home_clan_str = ""
                if a.home_clan.tag:
                    d, h, m, s = await convert_seconds_to_str(ctx,a.current_season.time_in_home_clan)
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

                clangames_str = f"<:ClanGames:834063648494190602> {a.current_season.clangames.score:,}"

                if a.current_season.clangames.ending_time > 0:
                    clangames_str += " (:stopwatch:"

                    cd, ch, cm, cs = await convert_seconds_to_str(ctx,(a.current_season.clangames.ending_time-a.current_season.clangames.games_start))
                    if cd > 0:
                        clangames_str += f" {int(cd)}d"
                    if ch > 0:
                        clangames_str += f" {int(ch)}h"
                    if cm > 0:
                        clangames_str += f" {int(cm)}m"

                    clangames_str += ")"

                pEmbed.add_field(
                    name=f"**Current Season Stats with AriX**",
                    value=f"{home_clan_str}"
                        + f"\n\n**Attacks Won**"
                        + f"\n<:Attack:828103854814003211> {a.current_season.attacks.statdisplay}"
                        + f"\n**Defenses Won**"
                        + f"\n<:Defense:828103708956819467> {a.current_season.defenses.statdisplay}"
                        + f"\n**Donations**"
                        + f"\n<:donated:825574412589858886> {a.current_season.donations_sent.statdisplay}\u3000<:received:825574507045584916> {a.current_season.donations_rcvd.statdisplay}"
                        + f"\n**Loot**"
                        + f"\n<:gold:825613041198039130> {a.current_season.loot_gold.statdisplay}\u3000<:elixir:825612858271596554> {a.current_season.loot_elixir.statdisplay}\u3000<:darkelixir:825640568973033502> {a.current_season.loot_darkelixir.statdisplay}"
                        + f"\n**Clan Capital**"
                        + f"\n<:CapitalGoldContributed:971012592057339954> {a.current_season.capitalcontribution.statdisplay}\u3000<:CapitalRaids:1034032234572816384> {a.current_season.raid_stats.raids_participated}\u3000<:RaidMedals:983374303552753664> {a.current_season.raid_stats.medals_earned:,}"
                        + f"\n**War Performance**"
                        + f"\n<:TotalWars:827845123596746773> {a.current_season.war_stats.wars_participated}\u3000<:WarStars:825756777844178944> {a.current_season.war_stats.offense_stars}\u3000<:Triple:1034033279411687434> {a.current_season.war_stats.triples}\u3000<:MissedHits:825755234412396575> {a.current_season.war_stats.unused_attacks}"
                        + f"\n**Clan Games**"
                        + f"\n{clangames_str}\n\u200b",
                    inline=False)

            else:
                pEmbed.add_field(
                    name=f"**Season Activity**",
                    value=f"**Attacks Won**"
                        + f"\n<:Attack:828103854814003211> {a.attack_wins}"
                        + f"\n**Defenses Won**"
                        + f"\n<:Defense:828103708956819467> {a.defense_wins}"
                        + f"\n**Donations**"
                        + f"\n<:donated:825574412589858886> {a.donations}\u3000<:received:825574507045584916> {a.received}\n\u200b",
                    inline=False)

                for achievement in a.achievements:
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
                        + f"\n<:CapitalGoldContributed:971012592057339954> {numerize.numerize(a.clan_capital_contributions,1)}\u3000<:CapitalRaids:1034032234572816384> {numerize.numerize(capitalraided_value,1)}"
                        + f"\n**War Stats**"
                        + f"\n<:WarStars:825756777844178944> {a.war_stars:,}\u3000<:ClanWarLeagues:825752759948279848> {warleague_value:,}"
                        + f"\n**Clan Games**"
                        + f"\n<:ClanGames:834063648494190602> {clangames_value:,}\n\u200b")

            nav_str = ""
            if a.is_member:
                nav_str += "<:ClanWars:825753092230086708> To view AriX War Log\n"
                nav_str += "<:CapitalRaids:1034032234572816384> To view AriX Raid Log\n"
            nav_str += "<:laboratory:1044904659917209651> To view current Troop Levels\n"
            #nav_str += "<:laboratory:1044904659917209651> To view remaining Lab Upgrades\n"
            nav_str += "???? To view Rushed Levels"

            if (ctx.bot.leader_role in ctx.author.roles or ctx.bot.coleader_role in ctx.author.roles) and len(a.notes)>0:
                nav_str += f"\n\n:mag: View Member Notes ({len(a.notes)})"

            if len(accounts) > 1:
                nav_str += "\n\n<:to_previous:1041988094943035422> Previous Account\n<:to_next:1041988114308137010> Next Account"

            pEmbed.add_field(
                name="Navigation",
                value=nav_str,
                inline=False)

            output_embed.append(pEmbed)

        await userprofile_main(ctx,output_embed,accounts)

    @commands.command(name="leaderboard",aliases=['leaderboards','lb'])
    async def arix_leaderboard(self,ctx,season='current'):
        """
        Alliance Leaderboards for Warlords, Heistlords, and Clan Games.
        """

        user = ctx.bot.get_user(ctx.author.id)

        if season == 'current':
            season = ctx.bot.current_season
        else:
            season = aClashSeason(season)

        navigation = []
        navigation_str = ""
        warlord_dict = {
            'id': 'warlord',
            'emoji': "<:Warlords:1054422701793611856>",
            'title': "",
            }
        navigation_str += f"<:Warlords:1047016981066436628> Warlord Leaderboard\n"
        navigation.append(warlord_dict)

        heistlord_dict = {
            'id': 'heistlord',
            'emoji': "<:Heistlords:1054422607933493270>",
            'title': "",
            }
        navigation_str += f"<:Heistlord:1047018048088965150> Heistlord Leaderboard\n"
        navigation.append(heistlord_dict)

        donations_dict = {
            'id': 'donations',
            'emoji': '<:clancastle:1054612010840641536>',
            'title': ''
            }
        navigation_str += f"<:clancastle:1054612010840641536> Donations Leaderboard\n"
        navigation.append(donations_dict)

        clangames_dict = {
            'id': 'clangames',
            'emoji': "<:ClanGames:834063648494190602>",
            'title': "",
            }
        navigation_str += f"<:ClanGames:834063648494190602> Clan Games Leaderboard\n"
        navigation.append(clangames_dict)

        menu_state = True
        menu_option = 'start'
        menu_message = None

        while menu_state:
            if menu_option in ['warlord','start']:
                warlord = await leaderboard_warlord(ctx,season)
                warlord.add_field(
                    name="**Navigation**",
                    value=navigation_str)

                if menu_message:
                    await menu_message.edit(embed=warlord)
                else:
                    menu_message = await ctx.send(embed=warlord)

                try:
                    await menu_message.remove_reaction("<:Warlords:1054422701793611856>",user)
                except:
                    pass

            if menu_option in ['heistlord']:
                heistlord = await leaderboard_heistlord(ctx,season)
                heistlord.add_field(
                    name="**Navigation**",
                    value=navigation_str)

                if menu_message:
                    await menu_message.edit(embed=heistlord)
                else:
                    menu_message = await ctx.send(embed=heistlord)

                try:
                    await menu_message.remove_reaction("<:Heistlords:1054422607933493270>",user)
                except:
                    pass

            if menu_option in ['clangames']:
                clangames = await leaderboard_clangames(ctx,season)
                clangames.add_field(
                    name="**Navigation**",
                    value=navigation_str)

                if menu_message:
                    await menu_message.edit(embed=clangames)
                else:
                    menu_message = await ctx.send(embed=clangames)

                try:
                    await menu_message.remove_reaction("<:ClanGames:834063648494190602>",user)
                except:
                    pass

            if menu_option in ['donations']:
                donations = await leaderboard_donations(ctx,season)
                donations.add_field(
                    name="**Navigation**",
                    value=navigation_str)

                if menu_message:
                    await menu_message.edit(embed=donations)
                else:
                    menu_message = await ctx.send(embed=donations)

                try:
                    await menu_message.remove_reaction("<:clancastle:1054612010840641536>",user)
                except:
                    pass

            selection = await multiple_choice_menu_select(ctx,menu_message,navigation,300)
            if selection:
                menu_option = selection['id']
            else:
                menu_state = False

        if menu_message:
            try:
                await menu_message.clear_reactions()
            except:
                pass

    @commands.command(name="clanstats",aliases=['donations','warstats','raidstats','clangames'])
    async def arix_clanstats(self,ctx,season='current'):
        """
        Displays stats for Clans.
        """

        user = ctx.author

        if ctx.invoked_with == 'clanstats':
            return await ctx.send("To use this command, run either `donations`, `warstats`, `raidstats` or `clangames`.")

        alliance_clans = [c for c in [ctx.bot.clan_cache[c_tag] for c_tag in list(ctx.bot.clan_cache)] if c.is_alliance_clan]
        alliance_clans = sorted(alliance_clans,key=lambda x:(x.level,x.capital_hall),reverse=True)

        if season == 'current':
            season = ctx.bot.current_season
        else:
            if season not in [season.id for season in ctx.bot.tracked_seasons]:
                return await ctx.send(f"The season `{season}` is not valid.")

            season = aClashSeason(season)

        menu = []

        for clan in alliance_clans:
            select_menu = {
                'id': clan.tag,
                'emoji': clan.emoji,
                'title': "",
                }
            menu.append(select_menu)

        menu_state = True
        clan_select = None
        message = None

        while menu_state:

            if not clan_select:
                clan_select = alliance_clans[0]

            clan_members = []
            for tag in list(ctx.bot.member_cache):

                member = ctx.bot.member_cache[tag]

                if season.id == ctx.bot.current_season.id:
                    season_member = member.current_season
                else:
                    try:
                        season_member = member.season_data[season.id]
                    except KeyError:
                        continue

                if season_member.is_member and season_member.home_clan.tag == clan_select.tag:
                    clan_members.append(season_member)
                else:
                    continue

            if ctx.invoked_with == 'donations':
                clan_members = sorted(clan_members,key=lambda x:(x.donations_sent.season,x.town_hall),reverse=True)

                rcvd_total = 0
                sent_total = 0

                stats_embed_str = f"{'TH':<2}{'':>2}{'SENT':>8}{'':^2}{'RCVD':>8}{'':^2}"
                for m in clan_members:
                    sent_total += m.donations_sent.season
                    rcvd_total += m.donations_rcvd.season

                    sent = f"{m.donations_sent.season:,}"
                    rcvd = f"{m.donations_rcvd.season:,}"

                    stats_embed_str += f"\n"
                    stats_embed_str += f"{m.town_hall:^2}{'':^2}"
                    stats_embed_str += f"{sent:>8}{'':^2}"
                    stats_embed_str += f"{rcvd:>8}{'':^2}"
                    stats_embed_str += f"{m.player.name}"

                clan_stats_embed = await clash_embed(ctx,
                    title=f"{clan_select.emoji} {clan_select.name} ({clan_select.tag})",
                    message=f"**Donations for {season.season_description} Season**"
                        + f"\n\nSent: {sent_total:,}\u3000|\u3000 Rcvd: {rcvd_total:,}"
                        + f"\n\n```{stats_embed_str}```")

            if ctx.invoked_with == 'warstats':
                clan_members = sorted(clan_members,key=lambda x:(x.town_hall,x.war_stats.wars_participated),reverse=True)

                average_stars = 0
                average_destruction = 0

                total_attacks = 0
                total_triples = 0
                total_stars = 0
                total_destruction = 0
                total_unused = 0

                stats_embed_str = f"{'TH':>2}{'':^2}{'WARS':>4}{'':^2}{'ATTKS':>5}{'':^2}{'TRP':>3}{'':^2}{'STRS':<4}{'':^2}{'DEST':<5}{'':^2}{'TIME':<4}{'':^2}"
                for m in clan_members:

                    ws = m.war_stats

                    total_attacks += ws.attack_count
                    total_triples += ws.triples
                    total_stars += ws.offense_stars
                    total_destruction += ws.offense_destruction
                    total_unused += ws.unused_attacks

                    attack_str = f"{ws.attack_count}/{ws.attack_count+ws.unused_attacks}"

                    stats_embed_str += f"\n"
                    stats_embed_str += f"{m.town_hall:^2}{'':^2}"
                    stats_embed_str += f"{ws.wars_participated:>4}{'':^2}"
                    stats_embed_str += f"{attack_str:>5}{'':^2}"
                    stats_embed_str += f"{ws.triples:>3}{'':^2}"
                    stats_embed_str += f"{ws.offense_stars:>4}{'':^2}"
                    stats_embed_str += f"{str(ws.offense_destruction)+'%':>5}{'':^2}"
                    stats_embed_str += f"{int(ws.average_attack_duration):>4}{'':^2}"

                    stats_embed_str += f"{m.player.name}"

                if total_attacks > 0:
                    average_stars = round(total_stars / total_attacks,1)
                    average_destruction = int(total_destruction / total_attacks)

                clan_stats_embed = await clash_embed(ctx,
                    title=f"{clan_select.emoji} {clan_select.name} ({clan_select.tag})",
                    message=f"**War Stats for {season.season_description} Season**"
                        + f"\n- Attacks (ATTKS) are shown as `Used/Total Available`."
                        + f"\n- TRP = War Triples. Only on bases of equivalent or higher Town Hall."
                        + f"\n\nTotal Attacks: {total_attacks}\u3000|\u3000Total Triples: {total_triples}"
                        + f"\nAverage per Attack: {average_stars} <:WarStars:825756777844178944>\u3000{average_destruction} :fire:"
                        + f"\n\n```{stats_embed_str}```")

            if ctx.invoked_with == 'raidstats':
                clan_members = sorted(clan_members,key=lambda x:(x.raid_stats.raids_participated,x.raid_stats.resources_looted,x.town_hall),reverse=True)

                total_attacks = 0
                total_loot = 0

                average_loot = 0

                stats_embed_str = f"{'RAIDS':>5}{'':^2}{'ATTKS':>6}{'':^2}{'LOOT':>6}{'':^2}{'MEDALS':<6}{'':^2}"
                for m in clan_members:

                    rs = m.raid_stats
                    other_clan_raids = [r for r in [m.raidlog[rid] for rid in list(m.raidlog)] if r.clan_tag != clan_select.tag]

                    total_attacks += rs.raid_attacks
                    total_loot += rs.resources_looted

                    if len(other_clan_raids) > 0:
                        attack_str = f"*{rs.raid_attacks}/{rs.raids_participated*6}"
                    else:
                        attack_str = f"{rs.raid_attacks}/{rs.raids_participated*6}"

                    stats_embed_str += f"\n"
                    stats_embed_str += f"{rs.raids_participated:>5}{'':^2}"
                    stats_embed_str += f"{attack_str:>6}{'':^2}"
                    stats_embed_str += f"{rs.resources_looted:>6}{'':^2}"
                    stats_embed_str += f"{rs.medals_earned:>6}{'':^2}"

                    stats_embed_str += f"{m.player.name}"

                if total_attacks > 0:
                    average_loot = int(total_loot / total_attacks)

                clan_stats_embed = await clash_embed(ctx,
                    title=f"{clan_select.emoji} {clan_select.name} ({clan_select.tag})",
                    message=f"**Capital Raid Stats for {season.season_description} Season**"
                        + f"\n- Attacks (ATTKS) are shown as `Used/Total Available` (assuming 6 attacks per Capital Raid)."
                        + f"\n- Asterisk (*) denotes that this player has done 1 or more Capital Raids in another clan."
                        + f"\n\nTotal Attacks: {total_attacks}\u3000|\u3000Total Loot: {total_loot:,} <:CapitalGoldLooted:1045200974094028821>"
                        + f"\nAverage per Attack: {average_loot:,} <:CapitalGoldLooted:1045200974094028821>"
                        + f"\n\n```{stats_embed_str}```")

            if ctx.invoked_with == 'clangames':
                if time.time() < season.clangames_start:
                    clan_stats_embed = await clash_embed(ctx,
                        title=f"{clan_select.emoji} {clan_select.name} ({clan_select.tag})",
                        message=f"**Clan Games Stats for {season.season_description} Season**"
                            + f"\n\nClan Games has not started for this season. The games will start on:"
                            + f"\n\n<t:{season.clangames_start}:F>")

                clan_members = sorted(clan_members,key=lambda x:(x.clangames.score,(x.clangames.ending_time*-1),x.town_hall),reverse=True)

                total_score = 0

                stats_embed_str = f"{'TH':>2}{'':>2}{'SCORE':>5}{'':^2}{'TIME':>10}{'':^2}"
                for m in clan_members:

                    cg = m.clangames
                    ct = ""
                    if cg.ending_time:
                        cd, ch, cm, cs = await convert_seconds_to_str(ctx,(cg.ending_time-cg.games_start))
                        if cd > 0:
                            ct += f"{int(cd)}d "
                        if ch > 0:
                            ct += f"{int(ch)}h "
                        if cm > 0:
                            ct += f"{int(cm)}m"

                    total_score += cg.score

                    stats_embed_str += f"\n"
                    stats_embed_str += f"{m.town_hall:^2}{'':^2}"
                    stats_embed_str += f"{cg.score:>5}{'':^2}"
                    stats_embed_str += f"{ct:>10}{'':^2}"

                    stats_embed_str += f"{m.player.name}"

                clan_stats_embed = await clash_embed(ctx,
                    title=f"{clan_select.emoji} {clan_select.name} ({clan_select.tag})",
                    message=f"**Clan Games Stats for {season.season_description} Season**"
                        + f"\n\nTotal Points: {total_score:,}"
                        + f"\n\n```{stats_embed_str}```")

            if message:
                await message.edit(embed=clan_stats_embed)
            else:
                message = await ctx.send(embed=clan_stats_embed)

            selection = await multiple_choice_menu_select(ctx,message,menu,300)
            if selection:
                clan_select = [c for c in alliance_clans if c.tag == selection['id']][0]
                await message.remove_reaction(selection['emoji'],user)
            else:
                menu_state = False

        if message:
            try:
                await message.clear_reactions()
            except:
                pass

    @commands.group(name="eclipse",autohelp=False)
    async def eclipse_group(self,ctx):
        """
        Access E.C.L.I.P.S.E.

        An **E**xtraordinarily **C**ool **L**ooking **I**nteractive & **P**rofessional **S**earch **E**ngine.
        Your Clash of Clans database of attack strategies, guides and war bases.
        """

        if not ctx.invoked_subcommand:

            #check if user has open session
            existing_session = [s for s in ctx.bot.clash_eclipse_sessions if s.user.id == ctx.author.id]
            if len(existing_session) > 0:
                embed = await eclipse_embed(ctx,
                    message=f"You already have an E.C.L.I.P.S.E. session open in <#{existing_session[0].channel.id}>.\n\nPlease end this session before starting a new one.")

                await ctx.send(content=ctx.author.mention,embed=embed,delete_after=30)
                await ctx.message.delete()
                return

            #start new session
            response = "start"
            session = EclipseSession(ctx)
            tries = 10

            #add session to active list
            ctx.bot.clash_eclipse_sessions.append(session)

            while session.state:
                tries -= 1
                try:
                    session.add_to_path(response)
                    if response in ['start','menu']:
                        tries = 10
                        response = await eclipse_main_menu(ctx,session)

                    if response == 'personalvault':
                        tries = 10
                        try:
                            await ctx.message.delete()
                        except:
                            pass
                        response = await eclipse_personal_bases(ctx,session)

                    if response == 'mybases':
                        tries = 10
                        try:
                            await ctx.message.delete()
                        except:
                            pass
                        response = await eclipse_personal_bases(ctx,session)

                    #Base Vault: Townhall Selection
                    if response in ['basevault','basevaultnone']:
                        tries = 10
                        if response == 'basevaultnone':
                            response = await eclipse_base_vault(ctx,session,base_th_select)
                        else:
                            response = await eclipse_base_vault(ctx,session)

                        if not response or response == 'menu':
                            pass
                        else:
                            base_th_select = response
                            response = 'basevaultselect'

                    #Base Vault: View Bases / Category Selection
                    if response in ['basevaultselect']:
                        tries = 10
                        response = await get_eclipse_bases(ctx,session,base_th_select)

                    if response == 'armyanalyze':
                        tries = 10
                        response = await eclipse_army_analyzer(ctx,session)

                        if not response or response in ['menu','armyanalyze']:
                            pass
                        else:
                            army_analyze_th_select = response
                            response = 'armyanalyzerselect'

                    if response in ['armyanalyzerselect']:
                        tries = 10
                        response = await eclipse_army_analyzer_main(ctx,session,army_analyze_th_select)

                    #if response == 'strategy':
                    #    await ctx.send("This bit doesn't exist yet.")
                    #    response = "menu"
                
                except Exception as e:
                    err_embed = await eclipse_embed(ctx,
                        message=f"**Error encountered during E.C.L.I.P.S.E. session.**"
                            + f"\n\nError: {e}"
                            + f"\n\nSession User: {session.user.mention}"
                            + f"\nSession ID: {session.channel.id}"
                            + f"\nResponse Path: {session.response_path}"
                            + f"\nLast Response: {response}")

                    await ctx.bot.send_to_owners(embed=err_embed)
                    response = None

                if tries == 0 or not response:
                    session.state = False
                    session_closed = await eclipse_embed(ctx,
                        message=f"Your **E.C.L.I.P.S.E.** session is closed. We hope to see you again!")

                    try:
                        ctx.bot.clash_eclipse_sessions.remove(session)
                    except:
                        pass

                    if session.guild and session.message:
                        await session.message.clear_reactions()
                        await session.message.edit(content=ctx.author.mention,embed=session_closed)
                    else:
                        if session.message:
                            try:
                                await session.message.delete()
                            except:
                                pass
                        await session.channel.send(content=ctx.author.mention,embed=session_closed)

            try:
                ctx.bot.clash_eclipse_sessions.remove(session)
            except:
                pass
            try:
                await ctx.message.delete()
            except:
                pass


    @eclipse_group.command(name="addbase")
    @commands.is_owner()
    async def eclipse_add_base(self,ctx):
        """
        Add a base to Eclipse.
        """

        if ctx.author.id not in ctx.bot.owner_ids:
            embed = await clash_embed(ctx,message="To use this command please contact <@644530507505336330>.")
            return await ctx.send(embed=embed)


        timeout_embed = await eclipse_embed(ctx,message=f"Operation timed out.")
        
        def baselink_check(m):
            msg_check = False
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    msg_check = True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    msg_check = True
            if msg_check:
                check_url = False
                try:
                    link_parse = urllib.parse.urlparse(m.content)
                    link_action = urllib.parse.parse_qs(link_parse.query)['action'][0]

                    if link_parse.netloc == "link.clashofclans.com" and link_action == "OpenLayout":
                        check_url = True
                except:
                    pass
                return check_url

        def armylink_check(m):
            msg_check = False
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    msg_check = True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    msg_check = True
            if msg_check:
                try:
                    link_parse = urllib.parse.urlparse(m.content)
                    link_action = urllib.parse.parse_qs(link_parse.query)['action'][0]

                    if link_parse.netloc == "link.clashofclans.com" and link_action == "CopyArmy":
                        check_url = True
                except:
                    pass
                return check_url

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
            title="Add Base -- Step 1/7",
            message=f"Please provide the Base Link.\n\nI will get the Base Townhall level from the link provided.")

        base_link_msg = await ctx.send(embed=base_link_embed)
        try:
            base_link_response = await ctx.bot.wait_for("message",timeout=60,check=baselink_check)
        except asyncio.TimeoutError:
            await base_link_msg.edit(embed=timeout_embed)
            return
        else:
            base_link = base_link_response.content
            link_parse = urllib.parse.urlparse(base_link)
            base_id = urllib.parse.quote_plus(urllib.parse.parse_qs(link_parse.query)['id'][0])
            try:
                base_townhall = int(base_id.split('TH',1)[1][:2])
            except:
                base_townhall = int(base_id.split('TH',1)[1][:1])

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
                'id': 'bp',
                'emoji': '<:BPBB:1043081040090107968>',
                'title': 'Blueprint Base Building',
                'description': None
                },
            {
                'id': 'other',
                'emoji': "<a:aa_AriX:1031773589231374407>",
                'title': "Others",
                'description': None
                }
            ]

        base_supplier_str = ""
        for i in base_supplier_list:
            base_supplier_str += f"{i['emoji']} {i['title']}\n\n"

        base_source_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 2/7",
            message=f"Where is this Base from?\n\u200b")

        base_source_embed.add_field(
            name="Select from the options below.",
            value=base_supplier_str)

        source_msg = await ctx.send(embed=base_source_embed)
        select_source = await multiple_choice_menu_select(
            ctx=ctx,
            smsg=source_msg,
            sel_list=base_supplier_list)

        await source_msg.delete()
        if not select_source:
            return
        base_source = f"{select_source['emoji']} {select_source['title']}"

        # BASE BUILDER
        base_builder_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 3/7",
            message=f"Provide the Name of the Builder. If no Builder is specified, please respond with an asterisk [`*`].")
        base_builder_msg = await ctx.send(embed=base_builder_embed)

        try:
            builder_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            await base_builder_msg.edit(embed=timeout_embed)
            return
        else:
            base_builder = builder_response.content
            await base_builder_msg.delete()
            await builder_response.delete()


        #BASE TYPE
        base_type_list = [
            {   
                'id': 'anti3',
                'title': 'War Base: Anti-3 Star',
                'description': None,
                'emoji': '<:3_Star:1043063806378651720>',
                },
            {
                'id': 'anti2',
                'title': 'War Base: Anti-2 Star',
                'description': None,
                'emoji': '<:Attack_Star:1043063829430542386>'
                },
            {
                'id': 'legends',
                'title': 'Legends Base',
                'description': None,
                'emoji': '<:legend_league_star:1043062895652655125>',
                },
            {
                'id': 'home',
                'title': 'Trophy/Farm Base',
                'description': None,
                'emoji': '<:HomeTrophies:825589905651400704>'
                },
            ]

        base_type_str = ""
        for i in base_type_list:
            base_type_str += f"{i['emoji']} {i['title']}\n\n"

        base_type_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 4/7",
            message=f"Select the type of base this is.\n\u200b")

        base_type_embed.add_field(
            name="Select from the options below.",
            value=base_type_str)

        base_type_msg = await ctx.send(embed=base_type_embed)

        select_type = await multiple_choice_menu_select(
            ctx=ctx,
            smsg=base_type_msg,
            sel_list=base_type_list)

        await base_type_msg.delete()
        if not select_type:
            return
        base_type = f"{select_type['title']}"


        #DEFENSIVE CC
        defensive_cc_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 5/7",
            message=f"Provide the Army Link for the Defensive Clan Castle.")
        defensive_cc_msg = await ctx.send(embed=defensive_cc_embed)
        try:
            army_link_response = await ctx.bot.wait_for("message",timeout=60,check=armylink_check)
        except asyncio.TimeoutError:
            await defensive_cc_msg.edit(embed=timeout_embed)
            return
        else:
            defensive_cc = army_link_response.content

            parsed_cc = ctx.bot.coc_client.parse_army_link(defensive_cc)
            cc_space = 0
            for troop in parsed_cc[0]:
                if troop[0].name in coc.HOME_TROOP_ORDER:
                    cc_space += (army_campsize[troop[0].name] * troop[1])

            if cc_space > clan_castle_size[base_townhall][0]:
                invalid_cc = await eclipse_embed(ctx,message=f"This Clan Castle composition has more troops than available for this Townhall level.")
                await ctx.send(embed=invalid_cc)
                return
            await defensive_cc_msg.delete()
            await army_link_response.delete()


        #BUIDLER NOTES
        builder_notes_embed = await eclipse_embed(ctx,
            title="Add Notes -- Step 6/7",
            message=f"Add any Notes from the Builder, if any. If there are no notes, please respond with an asterisk [`*`].")

        builder_notes_msg = await ctx.send(embed=builder_notes_embed)
        try:
            builder_notes_response = await ctx.bot.wait_for("message",timeout=120,check=response_check)
        except asyncio.TimeoutError:
            await builder_notes_msg.edit(embed=timeout_embed)
            return
        else:
            builder_notes = builder_notes_response.content
            await builder_notes_msg.delete()
            await builder_notes_response.delete()


        #BASE IMAGE
        base_image_embed = await eclipse_embed(ctx,
            title="Add Base -- Step 7/7",
            message=f"Upload the Base Image.")

        base_image_msg = await ctx.send(embed=base_image_embed)
        try:
            base_image_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
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
            notes=builder_notes,
            image_attachment=base_image)

        await new_base.save_to_json()

        embed,image = await new_base.base_embed(ctx)

        return await ctx.send(content="Base Added!",embed=embed,file=image)


    # @eclipse_group.command(name="addarmy", hidden=True)
    # async def eclipse_add_army(self,ctx):
    #     """
    #     Add an army to Eclipse.
    #     """

    #     timeout_embed = await eclipse_embed(ctx,message=f"Operation timed out.")

    #     def difficulty_check(m):
    #         msg_check = False
    #         if m.author.id == ctx.author.id:
    #             if m.channel.id == ctx.channel.id:
    #                 msg_check = True
    #             elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
    #                 msg_check = True
    #         if msg_check:
    #             try:
    #                 d_int = int(m.content)
    #             except:
    #                 return False
    #             else:
    #                 return 0 < d_int < 6

    #     def armylink_check(m):
    #         msg_check = False
    #         if m.author.id == ctx.author.id:
    #             if m.channel.id == ctx.channel.id:
    #                 msg_check = True
    #             elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
    #                 msg_check = True
    #         if msg_check:
    #             check_url = False
    #             try:
    #                 link_parse = urllib.parse.urlparse(m.content)
    #                 link_action = urllib.parse.parse_qs(link_parse.query)['action'][0]

    #                 if link_parse.netloc == "link.clashofclans.com" and link_action == "CopyArmy":
    #                     check_url = True
    #             except:
    #                 pass
    #             return check_url

    #     def response_check(m):
    #         if m.author.id == ctx.author.id:
    #             if m.channel.id == ctx.channel.id:
    #                 return True
    #             elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
    #                 return True
    #             else:
    #                 return False

    #     #ARMY NAME
    #     army_name_embed = await eclipse_embed(ctx,
    #         title="Add Army -- Step 1/8",
    #         message=f"**What is the name of this strategy?**")

    #     army_name_msg = await ctx.send(embed=army_name_embed)
    #     try:
    #         army_name_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
    #     except asyncio.TimeoutError:
    #         await army_name_msg.edit(embed=timeout_embed)
    #         return
    #     else:
    #         army_name = army_name_response.content
    #         await army_name_msg.delete()
    #         await army_name_response.delete()


    #     # TOWNHALL
    #     th_range = range(9,16)
    #     th_select = []

    #     for i in th_range:
    #         th_dict = {
    #             'id': i,
    #             'title': f'Townhall {i}',
    #             'emoji': emotes_townhall[i],
    #             'description': None
    #             }
    #         th_select.append(th_dict)

    #     townhall_level_embed = await eclipse_embed(ctx,
    #         title="Add Army -- Step 2/8",
    #         message=f"**What Townhall level is this Strategy designed for?**"
    #             + f"\n\n*Only 1 Townhall can be selected. Strategies at different Townhall Levels are considered separate strategies.*")

    #     select_townhall = await multiple_choice_select(
    #         ctx=ctx,
    #         sEmbed=townhall_level_embed,
    #         selection_list=th_select)

    #     if not select_townhall:
    #         return
    #     army_townhall = select_townhall['id']


    #     #3 ARMY LINK
    #     army_link_embed = await eclipse_embed(ctx,
    #         title="Add Army -- Step 3/8",
    #         message=f"**Provide the Army Link(s) for this Strategy.**"
    #             + f"\n\nYou may separate variations ")
    #     army_link_msg = await ctx.send(embed=army_link_embed)

    #     try:
    #         army_link_response = await ctx.bot.wait_for("message",timeout=60,check=armylink_check)
    #     except asyncio.TimeoutError:
    #         await army_author_msg.edit(embed=timeout_embed)
    #         return
    #     else:
    #         army_link = army_link_response.content
    #         await army_link_msg.delete()
    #         await army_link_response.delete()


    #     #4 CLAN CASTLE
    #     army_cc_embed = await eclipse_embed(ctx,
    #         title="Add Army -- Step 4/8",
    #         message=f"Provide the Army Link for the Clan Castle composition in this Army.")
    #     army_cc_msg = await ctx.send(embed=army_cc_embed)

    #     try:
    #         army_cc_response = await ctx.bot.wait_for("message",timeout=60,check=armylink_check)
    #     except asyncio.TimeoutError:
    #         await army_cc_msg.edit(embed=timeout_embed)
    #         return
    #     else:
    #         army_cc = army_cc_response.content

    #         parsed_cc = ctx.bot.coc_client.parse_army_link(army_cc)
    #         cc_troop_space = 0
    #         cc_siege_space = 0
    #         cc_spell_space = 0
    #         for troop in parsed_cc[0]:
    #             if troop[0].name in coc.HOME_TROOP_ORDER:
    #                 cc_troop_space += (army_campsize[troop[0].name] * troop[1])
    #             if troop[0].name in coc.SIEGE_MACHINE_ORDER:
    #                 cc_siege_space += (army_campsize[troop[0].name] * troop[1])
    #         for spell in parsed_cc[1]:
    #             if spell[0].name in coc.SPELL_ORDER:
    #                 cc_spell_space += (army_campsize[spell[0].name] * spell[1])

    #         if cc_troop_space > clan_castle_size[army_townhall][0] or cc_siege_space > clan_castle_size[army_townhall][2] or cc_spell_space > clan_castle_size[army_townhall][1]:
    #             invalid_cc = await eclipse_embed(ctx,message=f"This Clan Castle composition has more troops than available for this Townhall level.")
    #             await ctx.send(embed=invalid_cc)
    #             return

    #         await army_cc_msg.delete()
    #         await army_cc_response.delete()


    #     #5 DIFFICULTY
    #     army_difficulty_embed = await eclipse_embed(ctx,
    #         title="Add Army -- Step 5/8",
    #         message=f"From a range of `1` to `5`, rank the difficulty of this Army."
    #             + f"\n\n1 -- Not Difficult to Use, 5 -- Very Difficult to Use")
    #     army_difficulty_msg = await ctx.send(embed=army_difficulty_embed)

    #     try:
    #         army_difficulty_response = await ctx.bot.wait_for("message",timeout=60,check=difficulty_check)
    #     except asyncio.TimeoutError:
    #         await army_difficulty_msg.edit(embed=timeout_embed)
    #         return
    #     else:
    #         army_difficulty = army_difficulty_response.content

    #         await army_difficulty_msg.delete()
    #         await army_difficulty_response.delete()

    #     #6 VIDEO
    #     army_videos_embed = await eclipse_embed(ctx,
    #         title="Add Army -- Step 6/8",
    #         message=f"Provide up to 5 reference videos for this Army. Separate multiple videos with a space."
    #             +f"\n\nNote: Video links must start with `https://www.youtube.com/watch?` or `https://youtu.be/`. ")
    #     army_videos_msg = await ctx.send(embed=army_videos_embed)

    #     try:
    #         army_videos_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
    #     except asyncio.TimeoutError:
    #         await army_videos_msg.edit(embed=timeout_embed)
    #         return
    #     else:
    #         army_videos = []
    #         for v in army_videos_response.content.split():
    #             if urllib.parse.urlparse(v).netloc == "www.youtube.com":
    #                 b = f"https://youtu.be/{urllib.parse.parse_qs(urllib.parse.urlparse(v).query)['v'][0]}"
    #             elif urllib.parse.urlparse(v).netloc == "youtu.be":
    #                 b = f"https://youtu.be/{urllib.parse.urlparse(v).path.split('/')[1]}"
    #                 army_videos.append(v)

    #         await army_videos_msg.delete()
    #         await army_videos_response.delete()


    #     #7 DESCRIPTION
    #     army_description_embed = await eclipse_embed(ctx,
    #         title="Add Army -- Step 7/8",
    #         message=f"Provide a brief description for this Army. Use this space to include any tips/steps/etc.")
    #     army_description_msg = await ctx.send(embed=army_description_embed)

    #     try:
    #         army_description_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
    #     except asyncio.TimeoutError:
    #         await army_description_msg.edit(embed=timeout_embed)
    #         return
    #     else:
    #         army_description = army_description_response.content
    #         await army_description_msg.delete()
    #         await army_description_response.delete()


    #     #8 AUTHOR
    #     army_author_embed = await eclipse_embed(ctx,
    #         title="Add Army -- Step 7/8",
    #         message=f"Provide the Author of this Army.")
    #     army_author_msg = await ctx.send(embed=army_author_embed)

    #     try:
    #         army_author_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
    #     except asyncio.TimeoutError:
    #         await army_author_msg.edit(embed=timeout_embed)
    #         return
    #     else:
    #         army_author = army_author_response.content
    #         await army_author_msg.delete()
    #         await army_author_response.delete()


    #     async with ctx.bot.async_eclipse_lock:
    #         with ctx.bot.clash_eclipse_lock.write_lock():
    #             new_army = await eWarArmy.new_army(ctx=ctx,
    #                 name=army_name,
    #                 town_hall=army_townhall,
    #                 author=army_author,
    #                 difficulty=army_difficulty,
    #                 video=army_videos,
    #                 army_link=army_link,
    #                 cc_link=army_cc,
    #                 description=army_description,
    #                 )

    #             await new_army.save_to_json()

    #     embed = await new_army.army_embed(ctx)

    #     return await ctx.send(content="Army Added!",embed=embed)
