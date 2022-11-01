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
from aa_resourcecog.constants import confirmation_emotes
from aa_resourcecog.notes import aNote
from aa_resourcecog.player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from aa_resourcecog.clan import aClan
from aa_resourcecog.clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from aa_resourcecog.raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog

class AriXClashLeaders(commands.Cog):
    """AriX Clash of Clans Leaders' Module."""

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

    # @commands.group(name="leaderset",autohelp=False)
    # async def leader_personalization(self,ctx):
    #     """Allows Leaders to personalize the Leader Bot for personal convenience."""
    #     pass

    # @leader_personalization.command(name="myclan")
    # @commands.admin_or_permissions(administrator=True)
    # async def leader_personalization_myclan(self,ctx,*clan_abbreviation:str):
    #     """Set a default clan for yourself. Accepts any of the registered clan abbreviations."""

    #     input_abbr = []
    #     for i in clan_abbreviation:
    #         input_abbr.append(i.upper())

    #     currentClans,currentMembers = await get_current_alliance(self,rdict=True)

    #     clanAbbr = [v['abbr'] for (k,v) in currentClans.items()]
        
    #     for i in input_abbr:
    #         if i not in clanAbbr:
    #             embed = await clash_embed(ctx=ctx,
    #                 message=f"The abbreviation **{i}** is not recognized. Please retry the command.\nRegistered abbreviations: {humanize_list(clanAbbr)}.",
    #                 color="fail")
    #             return await ctx.send(embed=embed)

    #     userClans = await self.config.user(ctx.author).default_clan()

    #     for i in input_abbr:
    #         userClans.append(i)

    #     await self.config.user(ctx.author).default_clan.set(userClans)

    #     embed = await clash_embed(ctx=ctx,
    #                 message=f"Your preferred clans have been updated to: {humanize_list(userClans)}.",
    #                 color="success")
    #     return await ctx.send(embed=embed)

    # @leader_personalization.command(name="reset")
    # @commands.admin_or_permissions(administrator=True)
    # async def leader_personalization_reset(self,ctx,clan_abbreviation:str):
    #     """Reset all customizations."""

    #     await self.config.user(ctx.author).default_clan.set([])

    #     await ctx.tick()

    @commands.group(name="clan")
    async def clan_manage(self,ctx):
        """Manage clans in the Alliance."""
            
        if not ctx.invoked_subcommand:
            pass

    @clan_manage.command(name="add")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_add(self, ctx, leader:discord.User, tag:str, abbr:str):
        """Add a clan to the Alliance."""

        try:
            c = await aClan.create(ctx,tag)
        except ClashClanError as err:
            eEmbed = await err.errEmbed()
            return await ctx.send(embed=eEmbed)
        except:
            eEmbed = await resc.clash_embed(ctx=ctx,
                message=f"An unknown error occurred.",
                color="fail")
            return await ctx.send(embed=eEmbed)

        if c.is_alliance_clan:
            embed = await resc.clash_embed(ctx=ctx,
                    message=f"The clan {c.name} ({c.tag}) is already part of the Alliance.",
                    color="fail",
                    thumbnail=c.clan.badge.url)
            return await ctx.send(embed=embed)

        embed = await resc.clash_embed(ctx=ctx,
                            message=f"Please confirm that you would like to add the below clan.",
                            thumbnail=c.c.badge.url)

        embed.add_field(name=f"**{c.name} ({c.tag})**",
                        value=f"Level: {c.c.level}\u3000\u3000Location: {c.c.location} / {c.c.chat_language}"
                            + f"\nLeader: {leader.mention}"
                            + f"\n```{c.description}```",
                        inline=False)

        cMsg = await ctx.send(embed=embed)
        if not await resc.user_confirmation(ctx,cMsg):
            return

        with ctx.bot.clash_file_lock.write_lock():
            await c.add_to_alliance(abbreviation=abbr.upper(),leader=leader)
            await c.save_to_json()

        await ctx.send(f"Successfully added **{clan.tag} {clan.name}**!")

    @clan_manage.command(name="remove")
    @commands.admin_or_permissions(administrator=True)
    async def clan_manage_remove(self, ctx, tag:str):
        """Remove a clan from the Alliance."""

        try:
            c = await aClan.create(ctx,tag)
        except ClashClanError as err:
            eEmbed = await err.errEmbed()
            return await ctx.send(embed=eEmbed)
        except:
            eEmbed = await resc.clash_embed(ctx=ctx,
                message=f"An unknown error occurred.",
                color="fail")
            return await ctx.send(embed=eEmbed)

        if not c.is_alliance_clan:
            embed = await resc.clash_embed(ctx=ctx,
                    message=f"The clan {c.name} ({c.tag}) is not part of the Alliance.",
                    color="fail",
                    thumbnail=c.c.badge.url)
            return await ctx.send(embed=embed)

        embed = await resc.clash_embed(ctx=ctx,
                message=f"Please confirm that you would like to remove the below clan.",
                thumbnail=c.c.badge.url)

        embed.add_field(name=f"**{c.name} ({c.tag})**",
                value=f"Level: {c.c.level}\u3000\u3000Location: {c.c.location} / {c.c.chat_language}"+
                            f"\n```{c.description}```",
                        inline=False)
        
        cMsg = await ctx.send(embed=embed)
        if not await resc.user_confirmation(ctx,cMsg):
            return

        with ctx.bot.clash_file_lock.write_lock():
            with open(ctx.bot.clash_dir_path+'/alliance.json','w+') as file:
                file_json = json.load(file)
                del file_json['clans'][c.tag]
                json.dump(file_json,file,indent=2)
                file.truncate()
    
        await ctx.send(f"Successfully removed **{c.tag} {c.name}**!")

    @commands.group(name="member",autohelp=False)
    @commands.admin_or_permissions(administrator=True)
    async def member_manage(self,ctx):
        """Member Management Tasks."""
        
        if not ctx.invoked_subcommand:
            pass

    @membermanage.command(name="add")
    @commands.admin_or_permissions(administrator=True)
    async def membermanage_add(self,ctx,user:discord.User, clan_abbreviation:str, *tags):
        """Add members to the Alliance. Multiple tags can be separated by a blank space."""

        home_clan = None
    
        process_add = []
        success_add = []
        failed_add = []

        clans, members = await get_current_alliance()

        if not len(clans) >= 1:
            return await ctx.send("No clans registered to the Alliance! Please first register a clan with `[p]clanset add`.")

        if len(tags) == 0:
            return await ctx.send("Provide Player Tags to be added. Separate multiple tags with a space.")

        try:
            user_id = user.id
        except:
            return await ctx.send("Unable to retrieve Discord User ID.")

        for tag in clans:
            c = await aClan.create(ctx,tag)
            if clan_abbreviation == c.abbreviation:
                home_clan = c

        if not home_clan:
            return await ctx.send(f"The Clan abbreviation **{clan_abbreviation}** does not correspond to any registered clan.")

        cEmbed = await resc.clash_embed(ctx,
            title=f"Please confirm that you are adding the below accounts.",
            message=f"Discord User: {user.mention}"
                    + f"\nHome Clan: {home_clan.tag} {home_clan.name}")

        for tag in tags:
            try:
                p = await aPlayer.create(ctx,tag)
                await p.retrieve_data()
            except ClashPlayerError as err:
                p = None
                errD = {
                    'tag':tag,
                    'reason':'Unable to find a user with this tag.'
                    }
                failed_add.append(errD)
                continue
            except:
                p = None
                errD = {
                    'tag':tag,
                    'reason':'Unknown error.'
                    }
                failed_add.append(errD)
                continue

            p_title, p_field = await resc.player_summary(ctx,p)

            #Discord User on file does not match new user: request confirmation.
            if p.discord_user != 0 and p.discord_user != user_id:
                try:
                    existing_user = ctx.bot.get_user(int(p.discord_user))
                    existing_user = existing_user.mention
                except:
                    existing_user = "Invalid User"
                
                zEmbed = await resc.clash_embed(ctx,
                    message=f"The account below is already linked to another user. Please confirm that you wish to continue.")
                zEmbed.add_field(
                    name=f"**{p_title}**",
                    value=f"{p_field}\n{p.arix_rank} of {p.home_clan.name}\nLinked to: {existing_user}",
                    inline=False)

                zMsg = await ctx.send(embed=zEmbed)
                if not await resc.user_confirmation(self,ctx,zMsg):
                    errD = {
                        'tag':tag,
                        'reason':'Already registered to another user.'
                        }
                    failed_add.append(errD)
                    continue

            #Is a current active member, but in a different clan: request confirmation.
            if p.is_member and home_clan.tag != p.home_clan.tag:
                zEmbed = await resc.clash_embed(ctx,
                    message=f"The account below is already an active member in the alliance. Please confirm that you wish to continue.")
                zEmbed.add_field(
                    name=f"**{p_title}**",
                    value=f"{p_field}\n{p.arix_rank} of {p.home_clan.name}\nLinked to: {existing_user}",
                    inline=False)

                zMsg = await ctx.send(embed=zEmbed)
                if not await resc.user_confirmation(self,ctx,zMsg):
                    errD = {
                        'tag':tag,
                        'reason':f"Already an active member in {p.home_clan.name}."
                        }
                    failed_add.append(errD)
                    continue

            #Current active member, and in the same clan: do not process.
            if p.is_member and home_clan.tag == p.home_clan.tag:
                errD = {
                    'tag':tag,
                    'reason':f"Already an active member in {p.home_clan.name}."
                    }
                failed_add.append(errD)
                continue

            cEmbed.add_field(
                name=f"**{p_title}**",
                value=f"{p_field}",
                inline=False)
            process_add.append(p)

        if len(process_add) > 0:
            cMsg = await ctx.send(embed=cEmbed)
            if not await react_confirmation(self,ctx,cMsg):
                return

            for p in process_add:
                await p.new_member(user_id,home_clan)
                await p.save_to_json()
                success_add.append(
                    {
                    'player':p,
                    'clan':home_clan
                    }
                )

        successStr = "\u200b"
        failStr = "\u200b"
        for success in successAdd:
            successStr += f"**{success['player'].tag} {success['player'].name}** added to {success['clan'].tag} {success['clan'].name}.\n"

        for fail in failedAdd:
            failStr += f"{fail['tag']}: {fail['reason']}\n"

        aEmbed = await resc.clash_embed(ctx=ctx,title=f"Operation: Add Member(s)")

        aEmbed.add_field(name=f"**__Success__**",
                        value=successStr,
                        inline=False)
        aEmbed.add_field(name=f"**__Failed__**",
                        value=failStr,
                        inline=False)

        return await ctx.send(embed=aEmbed)

    # @membermanage.command(name="report")
    # @commands.admin_or_permissions(administrator=True)
    # async def member_manage_report(self,ctx,*clan_abbreviation:str):
    #     """Generates a summary of all members in the provided clan(s)."""
        
    #     input_abbr = []
    #     output_embed = []
    #     if clan_abbreviation:
    #         for i in clan_abbreviation:
    #             input_abbr.append(i.upper())
    #     else:
    #         input_abbr = await self.config.user(ctx.author).default_clan()

    #     if not input_abbr:
    #         embed = await clash_embed(ctx=ctx,
    #                 message=f"To use this command, either provide a Clan Abbreviation, or set a default clan.",
    #                 color="fail")
    #         return await ctx.send(embed=embed)

    #     currentClans,currentMembers = await get_current_alliance(self,rdict=True)

    #     clanAbbr = [v['abbr'] for (k,v) in currentClans.items()]

    #     for i in input_abbr:
    #         if i not in clanAbbr:
    #             embed = await clash_embed(ctx=ctx,
    #                 message=f"The abbreviation **{i}** is not recognized. Please retry the command.\nRecognized abbreviations: {humanize_list(clanAbbr)}.",
    #                 color="fail")
    #             return await ctx.send(embed=embed)

    #     rptClans = {tag:clan for (tag,clan) in currentClans.items() if clan['abbr'] in input_abbr}

    #     for tag, clan in rptClans.items():
    #         try:
    #             c, w = await getClan(self,ctx,tag)
    #         except:
    #             eEmbed = await clash_embed(ctx=ctx,
    #                 message=f"An error was encountered when retrieving information for {tag} {clan['name']}.",
    #                 color="fail")
    #             output_embed.append(eEmbed)
    #             continue

    #         cMembers = {tag:member for (tag,member) in currentMembers.items() if member['home_clan']['tag'] == c.clan.tag and member['is_member']==True}
    #         aMembers = []

    #         th_Count = {15:0, 14:0, 13:0, 12:0, 11:0, 10:0, 9:0, 8:0}

    #         for tag, member in cMembers.items():
    #             mDict = {}
    #             try:
    #                 p = await getPlayer(self,ctx,tag)
    #             except ClashPlayerError as err:
    #                 errD = {
    #                     'tag':tag,
    #                     'reason':'Unable to find a user with this tag.'
    #                     }
    #                 eMembers.append(tag)
    #                 continue
    #             except Exception as e:
    #                 p = None
    #                 errD = {
    #                     'tag':tag,
    #                     'reason':e
    #                     }
    #                 eMembers.append(tag)
    #                 continue

    #             mDict['TH'] = p.player.town_hall
    #             mDict['BK'] = p.barbarianKing
    #             mDict['AQ'] = p.archerQueen
    #             mDict['GW'] = p.grandWarden
    #             mDict['RC'] = p.royalChampion
    #             mDict['Name'] = p.player.name

    #             aMembers.append(mDict)
    #             title, value = await player_shortfield(self,ctx,p)
    #             th_Count[max(p.player.town_hall,8)] += 1

    #         aMembers = sorted(aMembers,key=lambda p:(p['TH'],p['Name']),reverse=True)
    #         averageTH = sum([m['TH'] for m in aMembers]) / len(aMembers)

    #         thStr = ""
    #         for th,count in th_Count.items():
    #             if count > 0:
    #                 thStr += f"{get_th_emote(th)} {count}\u3000"

    #         cEmbed = await clash_embed(ctx=ctx,
    #                 title=f"{c.clan.tag} {c.clan.name}",
    #                 message=f"Level: {c.clan.level}\u3000\u3000Location: {c.clan.location} / {c.clan.chat_language}"
    #                     + f"\nMember Count: {len(aMembers)}\u3000Average TH: {round(averageTH,2)}"
    #                     + f"\n\n{thStr}"
    #                     + f"```{tabulate(aMembers,headers='keys')}```")

    #         # th_comp_str = ""
    #         # for th, count in th_Count.items():
    #         #     if count > 0:
    #         #         th_comp_str += f"{get_th_emote(th)} {count}\n"

    #         # cEmbed.add_field(
    #         #     name="**Townhall Composition**",
    #         #     value=th_comp_str,
    #         #     inline=False)

    #         # if len(mMembers) > 0:
    #         #     missingMembers_str = ""
    #         #     for m in mMembers:
                    
    #         #         missingMembers_str += f"__{m.player.name}__ ({m.player.tag})\n> {value}\n> <:Clan:825654825509322752> {m.clanDescription}\n"
    #         #     cEmbed.add_field(
    #         #         name="**Members Not in Clan**",
    #         #         value=missingMembers_str,
    #         #         inline=False)
            
    #         # if len(xMembers) > 0:
    #         #     extraMembers_str = ""
    #         #     for m in xMembers:
    #         #         extraMembers_str += f"{m.tag} {m.name}\n"
    #         #     cEmbed.add_field(
    #         #         name="**Extra Members in Clan**",
    #         #         value=extraMembers_str)

    #         output_embed.append(cEmbed)

    #     if len(output_embed)>1:
    #         paginator = BotEmbedPaginator(ctx,output_embed)
    #         return await paginator.run()
    #     elif len(output_embed)==1:
    #         return await ctx.send(embed=output_embed[0])

    # @membermanage.command(name="remove")
    # @commands.admin_or_permissions(administrator=True)
    # async def membermanage_remove(self,ctx,*tags):
    #     """Remove members from the Alliance. Multiple tags can be separated by a blank space."""

    #     processRemove = []
    #     successRemove = []
    #     failedRemove = []

    #     allianceJson = await datafile_retrieve(self,'alliance')

    #     currentClans = list(allianceJson['clans'].keys())
    #     currentMembers = list(allianceJson['members'].keys())

    #     cEmbed = await clash_embed(ctx,
    #         title=f"I found the below accounts to be removed. Please confirm this action.")

    #     for tag in tags:
    #         tag = coc.utils.correct_tag(tag)

    #         if tag not in currentMembers:
    #             errD = {
    #                 'tag':tag,
    #                 'reason':'Could not find this tag in the member list.'
    #                 }
    #             failedRemove.append(errD)
    #             continue

    #         if allianceJson['members'][tag]['is_member'] == False:
    #             errD = {
    #                 'tag':tag,
    #                 'reason':'Not currently an active member.'
    #                 }
    #             failedRemove.append(errD)
    #             continue

    #         try:
    #             p = await getPlayer(self,ctx,tag)
    #         except ClashPlayerError as err:
    #             p = None
    #             errD = {
    #                 'tag':tag,
    #                 'reason':'Unable to find a user with this tag.'
    #                 }
    #             failedRemove.append(errD)
    #             continue
    #         except:
    #             p = None
    #             errD = {
    #                 'tag':tag,
    #                 'reason':'Unknown error.'
    #                 }
    #             failedRemove.append(errD)
    #             continue

    #         fTitle, fStr = await player_shortfield(self,ctx,p)
    #         cEmbed.add_field(
    #             name=f"**{fTitle}**",
    #             value=f"\n{fStr}"
    #                 +f"\nHome Clan: {p.memberStatus} of {p.homeClan['name']}"
    #                 + f"\nLinked To: <@{p.discordUser}>",
    #             inline=False)
    #         processRemove.append(p)

    #     if len(processRemove) > 0:
    #         cMsg = await ctx.send(embed=cEmbed)
    #         if not await react_confirmation(self,ctx,cMsg):
    #             return

    #         for p in processRemove:
    #             p.removeMember()
    #             pAllianceJson,pMemberJson = p.toJson()
                    
    #             allianceJson['members'][p.player.tag] = pAllianceJson
    #             successRemove.append(
    #                 {
    #                 'player':p,
    #                 }
    #             )
    #         await datafile_save(self,'alliance',allianceJson)

    #     successStr = "\u200b"
    #     failStr = "\u200b"
    #     for success in successRemove:
    #         successStr += f"**{success['player'].player.tag} {success['player'].player.name}** removed from {p.homeClan['name']}.\n"

    #     for fail in failedRemove:
    #         failStr += f"{fail['tag']}: {fail['reason']}\n"

    #     aEmbed = await clash_embed(ctx=ctx,title=f"Operation: Remove Member(s)")

    #     aEmbed.add_field(name=f"**__Success__**",
    #                     value=successStr,
    #                     inline=False)

    #     aEmbed.add_field(name=f"**__Failed__**",
    #                     value=failStr,
    #                     inline=False)
    #     return await ctx.send(embed=aEmbed)

    # @membermanage.command(name="promote")
    # @commands.admin_or_permissions(administrator=True)
    # async def membermanage_promote(self,ctx,user:discord.User, clan_abbreviation:str):
    #     """Promote all of a User's Accounts in the specified clan. This command will take the member's highest rank and promote it one level higher."""

    #     promoteClan = None
    
    #     processPromote = []
    #     successPromote = []
    #     failedPromote = []

    #     allianceJson = await datafile_retrieve(self,'alliance')

    #     currentClans = list(allianceJson['clans'].keys())
    #     currentMembers = list(allianceJson['members'].keys())

    #     if not len(currentClans) >= 1:
    #         return await ctx.send("No clans registered to the Alliance! Please first register a clan with `[p]clanset add`.")

    #     try:
    #         userID = user.id
    #     except:
    #         return await ctx.send("Unable to retrieve Discord User ID.")

    #     for clanTag in currentClans:
    #         if allianceJson['clans'][clanTag]['abbr'] == clan_abbreviation:
    #             try:
    #                 c, w = await getClan(self,ctx,tag)
    #             except:
    #                 eEmbed = await clash_embed(ctx=ctx,
    #                     message=f"An unknown error occurred.",
    #                     color="fail")
    #                 return await ctx.send(embed=eEmbed)
    #             else:
    #                 promoteClan = c

    #     if not promoteClan:
    #         return await ctx.send(f"The Clan abbreviation **{clan_abbreviation}** does not correspond to any registered clan.")

    #     cEmbed = await clash_embed(ctx,
    #         title=f"Please confirm that you would like to promote the below accounts.",
    #         message=f"Discord User: {user.mention}"
    #             + f"\nHome Clan: {promoteClan.clan.tag} {promoteClan.clan.name}")

    #     currentRank = "Member"
    #     for tag, member in allianceJson['members'].items(): 
    #         if member['discord_user'] == userID and member['is_member'] == True and member['home_clan'] == promoteClan.clan.tag:
    #             try:
    #                 p = await getPlayer(self,ctx,tag,force_member=True)
    #             except ClashPlayerError as err:
    #                 p = None
    #                 errD = {
    #                     'tag':tag,
    #                     'reason':'Unable to find a user with this tag.'
    #                     }
    #                 failedPromote.append(errD)
    #                 continue
    #             except:
    #                 p = None
    #                 errD = {
    #                     'tag':tag,
    #                     'reason':'Unknown error.'
    #                     }
    #                 failedPromote.append(errD)
    #                 continue

    #             fTitle, fStr = await player_shortfield(self,ctx,p)
    #             cEmbed.add_field(
    #                 name=f"**{fTitle}**",
    #                 value=f"{fStr}",
    #                 inline=False)
    #             processPromote.append(p)

    #             if membershipGrid.index(p.memberStatus) > membershipGrid.index(currentRank):
    #                 currentRank = p.memberStatus

    #     if len(processPromote) == 0:
    #         return await ctx.send(f"This user does not have any valid accounts for promotion.")

    #     if currentRank == "Leader":
    #         newRank = "Leader"
    #     else:
    #         newRankID = membershipGrid.index(currentRank) + 1
    #         newRank = membershipGrid[newRankID]

    #     cEmbed.add_field(
    #         name="**New Rank after Promotion**",
    #         value=f"{newRank} of {promoteClan.clan.name}")

    #     cMsg = await ctx.send(embed=cEmbed)
    #     if not await react_confirmation(self,ctx,cMsg):
    #         return

    #     for p in processPromote:
    #         p.updateRank(newRank)
    #         pAllianceJson, pMemberStatsJson = p.toJson()
    #         allianceJson['members'][p.player.tag] = pAllianceJson

    #         successPromote.append(p)

    #     await datafile_save(self,'alliance',allianceJson)

    #     successStr = "\u200b"
    #     failStr = "\u200b"
    #     for success in successPromote:
    #         successStr += f"**{success.player.tag} {success.player.name}** promoted to {newRank} of {promoteClan.clan.name}.\n"

    #     for fail in failedPromote:
    #         failStr += f"{fail['tag']}: {fail['reason']}\n"

    #     aEmbed = await clash_embed(ctx=ctx,title=f"Operation Report: Promote {user.name}#{user.discriminator}")

    #     aEmbed.add_field(name=f"**__Success__**",
    #                     value=successStr,
    #                     inline=False)

    #     aEmbed.add_field(name=f"**__Failed__**",
    #                     value=failStr,
    #                     inline=False)
    #     return await ctx.send(embed=aEmbed)

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

    @commands.command(name="test")
    async def test(self, ctx):
        #cWar = await self.cClient.get_clan_war('92g9j8cg')

        clan = await self.cClient.get_clan('2yl99gc9l')

        await ctx.send(f"clan: {clan.name}")
        await ctx.send(f".{dir(self.cClient)}")
        await ctx.send(f".{dir(clan)}")