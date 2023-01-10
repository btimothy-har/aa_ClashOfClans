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

from .challengepass_functions import get_challenge_pass_season, aChallengePass

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, eclipse_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select, paginate_embed
from aa_resourcecog.constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league, clan_castle_size, army_campsize, badge_emotes, xp_rank_roles
from aa_resourcecog.notes import aNote
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan, get_clan_members
from aa_resourcecog.player import aClashSeason, aPlayer, aClan, aMember
from aa_resourcecog.clan_war import aClanWar
from aa_resourcecog.raid_weekend import aRaidWeekend
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing

challengePassDisplayName = {
    'farm': "The Farmer's Life",
    'war': "The Warpath"
    }

class AriXChallengePass(commands.Cog):
    """AriX Challenge Pass"""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=395141260680,force_registration=True)
        default_global = {}
        default_guild = {}
        defaults_user = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**defaults_user)

    @commands.command(name="slash_challengepass_info",hidden=True)
    async def slashwrapper_challengepass_information(self,ctx):
        s_embed = await clash_embed(ctx,message="<a:loading:1042769157248262154> Loading...")
        message = await ctx.send(embed=s_embed)

        embed = await clash_embed(ctx,
            title=f"**AriX Challenge Pass**",
            message=f"__Overview__"
                + f"\nThe AriX Challenge Pass is an on-going seasonal event open to AriX Members to participate. Each Challenge Pass season starts at the end of the CWL Period and lasts till the next CWL."
                + f"\n\n**Current Pass Season:** {ctx.bot.current_season.season_description}"
                + f"\n**Season Started:** <t:{int(ctx.bot.current_season.cwl_end)}:F>"
                + f"\n\n__Rewards__"
                + f"\n> - Top Player from each Challenge Track: 1x <:GoldPass:834093287106674698> Gold Pass (or 1 Month Nitro <a:nitro:1062371929337630770>)"
                + f"\n> - Every Player with 10K Challenge Points: 10,000XP + 1,000XP for every Reset Token unused"
                + f"\n\n__Commands__"
                + f"\n> `/challengepass`: Check/update your Challenge Pass. Manage your challenges."
                + f"\n> `/challengepass-info`: Display this message!"
                + f"\n> `/challengepass-leaderboard`: Retrieve the current leaderboard."
                + f"\n\u200b")

        embed.add_field(
            name=f"**How the Challenge Pass Works**",
            value=f"Earn Challenge Points to climb the seasonal leaderboards and win prizes!"
                + f"\n\nTo earn Challenge Points, complete as many Pass Challenges as you can within the season. Challenges award points based on varying difficulty and duration."
                + f"\n\n*Note: Challenge Passes are unique by Clash Account, and points do not stack across accounts.*\n\u200b",
            inline=False)

        embed.add_field(
            name=f"**About Challenge Tracks**",
            value=f"Choose between two Challenge Tracks: <:cp_war:1054997157654036561> `The Warpath` or <a:cp_farmer:1061676915724926986> `The Farmer's Life`."
                + f"\n\nYou get to choose a Challenge Track when starting your Challenge Pass. Your chosen Track is only valid for that season. Challenge Tracks determine the types of challenges you will receive in your pass.\n\u200b",
            inline=False)

        embed.add_field(
            name=f"**About Reset Tokens**",
            value=f"*Stuck with a difficult challenge?*"
                + f"\nReset Tokens allow you to trash your current challenge and get a new one. Use wisely!"
                + f"\n\nCompleting challenges from your chosen Challenge Track provides you with a small chance to receive a Reset Token.\n\u200b",
            inline=False)

        embed.add_field(
            name=f"**End of the Season**",
            value=f"At the end of every season, all Challenge Passes are reset. Challenge Points, Reset Tokens, and Challenge Tracks do not carry to the next season.\n\u200b",
            inline=False)

        await message.edit(embed=embed)


    @commands.command(name="slash_challengepass",hidden=True)
    async def slashwrapper_challengepass(self,ctx):
        st = time.time()

        embed = await clash_embed(ctx,message="<a:loading:1042769157248262154> Loading...")
        message = await ctx.send(embed=embed)
        channel_id = ctx.channel.id
        message_id = message.id

        if st < ctx.bot.current_season.cwl_end:
            embed = await clash_embed(ctx,message=f"The Challenge Pass season will start on <t:{int(ctx.bot.current_season.cwl_end)}:F>.")
            await message.edit(embed=embed)
            return

        challenge_member = await aMember.create(ctx,user_id=ctx.author.id)

        current_action = "start"

        while True:
            if not current_action:
                break

            if time.time() - st >= 800:
                message = await ctx.bot.get_channel(channel_id).fetch_message(message_id)
                st = time.time()

            if current_action in ['start','accounts']:
                await message.clear_reactions()

                challenge_account = await self.challengepass_accountselect(ctx,message,challenge_member)

                await message.clear_reactions()

                if not challenge_account:
                    current_action = None
                else:
                    current_action = 'view'

            if current_action in ['view','new','refresh']:
                current_action = await self.challengepass_display(ctx,message,challenge_account)

            if current_action in ['trash']:
                current_action = await self.challengepass_trash(ctx,message,challenge_account)

        embed = await clash_embed(ctx,message="Thanks for playing the Challenge Pass!")

        await message.edit(embed=embed)
        await message.clear_reactions()

    @commands.command(name="slash_challengepass_lb",hidden=True)
    async def slashwrapper_challengepass_leaderboard(self,ctx,season='current'):

        embed = await clash_embed(ctx,message="<a:loading:1042769157248262154> Loading...")
        message = await ctx.send(embed=embed)

        if season == 'current':
            season = ctx.bot.current_season
        else:
            season = aClashSeason(season)

        if season.id == ctx.bot.current_season.id:
            pass_data = ctx.bot.pass_cache
        else:
            pass_data = await get_challenge_pass_season(ctx,season.id)

        farmer_passes = [p for p in [ctx.bot.pass_cache[pass_tag] for pass_tag in list(ctx.bot.pass_cache)] if p.track == 'farm']
        farmer_passes = sorted(farmer_passes,key=lambda x:(x.points,x.tokens),reverse=True)

        war_passes = [p for p in [ctx.bot.pass_cache[pass_tag] for pass_tag in list(ctx.bot.pass_cache)] if p.track == 'war']
        war_passes = sorted(war_passes,key=lambda x:(x.points,x.tokens),reverse=True)

        challengepass_leaderboard_embed = await clash_embed(ctx,
            title=f"**AriX Challenge Pass Leaderboard**",
            message=f"The top player from each track will receive **1x <:GoldPass:834093287106674698> Gold Pass** in-game."
                + f"\n\nAll players who attain 10K Pass Points will receive 10,000 XP. You also receive 1,000 XP for every Reset Token unused."
                + f"\n\n*Only the top 10 players from each track are shown below.*"
                + f"\n`{'*C: Completed | M: Missed | T: Trashed*':>47}{'':<2}`"
                + f"\n`{'':<4}{'':<2}{'PTS':>6}{'':<3}{'TKNS':>4}{'':<2}{'C/M/T':>8}{'':<2}{'':<16}{'':<2}`")

        farmer_lb_str = ""
        lb_rank = 0
        for p in farmer_passes:

            completed_ct = len([c for c in p.challenges if c.status == 'Completed'])
            missed_ct = len([c for c in p.challenges if c.status == 'Missed'])
            trashed_ct = len([c for c in p.challenges if c.status == 'Trashed'])

            lb_rank += 1
            if lb_rank > 10:
                break
            points = f"{p.points:,}"
            ch_stats = f"{completed_ct}/{missed_ct}/{trashed_ct}"

            farmer_lb_str += "\n"
            farmer_lb_str += f"{emotes_townhall[p.member.town_hall.level]}{p.member.home_clan.emoji}{'':<2}"
            farmer_lb_str += f"`{points:>6}{'':<3}"
            farmer_lb_str += f"{p.tokens:>4}{'':<2}"
            farmer_lb_str += f"{ch_stats:>8}{'':<2}{'':<2}"
            farmer_lb_str += f"{p.member.name:<16}`"

        challengepass_leaderboard_embed.add_field(
            name=f"**The Farmer's Track**",
            value=f"{farmer_lb_str}\u200b",
            inline=False)

        warpath_lb_str = ""
        lb_rank = 0
        for p in war_passes:
            completed_ct = len([c for c in p.challenges if c.status == 'Completed'])
            missed_ct = len([c for c in p.challenges if c.status == 'Missed'])
            trashed_ct = len([c for c in p.challenges if c.status == 'Trashed'])

            lb_rank += 1
            if lb_rank > 10:
                break
            points = f"{p.points:,}"
            ch_stats = f"{completed_ct}/{missed_ct}/{trashed_ct}"

            warpath_lb_str += "\n"
            warpath_lb_str += f"{emotes_townhall[p.member.town_hall.level]}{p.member.home_clan.emoji}{'':<2}"
            warpath_lb_str += f"`{points:>6}{'':<3}"
            warpath_lb_str += f"{p.tokens:>4}{'':<2}"
            warpath_lb_str += f"{ch_stats:>8}{'':<2}{'':<2}"
            warpath_lb_str += f"{p.member.name:<16}`"

        challengepass_leaderboard_embed.add_field(
            name=f"**The Warpath**",
            value=f"{warpath_lb_str}\u200b",
            inline=False)

        await message.edit(embed=challengepass_leaderboard_embed)


    async def challengepass_accountselect(self,ctx,message,challenge_member):
        challenge_accounts = []
        for account in challenge_member.accounts:
            if account.is_member and account.home_clan.abbreviation == 'AS':
                challenge_accounts.append(await aChallengePass.create(ctx,member_tag=account.tag,refresh=True))

        if ctx.bot.leader_role in [challenge_member.discord_member.roles] or ctx.bot.coleader_role in [challenge_member.discord_member.roles]:
            for account in challenge_member.accounts:
                if account.is_member:
                    challenge_accounts.append(await aChallengePass.create(ctx,member_tag=account.tag,refresh=True))

        if len(challenge_accounts) == 0:
            embed = await clash_embed(ctx,
                title="No Eligible Accounts.",
                message="You don't have any eligible accounts to participate in the AriX Challenge Pass. For information on the Challenge Pass, run `/challengepass-info`."
                    + f"\n\nThe Challenge Pass is currently available to **Assassins** members of <:11:1045961399563714560> TH11 and above."
                    + f"\n\n*p.s. to other clan members: wait for your turn ;)*",
                color='fail')
            await message.edit(embed=embed)
            return None

        if len(challenge_accounts) == 1:
            return challenge_accounts[0]

        if len(challenge_accounts) > 1:
            select_menu = []
            for a in challenge_accounts:

                pass_description = "> *Pass not started.*"
                if a.track:
                    pass_description = f"> Track: {challengePassDisplayName[a.track]}"
                    pass_description += f"\n > Progress: {a.points} / 10,000 | Tokens: {a.tokens}"
                    if a.active_challenge:
                        pass_description += f"\n> Current Challenge: {a.active_challenge.description}"

                select_dict = {
                    'id': a.tag,
                    'title': f"{emotes_townhall[a.member.town_hall.level]} {a.member.name} ({a.tag})",
                    'desc': f"{pass_description}"
                    }

                select_menu.append(select_dict)

            select_menu = await multiple_choice_menu_generate_emoji(ctx,select_menu)

            select_msg = ""
            for i in select_menu:
                select_msg += f"**{i['emoji']} {i['title']}**"
                select_msg += f"\n{i['desc']}"
                select_msg += "\n\n"

            embed = await clash_embed(ctx,
                title=f"AriX Challenge Pass: {ctx.bot.current_season.season_description}",
                message=f"*For information on the Challenge Pass, run `/challengepass-info`.*"
                    + f"\n\nSelect an account below to view the Challenge Pass for that account. \n\n{select_msg}")

            await message.edit(embed=embed)
            select_account = await multiple_choice_menu_select(ctx,message,select_menu)

            if not select_account:
                return None

            select_account = [a for a in challenge_accounts if a.member.tag == select_account['id']]

            return select_account[0]


    async def challengepass_display(self,ctx,message,pass_account):
        if not pass_account.track:
            embed = await pass_account.to_embed(ctx)

            track_menu = []
            back_dict = {
                'id': 'accounts',
                'name': "Back",
                'emoji': "<:backwards:1041976602420060240>"
                }
            farm_dict = {
                'id': 'farm',
                'name': "The Farmer's Track",
                'emoji': "<a:cp_farmer:1061676915724926986>"
                }
            war_dict = {
                'id': 'war',
                'name': "The Warpath",
                'emoji': "<:cp_war:1054997157654036561>"
                }
            track_menu.append(back_dict)
            track_menu.append(farm_dict)
            track_menu.append(war_dict)

            embed.add_field(
                name="**Navigation**",
                value="<:backwards:1041976602420060240> Back to the Home tab.",
                inline=False)

            await message.edit(embed=embed)

            select_track = await multiple_choice_menu_select(ctx,message,track_menu,timeout=180)
            if not select_track:
                return None

            if select_track['id'] in ['accounts']:
                return select_track['id']

            pass_account.track = select_track['id']
            await pass_account.save_to_json(ctx)
            pass_account = await aChallengePass.create(ctx,pass_account.tag,refresh=True)

            await message.clear_reactions()

            confirm_embed = await clash_embed(ctx,
                title=f"**{pass_account.member.name} ({pass_account.member.tag})**",
                message=f"Congratulations, {ctx.author.mention}! You've chosen {select_track['emoji']} {select_track['name']}."
                    + f"\n\nPlease wait while we get your challenges ready...",
                color='success')
            await message.edit(embed=confirm_embed)
            await asyncio.sleep(12)

        if pass_account.track:
            pass_menu = []
            pass_account, update_status, challenge = await pass_account.update_pass(ctx)

            embed = await pass_account.to_embed(ctx,update_status)

            back_dict = {
                'id': 'accounts',
                'name': "Back",
                'emoji': "<:backwards:1041976602420060240>"
                }
            refresh_dict = {
                'id': 'refresh',
                'name': "Refresh this Challenge",
                'emoji': "<:refresh:1048916418466426941>"
                }
            new_dict = {
                'id': 'new',
                'name': "Get a new Challenge",
                'emoji': "<:refresh:1048916418466426941>"
                }
            trash_dict = {
                'id': 'trash',
                'name': "Trash this Challenge",
                'emoji': "<:trashcan:1042829064345497742>"
                }

            pass_menu.append(back_dict)

            if update_status == 'In Progress':
                await message.remove_reaction("<:red_cross:838461484312428575>",ctx.bot.user)
                embed.add_field(
                    name=f"**You're currently working on this challenge...**",
                    value=f"```{challenge.description}```"
                        + f"{challenge.get_descriptor()}\n\n",
                    inline=False)

                pass_menu.append(refresh_dict)
                pass_menu.append(trash_dict)
                embed.add_field(
                    name=f"**Navigation**",
                    value=f"<:refresh:1048916418466426941> To refresh from in-game data."
                        + f"\n<:trashcan:1042829064345497742> To Trash this challenge. Trashing costs 1 Reset Token."
                        + f"\n<:backwards:1041976602420060240> Back to the Home tab.",
                    inline=False)

            if update_status == 'New':
                await message.remove_reaction("<:red_cross:838461484312428575>",ctx.bot.user)
                embed.add_field(
                    name=f"**>> YOU RECEIVED A NEW CHALLENGE! <<**",
                    value=f"```{challenge.description}```"
                        + f"{challenge.get_descriptor()}\n\n",
                    inline=False)

                pass_menu.append(refresh_dict)
                pass_menu.append(trash_dict)
                embed.add_field(
                    name=f"**Navigation**",
                    value=f"<:refresh:1048916418466426941> To refresh from in-game data."
                        + f"\n<:trashcan:1042829064345497742> To Trash this challenge. Trashing costs 1 Reset Token."
                        + f"\n<:backwards:1041976602420060240> Back to the Home tab.",
                    inline=False)

            if update_status == 'Missed':
                await message.remove_reaction("<:trashcan:1042829064345497742>",ctx.author)
                await message.remove_reaction("<:trashcan:1042829064345497742>",ctx.bot.user)

                embed.add_field(
                    name=f"**>> YOU MISSED A NEW CHALLENGE! <<**",
                    value=f"```{challenge.description}```"
                        + f"{challenge.get_descriptor()}",
                    inline=False)

                pass_menu.append(new_dict)
                embed.add_field(
                    name=f"**Navigation**",
                    value=f"<:refresh:1048916418466426941> To get a new challenge."
                        + f"\n<:backwards:1041976602420060240> Back to the Home tab.",
                    inline=False)

            if update_status == 'Completed':
                await message.remove_reaction("<:trashcan:1042829064345497742>",ctx.author)
                await message.remove_reaction("<:trashcan:1042829064345497742>",ctx.bot.user)

                reward_str = f"You earned: **{challenge.reward:,} Points**."
                if challenge.token_rew:
                    reward_str += f" You also earned 1 Refresh Token!"
                embed.add_field(
                    name=f"**>> CHALLENGE COMPLETED! <<**",
                    value=f"{reward_str}"
                        + f"```{challenge.description}```"
                        + f"{challenge.get_descriptor()}",
                    inline=False)

                pass_menu.append(new_dict)
                embed.add_field(
                    name=f"**Navigation**",
                    value=f"<:refresh:1048916418466426941> To get a new challenge."
                        + f"\n<:backwards:1041976602420060240> Back to the Home tab.",
                    inline=False)

            await message.edit(embed=embed)

            select_action = await multiple_choice_menu_select(ctx,message,pass_menu,timeout=180)
            if not select_action:
                return None

            await message.remove_reaction(select_action['emoji'],ctx.author)
            return select_action['id']


    async def challengepass_trash(self,ctx,message,pass_account):
        pass_menu = []
        pass_account, update_status, challenge = await pass_account.trash_active_challenge(ctx)

        if update_status == "No Challenge":
            return 'refresh'

        embed = await pass_account.to_embed(ctx,update_status)

        back_dict = {
            'id': 'accounts',
            'name': "Back",
            'emoji': "<:backwards:1041976602420060240>"
            }
        refresh_dict = {
            'id': 'refresh',
            'name': "Refresh this Challenge",
            'emoji': "<:refresh:1048916418466426941>"
            }
        new_dict = {
            'id': 'new',
            'name': "Get a new Challenge",
            'emoji': "<:refresh:1048916418466426941>"
            }
        trash_dict = {
            'id': 'trash',
            'name': "Trash this Challenge",
            'emoji': "<:trashcan:1042829064345497742>"
            }

        pass_menu.append(back_dict)

        if update_status == "Insufficient":
            embed.add_field(
                name=f"**You don't have enough Reset Tokens...**",
                value=f"```{challenge.description}```"
                    + f"{challenge.get_descriptor()}\n\n",
                inline=False)

            pass_menu.append(refresh_dict)
            pass_menu.append(trash_dict)
            embed.add_field(
                name=f"**Navigation**",
                value=f"<:refresh:1048916418466426941> To refresh from in-game data."
                    + f"\n<:trashcan:1042829064345497742> To Trash this challenge. Trashing costs 1 Reset Token."
                    + f"\n<:backwards:1041976602420060240> Back to the Home tab.",
                inline=False)

        if update_status == "Trashed":
            await message.remove_reaction("<:trashcan:1042829064345497742>",ctx.author)
            await message.remove_reaction("<:trashcan:1042829064345497742>",ctx.bot.user)

            embed.add_field(
                name=f"**You spent a Reset Token and trashed this challenge.**",
                value=f"```{challenge.description}```"
                    + f"{challenge.get_descriptor()}\n\n",
                inline=False)

            pass_menu.append(new_dict)
            embed.add_field(
                name=f"**Navigation**",
                value=f"<:refresh:1048916418466426941> To get a new challenge."
                    + f"\n<:backwards:1041976602420060240> Back to the Home tab.",
                inline=False)

        await message.edit(embed=embed)
        select_action = await multiple_choice_menu_select(ctx,message,pass_menu,timeout=180)
        if not select_action:
            return None

        await message.remove_reaction(select_action['emoji'],ctx.author)

        return select_action['id']



