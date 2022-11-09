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
from aa_resourcecog.constants import clanRanks, emotes_townhall, emotes_league, emotes_capitalhall
from aa_resourcecog.notes import aNote
from aa_resourcecog.file_functions import get_current_season, get_current_alliance, get_alliance_clan, get_alliance_members, get_user_accounts, get_staff_position
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from aa_resourcecog.errors import TerminateProcessing

class AriXClashLeaders(commands.Cog):
    """AriX Clash of Clans Leaders' Module."""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=2170311125702803,force_registration=True)
        default_global = {}
        default_guild = {}
        defaults_user = {}       
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**defaults_user)

    ####################################################################################################

    ### CLAN MANAGEMENT COMMANDS
    ###
    ### - clan
    ###     > add : add clan to alliance [Admin/Mod]
    ###     > remove : remove clan from alliance [Admin/Mod]
    ###     > setleader : leader override [Admin/Mod]
    ###     > setannouncements : configuration options [Admin/Mod]
    ###     > setemoji : set the emoji for a clan [Admin/Mod]
    ###     > setrecruit : set the Townhalls that a clan is recruiting for [Co-Leader]
    ###     > setdescription : set the custom description for a clan [Co-Leader]
    ###     > addnote : add a note to the clan 
    ### - recruiting : leader's notes for recruiting

    ####################################################################################################


    @commands.command(name="recruiting")
    async def recruitment_information(self,ctx):
        """
        Get Recruiting information for all Alliance clans.

        This returns the number of registered members, the (suggested) townhall levels, and the last 5 Leader's notes on file.
        """

        clans, members = await get_current_alliance(ctx)
        output_embed = []

        for tag in clans:
            try:    
                c = await aClan.create(ctx,tag)
            except Exception as e:
                eEmbed = await resc.clash_embed(ctx=ctx,message=f"{e}",color="fail")
                return await ctx.send(embed=eEmbed)

            th_str = ""
            for th in c.recruitment_level:
                th_str += f"{emotes_townhall[th]} "

            clanEmbed = await resc.clash_embed(ctx=ctx,
                title=f"Clan Recruitment",
                message=f"**{c.emoji} {c.name} ({c.tag})**"
                    + f"\nMembers: {c.member_count} / 50\nRecruiting: {th_str}\n\u200b",
                thumbnail="https://i.imgur.com/TZF5r54.png")

            for note in c.notes[:4]:
                dt = f"{datetime.fromtimestamp(note.timestamp).strftime('%d %b %Y')}"

                clanEmbed.add_field(
                    name=f"__{note.author.name} @ {dt}__",
                    value=f">>> {note.content}",
                    inline=False)

            output_embed.append(clanEmbed)

        if len(output_embed)>1:
            paginator = BotEmbedPaginator(ctx,output_embed)
            return await paginator.run()
        elif len(output_embed)==1:
            return await ctx.send(embed=output_embed[0])

    @commands.group(name="clan")
    async def clan_manage(self,ctx):
        """Command group to manage Alliance clans."""
            
        if not ctx.invoked_subcommand:
            pass

    @clan_manage.command(name="add")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_add(self, ctx, tag:str, force=False):
        """
        Add a clan to the Alliance.

        Only the in-game tag of the clan is required when running the command. Any other information will be requested by the bot.
        """

        def response_check(m):
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    return True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    return True
                else:
                    return False

        try:
            c = await aClan.create(ctx,tag)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx=ctx,message=f"{e}",color="fail")
            return await ctx.send(embed=eEmbed)

        if force and ctx.author.id in ctx.bot.owner_ids:
            pass
        else:
            if c.is_alliance_clan:
                embed = await resc.clash_embed(ctx=ctx,
                    message=f"The clan {c.name} ({c.tag}) is already part of the Alliance.",
                    color="fail",
                    thumbnail=c.clan.badge.url)
                return await ctx.send(embed=embed)

        leader_msg = await ctx.send(content=f"{ctx.author.mention}, who will be the Leader of this clan? Please mention the user.")
        try:
            leader_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            await leader_msg.edit(content="Operation cancelled.")
            return
        else:
            leader_id = re.search('@(.*)>',leader_response.content).group(1)
            leader = ctx.bot.get_user(int(leader_id))
            await leader_msg.delete()
            await leader_response.delete()

        abbr_msg = await ctx.send(content=f"{ctx.author.mention}, please specify the abbreviation for **{c.name}**.")
        try:
            abbr_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            await abbr_msg.edit(content="Operation cancelled.")
            return
        else:
            clan_abbreviation = abbr_response.content.upper()
            check_abbr = await get_alliance_clan(ctx,clan_abbreviation)
            if not force and check_abbr:
                return await ctx.send(content=f"The abbreviation {clan_abbreviation} is already in use. Please try again.")
            await abbr_msg.delete()
            await abbr_response.delete()

        emoji_msg = await ctx.send(content=f"{ctx.author.mention}, please specify the emoji for **{c.name}**.")
        try:
            emoji_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            await emoji_msg.edit(content="Operation cancelled.")
            return
        else:
            emoji = emoji_response.content
            await emoji_msg.delete()
            await emoji_response.delete()

        leader_role_msg = await ctx.send(content=f"{ctx.author.mention}, please mention the **Leader** role for **{c.name}**.")
        try:
            leader_role_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            await leader_role_msg.edit(content="Operation cancelled.")
            return
        else:
            leader_role_id = re.search('@&(.*)>',leader_role_response.content).group(1)
            leader_role = ctx.guild.get_role(int(leader_role_id))
            await leader_role_msg.delete()
            await leader_role_response.delete()

        coleader_role_msg = await ctx.send(content=f"{ctx.author.mention}, please mention the **Co-Leader** role for **{c.name}**.")
        try:
            coleader_role_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            await coleader_role_msg.edit(content="Operation cancelled.")
            return
        else:
            coleader_role_id = re.search('@&(.*)>',coleader_role_response.content).group(1)
            coleader_role = ctx.guild.get_role(int(coleader_role_id))
            await coleader_role_msg.delete()
            await coleader_role_response.delete()

        elder_role_msg = await ctx.send(content=f"{ctx.author.mention}, please mention the **Elder** role for **{c.name}**.")
        try:
            elder_role_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            await elder_role_msg.edit(content="Operation cancelled.")
            return
        else:
            elder_role_id = re.search('@&(.*)>',elder_role_response.content).group(1)
            elder_role = ctx.guild.get_role(int(elder_role_id))
            await elder_role_msg.delete()
            await elder_role_response.delete()

        member_role_msg = await ctx.send(content=f"{ctx.author.mention}, please mention the **Member** role for **{c.name}**.")
        try:
            member_role_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            await member_role_msg.edit(content="Operation cancelled.")
            return
        else:
            member_role_id = re.search('@&(.*)>',member_role_response.content).group(1)
            member_role = ctx.guild.get_role(int(member_role_id))
            await member_role_msg.delete()
            await member_role_response.delete()

        confirm_embed = await resc.clash_embed(ctx=ctx,
            title=f"New Clan: {c.name} ({c.tag})",
            message=f"Leader: {leader.mention}\nAbbreviation: {clan_abbreviation}\u3000Emoji: {emoji}"
                + f"\n\n<:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} {c.capital_hall}\u3000Members: {c.c.member_count}"
                + f"\n{emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
                + f"\n:globe_with_meridians: {c.c.location.name}\u3000<:HomeTrophies:825589905651400704> {c.c.points}\u3000<:BuilderTrophies:825713625586466816> {c.c.versus_points}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link)

        confirm_add = await ctx.send(
            content=f"{ctx.author.mention}, please confirm you would like to add the below clan.",
            embed=confirm_embed)
        if not await resc.user_confirmation(self,ctx,confirm_add):
            return

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                await c.add_to_alliance(
                    leader=leader,
                    abbreviation=clan_abbreviation,
                    emoji=emoji,
                    leader_role=leader_role,
                    coleader_role=coleader_role,
                    elder_role=elder_role,
                    member_role=member_role)
                await c.save_to_json()

        final_embed = await resc.clash_embed(ctx=ctx,
            title=f"Clan Sucessfully Added: {c.name} ({c.tag})",
            message=f"Leader: {leader.mention}\u3000Abbr: {clan_abbreviation}\u3000Emoji: {emoji}"
                + f"\n\n<:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} {c.capital_hall}\u3000Members: {c.c.member_count}"
                + f"\n{emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
                + f"\n:globe_with_meridians: {c.c.location.name}\u3000<:HomeTrophies:825589905651400704> {c.c.points}\u3000<:BuilderTrophies:825713625586466816> {c.c.versus_points}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link,
            color='success')

        return await ctx.send(embed=final_embed)

    @clan_manage.command(name="remove")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_remove(self, ctx, clan_abbreviation):
        """
        Remove a clan from the Alliance.

        Use the Clan Abbreviation to specify a clan.
        """

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)
        if not clan_from_abbreviation:
            await ctx.send(f"The abbreviation {clan_abbreviation} does not correspond to any Alliance clan.")

        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx=ctx,
                message=f"{e}",
                color="fail")
            return await ctx.send(embed=eEmbed)

        confirm_embed = await resc.clash_embed(ctx=ctx,
            title=f"Remove Clan: {c.emoji} {c.name} ({c.tag})",
            message=f"Leader: <@{c.leader}>"
                + f"\n\n<:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} {c.capital_hall}\u3000Members: {c.member_count}"
                + f"\n{emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
                + f"\n:globe_with_meridians: {c.c.location.name}\u3000<:HomeTrophies:825589905651400704> {c.c.points}\u3000<:BuilderTrophies:825713625586466816> {c.c.versus_points}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link)

        confirm_remove = await ctx.send(
            content=f"{ctx.author.mention}, please confirm you would like to remove the below clan.",
            embed=confirm_embed)
        if not await resc.user_confirmation(self,ctx,confirm_remove):
            return

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(ctx.bot.clash_dir_path+'/alliance.json','w+') as file:
                    file_json = json.load(file)
                    del file_json['clans'][c.tag]
                    json.dump(file_json,file,indent=2)
                    file.truncate()

        final_embed = await resc.clash_embed(ctx=ctx,
            title=f"Clan Sucessfully Removed: {c.name} ({c.tag})",
            message=f"Leader: {c.emoji} <@{c.leader}>"
                + f"\n\n<:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} {c.capital_hall}\u3000Members: {c.member_count}"
                + f"\n{emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
                + f"\nLocation: {c.c.location.name}\u3000<:HomeTrophies:825589905651400704> {c.c.points}\u3000<:BuilderTrophies:825713625586466816> {c.c.versus_points}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link,
            color='success')
    
        await confirm_embed.delete()
        await ctx.send(embed=final_embed)

    @clan_manage.command(name="setleader")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_setleader(self, ctx, clan_abbreviation, new_leader:discord.User):
        """
        Admin-only command to override a Leader for a given clan.

        """

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)
        if not clan_from_abbreviation:
            await ctx.send(f"The abbreviation {clan_abbreviation} does not correspond to any Alliance clan.")

        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx=ctx,
                message=f"{e}",
                color="fail")
            return await ctx.send(embed=eEmbed)

        confirm_embed = await resc.clash_embed(ctx=ctx,
            title=f"Leader Override: {c.emoji} {c.name} ({c.tag})",
            message=f"New Leader: <@{c.leader}>"
                + f"\n\n<:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} {c.capital_hall}\u3000Members: {c.member_count}"
                + f"\n{emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
                + f"\n:globe_with_meridians: {c.c.location.name}\u3000<:HomeTrophies:825589905651400704> {c.c.points}\u3000<:BuilderTrophies:825713625586466816> {c.c.versus_points}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link)

        confirm_remove = await ctx.send(
            content=f"{ctx.author.mention}, please confirm you would like to assign {new_leader.mention} as the Leader of the above clan.",
            embed=confirm_embed)

        if not await resc.user_confirmation(self,ctx,confirm_remove):
            return

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                try:
                    await c.add_staff(new_leader,"Leader")
                    await c.save_to_json()
                except Exception as e:
                    err_embed = await resc.clash_embed(ctx,
                        message=f"Error encountered while updating clan: {e}.")
                    return await ctx.send(embed=err_embed)

        final_embed = await resc.clash_embed(ctx=ctx,
            title=f"Leader Assigned: {c.name} ({c.tag})",
            message=f"\n*Note: It may take up to 10 minutes for individual accounts to reflect the updated Rank.*"
                + f"\n\nLeader: {c.emoji} <@{c.leader}>"
                + f"\n\n<:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} {c.capital_hall}\u3000Members: {c.member_count}"
                + f"\n{emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
                + f"\nLocation: {c.c.location.name}\u3000<:HomeTrophies:825589905651400704> {c.c.points}\u3000<:BuilderTrophies:825713625586466816> {c.c.versus_points}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link,
            color='success')
    
        await confirm_embed.delete()
        await ctx.send(embed=final_embed)


    @clan_manage.command(name="announcements")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_announcements(self, ctx, clan_abbreviation):
        """
        Set up War / Raid Reminders for the given clan.
        """

        def response_check(m):
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    return True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    return True
                else:
                    return False

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)

        if not clan_from_abbreviation:
            await ctx.send(f"The abbreviation {clan_abbreviation} does not correspond to any Alliance clan.")

        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
            return await ctx.send(embed=eEmbed)

        selection_dict = [
            {
                'id': 'announcement_channel',
                'title': 'Set the Announcement channel.',
                'description': 'Automated announcements will be sent in this channel.'
            },
            {
                'id': 'reminder_channel',
                'title': 'Set the Reminder channel.',
                'description': 'Reminders will be sent in this channel.'
            },
            {
                'id': 'war_reminder',
                'title': 'Toggle War Reminders.',
                'description': 'War reminders are sent at the 12 hour, 4 hour, and 1 hour (remaining time) mark of a War.'
            },
            {
                'id': 'raid_reminder',
                'title': 'Toggle Raid Reminders.',
                'description': 'Raid reminders are sent at the 24 hour, 12 hour, and 4 hour (remaining time) mark of the Raid Weekend.'
            }
        ]

        selection_embed = await resc.clash_embed(ctx,
            title=f"Announcement Set Up: {c.name} ({c.tag})")

        menu, selected_option = await resc.multiple_choice_select(self,
            ctx=ctx,
            sEmbed=selection_embed,
            selection_list=selection_dict,
            selection_text="Select an option below.")

        if selected_option['id'] == 'announcement_channel':
            request_msg = await ctx.send(content=f"{ctx.author.mention}, please specify the Announcement Channel for {c.emoji} **{c.name}**.")
            try:
                response_msg = await ctx.bot.wait_for("message",timeout=60,check=response_check)
            except asyncio.TimeoutError:
                await request_msg.edit(content="Operation cancelled.")
                return
            else:
                try:
                    announcement_channel_id = re.search('#(.*)>',response_msg.content).group(1)
                    announcement_channel = ctx.guild.get_channel(int(announcement_channel_id))
                    async with ctx.bot.async_file_lock:
                        with ctx.bot.clash_file_lock.write_lock():
                            await c.set_announcement_channel(announcement_channel.id)
                            await c.save_to_json()
                except Exception as e:
                    cEmbed = await resc.clash_embed(ctx,
                        message=f"Error encountered when setting Announcement channel: {e}.",
                        color='fail')
                else:
                    await request_msg.delete()
                    await response_msg.delete()
                    cEmbed = await resc.clash_embed(ctx,
                        message=f"The Announcement Channel for {c.emoji} **{c.name}** is now <#{announcement_channel.id}>.",
                        color='success')
                    return await ctx.send(embed=cEmbed)

        if selected_option['id'] == 'reminder_channel':
            request_msg = await ctx.send(content=f"{ctx.author.mention}, please specify the Reminder Channel for {c.emoji} **{c.name}**.")
            try:
                response_msg = await ctx.bot.wait_for("message",timeout=60,check=response_check)
            except asyncio.TimeoutError:
                await request_msg.edit(content="Operation cancelled.")
                return
            else:
                try:
                    reminder_channel_id = re.search('#(.*)>',response_msg.content).group(1)
                    reminder_channel = ctx.guild.get_channel(int(reminder_channel_id))
                    async with ctx.bot.async_file_lock:
                        with ctx.bot.clash_file_lock.write_lock():
                            await c.set_reminder_channel(reminder_channel.id)
                            await c.save_to_json()
                except Exception as e:
                    cEmbed = await resc.clash_embed(ctx,
                        message=f"Error encountered when setting Reminder channel: {e}.",
                        color='fail')
                else:
                    await request_msg.delete()
                    await response_msg.delete()
                    cEmbed = await resc.clash_embed(ctx,
                        message=f"The Reminder Channel for {c.emoji} **{c.name}** is now <#{reminder_channel.id}>.",
                        color='success')
                    return await ctx.send(embed=cEmbed)

        if selected_option['id'] == 'war_reminder':
            async with ctx.bot.async_file_lock:
                with ctx.bot.clash_file_lock.write_lock():
                    await c.toggle_war_reminders()
                    await c.save_to_json()

            cEmbed = await resc.clash_embed(ctx,
                message=f"War Reminders for {c.emoji} **{c.name}** set to: {c.send_war_reminder}.",
                color='success')
            return await ctx.send(embed=cEmbed)

        if selected_option['id'] == 'raid_reminder':
            async with ctx.bot.async_file_lock:
                with ctx.bot.clash_file_lock.write_lock():
                    await c.toggle_raid_reminders()
                    await c.save_to_json()

            cEmbed = await resc.clash_embed(ctx,
                message=f"War Reminders for {c.emoji} **{c.name}** set to: {c.send_war_reminder}.",
                color='success')
            return await ctx.send(embed=cEmbed)

    @clan_manage.command(name="setemoji")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_emoji(self, ctx, clan_abbreviation, emoji_str:str):
        """
        Set the custom emoji for an Alliance clan.

        Reminder: emojis must be from a server that the bot is added to.
        """

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)

        if not clan_from_abbreviation:
            await ctx.send(f"The abbreviation {clan_abbreviation} does not correspond to any Alliance clan.")

        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
            return await ctx.send(embed=eEmbed)

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                await c.set_emoji(emoji_str)
                await c.save_to_json()

        cEmbed = await resc.clash_embed(ctx,
                    message=f"The emoji for **{c.name}** is now {emoji_str}.",
                    color='success')
        return await ctx.send(embed=cEmbed)

    @clan_manage.command(name="setrecruit")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_townhall(self, ctx, clan_abbreviation, *th_levels:int):
        """
        Set the Townhall levels for recruiting.

        You must be a Co-Leader of a clan to use this command. Separate multiple townhall levels with a blank space.

        """

        authorized = False

        townhall_out_of_range = [th for th in th_levels if th not in range(1,16)]
        if len(townhall_out_of_range) > 0:
            return await ctx.send(f"The following TH levels are invalid: {humanize_list(townhall_out_of_range)}.")

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)
        if not clan_from_abbreviation:
            await ctx.send(f"The abbreviation {clan_abbreviation} does not correspond to any Alliance clan.")

        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
            return await ctx.send(embed=eEmbed)

        #Must be Co-Leader or Leader to use.
        if ctx.author.id == c.leader or ctx.author.id in c.co_leaders:
            authorized = True

        if not authorized:
            return await ctx.send(f"You need to be a Leader or Co-Leader of **{c.emoji} {c.name}** to use this command.")

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                await ctx.send(f"ff{locked}")
                await c.set_recruitment_level(ctx,th_levels)
                await c.save_to_json()

        th_str = ""
        c.recruitment_level.sort()
        for th in c.recruitment_level:
            th_str += f"> {emotes_townhall[th]} TH{th}\n"

        cEmbed = await resc.clash_embed(ctx,
            message=f"**{c.emoji} {c.name}** is now recruiting for:\n {th_str}",
            color='success')

        return await ctx.send(embed=cEmbed)

    @clan_manage.command(name="setdescription")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_description(self, ctx, clan_abbreviation):
        """
        Set the custom description for an Alliance clan.

        You must be a Co-Leader of a clan to use this command. Separate multiple townhall levels with a blank space.

        This description overrides any in-game description, and is only applicable to the AriX Bot. 
        If using emojis in the description, ensure that they are in a server shared by the bot.
        """

        authorized = False

        def response_check(m):
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    return True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    return True
                else:
                    return False

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)
        if not clan_from_abbreviation:
            await ctx.send(f"The abbreviation {clan_abbreviation} does not correspond to any Alliance clan.")
        
        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
            return await ctx.send(embed=eEmbed)

        #Must be Co-Leader or Leader to use.
        if ctx.author.id == c.leader or ctx.author.id in c.co_leaders:
            authorized = True

        if not authorized:
            return await ctx.send(f"You need to be a Leader or Co-Leader of **{c.emoji} {c.name}** to use this command.")

        description_msg = await ctx.send(content=f"{ctx.author.mention}, send the new description for {c.emoji} **{c.name}** in your next message. You have 3mins.")
        
        try:
            description_response = await ctx.bot.wait_for("message",timeout=180,check=response_check)
        except asyncio.TimeoutError:
            await respond_msg.edit(content="Operation cancelled.")
            return

        new_description = description_response.content

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                await c.set_description(new_description)
                await c.save_to_json()

        cEmbed = await resc.clash_embed(ctx,
            title=f"Description set for {c.emoji} {c.name}",
            message=f"{c.description}",
            color='success')

        await ctx.send(embed=cEmbed)
        await description_msg.delete()
        await description_response.delete()

    @clan_manage.command(name="addnote")
    async def clan_manage_addnote(self,ctx,clan_abbreviation):
        """
        Add a Leader's note to a clan.

        Notes can be used to share information with other leaders.

        """

        def response_check(m):
            if m.author.id == ctx.author.id and m.channel.type == discord.ChannelType.private:
                return True
            else:
                return False

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)
        
        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
            return await ctx.send(embed=eEmbed)

        channel_msg = await ctx.send(content=f"{ctx.author.mention}, submit your note for {c.emoji} **{c.name}** via DMs. You have 3mins.")
        dm_message = await ctx.author.send(content=f"{ctx.author.message}, you are creating a new note for {c.emoji} **{c.name}**.")
        
        try:
            response_note = await ctx.bot.wait_for("message",timeout=180,check=response_check)
        except asyncio.TimeoutError:
            await channel_msg.edit(content="Sorry! You timed out.")
            await dm_message.edit(content="Sorry! You timed out.")
            return
        
        new_note = response_note.content

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                await c.add_note(ctx,new_note)
                await c.save_to_json()

        await response_note.add_reaction('<:green_check:838461472324583465>')

        final_embed = await resc.clash_embed(ctx,message=f"{ctx.author.mention} just added a note to {c.emoji} **{c.name}**.")

        await ctx.send(embed=final_embed)

    
    ####################################################################################################

    ### MEMBER MANAGEMENT COMMANDS
    ###
    ### - member
    ###     > add : add a member to the alliance
    ###     > remove : remove a member from the alliance
    ###     > addnote : add a note to a user
    ### - promote
    ### - demote
    ### - whois
    ### - getmissing
    ### - getunrecognized

    ####################################################################################################

    @commands.group(name="member")
    async def member_manage(self,ctx):
        """
        Add/remove members.
        """
        
        if not ctx.invoked_subcommand:
            pass

    @member_manage.command(name="add")
    async def member_manage_add(self,ctx,user:discord.User, *player_tags):
        """
        Add members to the Alliance. 

        Multiple tags can be separated by a blank space. You will be prompted to select a home clan for each account.
        """

        alliance_clan_tags, alliance_member_tags = await get_current_alliance(ctx)
        alliance_clans = []
        error_log = []
        added_count = 0

        if not len(alliance_clan_tags) >= 1:
            return await ctx.send("No clans registered! Please register a clan to the Alliance before adding members.")
        if len(player_tags) == 0:
            return await ctx.send("Please provide Player Tags to be added. Separate multiple tags with a space.")

        for clan_tag in alliance_clan_tags:
            try:
                c = await aClan.create(ctx,clan_tag)
            except Exception as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            alliance_clans.append(c)
            

        for tag in player_tags:
            clan_selection = []
            alliance_clans_sorted = sorted(alliance_clans, key=lambda x: (x.level,x.capital_hall),reverse=True)
            for c in alliance_clans_sorted:
                await c.update_member_count()
                th_str = ""
                for th in c.recruitment_level:
                    th_str += f"{emotes_townhall[th]} "
                c_dict = {
                    'id': c.tag,
                    'emoji': c.emoji,
                    'title': c.name,
                    'description': f"Members: {c.member_count}\u3000Recruiting: {th_str}"
                    }
                clan_selection.append(c_dict)
            try:
                p = await aPlayer.create(ctx,tag)
                await p.retrieve_data()
                p_title, p_field = await resc.player_summary(self,ctx,p)
            except TerminateProcessing as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            except Exception as e:
                p = None
                err_dict = {'tag':tag,'reason':f"Error retrieving data: {e}"}
                error_log.append(err_dict)
                continue

            player_notes = "**__Important Notes__**"
            try:
                existing_user = ctx.bot.get_user(int(p.discord_user))
                existing_user = existing_user.mention
            except:
                existing_user = None

            #Discord User on file does not match new user: request confirmation.
            if p.discord_user != 0 and p.discord_user != user.id:
                player_notes += f"\n- This account is already linked to <@{p.discord_user}>."
            
            #Is a current active member, but in a different clan: request confirmation.
            if p.is_member:
                player_notes += f"\n- This account is already a {p.arix_rank} in {p.home_clan.emoji} {p.home_clan.name}."

            player_embed = await resc.clash_embed(ctx,
                title=f"Add Member: {p.name} ({p.tag})",
                message=f"*[Click here to open in-game]({p.p.share_link})*"
                    + f"\n\nLinking to: {user.mention}"
                    + f"\n<:Exp:825654249475932170> {p.exp_level}\u3000<:Clan:825654825509322752> {p.clan_description}"
                    + f"\n{p.town_hall.emote} {p.town_hall.description}\u3000{emotes_league[p.league.name]} {p.trophies} (best: {p.best_trophies})\u3000<:TotalStars:825756777844178944> {p.war_stars}"
                    + f"\n\n{player_notes}\n\u200b")

            menu, selected_clan = await resc.multiple_choice_select(self,
                ctx=ctx,
                sEmbed=player_embed,
                selection_list=clan_selection,
                selection_text="Select a home clan for this account.")

            if not selected_clan:
                end_embed = await resc.clash_embed(ctx,
                    message=f"Did not add **{p.tag} {p.name}**. Skipping...",
                    color='fail')
                await menu.edit(embed=end_embed)
                continue

            added_count += 1
            target_clan = [c for c in alliance_clans if c.tag == selected_clan['id']][0]

            if target_clan.tag == p.home_clan.tag and p.is_member:
                c_embed = await resc.clash_embed(ctx,
                    message=f"**{p.tag} {p.name}** is already a **{p.arix_rank}** in **{p.home_clan.emoji} {p.home_clan.name}**.",
                    color='success')
                await menu.edit(embed=c_embed)
            else:
                async with ctx.bot.async_file_lock:
                    with ctx.bot.clash_file_lock.write_lock():
                        try:
                            await p.new_member(ctx,user,target_clan)
                            await p.set_baselines()
                            await p.save_to_json()
                        except Exception as e:
                            err_dict = {'tag':p.tag,'reason':f"Error while adding: {e}"}
                            error_log.append(err_dict)

                c_embed = await resc.clash_embed(ctx,
                    message=f"**{p.tag} {p.name}** added as **{p.arix_rank}** to **{p.home_clan.emoji} {p.home_clan.name}**.",
                    color='success')
                await menu.edit(embed=c_embed)

        if len(error_log) > 0:
            error_str = "\u200b"
            for error in error_log:
                error_str += f"{error['tag']}: {error['reason']}\n"

            error_embed = await resc.clash_embed(ctx=ctx,title=f"Errors Encountered",message=error_str)
            await ctx.send(embed=error_embed)

        if added_count >0:
            intro_embed = await resc.get_welcome_embed(self,ctx,user)

            try:
                await user.send(embed=intro_embed)
                await user.send(content="https://discord.gg/tYBh3Gk")
            except:
                await ctx.send(content=f"{user.mention}",embed=intro_embed)
                await ctx.send(content="https://discord.gg/tYBh3Gk")

    @member_manage.command(name="remove")
    async def member_manage_remove(self,ctx,*player_tags):
        """
        Remove members from the Alliance. 

        Multiple tags can be separated by a blank space.
        """

        remove_accounts = []
        error_log = []

        clans, members = await get_current_alliance(ctx)

        for tag in player_tags:
            try:
                p = await aPlayer.create(ctx,tag)
            except TerminateProcessing as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await log_channel.send(eEmbed)
            except Exception as e:
                p = None
                err_dict = {'tag':tag,'reason':e}
                error_log.append(err_dict)
                continue

            if not p.is_member:
                err_dict = {'tag':tag,'reason':'This player is currently not an active member.'}
                error_log.append(err_dict)
                continue

            remove_accounts.append(p)

        if len(remove_accounts) > 0:
            remove_accounts = sorted(remove_accounts,key=lambda a:(a.exp_level, a.town_hall.level),reverse=True)
            cEmbed = await resc.clash_embed(ctx,
                title=f"I found the below accounts to be removed. Please confirm this action.")

            for p in remove_accounts:
                cEmbed.add_field(
                    name=f"**{p.name}** ({p.tag})",
                    value=f">>> Linked to: <@{p.discord_user}>"
                        + f"\n<:Exp:825654249475932170> {p.exp_level}\u3000*{p.home_clan.emoji} {p.arix_rank} of {p.home_clan.name}*"
                        + f"\n{p.town_hall.emote} {p.town_hall.description}\u3000{emotes_league[p.league.name]} {p.trophies} (best: {p.best_trophies})\u3000<:TotalStars:825756777844178944> {p.war_stars}",
                    inline=False)

            confirm_remove = await ctx.send(embed=cEmbed)
            if not await resc.user_confirmation(self,ctx,confirm_remove):
                return

            async with ctx.bot.async_file_lock:
                with ctx.bot.clash_file_lock.write_lock():
                    for p in remove_accounts:
                        try:
                            await p.remove_member()
                            await p.save_to_json()
                        except Exception as e:
                            err_dict = {'tag':p.tag,'reason':f"Error while removing: {e}"}
                            error_log.append(err_dict)
                            remove_accounts.remove(p)

        success_str = "\u200b"
        error_str = "\u200b"
        for p in remove_accounts:
            success_str += f"**{p.tag} {p.name}** removed from {p.home_clan.emoji} {p.home_clan.name}.\n"

        for error in error_log:
            error_str += f"{error['tag']}: {error['reason']}\n"

        aEmbed = await resc.clash_embed(ctx=ctx,title=f"Operation: Remove Member(s)")

        aEmbed.add_field(name=f"**__Success__**",
                        value=success_str,
                        inline=False)

        aEmbed.add_field(name=f"**__Failed__**",
                        value=error_str,
                        inline=False)
        await confirm_remove.edit(embed=aEmbed)

    @member_manage.command(name="addnote")
    async def member_manage_addnote(self,ctx,user:discord.User):
        """
        Add a Leader's note to a member.

        Notes can only be added to active members, and can be added to all of a user's accounts, or only a specific one.
        """

        def response_check(m):
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    return True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    return True
                else:
                    return False
            else:
                return False

        user_accounts_tags = await get_user_accounts(ctx,user.id)
        user_accounts = []
        user_clan_tags = []
        user_clans = []

        for tag in user_accounts_tags:
            try:
                p = await aPlayer.create(ctx,tag)
            except Exception as e:
                eEmbed = await resc.clash_embed(ctx=ctx,message=f"Error retrieving data for {tag}: {e}",color="fail")
                return await ctx.send(embed=eEmbed)

            if p.home_clan.tag not in user_clan_tags:
                user_clan_tags.append(p.home_clan.tag)
                user_clans.append(p.home_clan)

        account_selection = []
        s_dict = {
            'id': 'all_accounts',
            'title': 'Add to User',
            'description': f"Add a Note to all of a Member's accounts."
            }

        if len(user_clans) > 1:
            for clan in user_clans:
                s_dict = {
                    'id': clan.tag,
                    'title': f'Only {clan.emoji} {clan.name}',
                    'description': f"Add a Note to all of a Member's accounts in {clan.name}."
                    }
                account_selection.append(s_dict)

        for p in user_accounts:
            s_dict = {
                'id': p.tag,
                'title': f"**{p.name} ({p.tag})**",
                'description': f"Home Clan: {p.home_clan.emoji} {p.home_clan.name} {p.town_hall.emote} {p.town_hall.description}"
                }
            account_selection.append(s_dict)

        select_embed = await resc.clash_embed(ctx,
            message=f"Where would you like to add this note to?")

        menu, selected_account = await resc.multiple_choice_select(self,
            ctx=ctx,
            sEmbed=select_embed,
            selection_list=account_selection)

        if not selected_account:
            end_embed = await resc.clash_embed(ctx,
                message=f"Did not receive a response. Operation cancelled.",
                color='fail')
            return await menu.edit(embed=end_embed)
        else:
            await menu.delete()

        channel_msg = await ctx.send(content=f"{ctx.author.mention}, submit your note for **{user.display_name}**. You have 3mins.")
        try:
            response_note = await ctx.bot.wait_for("message",timeout=180,check=response_check)
        except asyncio.TimeoutError:
            return await channel_msg.edit(content="Sorry! You timed out.")

        new_note = response_note.content
    
        if selected_account['id'] == 'all_accounts':
            for a in user_accounts:
                await a.add_note(ctx,new_note)
                await a.save_to_json()
        elif selected_account['id'] in user_clan_tags:
            for a in user_accounts:
                if a.home_clan.tag == selected_account['id']:
                    await a.add_note(ctx,new_note)
                    await a.save_to_json()
        else: 
            for a in user_accounts:
                if a.tag == selected_account['id']:
                    await a.add_note(ctx,new_note)
                    await a.save_to_json()

        await response_note.add_reaction('<:green_check:838461472324583465>')

        final_embed = await resc.clash_embed(ctx,message=f"{ctx.author.mention} just added a note to **{user.display_name}**.")

        await ctx.send(embed=final_embed)

    ####################################################################################################
    ### PROMOTE & DEMOTE
    ####################################################################################################
    
    async def rank_handler(self, ctx, action, user:discord.User):
        membership_clans = []
        current_leader = []
        operation_log = []
        error_log = []

        clans,members = await get_current_alliance(ctx)

        for clan_tag in clans:
            try:
                c = await aClan.create(ctx,clan_tag)
            except Exception as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)

            if ctx.author.id == c.leader or ctx.author.id in c.co_leaders:
                clan_accounts = await get_user_accounts(ctx,user.id,c.tag)
                if user.id == c.leader:
                    d = {
                        'clan': c,
                        'rank': 'Leader',
                        'accounts': clan_accounts,
                        }
                    membership_clans.append(d)
                elif user.id in c.co_leaders:
                    d = {
                        'clan': c,
                        'rank': 'Co-Leader',
                        'accounts': clan_accounts,
                        }
                    membership_clans.append(d)
                elif user.id in c.elders:
                    d = {
                        'clan': c,
                        'rank': 'Elder',
                        'accounts': clan_accounts,
                        }
                    membership_clans.append(d)
                elif len(clan_accounts) > 0:
                    d = {
                        'clan': c,
                        'rank': 'Member',
                        'accounts': clan_accounts,
                        }
                    membership_clans.append(d)
                else:
                    pass

        if len(membership_clans) < 1:
            return await ctx.send(f"Your powers are inadequate and you cannot perform this action.")

        if len(membership_clans) == 1:
            handle_rank = membership_clans[0]

            if handle_rank['rank'] == 'Leader':
                return await ctx.send(f"{user.mention} has already achieved god-status and cannot be touched by mere mortals.")
            if action == 'demote' and handle_rank['rank'] == 'Member':
                return await ctx.send(f"If {user.mention} gets demoted they would be banished to uranus.")

            confirm_embed = await resc.clash_embed(ctx,
                title=f"{action.capitalize()} {user.name}#{user.discriminator}",
                message=f"**{handle_rank['clan'].emoji} {handle_rank['clan'].name}**"
                    + f"\nCurrent Rank: {handle_rank['rank']}\nAccounts: {len(handle_rank['accounts'])}"
                    + f"\n\n**Please confirm the above action.**")

            confirm_rank = await ctx.send(embed=confirm_embed)
            if not await resc.user_confirmation(self,ctx,confirm_rank):
                return

        if len(membership_clans) > 1:
            rank_selection = []
            for m in membership_clans:
                if m['rank']=='Leader':
                    continue
                elif action=='demote' and m['rank']=='Member':
                    continue
                else:
                    s_dict = {
                        'id': m['clan'].tag,
                        'emoji': m['clan'].emoji,
                        'title': m['clan'].name,
                        'description': f"Current Rank: {m['rank']}\nAccounts: {len(m['accounts'])}"
                        }
                    rank_selection.append(s_dict)

            if len(rank_selection) == 0:
                if action == 'promote':
                    return await ctx.send(f"{user.mention} has already achieved god-status and cannot be touched by mere mortals.")
                if action == 'demote':
                    return await ctx.send(f"If {user.mention} gets demoted they would be banished to uranus.")

            select_embed = await resc.clash_embed(ctx,
                title=f"{action.capitalize()} {user.name}#{user.discriminator}",
                message="*Reminder: You cannot promote or demote a Leader of a clan. To change the leader of a clan, promote a Co-Leader.*")

            menu, selection = await resc.multiple_choice_select(self,
                ctx=ctx,
                sEmbed=select_embed,
                selection_list=rank_selection,
                selection_text=f"Select a clan to promote {user.name}.")

            if not selection:
                end_embed = await resc.clash_embed(ctx,
                    message=f"No clan selected. Operation cancelled.",
                    color='fail')
                return await menu.edit(embed=end_embed)

            for m in membership_clans:
                if m['clan'].tag == selection['id']:
                    handle_rank = m

        current_rank_index = clanRanks.index(handle_rank['rank'])
        if action == 'promote':
            new_rank = clanRanks[current_rank_index+1]
        if action == 'demote':
            new_rank = clanRanks[current_rank_index-1]

        for account in handle_rank['accounts']:
            async with ctx.bot.async_file_lock:
                with ctx.bot.clash_file_lock.write_lock():
                    try:
                        p = await aPlayer.create(ctx,account)
                        await p.update_rank(new_rank)
                        await p.save_to_json()
                        operation_log.append(p)
                    except Exception as e:
                        err_dict = {'tag':account,'reason':f"Error while updating rank: {e}"}
                        error_log.append(err_dict)
                        continue

        #demote current leader to Co
        if action=='promote' and new_rank == 'Leader':
            current_leader = await get_user_accounts(ctx,handle_rank['clan'].leader,handle_rank['clan'].tag)
            for tag in current_leader:
                async with ctx.bot.async_file_lock:
                    with ctx.bot.clash_file_lock.write_lock():
                        try:
                            p = await aPlayer.create(ctx,tag)
                            await p.update_rank('Co-Leader')
                            await p.save_to_json()
                            operation_log.append(p)
                        except Exception as e:
                            p = None
                            err_dict = {'tag':tag,'reason':f'Error while demoting leader: {e}.'}
                            error_log.append(err_dict)
                            continue
            
        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                try: 
                    await handle_rank['clan'].add_staff(user,new_rank)
                    await handle_rank['clan'].save_to_json()
                except Exception as e:
                    err_dict = {'tag':handle_rank['clan'].tag,'reason':f"Error while updating clan: {e}"}
                    error_log.append(err_dict)

        success_str = "\u200b"
        error_str = "\u200b"
        for p in operation_log:
            if p.tag in current_leader:
                success_str += f"**{p.tag} {p.name}** is now Co-Leader of {handle_rank['clan'].name}.\n"
            else:
                success_str += f"**{p.tag} {p.name}** is now {new_rank} of {handle_rank['clan'].name}.\n"

        for error in error_log:
            error_str += f"{error['tag']}: {error['reason']}\n"

        aEmbed = await resc.clash_embed(ctx=ctx,title=f"Operation Report: {action.capitalize()} {user.name}#{user.discriminator}")

        aEmbed.add_field(name=f"**__Success__**",
                        value=success_str,
                        inline=False)
        aEmbed.add_field(name=f"**__Failed__**",
                        value=error_str,
                        inline=False)
        return await ctx.send(embed=aEmbed)

    @commands.command(name="promote")
    async def member_promote(self,ctx,user:discord.User):
        """Promote a member."""

        if ctx.author.id == user.id:
            return await ctx.send("Self-glorification is not allowed. Go grovel and beg for mercy.")

        await self.rank_handler(
            ctx=ctx,
            action='promote',
            user=user)

    @commands.command(name="demote")
    async def member_demote(self,ctx,user:discord.User):
        """Demote a member."""

        if ctx.author.id == user.id:
            return await ctx.send("Self-mutilation is strongly discouraged. You might want to seek help.")

        await self.rank_handler(
            ctx=ctx,
            action='demote',
            user=user,)

    @commands.command(name="whois")
    async def member_whois(self,ctx,user:discord.User):
        """
        Get information about a Discord user.
        """

        def build_str(a):
            a_str = ""
            if a.is_member:
                clan_des = f"*{a.home_clan.emoji} {a.arix_rank} of {a.home_clan.name}*"
            else:
                clan_des = f"<:Clan:825654825509322752> {a.clan_description}"
            a_str += f"> {clan_des}"
            a_str += f"\n> <:Exp:825654249475932170> {a.exp_level}\u3000{a.town_hall.emote} {a.town_hall.description}\u3000{emotes_league[a.league.name]} {a.trophies}"
            a_str += f"\n> <:TotalTroopStrength:827730290491129856> {a.troop_strength} / {a.max_troop_strength}"
            if a.town_hall.level >= 5:
                a_str += f"\u3000<:TotalSpellStrength:827730290294259793> {a.spell_strength} / {a.max_spell_strength}"
            if a.town_hall.level >= 7:
                a_str += f"\u3000<:TotalHeroStrength:827730291149635596> {a.hero_strength} / {a.max_hero_strength}"
                a_str += f"\n> {a.hero_description}"
            return a_str

        info_embed = await resc.clash_embed(ctx,
            title=f"Member Profile: {user.name}#{user.discriminator}",
            thumbnail=user.avatar_url)

        user_alliance_accounts_tags = await get_user_accounts(ctx,user.id)
        user_linked_accounts = await ctx.bot.discordlinks.get_linked_players(user.id)

        user_alliance_accounts = []
        user_other_accounts = []
        user_error_tags = []
        
        for tag in user_alliance_accounts_tags:
            try:
                p = await aPlayer.create(ctx,tag)
                if p.trophies == 0:
                    await p.retrieve_data()
            except TerminateProcessing as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            except Exception as e:
                p = None
                err_dict = {'tag':tag,'reason':e}
                user_error_tags.append(err_dict)
                continue
            user_alliance_accounts.append(p)

        for tag in [u for u in user_linked_accounts if u not in user_alliance_accounts_tags]:
            try:
                p = await aPlayer.create(ctx,tag)
                await p.retrieve_data()
            except TerminateProcessing as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            except Exception as e:
                p = None
                err_dict = {'tag':tag,'reason':e}
                user_error_tags.append(err_dict)
                continue
            user_other_accounts.append(p)

        user_alliance_accounts = sorted(user_alliance_accounts,key=lambda a:(a.exp_level, a.town_hall.level),reverse=True)
        user_other_accounts = sorted(user_other_accounts,key=lambda a:(a.exp_level, a.town_hall.level),reverse=True)

        info_embed = await resc.clash_embed(ctx,title=f"Member Profile: {user.name}#{user.discriminator}")

        for a in user_alliance_accounts:
            al_str = build_str(a)
            info_embed.add_field(
                name=f"{a.name} ({a.tag})",
                value=al_str+"\n\u200b",
                inline=False)

        for a in user_other_accounts:
            al_str = build_str(a)
            info_embed.add_field(
                name=f"{a.name} ({a.tag})",
                value=al_str+"\n\u200b",
                inline=False)

        await ctx.send(embed=info_embed)

    ####################################################################################################

    ### LEADER REPORTS
    ###
    ### - Membership Summary
    ###     > Users & Accounts
    ###     > Composition
    ###     > TH / Hero / Strength
    ### - All Members
    ### - Missing Member Report
    ### - Unrecognized Accounts Report
    ### - Member Activity Report
    ###     > Donations
    ###     > Loot
    ###     > Clan Capital
    ###     > War
    ###     > Clan Games
    ### - Clan Report
    ###     > War Trends
    ###     > Raid Trends

    ####################################################################################################

    @commands.command(name="getreport")
    async def leader_report(self,ctx,clan_abbreviation:str,season=None):
        """
        Generate various reports for leaders.

        Clan selection by abbreviation.
        """

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)
        if not clan_from_abbreviation:
            await ctx.send(f"The abbreviation {clan_abbreviation} does not correspond to any Alliance clan.")

        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            eEmbed = await resc.clash_embed(ctx=ctx,
                message=f"{e}",
                color="fail")
            return await ctx.send(embed=eEmbed)

        menus_dict = [
            {
                'id': 'summary',
                'title': 'Membership Summary',
                'description': f"Composite Report - includes Discord Users & Accounts, Clan TH Composition, Account Progress, and Hero Levels."
                },
            {
                'id': 'allmembers',
                'title': 'All Members',
                'description': f"Gets a list of all registered members."
                },
            {   
                'id': 'missing',
                'title': 'Missing Member Report',
                'description': f"Gets a list of registered members missing from the in-game clan."
                },
            {
                'id': 'unrecognized',
                'title': 'Unrecognized Accounts',
                'description': f"Gets a list of unregistered accounts in the in-game clan."
                },
            {
                'id': 'activity',
                'title': 'Member Activity *(season-applicable)*',
                'description': f"Donations, Loot, Clan Capital, War, Clan Games"
                },
            {
                'id': 'clan',
                'title': 'Clan Performance Summary',
                'description': f"War Trends, Raid Trends"
                }
            ]

        select_embed = await resc.clash_embed(ctx,
            message=f"Please select a report to generate for **{c.emoji} {c.name}**.")

        menu, selected_report = await resc.multiple_choice_select(self,
            ctx=ctx,
            sEmbed=select_embed,
            selection_list=menus_dict)

        if not selected_report:
            end_embed = await resc.clash_embed(ctx,
                message=f"Did not receive a response. Operation cancelled.",
                color='fail')
            return await menu.edit(embed=end_embed)

        wait_embed = await resc.clash_embed(ctx,message=f"Please wait...")
        await menu.edit(embed=wait_embed)

        if selected_report['id'] == 'summary':
            await self.report_member_summary(ctx,c)

        if selected_report['id'] == 'allmembers':
            await self.report_all_members(ctx,c)

        if selected_report['id'] == 'missing':
            await self.report_missing_members(ctx,c)

        if selected_report['id'] == 'unrecognized':
            await self.report_unrecognized_members(ctx,c)

        if selected_report['id'] == 'activity':
            ##
            pass

        if selected_report['id'] == 'clan':
            ##
            pass

        await menu.delete()

    async def report_member_summary(self,ctx,clan):
        output_embed = []
        error_log = []
        
        member_tags = await get_alliance_members(ctx,clan)
        members = []

        th_composition = {}
        user_count = {}

        for m in member_tags:
            try:
                p = await aPlayer.create(ctx,m)
            except TerminateProcessing as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            except Exception as e:
                p = None
                errD = {
                    'tag':tag,
                    'reason':e
                    }
                error_log.append(tag)
                continue

            members.append(p)

            try:
                user_count[p.discord_user] += 1
            except:
                user_count[p.discord_user] = 0
                user_count[p.discord_user] += 1

            try:
                th_composition[p.town_hall.level] += 1
            except:
                th_composition[p.town_hall.level] = 0
                th_composition[p.town_hall.level] += 1

        members = sorted(members,key=lambda a:(a.town_hall.level,sum([h.level for h in a.heroes])),reverse=True)

        #Users & Accounts
        users_accounts_output = []
        for user, accounts in user_count.items():
            try:
                d_user = ctx.bot.get_user(int(user))
                d_user_display = d_user.display_name
            except:
                d_user_display = "<<Not in Server>>"

            user_accounts = [a for a in members if a.discord_user==user]
            user_accounts = sorted(user_accounts, key=lambda x: (x.exp_level,x.town_hall.level),reverse=True)

            user_account_th = [str(a.town_hall.level) for a in user_accounts]

            output = {
                'User': f"{d_user_display}",
                '# Accs': f"{accounts}",
                'Townhalls': f"{','.join(user_account_th)}"
                }
            users_accounts_output.append(output)

        users_accounts_embed = await resc.clash_embed(ctx,
            title=f"{clan.emoji} {clan.name} ({clan.tag})",
            message=f"**User Summary Report**"
                + f"\n\nTotal Members: {len(members)}"
                + f"\nUnique Members: {len(list(user_count.keys()))}"
                + f"\n\n{box(tabulate(users_accounts_output,headers='keys',tablefmt='pretty'))}")

        output_embed.append(users_accounts_embed)


        #TH Composition
        composition_str = ""
        th_keys_sorted = sorted(list(th_composition.keys()),reverse=True)
        th_all_accounts = [m.town_hall.level for m in members]
        average_th = sum(th_all_accounts) / len(members)

        for th_level in th_keys_sorted:
            composition_str += f"{emotes_townhall[th_level]} **{th_composition[th_level]}** ({int(round((th_composition[th_level] / len(members))*100,0))}%)\n"

        th_composition_embed = await resc.clash_embed(ctx,
            title=f"{clan.emoji} {clan.name} ({clan.tag})",
            message=f"**Clan Composition**"
                + f"\n\nTotal Members: {len(members)}"
                + f"\nAverage: {emotes_townhall[int(average_th)]} {round(average_th,1)}"
                + f"\n\n{composition_str}")

        output_embed.append(th_composition_embed)


        #TH/Hero/Strength
        account_strength_output = []
        hero_strength_output = []
        for m in members:
            bk = ""
            aq = ""
            gw = ""
            rc = ""
            
            troop_strength = str(int((m.troop_strength / m.max_troop_strength)*100)) + "%"
            spell_strength = ""

            if m.town_hall.level >= 6:
                spell_strength = str(int((m.spell_strength / m.max_spell_strength)*100)) + "%"

            if m.town_hall.level >= 7:
                hero_strength = str(int((m.hero_strength / m.max_hero_strength)*100)) + "%"
                bk = [h.level for h in m.heroes if h.name=='Barbarian King'][0]
            if m.town_hall.level >= 9:
                aq = [h.level for h in m.heroes if h.name=='Archer Queen'][0]
            if m.town_hall.level >= 11:
                gw = [h.level for h in m.heroes if h.name=='Grand Warden'][0]
            if m.town_hall.level >= 13:
                rc = [h.level for h in m.heroes if h.name=='Royal Champion'][0]

            account_output = {
                'Name': m.name,
                'TH':m.town_hall.level,
                'Troops': troop_strength,
                'Spells': spell_strength,
                'Heroes': hero_strength,
                }

            hero_output = {
                'Name': m.name,
                'TH': m.town_hall.level,
                'BK':bk,
                'AQ':aq,
                'GW':gw,
                'RC':rc
                }
            account_strength_output.append(account_output)
            hero_strength_output.append(hero_output)

        account_strength_embed = await resc.clash_embed(ctx,
            title=f"{clan.emoji} {clan.name} ({clan.tag})",
            message=f"**Clan Strength (Troops, Spells, Heroes)**"
                + f"\n\n{box(tabulate(account_strength_output,headers='keys',tablefmt='pretty'))}")
        output_embed.append(account_strength_embed)

        hero_strength_embed = await resc.clash_embed(ctx,
            title=f"{clan.emoji} {clan.name} ({clan.tag})",
            message=f"**Clan Strength (Hero Breakdown)**"
                + f"\n\n{box(tabulate(hero_strength_output,headers='keys',tablefmt='pretty'))}")
        output_embed.append(hero_strength_embed)


        if len(output_embed)>1:
            paginator = BotEmbedPaginator(ctx,output_embed)
            await paginator.run()
        elif len(output_embed)==1:
            await ctx.send(embed=output_embed[0])


    async def report_all_members(self,ctx,clan):
        output_embed = []
        error_log = []
        
        member_tags = await get_alliance_members(ctx,clan)
        members = []

        for m in member_tags:
            try:
                p = await aPlayer.create(ctx,m)
            except TerminateProcessing as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            except Exception as e:
                p = None
                errD = {
                    'tag':tag,
                    'reason':e
                    }
                error_log.append(tag)
                continue
            members.append(p)

        members = sorted(members,key=lambda a:(a.town_hall.level,sum([h.level for h in a.heroes]),a.exp_level),reverse=True)

        chunked_members = []
        for z in range(0, len(members), 10):
            chunked_members.append(members[z:z+10])

        page = 0
        mem_count = 0
        for chunk in chunked_members:
            page += 1

            members_embed = await resc.clash_embed(ctx,
                title=f"{clan.emoji} {clan.name} ({clan.tag})",
                message=f"**All Members (Page {page} of {len(chunked_members)})**"
                    + f"\n\nTotal: {len(members)} members")

            for m in chunk:
                mem_count += 1
                m_str = f"> *{m.arix_rank} of {m.home_clan.emoji} {m.home_clan.name}*"
                if m.discord_user:
                    m_str += f"\n> Linked to: <@{m.discord_user}>"
                m_str += f"\n> <:Exp:825654249475932170>{m.exp_level}\u3000{m.town_hall.emote} {m.town_hall.description}\u3000<:Clan:825654825509322752> {m.clan_description}"
                m_str += f"\n> {emotes_league[m.league.name]} {m.trophies} (best: {m.best_trophies})\u3000<:TotalStars:825756777844178944> {m.war_stars}"
                m_str += f"\n> [Open in-game]({m.share_link})"

                members_embed.add_field(
                    name=f"{mem_count}\u3000{m.name} ({m.tag})",
                    value=m_str,
                    inline=False)

            output_embed.append(members_embed)

        if len(output_embed)>1:
            paginator = BotEmbedPaginator(ctx,output_embed)
            await paginator.run()
        elif len(output_embed)==1:
            await ctx.send(embed=output_embed[0])


    async def report_missing_members(self,ctx,clan):
        output_embed = []
        error_log = []
        
        member_tags = await get_alliance_members(ctx,clan)
        members = []

        for m in member_tags:
            try:
                p = await aPlayer.create(ctx,m)
            except TerminateProcessing as e:
                eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            except Exception as e:
                p = None
                errD = {
                    'tag':tag,
                    'reason':e
                    }
                error_log.append(tag)
                continue
            members.append(p)

        members = sorted(members,key=lambda a:(a.town_hall.level,sum([h.level for h in a.heroes]),a.exp_level),reverse=True)

        members_not_in_clan = [m for m in members if m.clan.tag != m.home_clan.tag]

        chunked_not_in_clan = []
        for z in range(0, len(members_not_in_clan), 10):
            chunked_not_in_clan.append(members_not_in_clan[z:z+10])

        page = 0
        for chunk in chunked_not_in_clan:
            page += 1
            members_not_in_clan_embed = await resc.clash_embed(ctx,
                title=f"{clan.emoji} {clan.name} ({clan.tag})",
                message=f"**Members Not In Clan (Page {page} of {len(chunked_not_in_clan)})**"
                    + f"\n\nTotal: {len(members_not_in_clan)} members")

            for m in chunk:
                m_str = f"> {m.town_hall.emote} {m.town_hall.level}\u3000<:Clan:825654825509322752> {m.clan_description}"

                if m.discord_user:
                    m_str += f"\n> Linked to: <@{m.discord_user}>"
                elif m.discord_link:
                    m_str += f"\n> Linked to: <@{m.discord_link}>"
                m_str += f"\n> [Open in-game]({m.share_link})"
                
                members_not_in_clan_embed.add_field(
                    name=f"{m.name} ({m.tag})",
                    value=m_str,
                    inline=False)

            output_embed.append(members_not_in_clan_embed)

        if len(output_embed)>1:
            paginator = BotEmbedPaginator(ctx,output_embed)
            await paginator.run()
        elif len(output_embed)==1:
            await ctx.send(embed=output_embed[0])


    async def report_unrecognized_members(self,ctx,clan):
        output_embed = []
        error_log = []
        
        member_tags = await get_alliance_members(ctx,clan)

        unrecognized_members = [m for m in clan.c.members if m.tag not in member_tags]

        chunked_unrecognized = []
        for z in range(0, len(unrecognized_members), 10):
            chunked_unrecognized.append(unrecognized_members[z:z+10])

        page = 0
        for chunk in chunked_unrecognized:
            page += 1
            members_unrecognized_embed = await resc.clash_embed(ctx,
                title=f"{clan.emoji} {clan.name} ({clan.tag})",
                message=f"**Unrecognized Accounts (Page {page} of {len(chunked_unrecognized)})**"
                    + f"\n\nTotal: {len(unrecognized_members)} members")

            for m in chunk:
                try:
                    m = await aPlayer.create(ctx,m.tag)
                    if not m.is_member:
                        await m.retrieve_data()
                except TerminateProcessing as e:
                    eEmbed = await resc.clash_embed(ctx,message=e,color='fail')
                    return await ctx.send(eEmbed)
                except Exception as e:
                    p = None
                    errD = {
                        'tag':m.tag,
                        'reason':e
                        }
                    error_log.append(tag)
                    continue

                m_str = f"> {m.town_hall.emote} {m.town_hall.level}\u3000<:Clan:825654825509322752> {m.clan_description}"

                if m.discord_user:
                    m_str += f"\n> Linked to: <@{m.discord_user}>"
                elif m.discord_link:
                    m_str += f"\n> Linked to: <@{m.discord_link}>"
                m_str += f"\n> [Open in-game]({m.share_link})"

                members_unrecognized_embed.add_field(
                    name=f"{m.name} ({m.tag})",
                    value=m_str,
                    inline=False)

            output_embed.append(members_unrecognized_embed)

        if len(output_embed)>1:
            paginator = BotEmbedPaginator(ctx,output_embed)
            await paginator.run()
        elif len(output_embed)==1:
            await ctx.send(embed=output_embed[0])


    # @commands.command(name="profile")
    # async def profile(self, ctx, user_or_tag=None):

    #     allianceJson = await datafile_retrieve(self,'alliance')
    #     accounts = []

    #     if not user_or_tag:
    #         user = ctx.author
    #         tag = None
    #     else:
    #         try:
    #             userID = re.search('@(.*)>',user_or_tag).group(1)
    #             user = ctx.bot.get_user(int(userID))
    #             tag = None
    #         except:
    #             tag = user_or_tag        
    #             user = None

    #     if user:
    #         for tag, member in allianceJson['members'].items():
    #             if member['discord_user'] == user.id:
    #                 try:
    #                     p = await getPlayer(self,ctx,tag)
    #                 except ClashPlayerError as err:
    #                     p = None
    #                     errD = {
    #                         'tag':tag,
    #                         'reason':'Unable to find a user with this tag.'
    #                         }
    #                     continue
    #                 except:
    #                     p = None
    #                     errD = {
    #                         'tag':tag,
    #                         'reason':'Unknown error.'
    #                         }
    #                     continue
    #                 else:
    #                     pEmbed = await player_embed(self,ctx,p)
    #                     accounts.append(pEmbed)
    #     elif tag:
    #         try:
    #             p = await getPlayer(self,ctx,tag)
    #         except ClashPlayerError as err:
    #             return await ctx.send(f'Unable to find a user with the tag {tag}.')
    #         except:
    #             return await ctx.send(f'Unable to find a user with the tag {tag}.')
    #         else:
    #             pEmbed = await player_embed(self,ctx,p)
    #             accounts.append(pEmbed)

    #     if len(accounts)>1:
    #         paginator = BotEmbedPaginator(ctx,accounts)
    #         return await paginator.run()
    #     elif len(accounts)==1:
    #         return await ctx.send(embed=embed)

    @commands.command(name="claninfo")
    async def clan_information(self,ctx):
        """Gets information about clans in the alliance."""

        clans, members = await get_current_alliance(ctx)
        alliance_clans = []

        for tag in clans:
            try:    
                c = await aClan.create(ctx,tag)
            except Exception as e:
                eEmbed = await resc.clash_embed(ctx=ctx,message=f"{e}",color="fail")
                return await ctx.send(embed=eEmbed)
            alliance_clans.append(c)

        m_text = ""

        for c in alliance_clans:
            th_str = ""
            for th in c.recruitment_level:
                th_str += f"{emotes_townhall[th]} "

            c_str = f"**__[{c.emoji} {c.name} ({c.tag})]({c.c.share_link})__**"
            c_str += f"\n> <:Clan:825654825509322752> Level {c.level}\u3000{emotes_capitalhall[c.capital_hall]} {c.capital_hall}\u3000Leader: <@{c.leader}>"
            c_str += f"\n> {emotes_league[c.c.war_league.name]} {c.c.war_league.name}\u3000<:ClanWars:825753092230086708> W{c.c.war_wins}/D{c.c.war_ties}/L{c.c.war_losses} (Streak: {c.c.war_win_streak})"
            c_str += f"\n> Members: {c.member_count}/50\u3000Recruiting: {th_str}"
            c_str += f"\n\n{c.description}"
            
            if alliance_clans.index(c) != (len(alliance_clans)-1):
                c_str += f"\n\u200b\n\u200b\n\u200b"

            m_text += c_str

        rEmbed = await resc.clash_embed(ctx=ctx,
            title="AriX Alliance | Clash of Clans",
            message=m_text,
            thumbnail="https://i.imgur.com/TZF5r54.png")

        await ctx.send(embed=rEmbed)

    @commands.command(name="testing")
    async def test_ask(self, ctx):
        #cWar = await self.cClient.get_clan_war('92g9j8cg')

        leader_role_msg = await ctx.send(content=f"{ctx.author.mention}, please mention the Leader role for **cc**.")
        try:
            leader_role_response = await ctx.bot.wait_for("message",timeout=60)
        except asyncio.TimeoutError:
            await emoji_msg.edit(content="Operation cancelled.")
            return
        else:
            leader_role = leader_role_response.content

        await ctx.send(type(leader_role))
        await ctx.send(f"`{leader_role}`")