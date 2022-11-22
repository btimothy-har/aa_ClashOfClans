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
import xlsxwriter

from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from tabulate import tabulate

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select
from aa_resourcecog.constants import clanRanks, emotes_townhall, emotes_league, emotes_capitalhall
from aa_resourcecog.notes import aNote
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing

class AriXLeaderCommands(commands.Cog):
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


    @commands.command(name="recruitment",aliases=["recruiting"])
    async def recruitment_information(self,ctx):
        """
        The Recruiting Hub.

        Provides an overview of all Clan's Recruitment Statuses.
        This includes the number of registered members, the (suggested) townhall levels, and the last 5 Leader's notes on file.
        """

        clans, members = await get_current_alliance(ctx)
        output_embed = []

        for tag in clans:
            try:    
                c = await aClan.create(ctx,tag)
            except Exception as e:
                eEmbed = await clash_embed(ctx=ctx,message=f"{e}",color="fail")
                return await ctx.send(embed=eEmbed)

            th_str = ""
            for th in c.recruitment_level:
                th_str += f"{emotes_townhall[th]} "

            clanEmbed = await clash_embed(ctx=ctx,
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
        """
        Manage Alliance clans.
        """
            
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
            eEmbed = await clash_embed(ctx=ctx,message=f"{e}",color="fail")
            return await ctx.send(embed=eEmbed)

        if force and ctx.author.id in ctx.bot.owner_ids:
            pass
        else:
            if c.is_alliance_clan:
                embed = await clash_embed(ctx=ctx,
                    message=f"The clan {c.name} ({c.tag}) is already part of the Alliance.",
                    color="fail",
                    thumbnail=c.clan.badge.url)
                return await ctx.send(embed=embed)

        info_embed = await clash_embed(ctx=ctx,
            title=f"**You are adding: {c.desc_title}**",
            message=f"{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url)
        add_msg = await ctx.send(embed=info_embed)


        leader_embed = await clash_embed(ctx,message=f"Who will be the **Leader** of **{c.tag} {c.name}**?\n\nPlease mention the user.")
        leader_msg = await ctx.send(content=f"{ctx.author.mention}", embed=leader_embed)
        try:
            leader_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,message=f"Operation timed out.")
            await leader_msg.edit(embed=timeout_embed)
            return
        else:
            leader_id = re.search('@(.*)>',leader_response.content).group(1)
            leader = await ctx.bot.fetch_user(int(leader_id))
            await leader_msg.delete()
            await leader_response.delete()


        abbr_embed = await clash_embed(ctx,
            message=f"Please specify the abbreviation for **{c.tag} {c.name}**?\n\nThis will be used to identify the clan within the Alliance.")
        abbr_msg = await ctx.send(content=f"{ctx.author.mention}", embed=abbr_embed)
        try:
            abbr_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,message=f"Operation timed out.")
            await leader_msg.edit(embed=timeout_embed)
            return
        else:
            clan_abbreviation = abbr_response.content.upper()
            check_abbr = await get_alliance_clan(ctx,clan_abbreviation)
            if not force and check_abbr:
                in_use_embed = await clash_embed(ctx,message=f"The abbreviation {clan_abbreviation} is already in use. Please try again.")
                return await ctx.send(embed=in_use_embed)
            await abbr_msg.delete()
            await abbr_response.delete()


        emoji_embed = await clash_embed(ctx,
            message=f"Please provide the emoji for **{c.tag} {c.name}**.\n\nNote: The emoji must be from a server that the bot is invited to.")
        emoji_msg = await ctx.send(content=f"{ctx.author.mention}", embed=emoji_embed)
        try:
            emoji_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,message=f"Operation timed out.")
            await emoji_msg.edit(embed=timeout_embed)
            return
        else:
            emoji = emoji_response.content
            await emoji_msg.delete()
            await emoji_response.delete()


        coleader_role_embed = await clash_embed(ctx,
            message=f"Please mention the **Co-Leader** role for **{c.tag} {c.name}**.")
        coleader_role_msg = await ctx.send(content=f"{ctx.author.mention}", embed=coleader_role_embed)
        try:
            coleader_role_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,message=f"Operation timed out.")
            await coleader_role_msg.edit(embed=timeout_embed)
            return
        else:
            coleader_role_id = re.search('@&(.*)>',coleader_role_response.content).group(1)
            coleader_role = ctx.guild.get_role(int(coleader_role_id))
            await coleader_role_msg.delete()
            await coleader_role_response.delete()


        elder_role_embed = await clash_embed(ctx,
            message=f"Please mention the **Elder** role for **{c.tag} {c.name}**.")
        elder_role_msg = await ctx.send(content=f"{ctx.author.mention}", embed=elder_role_embed)
        try:
            elder_role_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,message=f"Operation timed out.")
            await elder_role_msg.edit(embed=timeout_embed)
            return
        else:
            elder_role_id = re.search('@&(.*)>',elder_role_response.content).group(1)
            elder_role = ctx.guild.get_role(int(elder_role_id))
            await elder_role_msg.delete()
            await elder_role_response.delete()


        member_role_embed = await clash_embed(ctx,
            message=f"Please mention the **Member** role for **{c.tag} {c.name}**.")
        member_role_msg = await ctx.send(content=f"{ctx.author.mention}", embed=member_role_embed)
        try:
            member_role_response = await ctx.bot.wait_for("message",timeout=60,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,message=f"Operation timed out.")
            await member_role_msg.edit(embed=timeout_embed)
            return
        else:
            member_role_id = re.search('@&(.*)>',member_role_response.content).group(1)
            member_role = ctx.guild.get_role(int(member_role_id))
            await member_role_msg.delete()
            await member_role_response.delete()


        confirm_embed = await clash_embed(ctx=ctx,
            title=f"**New Clan: {c.desc_title}**",
            message=f"Leader: {leader.mention}\nAbbreviation: `{clan_abbreviation}`\u3000Emoji: {emoji}"
                + f"\n\n{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url)

        await add_msg.edit(
            content=f"{ctx.author.mention}, please confirm you would like to add the below clan.",
            embed=confirm_embed)
        if not await user_confirmation(ctx,add_msg):
            return

        await c.add_to_alliance(
            ctx=ctx,
            leader=leader,
            abbreviation=clan_abbreviation,
            emoji=emoji,
            coleader_role=coleader_role,
            elder_role=elder_role,
            member_role=member_role)

        final_embed = await clash_embed(ctx=ctx,
            title=f"Clan Sucessfully Added: **{c.emoji} {c.desc_title}**",
            message=f"Leader: {leader.mention}\u3000Abbreviation: `{c.abbreviation}`"
                + f"\n\n{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            color='success')

        await add_msg.delete()
        return await ctx.send(embed=final_embed)

    @clan_manage.command(name="remove")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_remove(self, ctx, clan_abbreviation):
        """
        Remove a clan from the Alliance.

        Use the Clan Abbreviation to specify a clan.
        """

        c = await get_alliance_clan(ctx,clan_abbreviation)
        if not c:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)
        c = c[0]

        confirm_embed = await clash_embed(ctx=ctx,
            title=f"Remove Clan: **{c.emoji} {c.desc_title}**",
            message=f"Leader: <@{c.leader}>\u3000Abbreviation: `{c.abbreviation}`"
                + f"\n\n{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link)

        confirm_remove = await ctx.send(
            content=f"{ctx.author.mention}, please confirm you would like to remove the below clan.",
            embed=confirm_embed)
        if not await user_confirmation(ctx,confirm_remove):
            return

        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(ctx.bot.clash_dir_path+'/alliance.json','r+') as file:
                    file_json = json.load(file)
                    del file_json['clans'][c.tag]
                    file.seek(0)
                    json.dump(file_json,file,indent=2)
                    file.truncate()

        final_embed = await clash_embed(ctx=ctx,
            title=f"Clan Sucessfully Removed: **{c.emoji} {c.desc_title}**",
            message=f"Leader: <@{c.leader}>\u3000Abbreviation: `{c.abbreviation}`"
                + f"\n\n{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link,
            color='success')
    
        await confirm_remove.delete()
        await ctx.send(embed=final_embed)


    @clan_manage.command(name="setleader")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_setleader(self, ctx, clan_abbreviation, new_leader:discord.User):
        """
        [Admin-only] Overrides the set Leader for a clan.

        """

        c = await get_alliance_clan(ctx,clan_abbreviation)
        if not c:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)
        c = c[0]

        confirm_embed = await clash_embed(ctx=ctx,
            title=f"Leader Override: **{c.emoji} {c.desc_title}**",
            message=f"**New Leader: {new_leader.mention}**"
                + f"\n\n{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url)

        confirm_remove = await ctx.send(
            content=f"{ctx.author.mention}, please confirm you would like to assign {new_leader.mention} as the Leader of the above clan.",
            embed=confirm_embed)
        if not await user_confirmation(ctx,confirm_remove):
            return

        try:
            await c.add_staff(ctx,new_leader,"Leader")
        except Exception as e:
            err_embed = await clash_embed(ctx,
                message=f"Error encountered while updating clan: {e}.",
                color="fail")
            return await ctx.send(embed=err_embed)

        final_embed = await clash_embed(ctx=ctx,
            title=f"Leader Assigned: **{c.emoji} {c.desc_title}**",
            message=f"\n*Note: It may take up to 10 minutes for player accounts to reflect the updated Rank.*"
                + f"\n\n**New Leader: <@{c.leader}>**"
                + f"\n\n{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.c.badge.url,
            url=c.c.share_link,
            color='success')
    
        await confirm_remove.delete()
        await ctx.send(embed=final_embed)


    @clan_manage.command(name="settings")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_settings(self, ctx, clan_abbreviation):
        """
        Change various settings for the provided clan.

        Select a Clan by specifying the Clan Abbreviation.
        """

        toggle_state = {
            True: "On",
            False: "Off"
            }

        def response_check(m):
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    return True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    return True
                else:
                    return False

        def townhall_check(m):
            msg_check = False
            all_check = False
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    msg_check = True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    msg_check = True

            if msg_check:
                townhall_out_of_range = [int(th) for th in m.content.split() if int(th) not in range(1,16)]
                if len(townhall_out_of_range) == 0:
                    all_check = True
            return all_check


        c = await get_alliance_clan(ctx,clan_abbreviation)
        if not c:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)
        c = c[0]

        menu_dict = []

        emoji_option =  {
            'id': 'emoji',
            'title': 'Change the Clan Emoji',
            'description': 'The Clan Emoji is used to identify the clan within the Alliance.',
            }

        recruit_option = {
            'id': 'recruit',
            'title': 'Change the Recruiting Townhalls',
            'description': 'Change the Townhall Levels the clan is currently recruiting for.',
            }

        description_option = {
            'id': 'description',
            'title': 'Change the custom Description.',
            'description': 'Change the custom Description used for this clan.'
            }

        announcement_option = {
            'id': 'announcement_channel',
            'title': 'Set the Announcement channel.',
            'description': 'Automated announcements will be sent in this channel.'
            }

        reminder_ch_option = {
            'id': 'reminder_channel',
            'title': 'Set the Reminder channel.',
            'description': 'Reminders will be sent in this channel.'
            }

        war_reminder_toggle = {
            'id': 'war_reminder',
            'title': 'Toggle War Reminders.',
            'description': 'War reminders are sent at the 12 hour, 4 hour, and 1 hour (remaining time) mark of a War.'
            }

        raid_reminder_toggle = {
            'id': 'raid_reminder',
            'title': 'Toggle Raid Reminders.',
            'description': 'Raid reminders are sent at the 36 hour, 24 hour, 12 hour, and 4 hour (remaining time) mark of the Raid Weekend.'
            }

        if (ctx.author.id == c.leader or ctx.author.id in c.co_leaders) or ctx.author.id in ctx.bot.owner_ids:
            menu_dict.append(emoji_option)
            menu_dict.append(recruit_option)
            menu_dict.append(war_reminder_toggle)
            menu_dict.append(raid_reminder_toggle)

        if ctx.author.id in ctx.bot.owner_ids:
            menu_dict.append(announcement_option)
            menu_dict.append(reminder_ch_option)

        if len(menu_dict) == 0:
            no_permission_embed = await clash_embed(ctx,
                message=f"You don't have the necessary permissions to make changes to {c.emoji} **{c.name}**.\n\nYou need to be a Co-Leader or Leader to change a Clan's settings.",
                color='fail')

            return await ctx.send(content=ctx.author.mention,embed=no_permission_embed)

        menu_dict = await multiple_choice_menu_generate_emoji(ctx,menu_dict)

        select_str = ""
        for i in menu_dict:
            select_str += f"{i['emoji']} **{i['title']}**"
            select_str += f"\n{i['description']}"

            if menu_dict.index(i) < (len(menu_dict)-1):
                select_str += f"\n\n"

        message = None
        response = 'start'
        task_state = True
        state_text = ""

        while task_state:
            #try:
            if response in ['start','menu']:

                th_str = ''
                for th in c.recruitment_level:
                    th_str += emotes_townhall[th]

                announcement_embed = await clash_embed(ctx,
                    title=f"Clan Settings: {c.emoji} {c.desc_title}",
                    message=f"\n{state_text}"
                        + f"\n\nEmoji: {c.emoji}"
                        + f"\nRecruiting: {th_str}"
                        + f"\n\nAnnouncement Channel: <#{c.announcement_channel}>"
                        + f"\nReminder Channel: <#{c.reminder_channel}>"
                        + f"\n\nWar Reminders: `{toggle_state[c.send_war_reminder]}`"
                        + f"\nRaid Reminders: `{toggle_state[c.send_raid_reminder]}`\n\u200b")

                announcement_embed.add_field(
                    name="```**What would you like to do today?**```",
                    value=f"\u200b\n{select_str}\n\n*Exit this Menu at any time by clicking on <:red_cross:838461484312428575>.*\n\u200b",
                    inline=False
                    )

                if message:
                    await message.edit(content=ctx.author.mention,embed=announcement_embed)
                else:
                    message = await ctx.send(content=ctx.author.mention,embed=announcement_embed)

                await message.clear_reactions()
                selection = await multiple_choice_menu_select(ctx,message,menu_dict,timeout=60)

                if selection:
                    response = selection['id']
                else:
                    response = None

            if response in ['emoji']:
                await message.clear_reactions()
                emoji_embed = await clash_embed(ctx,message=f"Please provide the new Emoji for **{c.name}**.")
                await message.edit(content=ctx.author.mention,embed=emoji_embed)

                try:
                    response_msg = await ctx.bot.wait_for("message",timeout=60,check=response_check)
                except asyncio.TimeoutError:
                    end_embed = await clash_embed(ctx,message=f"Operation timed out.")
                    await message.edit(embed=end_embed)
                    return

                await c.set_emoji(ctx,response_msg.content)
                state_text = f"**The emoji for {c.name} is now {c.emoji}.**"
                response = 'menu'


            if response in ['recruit']:
                await message.clear_reactions()
                rectownhall_embed = await clash_embed(ctx,
                    message=f"Please provide the Townhall Levels that {c.emoji} **{c.name}** will be recruiting for."
                        + "\n\nYou can separate multiple Townhall Levels with spaces.")
                await message.edit(content=ctx.author.mention,embed=rectownhall_embed)

                try:
                    response_msg = await ctx.bot.wait_for("message",timeout=60,check=townhall_check)
                except asyncio.TimeoutError:
                    end_embed = await clash_embed(ctx,message=f"Operation timed out.")
                    await message.edit(embed=end_embed)
                    return

                townhalls = response_msg.content.split()
                await c.set_recruitment_level(ctx,townhalls)
                await response_msg.delete()
                th_str = ""
                for th in c.recruitment_level:
                    th_str += emotes_townhall[int(th)]
                state_text = f"**{c.emoji} {c.name} is now recruiting for {th_str}.**"
                response = 'menu'


            if response in ['announcement_channel']:
                await message.clear_reactions()
                announcement_ch_embed = await clash_embed(ctx,message=f"Please specify the Announcement Channel for **{c.emoji} {c.name}**.")
                await message.edit(content=ctx.author.mention,embed=announcement_ch_embed)

                try:
                    response_msg = await ctx.bot.wait_for("message",timeout=60,check=response_check)
                except asyncio.TimeoutError:
                    end_embed = await clash_embed(ctx,message=f"Operation timed out.")
                    await message.edit(embed=end_embed)
                    return

                try:
                    announcement_channel_id = re.search('#(.*)>',response_msg.content).group(1)
                    announcement_channel = ctx.guild.get_channel(int(announcement_channel_id))
                    await c.set_announcement_channel(ctx,announcement_channel.id)
                except Exception as e:
                    return await error_end_processing(ctx,
                        preamble=f"Error encountered when setting Announcement channel",
                        err=e)
                else:
                    await response_msg.delete()
                    state_text = f"**The Announcement Channel for {c.emoji} {c.name} is now <#{announcement_channel.id}>.**"
                    response = 'menu'


            if response in ['reminder_channel']:
                await message.clear_reactions()
                reminder_ch_embed = await clash_embed(ctx,message=f"Please specify the Reminder Channel for **{c.emoji} {c.name}**.")
                await message.edit(content=ctx.author.mention,embed=reminder_ch_embed)

                try:
                    response_msg = await ctx.bot.wait_for("message",timeout=60,check=response_check)
                except asyncio.TimeoutError:
                    end_embed = await clash_embed(ctx,message=f"Operation timed out.")
                    await message.edit(embed=end_embed)
                    return

                try:
                    reminder_channel_id = re.search('#(.*)>',response_msg.content).group(1)
                    reminder_channel = ctx.guild.get_channel(int(reminder_channel_id))
                    await c.set_reminder_channel(ctx,reminder_channel.id)
                except Exception as e:
                    return await error_end_processing(ctx,
                        preamble=f"Error encountered when setting Reminder channel",
                        err=e)
                else:
                    await response_msg.delete()
                    state_text = f"**The Reminder Channel for {c.emoji} {c.name} is now <#{reminder_channel.id}>.**"
                    response = 'menu'


            if response in ['war_reminder']:
                await message.clear_reactions()
                await c.toggle_war_reminders(ctx)
                state_text = f"**War Reminders for {c.emoji} {c.name} is now {toggle_state[c.send_war_reminder]}.**"
                response = 'menu'

            if response in ['raid_reminder']:
                await message.clear_reactions()
                await c.toggle_raid_reminders(ctx)
                state_text = f"**Raid Reminders for {c.emoji} {c.name} is now {toggle_state[c.send_war_reminder]}.**"
                response = 'menu'


            # except Exception as e:
            #     err_embed = await clash_embed(ctx,
            #         message=f"Error encountered while changing settings: {e}.",
            #         color="fail")
            #     if message:
            #         await message.edit(embed=err_embed)
            #     else:
            #         await ctx.send(embed=err_embed)
            #     response = None

            if not response:
                task_state = False

        ended_embed = await clash_embed(ctx,
            message="Menu closed.",
            color="fail")

        if message:
            await message.edit(embed=ended_embed)
            await message.clear_reactions()
        else:
            await ctx.send(embed=ended_embed)


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

        c = await get_alliance_clan(ctx,clan_abbreviation)
        if not c:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)
        c = c[0]

        cEmbed = await clash_embed(ctx,message=f"You may create your note for {c.emoji} **{c.name}** via DMs. You have 3 minutes to respond in DMs.")
        dEmbed = await clash_embed(ctx,message=f"You have 3 minutes to create your new note for {c.emoji} **{c.name}**.")

        channel_msg = await ctx.send(content=f"{ctx.author.mention}",embed=cEmbed)
        dm_message = await ctx.author.send(content=f"{ctx.author.mention}",embed=dEmbed)
        
        try:
            response_note = await ctx.bot.wait_for("message",timeout=180,check=response_check)
        except asyncio.TimeoutError:
            tEmbed = await clash_embed(ctx,message=f"Operation timed out.")
            await channel_msg.edit(embed=tEmbed)
            await dm_message.edit(embed=tEmbed)
            return
        
        new_note = response_note.content

        try:
            await c.add_note(ctx,new_note)
        except Exception as e:
            eEmbed = await clash_embed(ctx,message=f"Error encountered while saving note: {e}")
            return await ctx.send(embed=eEmbed)

        await response_note.add_reaction('<:green_check:838461472324583465>')

        final_embed = await clash_embed(ctx,message=f"{ctx.author.mention} just added a note to {c.emoji} **{c.name}**.")
        await channel_msg.delete()
        await ctx.send(embed=final_embed)

    
    ####################################################################################################

    ### MEMBER MANAGEMENT COMMANDS
    ###
    ### - member
    ###     > add : add a member to the alliance
    ###     > remove : remove a member from the alliance
    ###     > setnick : set a user's nickname based on their registered accounts
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
        Manage Alliance Members.
        """
        
        if not ctx.invoked_subcommand:
            pass

    @member_manage.command(name="add")
    async def member_manage_add(self,ctx,user:discord.User, silent_mode_param=None):
        """
        Add a member to the Alliance.

        You will be prompted for the Player Tags after the command is executed.

        To add silently and not send the welcome message, include an "S" after mentioning the Discord user. (e.g. `member add @user S`).
        """

        def response_check(m):
            msg_check = False
            tag_check = False
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    msg_check = True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    msg_check = True

            if msg_check:
                tag_check = True
                if m.content.lower() == 'cancel':
                    pass
                else:
                    for tag in m.content.split():
                        if not coc.utils.is_valid_tag(tag):
                            tag_check = False
            return tag_check

        silent_mode = False
        error_log = []
        added_count = 0

        if silent_mode_param:
            if silent_mode_param.lower() == "s":
                silent_mode = True

        alliance_clans = await get_alliance_clan(ctx)

        if not len(alliance_clans) >= 1:
            return await no_clans_registered(ctx)

        ask_player_tags = await clash_embed(ctx,
            message=f"**Please send the Clash Player Tags for {user.mention}.**"
                + f"\n\nSeparate multiple tags with a space in between."
                + f"\n\nTo cancel, send `cancel`.")

        ask_tags_msg = await ctx.send(content=ctx.author.mention,embed=ask_player_tags)

        try:
            player_tags_reply = await ctx.bot.wait_for("message",timeout=120,check=response_check)
        except asyncio.TimeoutError:
            timeout_embed = await clash_embed(ctx,
                message="Sorry, the sequence timed out! Please try again.",
                color='fail')
            await ask_tags_msg.edit(embed=timeout_embed)
            return

        if player_tags_reply.content.lower() == 'cancel':
            cancel_embed = await clash_embed(ctx,
                message="Member add cancelled.",
                color='fail')
            await player_tags_reply.delete()
            await ask_tags_msg.edit(embed=cancel_embed)
            return

        input_tags = player_tags_reply.content.split()
        player_tags = []
        [player_tags.append(x) for x in input_tags if x not in player_tags]

        await ask_tags_msg.delete()
        await player_tags_reply.delete()

        for tag in player_tags:
            clan_selection = []
            clan_selection_str = ""
            for c in alliance_clans:
                await c.update_member_count(ctx)

                th_str = ""
                for th in c.recruitment_level:
                    th_str += f"{emotes_townhall[th]} "
                c_dict = {
                    'id': c.tag,
                    'emoji': c.emoji,
                    'title': f"**{c.abbreviation} {c.name} ({c.tag})**",
                    'description': f"\u200b\u3000Members: {c.member_count}\u3000Recruiting: {th_str}"
                    }
                clan_selection.append(c_dict)
                clan_selection_str += f"{c_dict['emoji']} {c_dict['title']}\n{c_dict['description']}"

                if alliance_clans.index(c) < (len(alliance_clans)-1):
                    clan_selection_str += "\n\n"

            try:
                p = await aPlayer.create(ctx,tag,fetch=True)
            except TerminateProcessing as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for {tag}",
                    err=e)
            except Exception as e:
                p = None
                err_dict = {'tag':tag,'reason':f"Error retrieving data: {e}"}
                error_log.append(err_dict)
                continue

            player_notes = ""
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

            if player_notes != "":
                p_notes = "\n\n**__Important Notes__**" + player_notes
            else:
                p_notes = ""

            player_embed = await clash_embed(ctx,
                title=f"Add Member: {p.desc_title}",
                message=f"<:Discord:1040423151760314448> {user.mention}\n"
                    + f"{p.desc_full_text}"
                    + f"{p_notes}\n\u200b",
                thumbnail=user.avatar_url)

            player_embed.add_field(
                name="__**Select a Home Clan for this account.**__",
                value=clan_selection_str,
                inline=False)

            homeclan_msg = await ctx.send(content=ctx.author.mention,embed=player_embed)

            selected_clan = await multiple_choice_menu_select(
                ctx=ctx,
                smsg = homeclan_msg,
                sel_list=clan_selection)

            if not selected_clan:
                not_added_embed = await clash_embed(ctx,message=f"{p.desc_title} was not added to AriX. Skipping...")
                homeclan_msg.edit(embed=not_added_embed)
                continue

            added_count += 1
            target_clan = [c for c in alliance_clans if c.tag == selected_clan['id']][0]

            if target_clan.tag == p.home_clan.tag and p.is_member:
                await homeclan_msg.delete()
                c_embed = await clash_embed(ctx,
                    message=f"**{p.tag} {p.name}** is already a **{p.arix_rank}** in **{p.home_clan.emoji} {p.home_clan.name}**.",
                    color='success')
                await ctx.send(embed=c_embed)
            else:
                try:
                    previous_home_clan = p.home_clan
                    await p.new_member(ctx,user,target_clan)

                except Exception as e:
                    err_dict = {'tag':p.tag,'reason':f"Error while adding: {e}"}
                    error_log.append(err_dict)

                await homeclan_msg.delete()
                c_embed = await clash_embed(ctx,
                    message=f"**{p.tag} {p.name}** added as **{p.arix_rank}** to **{p.home_clan.emoji} {p.home_clan.name}**.",
                    color='success')
                await ctx.send(embed=c_embed)

        if len(error_log) > 0:
            error_str = "\u200b"
            for error in error_log:
                error_str += f"{error['tag']}: {error['reason']}\n"

            error_embed = await clash_embed(ctx=ctx,title=f"Errors Encountered",message=error_str)
            await ctx.send(embed=error_embed)

        if not silent_mode and added_count >0:
            intro_embed = await resc.get_welcome_embed(ctx,user)

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

        if len(player_tags) == 0:
            eEmbed = await clash_embed(ctx=ctx,
                message=f"Please provide Player Tags to be added. Separate multiple tags with a space.",
                color="fail")
            return await ctx.send(embed=eEmbed)

        for tag in player_tags:
            try:
                p = await aPlayer.create(ctx,tag)
            except TerminateProcessing as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for {tag}",
                    err=e)
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
            remove_accounts = sorted(remove_accounts,key=lambda x:(x.exp_level, x.town_hall.level),reverse=True)
            cEmbed = await clash_embed(ctx,
                title=f"I found the below accounts to be removed. Please confirm this action.")

            for p in remove_accounts:
                title, text, summary = await resc.player_description(ctx,p)
                cEmbed.add_field(
                    name=f"{title}",
                    value=f"> <:Discord:1040423151760314448> <@{p.discord_user}>"
                        + f"\n> {summary}",
                    inline=False)

            confirm_remove = await ctx.send(embed=cEmbed)
            if not await user_confirmation(ctx,confirm_remove):
                return

            for p in remove_accounts:
                try:
                    await p.remove_member(ctx)
                except Exception as e:
                    err_dict = {'tag':p.tag,'reason':f"Error while removing: {e}"}
                    error_log.append(err_dict)
                    remove_accounts.remove(p)

            await confirm_remove.delete()

        success_str = "\u200b"
        error_str = "\u200b"
        for p in remove_accounts:
            home_clan = p.home_clan
            success_str += f"**{p.tag} {p.name}** removed from {home_clan.emoji} {home_clan.name}.\n"

        for error in error_log:
            error_str += f"{error['tag']}: {error['reason']}\n"

        aEmbed = await clash_embed(ctx=ctx,title=f"Operation: Remove Member(s)")

        if len(remove_accounts) > 0 :
            aEmbed.add_field(name=f"**__Success__**",
                value=success_str,
                inline=False)

        if len(error_log) > 0:
            aEmbed.add_field(name=f"**__Failed__**",
                value=error_str,
                inline=False)
        await ctx.send(embed=aEmbed)


    @member_manage.command(name="addnote")
    async def member_manage_addnote(self,ctx,user:discord.User):
        """
        Add a Leader's note to a member.

        Notes can only be added to active members, and can be added to all of a user's accounts, or only a specific one.
        """

        def response_check(m):
            if m.author.id == ctx.author.id and m.channel.type == discord.ChannelType.private:
                return True
            else:
                return False

        home_clans, user_accounts = await get_user_profile(ctx,user.id)

        user_accounts = [a for a in user_accounts if a.is_member]
        user_accounts = sorted(user_accounts,key=lambda x:(x.exp_level, x.town_hall.level),reverse=True)

        account_selection = []
        s_dict = {
            'id': 'all_accounts',
            'title': 'Add to User',
            'description': f"Add a Note to all of a Member's accounts."
            }
        account_selection.append(s_dict)

        if len(home_clans) > 1:
            for clan in home_clans:
                s_dict = {
                    'id': clan.tag,
                    'title': f'Only {clan.emoji} {clan.name}',
                    'description': f"Add a Note to all of a Member's accounts in {clan.name}."
                    }
                account_selection.append(s_dict)

        for p in user_accounts:
            s_dict = {
                'id': p.tag,
                'title': f"{p.desc_title}",
                'description': f"{p.desc_summary_text}"
                }
            account_selection.append(s_dict)

        account_selection = await multiple_choice_menu_generate_emoji(ctx,account_selection)

        selection_str = ""
        for i in account_selection:
            selection_str += f"{i['emoji']} **{i['title']}**\n{i['description']}"
            if account_selection.index(i) < (len(account_selection)-1):
                selection_str += "\n\n"

        select_embed = await clash_embed(ctx,
            title=f"Add Note: {user.name}#{user.discriminator}",
            message=f"**Where would you like to add this note to?**"
                + f"\n\n{selection_str}")

        select_msg = await ctx.send(content=ctx.author.mention,embed=select_embed)

        selected_account = await multiple_choice_menu_select(ctx,select_msg,account_selection)
        if not selected_account:
            cancel_embed = await clash_embed(ctx,
                message="Operation cancelled.",
                color="fail")
            await select_msg.edit(embed=cancel_embed)
            return

        cEmbed = await clash_embed(ctx,message=f"You may create your note for {user.mention} via DMs. You have 3 minutes to respond in DMs.")
        dEmbed = await clash_embed(ctx,message=f"You have 3 minutes to create your new note for {user.mention}.")

        channel_msg = await ctx.send(content=f"{ctx.author.mention}",embed=cEmbed)
        dm_message = await ctx.author.send(content=f"{ctx.author.mention}",embed=dEmbed)

        try:
            response_note = await ctx.bot.wait_for("message",timeout=180,check=response_check)
        except asyncio.TimeoutError:
            tEmbed = await clash_embed(ctx,message=f"Operation timed out.")
            await channel_msg.edit(embed=tEmbed)
            await dm_message.edit(embed=tEmbed)

        new_note = response_note.content
    
        try:
            if selected_account['id'] == 'all_accounts':
                for a in user_accounts:
                    await a.add_note(ctx,new_note)

            elif selected_account['id'] in [c.tag for c in home_clans]:
                for a in user_accounts:
                    if a.home_clan.tag == selected_account['id']:
                        await a.add_note(ctx,new_note)

            else:
                for a in user_accounts:
                    if a.tag == selected_account['id']:
                        await a.add_note(ctx,new_note)

        except Exception as e:
            eEmbed = await clash_embed(ctx,message=f"Error encountered while saving note: {e}")
            return await ctx.send(embed=eEmbed)

        await response_note.add_reaction('<:green_check:838461472324583465>')
        final_embed = await clash_embed(ctx,message=f"{ctx.author.mention} just added a note to **{user.mention}**.")

        await ctx.send(embed=final_embed)

    @member_manage.command(name="setnick")
    async def member_manage_setnickname(self,ctx,user:discord.User):
        """
        Set a member's nickname.

        Nicknames can only be set from a user's active accounts. 
        """

        new_nickname = await resc.user_nickname_handler(ctx,user)

        if not new_nickname:
            return

        try:
            discord_member = ctx.guild.get_member(user.id)
            await discord_member.edit(nick=new_nickname)
            success_embed = await clash_embed(ctx,
                message=f"{user.name}#{user.discriminator}'s nickname has been set to {new_nickname}.",
                color='success')
            return await ctx.send(embed=success_embed)
        except Exception as e:
            end_embed = await clash_embed(ctx,
                message=f"I don't have permissions to change {user.mention}'s nickname. Error: {e}.\n\nProposed nickname: {new_nickname}.",
                color='fail')
            return await ctx.send(embed=end_embed)


    ####################################################################################################
    ### PROMOTE & DEMOTE
    ####################################################################################################
    
    async def rank_handler(self, ctx, action, user:discord.User):

        eligible_ranks = []
        operation_log = []
        error_log = []

        leader_ct = 0
        member_ct = 0

        user_home_clans, user_accounts = await get_user_profile(ctx,user.id)

        for c in user_home_clans:
            clan_accounts = [a for a in user_accounts if a.home_clan.tag == c.tag]

            #do nothing to Leaders
            if clan_accounts[0].arix_rank == 'Leader':
                leader_ct += 1
                pass

            #Only Leaders can promote/demote Co-Leaders
            elif clan_accounts[0].arix_rank == 'Co-Leader' and ctx.author.id == c.leader:
                d = {
                    'clan': c,
                    'emoji': c.emoji,
                    'rank': 'Co-Leader',
                    'accounts': clan_accounts
                    }
                eligible_ranks.append(d)

            #Leaders or Co-Leaders can promote/demote Members/Elders
            elif ctx.author.id == c.leader or ctx.author.id in c.co_leaders:
                if action == 'demote' and clan_accounts[0].arix_rank == 'Member':
                    member_ct += 1
                    pass
                else:
                    d = {
                        'clan': c,
                        'emoji': c.emoji,
                        'rank': clan_accounts[0].arix_rank,
                        'accounts': clan_accounts
                        }
                    eligible_ranks.append(d)

        if len(eligible_ranks) == 0:
            if leader_ct > 0:
                ineligible_embed = await clash_embed(ctx,
                    message=f"{user.mention} has already achieved god-status and cannot be touched by mere mortals.",
                    color='fail')
            elif action=='demote' and member_ct > 0:
                ineligible_embed = await clash_embed(ctx,
                    message=f"I cannot allow you to banish {user.mention} to uranus.",
                    color='fail')
            else:
                ineligible_embed = await clash_embed(ctx,
                    message=f"Your powers are inadequate and you cannot perform this action.",
                    color='fail')

            return await ctx.send(content=ctx.author.mention,embed=ineligible_embed)


        if len(eligible_ranks) == 1:
            handle_rank = eligible_ranks[0]

            confirm_embed = await clash_embed(ctx,
                title=f"{action.capitalize()} {user.name}#{user.discriminator}",
                message=f"**Please confirm this action.**"
                    + f"\n\n**{handle_rank['clan'].emoji} {handle_rank['clan'].name}**"
                    + f"\nCurrent Rank: {handle_rank['rank']}"
                    + f"\nNew Rank: *{clanRanks[clanRanks.index(handle_rank['rank'])+1]}*"
                    + f"\nAccounts: {len(handle_rank['accounts'])}")

            confirm = await ctx.send(content=ctx.author.mention,embed=confirm_embed)
            if not await user_confirmation(ctx,confirm):
                return

        if len(eligible_ranks) > 1:
            selection_list = ""
            selection_str = ""
            for i in eligible_ranks:
                d = {
                    'id': i['clan'].tag,
                    'title': i['clan'].desc_title,
                    'emoji': i['emoji'],
                    'description': f"Current Rank: {i['rank']}\u3000New Rank: {clanRanks[clanRanks.index(i['rank'])+1]}\nAccounts: {len(i['accounts'])}"
                    }
                selection_list.append(d)
                selection_str += f"{d['emoji']} **{d['title']}**\n{d['description']}"

                if eligible_ranks.index(i) < (len(eligible_ranks)-1):
                    selection_str += "\n\n"

            select_embed = await clash_embed(ctx,
                title=f"{action.capitalize()} {user.name}#{user.discriminator}",
                message="*Reminder: You cannot promote or demote a Leader of a clan. To change the leader of a clan, promote a Co-Leader.*"
                    + f"\n\n**Select a Clan to {action} {user.mention} in.**"
                    + f"\n\n{selection_str}")

            select = await ctx.send(content=ctx.author.mention,embed=select_embed)

            selected_clan = await multiple_choice_menu_select(ctx,select,selection_list)

            if not selected_clan:
                return None

            handle_rank = [i for i in eligible_ranks if i['clan'].tag == selected_clan['id']][0]

        rank_clan = handle_rank['clan']

        current_rank_index = clanRanks.index(handle_rank['rank'])
        if action == 'promote':
            new_rank = clanRanks[current_rank_index+1]
        if action == 'demote':
            new_rank = clanRanks[current_rank_index-1]

        try:
            await rank_clan.update_member_rank(ctx,user,new_rank)
        except:
            err_embed = await clash_embed(ctx,
                message=f"I ran into an error while updating Ranks: {rank_clan.tag} {e}.",
                color='fail')
            return await ctx.send(embed=err_embed)

        for a in handle_rank['accounts']:
            await aPlayer.create(ctx,a.tag,fetch=True)

        result_embed = await clash_embed(ctx,
            message=f"{user.mention} is now a **{new_rank}** in {rank_clan.emoji} **{rank_clan.desc_title}**.",
            color='success')

        return await ctx.send(embed=result_embed)


    @commands.command(name="promote")
    async def member_promote(self,ctx,user:discord.User):
        """Promote a member."""

        if ctx.author.id == user.id:
            eEmbed = await clash_embed(ctx,message=f"Self-glorification is not allowed. Go grovel and beg for mercy.",color='fail')
            return await ctx.send(embed=eEmbed)

        await self.rank_handler(
            ctx=ctx,
            action='promote',
            user=user)

    @commands.command(name="demote")
    async def member_demote(self,ctx,user:discord.User):
        """Demote a member."""

        if ctx.author.id == user.id:
            eEmbed = await clash_embed(ctx,message=f"Self-mutilation is strongly discouraged. You might want to seek help.",color='fail')
            return await ctx.send(embed=eEmbed)

        await self.rank_handler(
            ctx=ctx,
            action='demote',
            user=user)


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

        info_embed = await clash_embed(ctx,
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
                eEmbed = await clash_embed(ctx,message=e,color='fail')
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
                eEmbed = await clash_embed(ctx,message=e,color='fail')
                return await ctx.send(eEmbed)
            except Exception as e:
                p = None
                err_dict = {'tag':tag,'reason':e}
                user_error_tags.append(err_dict)
                continue
            user_other_accounts.append(p)

        user_alliance_accounts = sorted(user_alliance_accounts,key=lambda a:(a.exp_level, a.town_hall.level),reverse=True)
        user_other_accounts = sorted(user_other_accounts,key=lambda a:(a.exp_level, a.town_hall.level),reverse=True)

        info_embed = await clash_embed(ctx,title=f"Member Profile: {user.name}#{user.discriminator}")

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
    ### - Excel Extract

    ####################################################################################################

    @commands.command(name="getreport")
    async def leader_report(self,ctx,clan_abbreviation:str,season=None):
        """
        Generate various reports for leaders.

        Clan selection by abbreviation.
        """

        clan_from_abbreviation = await get_alliance_clan(ctx,clan_abbreviation)
        if not clan_from_abbreviation:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)

        try:
            c = await aClan.create(ctx,clan_from_abbreviation)
        except Exception as e:
            return await error_end_processing(ctx,
                preamble=f"Error encountered while geting clan {clan_abbreviation}.",
                err=e)

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
            #{
            #    'id': 'activity',
            #    'title': 'Member Activity *(season-applicable)*',
            #    'description': f"Donations, Loot, Clan Capital, War, Clan Games"
            #    },
            #{
            #    'id': 'clan',
            #    'title': 'Clan Performance Summary',
            #    'description': f"War Trends, Raid Trends"
            #    },
            {
                'emoji': '<:download:1040800550373044304>',
                'id': 'excel',
                'title': 'Download to Excel (.xlsx)',
                'description': 'Get an Excel file containing all Member, Clan War, and Raid Weekend data.'
                }
            ]

        select_embed = await clash_embed(ctx,
            message=f"Please select a report to generate for **{c.emoji} {c.name}**.")

        selected_report = await multiple_choice_select(
            ctx=ctx,
            sEmbed=select_embed,
            selection_list=menus_dict)

        if not selected_report:
            return

        wait_embed = await clash_embed(ctx,message=f"Please wait...")
        wembed = await ctx.send(embed=wait_embed)

        if selected_report['id'] == 'summary':
            o,e = await self.report_member_summary(ctx,c)

        if selected_report['id'] == 'allmembers':
            o,e = await self.report_all_members(ctx,c)

        if selected_report['id'] == 'missing':
            o,e = await self.report_missing_members(ctx,c)

        if selected_report['id'] == 'unrecognized':
            o,e = await self.report_unrecognized_members(ctx,c)

        if selected_report['id'] == 'activity':
            ##
            pass

        if selected_report['id'] == 'clan':
            ##
            pass

        if selected_report['id'] == 'excel':
            file,err_log = await self.report_to_excel(ctx,c)

            err_str = ""
            if len(err_log) > 0:
                for l in err_log:
                    err_str += f"{l['tag']}: {l['reason']}\n"
                if len(err_str) > 1024:
                    err_str = err_str[0:500]

            rept_embed = await clash_embed(ctx,
                title="Get Excel Report",
                message=f"Your report is available for download below."
                    + f"\n\n{err_str}",
                color='success')

            await wembed.delete()
            await ctx.send(embed=rept_embed)
            return await ctx.send(file=discord.File(file))
        
        await wembed.delete()

        if len(e)>0:
            err_str = ""
            for l in e:
                err_str += f"{l['tag']}: {l['reason']}\n"

            if len(err_str) > 1024:
                err_str = err_str[0:500]

            err_embed = await clash_embed(ctx,
                title="Errors Encountered.",
                message=err_str)

            o.append(err_embed)

        if len(o)>1:
            paginator = BotEmbedPaginator(ctx,o)
            await paginator.run()
        elif len(o)==1:
            await ctx.send(embed=o[0])


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
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for {m}.",
                    err=e)
            except Exception as e:
                p = None
                errD = {'tag':m,'reason':e}
                error_log.append(errD)
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
                d_user_display = "<<Unknown User>>"

            user_accounts = [a for a in members if a.discord_user==user]
            user_accounts = sorted(user_accounts, key=lambda b: (b.exp_level,b.town_hall.level),reverse=True)

            user_account_th = [str(a.town_hall.level) for a in user_accounts]

            output = {
                'User': f"{d_user_display}",
                '# Accs': f"{accounts}",
                'Townhalls': f"{','.join(user_account_th)}"
                }
            users_accounts_output.append(output)

        users_accounts_embed = await clash_embed(ctx,
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

        th_composition_embed = await clash_embed(ctx,
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

        account_strength_embed = await clash_embed(ctx,
            title=f"{clan.emoji} {clan.name} ({clan.tag})",
            message=f"**Clan Strength (Troops, Spells, Heroes)**"
                + f"\n\n{box(tabulate(account_strength_output,headers='keys',tablefmt='pretty'))}")
        output_embed.append(account_strength_embed)

        hero_strength_embed = await clash_embed(ctx,
            title=f"{clan.emoji} {clan.name} ({clan.tag})",
            message=f"**Clan Strength (Hero Breakdown)**"
                + f"\n\n{box(tabulate(hero_strength_output,headers='keys',tablefmt='pretty'))}")
        output_embed.append(hero_strength_embed)

        return output_embed, error_log


    async def report_all_members(self,ctx,clan):
        output_embed = []
        error_log = []
        
        member_tags = await get_alliance_members(ctx,clan)
        members = []

        for m in member_tags:
            try:
                p = await aPlayer.create(ctx,m)
            except TerminateProcessing as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for {m}.",
                    err=e)
            except Exception as e:
                p = None
                errD = {'tag':m,'reason':e}
                error_log.append(errD)
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

            members_embed = await clash_embed(ctx,
                title=f"{clan.emoji} {clan.name} ({clan.tag})",
                message=f"**All Members (Page {page} of {len(chunked_members)})**"
                    + f"\n\nTotal: {len(members)} members")

            for m in chunk:
                mem_count += 1
                title, text, summary = await resc.player_description(ctx,m)

                m_str = f"> {summary}"
                if m.discord_user or m.discord_link or m.clan.name != m.home_clan.name:
                    m_str += f"\n> "
                
                if m.discord_user:
                    m_str += f"<:Discord:1040423151760314448> <@{m.discord_user}>\u3000"
                elif m.discord_link:
                    m_str += f"<:Discord:1040423151760314448> <@{m.discord_link}\u3000"

                if m.clan.name != m.home_clan.name:
                    m_str += f"<:Clan:825654825509322752> {m.clan_description}"

                m_str += f"\n> [Open player in-game]({m.share_link})"

                members_embed.add_field(
                    name=f"{mem_count} {m.name} ({m.tag})",
                    value=m_str,
                    inline=False)

            output_embed.append(members_embed)
        return output_embed, error_log


    async def report_missing_members(self,ctx,clan):
        output_embed = []
        error_log = []
        
        member_tags = await get_alliance_members(ctx,clan)
        members = []

        for m in member_tags:
            try:
                p = await aPlayer.create(ctx,m)
            except TerminateProcessing as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for {m}.",
                    err=e)
            except Exception as e:
                p = None
                errD = {'tag':m,'reason':e}
                error_log.append(errD)
                continue
            members.append(p)

        members = sorted(members,key=lambda a:(a.town_hall.level,sum([h.level for h in a.heroes]),a.exp_level),reverse=True)

        members_not_in_clan = [m for m in members if m.clan.tag != m.home_clan.tag]

        chunked_not_in_clan = []
        for z in range(0, len(members_not_in_clan), 10):
            chunked_not_in_clan.append(members_not_in_clan[z:z+10])

        page = 0
        mem_count = 0
        for chunk in chunked_not_in_clan:
            page += 1
            members_not_in_clan_embed = await clash_embed(ctx,
                title=f"{clan.emoji} {clan.name} ({clan.tag})",
                message=f"**Members Not In Clan (Page {page} of {len(chunked_not_in_clan)})**"
                    + f"\n\nTotal: {len(members_not_in_clan)} members")

            for m in chunk:
                mem_count += 1
                title, text, summary = await resc.player_description(ctx,m)

                m_str = f"> {summary}"
                if m.discord_user or m.discord_link or m.clan.name != m.home_clan.name:
                    m_str += f"\n> "

                if m.discord_user:
                    m_str += f"<:Discord:1040423151760314448> <@{m.discord_user}>\u3000"
                elif m.discord_link:
                    m_str += f"<:Discord:1040423151760314448> <@{m.discord_link}\u3000"

                if m.clan.name != m.home_clan.name:
                    m_str += f"<:Clan:825654825509322752> {m.clan_description}"

                m_str += f"\n> [Open player in-game]({m.share_link})"
                
                members_not_in_clan_embed.add_field(
                    name=f"{mem_count} {m.name} ({m.tag})",
                    value=m_str,
                    inline=False)

            output_embed.append(members_not_in_clan_embed)

        return output_embed, error_log


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
            members_unrecognized_embed = await clash_embed(ctx,
                title=f"{clan.emoji} {clan.name} ({clan.tag})",
                message=f"**Unrecognized Accounts (Page {page} of {len(chunked_unrecognized)})**"
                    + f"\n\nTotal: {len(unrecognized_members)} members")

            for m in chunk:
                try:
                    m = await aPlayer.create(ctx,m.tag)
                    if not m.is_member:
                        await m.retrieve_data()
                except TerminateProcessing as e:
                    return await error_end_processing(ctx,
                        preamble=f"Error encountered while retrieving data for {m.tag}.",
                        err=e)
                except Exception as e:
                    p = None
                    errD = {'tag':m.tag,'reason':e}
                    error_log.append(errD)
                    continue

                title, text, summary = await resc.player_description(ctx,m)

                m_str = f"> {summary}"
                if m.discord_user or m.discord_link or m.clan.name != m.home_clan.name:
                    m_str += f"\n > "

                if m.discord_user:
                    m_str += f"<:Discord:1040423151760314448> <@{m.discord_user}>\u3000"
                elif m.discord_link:
                    m_str += f"<:Discord:1040423151760314448> <@{m.discord_link}\u3000"

                if m.clan.name != m.home_clan.name:
                    m_str += f"<:Clan:825654825509322752> {m.clan_description}"

                m_str += f"\n> [Open player in-game]({m.share_link})"

                members_unrecognized_embed.add_field(
                    name=f"{m.name} ({m.tag})",
                    value=m_str,
                    inline=False)

            output_embed.append(members_unrecognized_embed)

        return output_embed, error_log



    async def report_to_excel(self,ctx,clan):

        member_tags = await get_alliance_members(ctx,clan)
        members = []
        error_log = []

        for m in member_tags:
            try:
                p = await aPlayer.create(ctx,m)
            except TerminateProcessing as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for {m}.",
                    err=e)
            except Exception as e:
                p = None
                errD = {'tag':m,'reason':e}
                error_log.append(errD)
                continue
            members.append(p)

        members = sorted(members,key=lambda a:(a.town_hall.level,sum([h.level for h in a.heroes]),a.exp_level),reverse=True)

        dt = f"{datetime.fromtimestamp(time.time()).strftime('%m%d%Y%H%M%S')}"
        report_file = f"{ctx.bot.clash_report_path}/{ctx.author.display_name}_{clan.abbreviation}_{dt}.xlsx"

        rp_workbook = xlsxwriter.Workbook(report_file)
        bold = rp_workbook.add_format({'bold': True})

        mem_worksheet = rp_workbook.add_worksheet('Members')
        mem_headers = ['Tag',
            'Name',
            'Discord User',
            'Home Clan',
            'Rank',
            'Days in Home Clan',
            'Exp',
            'Townhall',
            'TH Weapon',
            'Current Clan',
            'Role in Clan',
            'League',
            'Trophies',
            'Barbarian King',
            'Archer Queen',
            'Grand Warden',
            'Royal Champion',
            'Hero Completion',
            'Troop Levels',
            'Troop Completion',
            'Spell Levels',
            'Spell Completion',
            'Attack Wins',
            'Defense Wins',
            'Donations Sent',
            'Donations Received',
            'Gold Looted',
            'Elixir Looted',
            'Dark Elixir Looted',
            'Clan Games Points',
            'Wars Participated',
            'Total Attacks',
            'Missed Attacks',
            'Triples',
            'Offense Stars',
            'Offense Destruction',
            'Defense Stars',
            'Defense Destruction',
            'Raids Participated',
            'Raid Attacks',
            'Capital Gold Looted',
            'Raid Medals Earned',
            'Capital Contribution']

        row = 0
        col = 0
        for h in mem_headers:
            mem_worksheet.write(row,col,h,bold)
            col += 1

        for m in members:
            col = 0
            row += 1

            m_data = []

            m_data.append(m.tag)
            m_data.append(m.name)

            try:
                m_user = ctx.bot.get_user(int(m.discord_user))
                m_user_display = m_user.display_name
            except:
                m_user_display = str(m.discord_user)
            m_data.append(m_user_display)

            m_data.append(m.home_clan.name)
            m_data.append(m.arix_rank)

            dd, hh, mm, ss = await convert_seconds_to_str(ctx,m.time_in_home_clan)
            m_data.append(dd)

            m_data.append(m.exp_level)
            m_data.append(m.town_hall.level)
            m_data.append(m.town_hall.weapon)

            m_data.append(f"{m.clan.name} ({m.clan.tag})")

            m_data.append(m.role)

            m_data.append(m.league.name)

            m_data.append(m.trophies)

            m_data.append(sum([h.level for h in m.heroes if h.name=='Barbarian King']))
            m_data.append(sum([h.level for h in m.heroes if h.name=='Archer Queen']))
            m_data.append(sum([h.level for h in m.heroes if h.name=='Grand Warden']))
            m_data.append(sum([h.level for h in m.heroes if h.name=='Royal Champion']))

            hero_completion = round((m.hero_strength/m.max_hero_strength)*100,1)
            m_data.append(hero_completion)

            troop_completion = round((m.troop_strength/m.max_troop_strength)*100,1)
            m_data.append(m.troop_strength)
            m_data.append(troop_completion)

            spell_completion = round((m.spell_strength/m.max_spell_strength)*100,1)
            m_data.append(m.spell_strength)
            m_data.append(spell_completion)

            m_data.append(m.attack_wins.season)
            m_data.append(m.defense_wins.season)

            m_data.append(m.donations_sent.season)
            m_data.append(m.donations_rcvd.season)

            m_data.append(m.loot_gold.season)
            m_data.append(m.loot_elixir.season)
            m_data.append(m.loot_darkelixir.season)

            m_data.append(m.clangames.season)

            m_data.append(m.war_stats.wars_participated)
            m_data.append(m.war_stats.total_attacks)
            m_data.append(m.war_stats.missed_attacks)

            m_data.append(m.war_stats.triples)
            m_data.append(m.war_stats.offense_stars)

            m_data.append(m.war_stats.offense_destruction)

            m_data.append(m.war_stats.defense_stars)
            m_data.append(m.war_stats.defense_destruction)

            m_data.append(m.raid_stats.raids_participated)

            m_data.append(m.raid_stats.raid_attacks)
            m_data.append(m.raid_stats.resources_looted)
            m_data.append(m.raid_stats.medals_earned)
            m_data.append(m.capitalcontribution.season)

            for d in m_data:
                mem_worksheet.write(row,col,d)
                col += 1

        war_worksheet = rp_workbook.add_worksheet('Clan Wars')
        war_headers = [
            'Clan',
            'Clan Tag',
            'Opponent',
            'Opponent Tag',
            'War Type',
            'Start Time',
            'End Time',
            'State',
            'Size',
            'Attacks per Member',
            'Result',
            'Clan Stars',
            'Clan Destruction',
            'Average Attack Duration',
            'Member Tag',
            'Member Name',
            'Member Townhall',
            'Member Map Position',
            'Attack Order',
            'Attack Defender',
            'Attack Stars',
            'Attack Destruction',
            'Attack Duration',
            'Defense Order',
            'Defense Attacker',
            'Defense Stars',
            'Defense Destruction',
            'Defense Duration',
            ]

        row = 0
        col = 0
        for h in war_headers:
            war_worksheet.write(row,col,h,bold)
            col += 1

        wid_sorted = sorted([wid for wid in list(clan.war_log.keys())],reverse=True)
        for wid in wid_sorted:
            war = clan.war_log[wid]
            for m in war.clan.members:
                for i in range(0,war.attacks_per_member):

                    mwar_data = []
                    mwar_data.append(war.clan.name)
                    mwar_data.append(war.clan.tag)
                    mwar_data.append(war.opponent.name)
                    mwar_data.append(war.opponent.tag)
                    mwar_data.append(war.type)
                    mwar_data.append(datetime.fromtimestamp(war.start_time).strftime('%b %d %Y %H:%M:%S'))
                    mwar_data.append(datetime.fromtimestamp(war.end_time).strftime('%b %d %Y %H:%M:%S'))
                    mwar_data.append(war.state)
                    mwar_data.append(war.size)
                    mwar_data.append(war.attacks_per_member)
                    mwar_data.append(war.result)

                    mwar_data.append(war.clan.stars)
                    mwar_data.append(war.clan.destruction)
                    mwar_data.append(war.clan.average_attack_duration)

                    mwar_data.append(m.tag)
                    mwar_data.append(m.name)
                    mwar_data.append(m.town_hall)
                    mwar_data.append(m.map_position)
                    try:
                        a = m.attacks[i]
                        mwar_data.append(a.order)
                        mwar_data.append(a.defender)
                        mwar_data.append(a.stars)
                        mwar_data.append(a.destruction)
                        mwar_data.append(a.duration)
                    except:
                        mwar_data.append(None)
                        mwar_data.append(None)
                        mwar_data.append(None)
                        mwar_data.append(None)
                        mwar_data.append(None)

                    if i == 0:
                        try:
                            mwar_data.append(m.best_opponent_attack.order)
                            mwar_data.append(m.best_opponent_attack.attacker)
                            mwar_data.append(m.best_opponent_attack.stars)
                            mwar_data.append(m.best_opponent_attack.destruction)
                            mwar_data.append(m.best_opponent_attack.duration)
                        except:
                            mwar_data.append(None)
                            mwar_data.append(None)
                            mwar_data.append(None)
                            mwar_data.append(None)
                            mwar_data.append(None)

                    col = 0
                    row += 1
                    for d in mwar_data:
                        war_worksheet.write(row,col,d)
                        col += 1

        raid_worksheet = rp_workbook.add_worksheet('Raid Weekends')
        raid_headers = [
            'Clan',
            'Clan Tag',
            'Start Date',
            'End Date',
            'State',
            'Total Loot Gained',
            'Offensive Raids Completed',
            'Defensive Raids Completed',
            'Raid Attack Count',
            'Districts Destroyed',
            'Offense Rewards',
            'Defense Rewards',
            'Participant Tag',
            'Participant Name',
            'Number of Attacks',
            'Capital Gold Looted',
            'Raid Medals'
            ]

        row = 0
        col = 0
        for h in raid_headers:
            raid_worksheet.write(row,col,h,bold)
            col += 1

        rid_sorted = sorted([rid for rid in list(clan.raid_log.keys())],reverse=True)
        for rid in rid_sorted:
            r = clan.raid_log[rid]
            for m in r.members:
                raid_data = []

                raid_data.append(r.clan.name)
                raid_data.append(r.clan.tag)
                raid_data.append(datetime.fromtimestamp(r.start_time).strftime('%b %d %Y'))
                raid_data.append(datetime.fromtimestamp(r.end_time).strftime('%b %d %Y'))
                raid_data.append(r.state)
                raid_data.append(r.total_loot)
                raid_data.append(r.offense_raids_completed)
                raid_data.append(r.defense_raids_completed)
                raid_data.append(r.raid_attack_count)
                raid_data.append(r.districts_destroyed)
                raid_data.append(r.offense_rewards)
                raid_data.append(r.defense_rewards)
                #m_data = raid_data
                raid_data.append(m.tag)
                raid_data.append(m.name)
                raid_data.append(m.attack_count)
                raid_data.append(m.resources_looted)
                raid_data.append(m.medals_earned)

                col = 0
                row += 1
                for d in raid_data:
                    raid_worksheet.write(row,col,d)
                    col += 1

        rp_workbook.close()

        return report_file, error_log
