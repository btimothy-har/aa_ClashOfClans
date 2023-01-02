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

from .leader_reports import report_member_summary, report_super_troops, report_war_status, report_all_members, report_missing_members, report_unrecognized_members, get_xp_report, report_to_excel

from aa_resourcecog.aa_resourcecog import AriXClashResources as resc
from aa_resourcecog.discordutils import convert_seconds_to_str, clash_embed, user_confirmation, multiple_choice_menu_generate_emoji, multiple_choice_menu_select, paginate_embed
from aa_resourcecog.constants import clanRanks, emotes_townhall, emotes_league, emotes_capitalhall
from aa_resourcecog.notes import aNote
from aa_resourcecog.alliance_functions import get_user_profile, get_alliance_clan, get_clan_members
from aa_resourcecog.player import aClashSeason, aPlayer, aClan, aMember
from aa_resourcecog.clan_war import aClanWar
from aa_resourcecog.raid_weekend import aRaidWeekend
from aa_resourcecog.errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing

class AriXLeaderCommands(commands.Cog):
    """AriX Clash of Clans Leaders' Module."""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=2170311125702803,force_registration=True)
        default_global = {}
        default_guild = {
            'silent_member_add': False
            }
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

    @commands.command(name="silentadd")
    @commands.is_owner()
    async def toggle_member_silent_add(self,ctx):

        current_setting = await self.config.guild(ctx.guild).silent_member_add()

        if current_setting:
            await self.config.guild(ctx.guild).silent_member_add.set(False)
        else:
            await self.config.guild(ctx.guild).silent_member_add.set(True)

        current_setting = await self.config.guild(ctx.guild).silent_member_add()

        await ctx.send(f"Silent Add Mode for this server has been set to {current_setting}.")


    @commands.command(name="recruitment",aliases=["recruiting"])
    async def recruitment_information(self,ctx):
        """
        The Recruiting Hub.

        Provides an overview of all Clan's Recruitment Statuses.
        This includes the number of registered members, the (suggested) townhall levels, and the last 5 Leader's notes on file.
        """

        clans = await get_alliance_clan(ctx)
        output_embed = []

        for c in clans:
            th_str = ""
            for th in c.recruitment_level:
                th_str += f"{emotes_townhall[th]} "

            clanEmbed = await clash_embed(ctx=ctx,
                title=f"Clan Recruitment",
                message=f"**{c.emoji} {c.name} ({c.tag})**"
                    + f"\nMembers: {c.arix_member_count} / 50\nRecruiting: {th_str}\n\u200b",
                thumbnail="https://i.imgur.com/TZF5r54.png")

            for note in c.notes[:9]:
                dt = f"{datetime.fromtimestamp(note.timestamp).strftime('%d %b %Y')}"

                clanEmbed.add_field(
                    name=f"__{note.author.name} @ {dt}__",
                    value=f">>> {note.content}",
                    inline=False)

            output_embed.append(clanEmbed)

        await paginate_embed(ctx,output_embed)


    @commands.group(name="clan")
    async def clan_manage(self,ctx):
        """
        Manage Alliance clans.

        All sub-commands in this group have required inputs when running them.
        To view additional information about the commands, run them without the parameters.

        Example: to get information about `clan settings`, simply run `$clan settings`.

        **This is a command group. To use the sub-commands below, follow the syntax: `$clan [sub-command]`.**

        """
            
        if not ctx.invoked_subcommand:
            pass


    @clan_manage.command(name="add")
    @commands.is_owner()
    async def clan_manage_add(self, ctx, tag:str, force=False):
        """
        [Owner-only] Add a Clan to the Alliance.

        To successfully add a clan, you will need:
        > - A Clan Leader (by Discord User)
        > - A Clan Abbreviation
        > - A Clan Emoji
        > - Co-Leader Role
        > - Elder Role
        > - Member Role
        """

        def response_check(m):
            if m.author.id == ctx.author.id:
                if m.channel.id == ctx.channel.id:
                    return True
                elif m.channel.type == ctx.channel.type == discord.ChannelType.private:
                    return True
                else:
                    return False

        if ctx.author.id not in ctx.bot.owner_ids:
            embed = await clash_embed(ctx,message="To use this command please contact <@644530507505336330>.")
            return await ctx.send(embed=embed)

        try:
            c = await aClan.create(ctx,tag=tag)
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
                    thumbnail=c.badge.url)
                return await ctx.send(embed=embed)

        info_embed = await clash_embed(ctx=ctx,
            title=f"**You are adding: {c.desc_title}**",
            message=f"{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.badge.url)
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
            thumbnail=c.badge.url)

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
            thumbnail=c.badge.url,
            color='success')

        await add_msg.delete()
        return await ctx.send(embed=final_embed)


    @clan_manage.command(name="remove")
    @commands.is_owner()
    async def clan_manage_remove(self, ctx, clan_abbreviation):
        """
        [Owner-only] Remove a Clan from the Alliance.

        This removes a Clan from the Alliance. The Clan and it's associated data will be permanently deleted.

        **Unlike removing members, this deletes the record of the Clan. This action is irreversible.**
        """

        if ctx.author.id not in ctx.bot.owner_ids:
            embed = await clash_embed(ctx,message="To use this command please contact <@644530507505336330>.")
            return await ctx.send(embed=embed)

        c = await get_alliance_clan(ctx,clan_abbreviation)
        if not c:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)
        c = c[0]

        confirm_embed = await clash_embed(ctx=ctx,
            title=f"Remove Clan: **{c.emoji} {c.desc_title}**",
            message=f"Leader: <@{c.leader}>\u3000Abbreviation: `{c.abbreviation}`"
                + f"\n\n{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.badge.url,
            url=c.share_link)

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
            thumbnail=c.badge.url,
            url=c.share_link,
            color='success')
    
        await confirm_remove.delete()
        await ctx.send(embed=final_embed)


    @clan_manage.command(name="setleader")
    @commands.is_owner()
    async def clan_manage_setleader(self, ctx, clan_abbreviation, new_leader:discord.User):
        """
        [Owner-only] Overrides the Leader of a Clan.

        This is a very powerful command and confers Leader permissions to the specified user.

        **This should only be used in cases of emergencies.**

        """

        new_id = new_leader.id

        if ctx.author.id not in ctx.bot.owner_ids:
            embed = await clash_embed(ctx,message="To use this command please contact <@644530507505336330>.")
            return await ctx.send(embed=embed)

        c = await get_alliance_clan(ctx,clan_abbreviation)
        if not c:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)
        c = c[0]

        confirm_embed = await clash_embed(ctx=ctx,
            title=f"Leader Override: **{c.emoji} {c.desc_title}**",
            message=f"**New Leader: {new_leader.mention}**"
                + f"\n\n{c.desc_full_text}"
                + f"\n\n>>> {c.description}",
            thumbnail=c.badge.url)

        confirm_remove = await ctx.send(
            content=f"{ctx.author.mention}, please confirm you would like to assign {new_leader.mention} as the Leader of the above clan.",
            embed=confirm_embed)
        if not await user_confirmation(ctx,confirm_remove):
            return

        try:
            await c.update_member_rank(ctx,new_id,"Leader")
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
            thumbnail=c.badge.url,
            url=c.share_link,
            color='success')
    
        await confirm_remove.delete()
        await ctx.send(embed=final_embed)


    @clan_manage.command(name="settings")
    async def clan_manage_settings(self,ctx,clan_abbreviation):
        """
        Change Clan Settings.

        **Usable only by Co-Leaders and Leaders.**

        The following settings can be adjusted from this command:

        > - Clan Emoji
        > - Recruiting Townhalls
        > - Turn War Reminders On/Off
        > - Turn Raid Reminders On/Off
        > - War Reminder Interval
        > - Raid Reminder Interval

        **Note on War/Raid Reminders: Any changes to the Reminder Intervals will only take effect from the next war/raid weekend.**
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
            'description': 'War reminders are by default sent at the 12 hour, 4 hour, and 1 hour (remaining time) mark of a War.'
            }

        raid_reminder_toggle = {
            'id': 'raid_reminder',
            'title': 'Toggle Raid Reminders.',
            'description': 'Raid reminders are by default sent at the 36 hour, 24 hour, 12 hour, and 4 hour (remaining time) mark of the Raid Weekend.'
            }

        war_reminder_interval = {
            'id': 'war_reminder_interval',
            'title': 'Set the War Reminder Interval.',
            'description': 'Change the time when War Reminders are sent. There will always be one reminder sent at 1 hour left.'
            }

        raid_reminder_interval = {
            'id': 'raid_reminder_interval',
            'title': 'Set the Raid Reminder Interval.',
            'description': 'Change the time when Raid Reminders are sent.'
            }

        if (ctx.author.id == c.leader or ctx.author.id in c.co_leaders) or ctx.author.id in ctx.bot.owner_ids:
            menu_dict.append(recruit_option)
            menu_dict.append(description_option)
            menu_dict.append(war_reminder_toggle)
            menu_dict.append(war_reminder_interval)
            menu_dict.append(raid_reminder_toggle)
            menu_dict.append(raid_reminder_interval)

        if ctx.author.id in ctx.bot.owner_ids:
            menu_dict.append(emoji_option)
            menu_dict.append(announcement_option)
            menu_dict.append(reminder_ch_option)

        if len(menu_dict) == 0:
            no_permission_embed = await clash_embed(ctx,
                message=f"You don't have the necessary permissions to make changes to {c.emoji} **{c.name}**.\n\nYou need to be a Co-Leader or Leader to change a Clan's settings.",
                color='fail')

            return await ctx.send(content=ctx.author.mention,embed=no_permission_embed)

        menu_dict = await multiple_choice_menu_generate_emoji(ctx,menu_dict)

        select_str = ""
        admin_str = ""
        for i in menu_dict:
            if i['id'] in ['emoji','announcement_channel','reminder_channel']:
                admin_str += f"{i['emoji']} **{i['title']}**\n\n"
            else:
                select_str += f"{i['emoji']} **{i['title']}**"
                select_str += f"\n{i['description']}"
                if menu_dict.index(i) < (len(menu_dict)-1):
                    select_str += f"\n\n"

        message = None
        response = 'start'
        task_state = True
        state_text = ""

        while task_state:
            try:
                if response in ['start','menu']:

                    state_text_fmt = ""
                    if state_text != "":
                        state_text_fmt = f"**{state_text}**"

                    th_str = ''
                    for th in c.recruitment_level:
                        th_str += emotes_townhall[th]

                    announcement_embed = await clash_embed(ctx,
                        title=f"Clan Settings: {c.emoji} {c.desc_title}",
                        message=f"\n{state_text_fmt}"
                            + f"\n\nEmoji: {c.emoji}"
                            + f"\nRecruiting: {th_str}"
                            + f"\n\nAnnouncement Channel: <#{c.announcement_channel}>"
                            + f"\nReminder Channel: <#{c.reminder_channel}>"
                            + f"\n\nWar Reminders: ` {toggle_state[c.send_war_reminder]} `"
                            + f"\nReminder Interval: ` {humanize_list(c.war_reminder_intervals)} `"
                            + f"\n\nRaid Reminders: ` {toggle_state[c.send_raid_reminder]} `"
                            + f"\nReminder Interval: ` {humanize_list(c.raid_reminder_intervals)} `"
                            + f"\n\u200b")

                    announcement_embed.add_field(
                        name="```**What would you like to do today?**```",
                        value=f"\u200b\n{select_str}*Exit this Menu at any time by clicking on <:red_cross:838461484312428575>.*\n\u200b",
                        inline=False
                        )

                    if admin_str:
                        announcement_embed.add_field(
                            name="```**Admin Options**```",
                            value=f"\u200b\n{admin_str}\u200b",
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


                if response in ['description']:
                    await message.clear_reactions()
                    desc_embed = await clash_embed(ctx,message=f"Please enter the new Description for **{c.name}**.\n\n**Note: When using emojis, please note that only emojis found in this server are usable.**")
                    await message.edit(content=ctx.author.mention,embed=desc_embed)

                    try:
                        response_msg = await ctx.bot.wait_for("message",timeout=180,check=response_check)
                    except asyncio.TimeoutError:
                        end_embed = await clash_embed(ctx,message=f"Operation timed out.")
                        await message.edit(embed=end_embed)
                        return

                    await c.set_description(ctx,response_msg.content)
                    await response_msg.delete()
                    state_text = f"**The description for {c.name} is now set as follows:**\n\n`\u200b`{c.description}`\u200b`"
                    response = 'menu'


                if response in ['recruit']:
                    await message.clear_reactions()
                    rectownhall_embed = await clash_embed(ctx,
                        message=f"Please provide the Townhall Levels (using numbers) that {c.emoji} **{c.name}** will be recruiting for."
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


                if response in ['war_reminder_interval']:
                    await message.clear_reactions()
                    war_interval_embed = await clash_embed(ctx,
                        message=f"Please provide the intervals for War Reminders, in **hours**. Separate intervals with a space."
                            + f"\n\nExample: To send a reminder at the 1 hour, 3 hour, and 15 hour mark, reply with `1 3 15`."
                            + f"\n\n> - There will always be a reminder sent at 1 hour."
                            + f"\n> - Any intervals above 24 hours will be ignored."
                            + f"\n\n**Changes will take effect in the next war.**"
                            + f"\n\n`Enter any non-numeric digit to return to the menu.`")
                    await message.edit(content=ctx.author.mention,embed=war_interval_embed)

                    try:
                        response_msg = await ctx.bot.wait_for("message",timeout=60,check=response_check)
                    except asyncio.TimeoutError:
                        end_embed = await clash_embed(ctx,message=f"Operation timed out.")
                        await message.edit(embed=end_embed)
                        return
                    else:
                        try:
                            new_interval = response_msg.content.split()
                            new_interval_list = []
                            [new_interval_list.append(int(i)) for i in new_interval if int(i) not in new_interval_list]
                            await response_msg.delete()

                            if len(new_interval_list) == 0:
                                raise Exception
                            await c.set_war_reminder_interval(ctx,new_interval_list)
                            state_text = f"War Reminder Intervals for {c.emoji} {c.name} have been set to {humanize_list(c.war_reminder_intervals)} hours."
                            response = 'menu'
                        except:
                            await response_msg.delete()
                            state_text = f"I didn't know what you were trying to do. I've brought you back to the main menu."
                            response = 'menu'


                if response in ['raid_reminder_interval']:
                    await message.clear_reactions()
                    war_interval_embed = await clash_embed(ctx,
                        message=f"Please provide the intervals for Raid Reminders, in **hours**. Separate intervals with a space."
                            + f"\n\nExample: To send a reminder at the 12 hour, 1 day, and 2 day mark, reply with `12 24 48`."
                            + f"\n\n> - There will always be a reminder sent at 24 hours."
                            + f"\n> - Any intervals above 48 hours will be ignored."
                            + f"\n\n**Changes will take effect in the next raid weekend.**"
                            + f"\n\n`Enter any non-numeric digit to return to the menu.`")
                    await message.edit(content=ctx.author.mention,embed=war_interval_embed)

                    try:
                        response_msg = await ctx.bot.wait_for("message",timeout=60,check=response_check)
                    except asyncio.TimeoutError:
                        end_embed = await clash_embed(ctx,message=f"Operation timed out.")
                        await message.edit(embed=end_embed)
                        return
                    else:
                        try:
                            new_interval = response_msg.content.split()
                            new_interval_list = []
                            [new_interval_list.append(int(i)) for i in new_interval if int(i) not in new_interval_list]
                            await response_msg.delete()

                            if len(new_interval_list) == 0:
                                raise Exception

                            await c.set_raid_reminder_interval(ctx,new_interval_list)
                            state_text = f"Raid Reminder Intervals for {c.emoji} {c.name} have been set to {humanize_list(c.raid_reminder_intervals)} hours."
                            response = 'menu'
                        except:
                            await response_msg.delete()
                            state_text = f"I didn't know what you were trying to do. I've brought you back to the main menu."
                            response = 'menu'

                if response in ['raid_reminder']:
                    await message.clear_reactions()
                    await c.toggle_raid_reminders(ctx)
                    state_text = f"**Raid Reminders for {c.emoji} {c.name} is now {toggle_state[c.send_war_reminder]}.**"
                    response = 'menu'

            except Exception as e:
                err_embed = await clash_embed(ctx,
                    message=f"Error encountered while changing settings: {e}.",
                    color="fail")
                if message:
                    await message.edit(embed=err_embed)
                else:
                    await ctx.send(embed=err_embed)
                response = None

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

        Notes appear in the Recruiting Hub (`$recruitment`), and can be used to share information between Leaders.
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
    ### - transfer

    ####################################################################################################

    @commands.group(name="member")
    async def member_manage(self,ctx):
        """
        Manage Alliance Members.

        All sub-commands in this group have required inputs when running them.
        To view additional information about the commands, run them without the parameters.

        Example: to get information about `member add`, simply run `$member add`.

        **This is a command group. To use the sub-commands below, follow the syntax: `$member [sub-command]`.**
        """
        
        if not ctx.invoked_subcommand:
            pass

    @member_manage.command(name="add")
    async def member_manage_add(self,ctx,Discord_User:discord.User, Toggle_Silent_Mode=None):
        """
        Add a Member to the Alliance.

        A Member is permanently assigned to a Home Clan in the Alliance. Until removed, they will be treated as a Member, regardless of their in-game status.

        Once added, the Welcome DM will be sent to the tagged user by NEBULA.

        **Toggle Silent Mode**: To add silently and not send the welcome message, include an "S" after mentioning the Discord user. (e.g. `$member add @user S`).
        """

        user = Discord_User

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

        report_str = ""
        cleanup_msgs = []
        silent_mode = False
        sent_welcome = False
        error_log = []
        added_count = 0

        if Toggle_Silent_Mode:
            if Toggle_Silent_Mode.lower() == "s":
                silent_mode = True

        if not silent_mode:
            silent_mode = await self.config.guild(ctx.guild).silent_member_add()

        alliance_clans = await get_alliance_clan(ctx)

        if not len(alliance_clans) >= 1:
            return await no_clans_registered(ctx)

        ask_player_tags = await clash_embed(ctx,
            message=f"**Please send the Clash Player Tags for {user.mention}.**"
                + f"\n\nSeparate multiple tags with a space in between."
                + f"\n\nSilent mode: {silent_mode}"
                + f"\nTo cancel, send `cancel`.")

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
                p = await aPlayer.create(ctx,tag=tag,refresh=True)
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
            if p.discord_user and p.discord_user.user_id != user.id:
                player_notes += f"\n- This account has been previously linked to <@{p.discord_user.user_id}>."
            
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

            await homeclan_msg.delete()

            if not selected_clan:
                not_added_embed = await clash_embed(ctx,message=f"{p.desc_title} was not added to AriX. Skipping...")
                await ctx.send(embed=not_added_embed,delete_after=20)

                report_str += f"<a:animated_Cross:1050931677033140294> **{p.tag} {p.name}** not added to AriX.\n"
                continue

            added_count += 1
            target_clan = [c for c in alliance_clans if c.tag == selected_clan['id']][0]

            previous_home_clan = p.home_clan
            try:
                await p.new_member(ctx,user,target_clan)
            except Exception as e:
                err_dict = {'tag':p.tag,'reason':f"Error while adding: {e}"}
                error_log.append(err_dict)

            c_embed = await clash_embed(ctx,
                message=f"**{p.tag} {p.name}** added as **{p.arix_rank}** to **{p.home_clan.emoji} {p.home_clan.name}**.",
                color='success')
            await ctx.send(embed=c_embed,delete_after=20)

            report_str += f"<a:check_black:1050969577556811876> **{p.tag} {p.name}** added as **{p.arix_rank}** to **{p.home_clan.emoji} {p.home_clan.name}**.\n"

        new_nickname = await resc.user_nickname_handler(ctx,user,selection=False)
        ex_member_role = ctx.bot.alliance_server.get_role(870193115703697448)
        visitor_role = ctx.bot.alliance_server.get_role(733362618647183531)
        new_applicant_role = ctx.bot.alliance_server.get_role(811204363263410187)

        if added_count > 0:
            member = await aMember.create(user.id)

            if member.discord_member:
                await member.sync_roles(ctx)

                try:
                    new_nickname = await member.set_nickname(ctx)
                    report_str += f"<a:check_black:1050969577556811876> Nickname set to {new_nickname}.\n"
                except Exception as e:
                    report_str += f"<a:aa_warning:1050970131863453746> Error while changing nickname: {e}\n"

                if ex_member_role in member.discord_member.roles:
                    try:
                        await discord_member.remove_roles(ex_member_role)
                        report_str += f"<a:check_black:1050969577556811876> Removed {ex_member_role.mention}.\n"
                    except Exception as e:
                        report_str += f"<a:aa_warning:1050970131863453746> Could not remove {ex_member_role.mention}: {e}\n"

                if new_applicant_role in member.discord_member.roles:
                    try:
                        await discord_member.remove_roles(new_applicant_role)
                        report_str += f"<a:check_black:1050969577556811876> Removed {new_applicant_role.mention}.\n"
                    except Exception as e:
                        report_str += f"<a:aa_warning:1050970131863453746> Could not remove {new_applicant_role.mention}: {e}\n"

                if visitor_role in member.discord_member.roles:
                    try:
                        await discord_member.remove_roles(visitor_role)
                        report_str += f"<a:check_black:1050969577556811876> Removed {visitor_role.mention}.\n"
                    except Exception as e:
                        report_str += f"<a:aa_warning:1050970131863453746> Could not remove {visitor_role.mention}: {e}\n"

            if not silent_mode:
                intro_embed = await resc.get_welcome_embed(ctx,user)

                try:
                    await user.send(embed=intro_embed)
                    await user.send(content="https://discord.gg/tYBh3Gk")
                except:
                    await ctx.send(content=f"{user.mention}",embed=intro_embed)
                    await ctx.send(content="https://discord.gg/tYBh3Gk")

                else:
                    sent_welcome = True
                    welcome_embed = await clash_embed(ctx,
                        message=f"**Welcome to AriX, {user.mention}**!\n\nI've sent you some information and instructions in your DMs. Please review them ASAP.",
                        show_author=False)

                    report_str += f"<a:check_black:1050969577556811876> Welcome DM sent.\n"

        result_embed = await clash_embed(ctx,
            title=f"Member Add: {user.name}#{user.discriminator}",
            message=f"{report_str}\u200b",
            thumbnail=user.avatar_url)

        if len(error_log) > 0:
            error_str = "\u200b"
            for error in error_log:
                error_str += f"{error['tag']}: {error['reason']}\n"

            result_embed.add_field(
                name="__**Errors Encountered**__",
                value=error_str)

        await ctx.send(embed=result_embed)

        if sent_welcome:
            await ctx.send(content=f"**Welcome to AriX, {user.mention}!**\n\nTo get you set up, I've sent you some information and instructions in your DMs. Please do review them ASAP!")


    @member_manage.command(name="remove")
    async def member_manage_remove(self,ctx,*tags_or_user_mention):
        """
        Remove Members from the Alliance.

        This removes the Member Status from the provided player tag(s), and removes them from the originally assigned Home Clan.

        You can provide multiple player tags, separated by a space in between.
        """

        user = None
        report_str = ""
        player_tags = []
        discord_users = []
        accounts = []
        error_log = []

        def response_check(m):
            if m.author.id == ctx.author.id and m.channel.type == discord.ChannelType.private:
                return True
            else:
                return False

        if len(tags_or_user_mention) == 0:
            embed = await clash_embed(ctx,
                message="Provide either 1 Discord User (through mention) or 1 or more Clash Tags, separated by spaces.")
            return await ctx.send(embed=embed)

        else:
            try:
                check_for_discord_mention = int(re.search('@(.*)>',tags_or_user_mention[0]).group(1))
                user = ctx.bot.alliance_server.get_member(check_for_discord_mention)
            except:
                for t in tags_or_user_mention:
                    t = coc.utils.correct_tag(t)
                    if not coc.utils.is_valid_tag(t):
                        continue
                    player_tags.append(t)

        if user:
            home_clans, user_accounts = await get_user_profile(ctx,user.id)

            accounts = [a for a in user_accounts if a.is_member]
            accounts = sorted(accounts,key=lambda x:(x.exp_level, x.town_hall.level),reverse=True)

        else:
            for tag in player_tags:
                try:
                    p = await aPlayer.create(ctx,tag=tag)
                except Exception as e:
                    eEmbed = await clash_embed(ctx,message=e,color='fail')
                    return await ctx.send(embed=eEmbed)
                if p.is_member:
                    accounts.append(p)

        if len(accounts) == 0:
            embed = await clash_embed(ctx,
                message=f"I couldn't find any accounts to remove. The user/account(s) you provided may not be active AriX Members.")
            return await ctx.send(embed=embed)

        if user:
            account_selection = []
            s_dict = {
                'id': 'all_accounts',
                'title': 'Remove all Accounts',
                'description': f"This will remove the Member from all AriX clans."
                }
            account_selection.append(s_dict)

            if len(home_clans) > 1:
                for clan in home_clans:
                    s_dict = {
                        'id': clan.tag,
                        'title': f'Only {clan.emoji} {clan.name}',
                        'description': f"Remove only accounts in {clan.name}."
                        }
                    account_selection.append(s_dict)

            for p in accounts:
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
                title=f"Remove Member: {user.name}#{user.discriminator}",
                message=f"**Select account(s) to remove.**"
                    + f"\n\n{selection_str}")

            select_msg = await ctx.send(content=ctx.author.mention,embed=select_embed)

            selected_account = await multiple_choice_menu_select(ctx,select_msg,account_selection)
            if not selected_account:
                cancel_embed = await clash_embed(ctx,
                    message="Operation cancelled.",
                    color="fail")
                await select_msg.edit(embed=cancel_embed)
                await select_msg.clear_reactions()
                return

            await select_msg.delete()

            if selected_account['id'] == 'all_accounts':
                remove_accounts = accounts
            elif selected_account['id'] in [c.tag for c in home_clans]:
                remove_accounts = [a for a in accounts if a.home_clan.tag == selected_account['id']]
            else:
                remove_accounts = [a for a in accounts if a.tag == selected_account['id']]

        else:
            confirm_remove = await clash_embed(ctx,
                title="I found the below accounts to be removed. Please confirm.")

            for p in accounts:
                confirm_remove.add_field(
                    name=f"{p.desc_title}",
                    value=f"> <:Discord:1040423151760314448> <@{p.discord_user}>"
                        + f"\n> {p.desc_summary_text}",
                    inline=False)

            confirm_remove_msg = await ctx.send(embed=confirm_remove)
            if not await user_confirmation(ctx,confirm_remove_msg):
                return
            await confirm_remove_msg.delete()

            remove_accounts = accounts

        if len(remove_accounts) == 0:
            cEmbed = await clash_embed(ctx,
                message="I didn't find any accounts to be removed. Please try again.")
            return await ctx.send(embed=cEmbed)

        if len(remove_accounts) > 0:
            for p in remove_accounts:
                home_clan = p.home_clan
                try:
                    await p.remove_member(ctx)
                except Exception as e:
                    err_dict = {'tag':p.tag,'reason':f"Error while removing: {e}"}
                    error_log.append(err_dict)
                    remove_accounts.remove(p)

                report_str += f"<a:check_black:1050969577556811876> **{p.tag} {p.name}** removed from {home_clan.emoji} {home_clan.name}.\n"

                if p.discord_user and p.discord_user not in discord_users:
                    discord_users.append(p.discord_user)

        for u in discord_users:

            member = await aMember.create(ctx,user_id=u.user_id)

            if member.discord_member:
                try:
                    new_nickname = await member.set_nickname(ctx)
                    report_str += f"<a:check_black:1050969577556811876> Changed nickname for {member.discord_member.name}#{member.discord_member.discriminator} to {new_nickname}.\n"
                except Exception as e:
                    report_str += f"<a:aa_warning:1050970131863453746> Could not change nickname for {member.discord_member.name}#{member.discord_member.discriminator}: {e}\n"

                await member.sync_roles(ctx)

                if len(member.home_clans) == 0:
                    ex_member_role = ctx.bot.alliance_server.get_role(870193115703697448)
                    try:
                        await member.discord_member.add_roles(ex_member_role)
                        report_str += f"<a:check_black:1050969577556811876> {ex_member_role.mention} assigned to {member.discord_member.mention}.\n"
                    except Exception as e:
                        report_str += f"<a:aa_warning:1050970131863453746> Could not add Ex-Member Role to {member.discord_member.name}#{member.discord_member.discriminator}: {e}\n"

        result_embed = await clash_embed(ctx,
            title="**Remove Members**",
            message=f"{report_str}\u200b")

        if len(error_log) > 0:
            error_str = "\u200b"
            for error in error_log:
                error_str += f"{error['tag']}: {error['reason']}\n"

            result_embed.add_field(
                name="__**Errors Encountered**__",
                value=error_str)

        await ctx.send(embed=result_embed)

    @member_manage.command(name="addnote")
    async def member_manage_addnote(self,ctx,Discord_User:discord.User):
        """
        Add a Leader's note to a Member.

        As members are identified by Discord User, tagging a user will let you add the note to:

        > 1) All of the User's Linked Accounts; or
        > 2) All of the User's Accounts in a Clan; or
        > 3) A specific account

        Notes are viewable when using the `$player` command, when run as a Leader/Co-Leader.
        """

        user = Discord_User

        def response_check(m):
            if m.author.id == ctx.author.id and m.channel.type == discord.ChannelType.private:
                return True
            else:
                return False

        home_clans, user_accounts = await get_user_profile(ctx,user.id)

        user_accounts = [a for a in user_accounts if a.is_member]
        user_accounts = sorted(user_accounts,key=lambda x:(x.exp_level, x.town_hall.level),reverse=True)

        if len(user_accounts) == 0:
            embed = await clash_embed(ctx,
                message=f"{user.mention} is currently not on AriX Member.")
            return await ctx.send(embed=embed)

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


    @member_manage.command(name="setname")
    async def member_manage_setreadablename(self,ctx,player_tag,name):

        try:
            p = await aPlayer.create(ctx,player_tag)
        except Exception as e:
            await error_end_processing(ctx,
                preamble=f"Error encountered while retrieving data for Player Tag {tag}.",
                err=e)
            return

        if not p.is_member:
            cembed = await clash_embed(ctx,
                message=f"{p.tag} {p.name} is not an AriX Member.")
            return await ctx.send(embed=cembed)

        try:
            await p.set_readable_name(ctx,name)
        except Exception as e:
            await error_end_processing(ctx,
                preamble=f"Error encountered while setting name {tag}.",
                err=e)
            return

        cembed = await clash_embed(ctx,
            message=f"The name for {p.tag} {p.name} has been overridden to `{p.readable_name}`.")
        return await ctx.send(embed=cembed)


    @member_manage.command(name="setnick")
    async def member_manage_setnickname(self,ctx,Discord_User:discord.User):
        """
        Change a Member's Discord Nickname.

        Nicknames follow the format of: `In-Game Name | Clan Membership`.

        This command will let you pick an active member account to set the member's nickname to. Clan Membership is automatically populated.

        If the provided user only has 1 active account, that account becomes the default nickname.
        """

        user = Discord_User

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

        user_id = user.id

        member = await aMember.create(ctx,user_id=user_id)

        if len(member.home_clans) == 0:
            not_member_embed = await clash_embed(ctx,
                message=f"{user.mention} was not good enough to be an AriX Member and doesn't deserve your attention.",
                color='fail')
            return await ctx.send(content=ctx.author.mention,embed=not_member_embed)

        for c in member.home_clans:
            #do nothing to Leaders
            if member.user_id == c.leader:
                leader_ct += 1
                pass

            #Only Leaders can promote/demote Co-Leaders
            elif member.user_id in c.co_leaders and ctx.author.id == c.leader:
                eligible_ranks.append(c)

            #Leaders or Co-Leaders can promote/demote Members/Elders
            elif ctx.author.id == c.leader or ctx.author.id in c.co_leaders:
                if action == 'demote' and member.user_id not in (c.co_leaders + c.elders):
                    member_ct += 1
                    pass
                else:
                    eligible_ranks.append(c)

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
            rank_clan = eligible_ranks[0]

            if member.user_id in rank_clan.co_leaders:
                current_rank = 'Co-Leader'
            elif member.user_id in rank_clan.elders:
                current_rank = 'Elder'
            else:
                current_rank = 'Member'

            if action == 'demote':
                new_rank = clanRanks[clanRanks.index(current_rank)-1]
            if action == 'promote':
                new_rank = clanRanks[clanRanks.index(current_rank)+1]

            confirm_embed = await clash_embed(ctx,
                title=f"{action.capitalize()} {user.name}#{user.discriminator}",
                message=f"**Please confirm this action.**"
                    + f"\n\n**{rank_clan.emoji} {rank_clan.name}**"
                    + f"\nCurrent Rank: {current_rank}"
                    + f"\nNew Rank: *{new_rank}*"
                    + f"\nAccounts: {len([a for a in member.accounts if a.is_member and a.home_clan.tag == rank_clan.tag])}")

            confirm = await ctx.send(content=ctx.author.mention,embed=confirm_embed)
            if not await user_confirmation(ctx,confirm):
                await confirm.delete()
                return
            await confirm.delete()

        if len(eligible_ranks) > 1:
            selection_list = ""
            selection_str = ""
            for i in eligible_ranks:
                if member.user_id in i.co_leaders:
                    current_rank = 'Co-Leader'
                elif member.user_id in i.elders:
                    current_rank = 'Elder'
                else:
                    current_rank = 'Member'

                if action == 'demote':
                    new_rank = clanRanks[clanRanks.index(current_rank)-1]
                if action == 'promote':
                    new_rank = clanRanks[clanRanks.index(current_rank)+1]

                d = {
                    'id': i.tag,
                    'title': i.desc_title,
                    'emoji': i.emoji,
                    'description': f"Current Rank: {current_rank}\u3000New Rank: {new_rank}\nAccounts: {len([a for a in member.accounts if a.is_member and a.home_clan.tag == i.tag])}"
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
                end_embed = await clash_embed(ctx,
                    message="Task cancelled.",color='fail')
                await select.edit(embed=end_embed)
                return None

            rank_clan = [i for i in eligible_ranks if i.tag == selected_clan['id']][0]

            await select.delete()

        if member.user_id in rank_clan.co_leaders:
            current_rank = 'Co-Leader'
        elif member.user_id in rank_clan.elders:
            current_rank = 'Elder'
        else:
            current_rank = 'Member'

        if action == 'demote':
            new_rank = clanRanks[clanRanks.index(current_rank)-1]
        if action == 'promote':
            new_rank = clanRanks[clanRanks.index(current_rank)+1]

        try:
            await rank_clan.update_member_rank(ctx,user_id,new_rank)

            for a in [a for a in member.accounts if a.is_member and a.home_clan.tag == rank_clan.tag]:
                await aPlayer.create(ctx,a.tag,fetch=True)

            member = await aMember.create(ctx,user_id=user_id)
            await member.sync_roles(ctx)
        except:
            err_embed = await clash_embed(ctx,
                message=f"I ran into an error while updating Ranks: {rank_clan.tag} {e}.",
                color='fail')
            return await ctx.send(embed=err_embed)

        result_embed = await clash_embed(ctx,
            message=f"{user.mention} is now a **{new_rank}** in {rank_clan.emoji} **{rank_clan.desc_title}**.",
            color='success')

        return await ctx.send(embed=result_embed)


    @commands.command(name="promote")
    async def member_promote(self,ctx,Discord_User:discord.User):
        """
        Promote a Member.

        Members are ranked based on Discord User and Clan. When promoting a Discord User, all their accounts registered in the provided Clan are promoted/demoted as a group.

        **Clan Permissions Apply**
        > - Only Clan Leaders can promote/demote Co-Leaders.
        > - Clan Leaders and Co-Leaders can promote/demote Elders and Members.
        > - You can only promote/demote for Clans that you are a Leader/Co-Leader in.
        > - A User must be a Member in that Clan to be eligible for promotion/demotion.

        **To change a Clan Leader, promote a Co-Leader. A Clan Leader cannot be promoted or demoted.**

        """

        user = Discord_User

        if ctx.author.id == user.id:
            eEmbed = await clash_embed(ctx,message=f"Self-glorification is not allowed. Go grovel and beg for mercy.",color='fail')
            return await ctx.send(embed=eEmbed)

        await self.rank_handler(
            ctx=ctx,
            action='promote',
            user=user)

    @commands.command(name="demote")
    async def member_demote(self,ctx,Discord_User:discord.User):
        """
        Demote a Member.

        Members are ranked based on Discord User and Clan. When promoting a Discord User, all their accounts registered in the provided Clan are promoted/demoted as a group.

        **Clan Permissions Apply**
        > - Only Clan Leaders can promote/demote Co-Leaders.
        > - Clan Leaders and Co-Leaders can promote/demote Elders and Members.
        > - You can only promote/demote for Clans that you are a Leader/Co-Leader in.
        > - A User must be a Member in that Clan to be eligible for promotion/demotion.

        **To change a Clan Leader, promote a Co-Leader. A Clan Leader cannot be promoted or demoted.**
        **Members cannot be demoted.**
        """

        user = Discord_User

        if ctx.author.id == user.id:
            eEmbed = await clash_embed(ctx,message=f"Self-mutilation is strongly discouraged. You might want to seek help.",color='fail')
            return await ctx.send(embed=eEmbed)

        await self.rank_handler(
            ctx=ctx,
            action='demote',
            user=user)

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

    @commands.command(name="getexcel")
    async def leader_excel_extract(self,ctx,clan_abbreviation:str):

        try:
            clan = [c for (tag,c) in ctx.bot.clan_cache.items() if c.abbreviation == clan_abbreviation.upper()][0]
        except:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)

        rpfile = await report_to_excel(ctx,clan)

        rept_embed = await clash_embed(ctx,
            title=f"Download Excel Report",
            message=f"Your report for **{clan.emoji} {clan.name}** is available for download below.",
            color='success')

        await ctx.send(embed=rept_embed,delete_after=60)
        await ctx.send(file=discord.File(rpfile))


    @commands.command(name="calculatexp")
    async def leader_xp_report(self,ctx,season):

        msg = await ctx.send("Please wait...")

        if season not in [season.id for season in ctx.bot.tracked_seasons]:
            await msg.delete()
            return await ctx.send(f"The season `{season}` is not valid. Note: This command can only be used for **completed** seasons.")

        season = aClashSeason(season)

        rpfile = await get_xp_report(ctx,season)

        rept_embed = await clash_embed(ctx,
            title=f"Season XP Calculations",
            message=f"XP Calculations for **{season.season_description}** is available for download below.",
            color='success')

        await ctx.send(embed=rept_embed,delete_after=60)
        await ctx.send(file=discord.File(rpfile))

        await msg.delete()

    @commands.command(name="getreport")
    async def leader_reports(self,ctx,clan_abbreviation:str):
        """
        Leader's Report Hub.

        Provides a one-stop repository of reports and data through an interactive menu.
        """

        try:
            c = [c for (tag,c) in ctx.bot.clan_cache.items() if c.abbreviation == clan_abbreviation.upper()][0]
        except:
            return await error_not_valid_abbreviation(ctx,clan_abbreviation)

        menu_dict = [
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
                'id': 'supertroop',
                'title': 'Active Super Troops',
                'description': f"Gets a list of active Super Troops boost from all members."
                },
            {
                'id': 'warstatus',
                'title': 'War Opt-In Status',
                'description': f"Gets a list of all members opted into war."
                },
            {
                'emoji': '<:download:1040800550373044304>',
                'id': 'excel',
                'title': 'Download to Excel (.xlsx)',
                'description': 'Get an Excel file containing all Member, Clan War, and Raid Weekend data.'
                }
            ]

        menu_dict = await multiple_choice_menu_generate_emoji(ctx,menu_dict)

        wait_embed = await clash_embed(ctx,message=f"<a:loading:1042769157248262154> Preparing your report... please wait.")

        menu_str = ""
        for i in menu_dict:
            menu_str += f"{i['emoji']} **{i['title']}**"
            menu_str += f"\n{i['description']}"

            if menu_dict.index(i) < (len(menu_dict)-1):
                menu_str += f"\n\n"

        message = None
        response = 'start'
        report_state = True

        while report_state:

            if response in ['start','menu']:

                main_menu_embed = await clash_embed(ctx,
                    title=f"Report Hub: {c.emoji} {c.desc_title}",
                    message=f"**Welcome to the Report Hub.**"
                        + f"\n\nHere, you'll be able to generate various in-discord reports for your selected clan. "
                        + f"Alternatively, extract all data in the bot into an Excel spreadsheet.\n\u200b",
                    thumbnail=c.badge)

                main_menu_embed.add_field(
                    name="```**To get started, please select a report from the list below.**```",
                    value=f"\u200b\n{menu_str}\n\n**Exit this Menu at any time by clicking on <:red_cross:838461484312428575>.**\n\u200b",
                    inline=False)

                if message:
                    await message.edit(content=ctx.author.mention,embed=main_menu_embed)
                else:
                    message = await ctx.send(content=ctx.author.mention,embed=main_menu_embed)

                await message.clear_reactions()
                selection = await multiple_choice_menu_select(ctx,message,menu_dict,timeout=60)

                if selection:
                    response = selection['id']
                else:
                    response = None

            if response in ['summary']:
                await message.edit(content=ctx.author.mention,embed=wait_embed)
                response = await report_member_summary(ctx,message,c)

            if response in ['allmembers']:
                await message.edit(content=ctx.author.mention,embed=wait_embed)
                response = await report_all_members(ctx,message,c)

            if response in ['missing']:
                await message.edit(content=ctx.author.mention,embed=wait_embed)
                response = await report_missing_members(ctx,message,c)

            if response in ['unrecognized']:
                await message.edit(content=ctx.author.mention,embed=wait_embed)
                response = await report_unrecognized_members(ctx,message,c)

            if response in ['supertroop']:
                await message.edit(content=ctx.author.mention,embed=wait_embed)
                response = await report_super_troops(ctx,message,c)

            if response in ['warstatus']:
                await message.edit(content=ctx.author.mention,embed=wait_embed)
                response = await report_war_status(ctx,message,c)

            if response in ['excel']:
                await message.edit(content=ctx.author.mention,embed=wait_embed)
                rpfile = await report_to_excel(ctx,c)

                rept_embed = await clash_embed(ctx,
                    title=f"Download Excel Report",
                    message=f"Your report for **{c.emoji} {c.name}** is available for download below.",
                    color='success')

                await ctx.send(embed=rept_embed,delete_after=60)
                await ctx.send(file=discord.File(rpfile))

                response = 'menu'

            if not response:
                report_state = False

        end_embed = await clash_embed(ctx,
            message="Report Hub closed.")

        try:
            await message.edit(content=ctx.author.mention,embed=end_embed)
            await message.clear_reactions()
        except:
            await ctx.send(content=ctx.author.mention,embed=end_embed)


