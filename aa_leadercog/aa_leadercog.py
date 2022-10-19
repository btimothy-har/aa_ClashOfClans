import os
import sys

import discord
import coc

import json
import asyncio
import random
import time
import re

from dotenv import load_dotenv
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify
from discord.utils import get
from datetime import datetime
from string import ascii_letters, digits
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice

load_dotenv()

sys.path.append(os.getenv("RESOURCEPATH"))
from clash_resources import get_th_emote
from clash_resources import token_confirmation, standard_confirmation, react_confirmation, datafile_retrieve, datafile_save, get_current_alliance, get_current_season, clash_embed
from clash_resources import getPlayer, player_shortfield, player_embed, ClashPlayerError
from clash_resources import getClan, ClashClanError

membershipGrid = ["Member", "Elder", "Co-Leader", "Leader"]

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

    async def cog_initialize(self):
        #Initializes API Login and Data Directory.
        coc_client = coc.EventsClient()
        
        try:
            await coc_client.login(os.getenv("CLASH_DEV_EMAIL"), os.getenv("CLASH_DEV_PASSWORD"))
        except coc.InvalidCredentials as error:
            await ctx.send("error")
        
        self.cDirPath = os.getenv("DATAPATH")
        self.cClient = coc_client

    @commands.group(name="leaderset",autohelp=False)
    async def leader_personalization(self,ctx):
        """Allows Leaders to personalize the Leader Bot for personal convenience."""
        pass

    @leader_personalization.command(name="myclan")
    @commands.admin_or_permissions(administrator=True)
    async def leader_personalization_myclan(self,ctx,*clan_abbreviation:str):
        """Set a default clan for yourself. Accepts any of the registered clan abbreviations."""

        input_abbr = []
        for i in clan_abbreviation:
            input_abbr.append(i.upper())

        currentClans,currentMembers = await get_current_alliance(self,rdict=True)

        clanAbbr = [v['abbr'] for (k,v) in currentClans.items()]
        
        for i in input_abbr:
            if i not in clanAbbr:
                embed = await clash_embed(ctx=ctx,
                    message=f"The abbreviation **{i}** is not recognized. Please retry the command.\nRegistered abbreviations: {humanize_list(clanAbbr)}.",
                    color="fail")
                return await ctx.send(embed=embed)

        userClans = await self.config.user(ctx.author).default_clan()
        userClans.append(clan_abbreviation)

        await self.config.user(ctx.author).default_clan.set(userClans)

        embed = await clash_embed(ctx=ctx,
                    message=f"Your preferred clans have been updated to: {humanize_list(userClans)}.",
                    color="success")
        return await ctx.send(embed=embed)

    @leader_personalization.command(name="reset")
    @commands.admin_or_permissions(administrator=True)
    async def leader_personalization_reset(self,ctx,clan_abbreviation:str):
        """Reset all customizations."""

        await self.config.user(ctx.author).default_clan.set([])

        await ctx.tick()

    @commands.group(name="arix",autohelp=False)
    async def alliance_parent(self,ctx):
        """Get information about the Alliance. Sub-commands allow leaders to manage the Alliance."""
            
        if not ctx.invoked_subcommand:
            currentClans,currentMembers = await get_current_alliance(self)
            if not len(currentClans) > 0:
                return await ctx.send("No clans found.")

            return await ctx.send(f"Clan Set:{currentClans}")

    @alliance_parent.command(name="add")
    @commands.admin_or_permissions(administrator=True)
    async def alliance_parent_addclan(self, ctx, tag:str, abbr:str):
        """Add a clan to the Alliance."""

        try:
            c, w = await getClan(self,ctx,tag)
        except ClashClanError as err:
            eEmbed = await err.errEmbed()
            return await ctx.send(embed=eEmbed)
        except:
            eEmbed = await clash_embed(ctx=ctx,
                message=f"An unknown error occurred.",
                color="fail")
            return await ctx.send(embed=eEmbed)

        if c.isAllianceClan:
            embed = await clash_embed(ctx=ctx,
                    message=f"The clan {c.clan.name} ({c.clan.tag}) is already part of the Alliance.",
                    color="fail",
                    thumbnail=c.clan.badge.url)
            return await ctx.send(embed=embed)

        embed = await clash_embed(ctx=ctx,
                            message=f"Please confirm that you would like to add the below clan.\nTo confirm, enter the token below as your next message.",
                            thumbnail=c.clan.badge.url)

        embed.add_field(name=f"**{c.clan.name} ({c.clan.tag})**",
                        value=f"Level: {c.clan.level}\u3000\u3000Location: {c.clan.location} / {c.clan.chat_language}"
                            + f"\n```{c.description}```",
                        inline=False)

        await ctx.send(embed=embed)

        if not await token_confirmation(self,ctx):
            return

        allianceJson = await datafile_retrieve(self,'alliance')
        warlogJson = await datafile_retrieve(self,'warlog')
        capitalraidJson = await datafile_retrieve(self,'capitalraid')

        allianceJson['clans'][clan.tag] = {
            'name':clan.name,
            'abbr':abbr,
            'description':'',
            'recruitment':{
                'townHall':[],
                'notes':""}
            }
        warlogJson[clan.tag] = {}
        capitalraidJson[clan.tag] = {}

        await datafile_save(self,'alliance',allianceJson)
        await datafile_save(self,'warlog',warlogJson)
        await datafile_save(self,'capitalraid',capitalraidJson)

        await ctx.send(f"Successfully added **{clan.tag} {clan.name}**!")

    @alliance_parent.command(name="remove")
    @commands.admin_or_permissions(administrator=True)
    async def alliance_parent_removeclan(self, ctx, tag:str):
        """Remove a clan from the Alliance."""

        try:
            c, w = await getClan(self,ctx,tag)
        except ClashClanError as err:
            eEmbed = await err.errEmbed()
            return await ctx.send(embed=eEmbed)
        except:
            eEmbed = await clash_embed(ctx=ctx,
                message=f"An unknown error occurred.",
                color="fail")
            return await ctx.send(embed=eEmbed)

        if not c.isAllianceClan:
            embed = await clash_embed(ctx=ctx,
                    message=f"The clan {c.clan.name} ({c.clan.tag}) is not part of the Alliance.",
                    color="fail",
                    thumbnail=c.clan.badge.url)
            return await ctx.send(embed=embed)

        embed = await clash_embed(ctx=ctx,
                message=f"Please confirm that you would like to remove the below clan.\nTo confirm, enter the token below as your next message.",
                thumbnail=c.clan.badge.url)

        embed.add_field(name=f"**{c.clan.name} ({c.clan.tag})**",
                value=f"Level: {c.clan.level}\u3000\u3000Location: {c.clan.location} / {c.clan.chat_language}"+
                            f"\n```{c.description}```",
                        inline=False)
        await ctx.send(embed=embed)

        if not await token_confirmation(self,ctx):
            return

        allianceJson = await datafile_retrieve(self,'alliance')
        del allianceJson['clans'][clan.tag]
        await datafile_save(self,'alliance',allianceJson)
        await ctx.send(f"Successfully removed **{clan.tag} {clan.name}**!")

    @commands.group(name="member",autohelp=False)
    @commands.admin_or_permissions(administrator=True)
    async def membermanage(self,ctx):
        """Member Management Tasks."""
        
        if not ctx.invoked_subcommand:
            pass

    @membermanage.command(name="summary")
    @commands.admin_or_permissions(administrator=True)
    async def membermanage_summary(self,ctx,*clan_abbreviation:str):
        """Generates a summary of all members in the provided clan(s). If no clan is provided, defaults to the user preference."""
        
        input_abbr = []
        output_embed = []
        if clan_abbreviation:
            for i in clan_abbreviation:
                input_abbr.append(i.upper())
        else:
            input_abbr = await self.config.user(ctx.author).default_clan()

        if not input_abbr:
            embed = await clash_embed(ctx=ctx,
                    message=f"To use this command, either provide a Clan Abbreviation, or set a default clan.",
                    color="fail")
            return await ctx.send(embed=embed)

        currentClans,currentMembers = await get_current_alliance(self,rdict=True)

        clanAbbr = [v['abbr'] for (k,v) in currentClans.items()]

        for i in input_abbr:
            if i not in clanAbbr:
                embed = await clash_embed(ctx=ctx,
                    message=f"The abbreviation **{i}** is not recognized. Please retry the command.\nRecognized abbreviations: {humanize_list(clanAbbr)}.",
                    color="fail")
                return await ctx.send(embed=embed)

        rptClans = {tag:clan for (tag,clan) in currentClans.items() if clan['abbr'] in input_abbr}

        for tag, clan in rptClans.items():
            try:
                c, w = await getClan(self,ctx,tag)
            except:
                eEmbed = await clash_embed(ctx=ctx,
                    message=f"An error was encountered when retrieving information for {tag} {clan['name']}.",
                    color="fail")
                output_embed.append(eEmbed)
                continue

            cMembers = {tag:member for (tag,member) in currentMembers.items() if member['home_clan']['tag'] == c.clan.tag and member['is_member']==True}
            xMembers = [member for member in c.clan.members if member.tag not in list(cMembers.keys())]
            
            oMembers = []
            mMembers = []
            eMembers = []

            th_Count = {15:0, 14:0, 13:0, 12:0, 11:0, 10:0, 9:0, 8:0, 7:0, 6:0, 5:0, 4:0, 3:0, 2:0, 1:0}

            for tag, member in cMembers.items():
                try:
                    p = await getPlayer(self,ctx,tag)
                except ClashPlayerError as err:
                    errD = {
                        'tag':tag,
                        'reason':'Unable to find a user with this tag.'
                        }
                    eMembers.append(tag)
                    continue
                except Exception as e:
                    p = None
                    errD = {
                        'tag':tag,
                        'reason':e
                        }
                    eMembers.append(tag)
                    continue

                th_Count[p.player.town_hall] += 1
                oMembers.append(p)

                if getattr(p.player.clan,"tag","") != p.homeClan.get('tag',''):
                    mMembers.append(p)

            averageTH = sum([m.player.town_hall for m in oMembers]) / len(oMembers)

            cEmbed = await clash_embed(ctx=ctx,
                    title=f"{c.clan.tag} {c.clan.name}",
                    message=f"Level: {c.clan.level}\u3000\u3000Location: {c.clan.location} / {c.clan.chat_language}"
                        + f"\n**Member Count:** {len(oMembers)}\u3000**Average TH**: {round(averageTH,2)}",
                    thumbnail=c.clan.badge.url)

            th_comp_str = ""
            for th, count in th_Count.items():
                if count > 0:
                    th_comp_str += f"{get_th_emote(th)} {count}\n"

            cEmbed.add_field(
                name="**Townhall Composition**",
                value=th_comp_str,
                inline=False)

            if len(mMembers) > 0:
                missingMembers_str = ""
                for m in mMembers:
                    title, value = await player_shortfield(self,ctx,m)
                    missingMembers_str += f"__{m.player.name}__ ({m.player.tag})\n> {value}\n> <:Clan:825654825509322752> {m.clanDescription}\n"
                cEmbed.add_field(
                    name="**Members Not in Clan**",
                    value=missingMembers_str,
                    inline=False)
            
            if len(xMembers) > 0:
                extraMembers_str = ""
                for m in xMembers:
                    extraMembers_str += f"{m.tag} {m.name}\n"
                cEmbed.add_field(
                    name="**Extra Members in Clan**",
                    value=extraMembers_str)

            output_embed.append(cEmbed)

        if len(output_embed)>1:
            paginator = BotEmbedPaginator(ctx,output_embed)
            return await paginator.run()
        elif len(output_embed)==1:
            return await ctx.send(embed=output_embed[0])

    @membermanage.command(name="add")
    @commands.admin_or_permissions(administrator=True)
    async def membermanage_add(self,ctx,user:discord.User, clan_abbreviation:str, *tags):
        """Add members to the Alliance. Multiple tags can be separated by a blank space."""

        homeClan = None
    
        processAdd = []
        successAdd = []
        failedAdd = []

        allianceJson = await datafile_retrieve(self,'alliance')
        memberStatsJson = await datafile_retrieve(self,'members')

        currentClans = list(allianceJson['clans'].keys())
        currentMembers = list(allianceJson['members'].keys())

        if not len(currentClans) >= 1:
            return await ctx.send("No clans registered to the Alliance! Please first register a clan with `[p]clanset add`.")

        if len(tags) == 0:
            return await ctx.send("Provide Player Tags to be added. Separate multiple tags with a space.")

        try:
            userID = user.id
        except:
            return await ctx.send("Unable to retrieve Discord User ID.")

        for clanTag in currentClans:
            if allianceJson['clans'][clanTag]['abbr'] == clan_abbreviation:
                try:
                    c, w = await getClan(self,ctx,clanTag)
                except:
                    eEmbed = await clash_embed(ctx=ctx,
                        message=f"An error was encountered when retrieving the clan {clanTag}.",
                        color="fail")
                    return await ctx.send(embed=eEmbed)
                else:
                    homeClan = c

        if not homeClan:
            return await ctx.send(f"The Clan abbreviation **{clan_abbreviation}** does not correspond to any registered clan.")

        cClanMembers = {k:v for (k,v) in allianceJson['members'].items() if v['home_clan']['tag']==homeClan.clan.tag}

        await ctx.send(len(cClanMembers))

        cEmbed = await clash_embed(ctx,
            title=f"Please confirm that you are adding the below accounts.",
            message=f"Discord User: {user.mention}"
                    + f"\nHome Clan: {homeClan.clan.tag} {homeClan.clan.name}")

        for tag in tags:
            tag = coc.utils.correct_tag(tag)

            try:
                p = await getPlayer(self,ctx,tag)
            except ClashPlayerError as err:
                p = None
                errD = {
                    'tag':tag,
                    'reason':'Unable to find a user with this tag.'
                    }
                failedAdd.append(errD)
                continue
            except:
                p = None
                errD = {
                    'tag':tag,
                    'reason':'Unknown error.'
                    }
                failedAdd.append(errD)
                continue
            
            fTitle, fStr = await player_shortfield(self,ctx,p)

            if p.player.tag in currentMembers:
                try:
                    existing_user = ctx.bot.get_user(int(p.discordUser))
                    existing_user = existing_user.mention
                except:
                    existing_user = "Invalid User"

                if p.isMember == False:
                    mStatus = "Non-Member"
                else:
                    mStatus = f"{p.memberStatus} of {p.homeClan['name']}"
                
                #Discord User on file does not match new user: request confirmation.
                if p.discordUser != userID:
                    zEmbed = await clash_embed(ctx,
                        message=f"The account below is already linked to another user. Please confirm that you wish to continue.")
                    zEmbed.add_field(
                        name=f"**{fTitle}**",
                        value=f"{fStr}\n{mStatus}\nLinked to: {existing_user}",
                        inline=False)

                    zMsg = await ctx.send(embed=zEmbed)
                    if not await react_confirmation(self,ctx,zMsg):
                        errD = {
                            'tag':tag,
                            'reason':'Already registered to another user.'
                            }
                        failedAdd.append(errD)
                        continue

                #Is a current active member, but in a different clan: request confirmation.
                elif p.isMember == True and homeClan.clan.tag != p.homeClan['tag']:
                    zEmbed = await clash_embed(ctx,
                        message=f"The account below is already an active member in the alliance. Please confirm that you wish to continue.")
                    zEmbed.add_field(
                        name=f"**{fTitle}**",
                        value=f"{fStr}\n{mStatus}\nLinked to: {existing_user}",
                        inline=False)

                    zMsg = await ctx.send(embed=zEmbed)
                    if not await react_confirmation(self,ctx,zMsg):
                        errD = {
                            'tag':tag,
                            'reason':f"Already an active member in {p.homeClan['name']}."
                            }
                        failedAdd.append(errD)
                        continue

                #Current active member, and in the same clan: do not process.
                elif p.isMember == True and homeClan.clan.tag == p.homeClan['tag']:
                    errD = {
                        'tag':tag,
                        'reason':f"Already an active member in {p.homeClan['name']}."
                        }
                    failedAdd.append(errD)
                    continue

            cEmbed.add_field(
                name=f"**{fTitle}**",
                value=f"{fStr}",
                inline=False)
            processAdd.append(p)

        if len(processAdd) > 0:
            cMsg = await ctx.send(embed=cEmbed)
            if not await react_confirmation(self,ctx,cMsg):
                return

            for p in processAdd:
                p.newMember(userID,homeClan)
                pAllianceJson,pMemberJson = p.toJson()
                    
                allianceJson['members'][p.player.tag] = pAllianceJson
                memberStatsJson[p.player.tag] = pMemberJson
                successAdd.append(
                    {
                    'player':p,
                    'clan':homeClan
                    }
                )
            await datafile_save(self,'alliance',allianceJson)
            await datafile_save(self,'members',memberStatsJson)

        successStr = "\u200b"
        failStr = "\u200b"
        for success in successAdd:
            successStr += f"**{success['player'].player.tag} {success['player'].player.name}** added to {success['clan'].clan.tag} {success['clan'].clan.name}.\n"

        for fail in failedAdd:
            failStr += f"{fail['tag']}: {fail['reason']}\n"

        aEmbed = await clash_embed(ctx=ctx,title=f"Operation: Add Member(s)")

        aEmbed.add_field(name=f"**__Success__**",
                        value=successStr,
                        inline=False)
        aEmbed.add_field(name=f"**__Failed__**",
                        value=failStr,
                        inline=False)

        return await ctx.send(embed=aEmbed)

    @membermanage.command(name="remove")
    @commands.admin_or_permissions(administrator=True)
    async def membermanage_remove(self,ctx,*tags):
        """Remove members from the Alliance. Multiple tags can be separated by a blank space."""

        processRemove = []
        successRemove = []
        failedRemove = []

        allianceJson = await datafile_retrieve(self,'alliance')

        currentClans = list(allianceJson['clans'].keys())
        currentMembers = list(allianceJson['members'].keys())

        cEmbed = await clash_embed(ctx,
            title=f"I found the below accounts to be removed. Please confirm this action.")

        for tag in tags:
            tag = coc.utils.correct_tag(tag)

            if tag not in currentMembers:
                errD = {
                    'tag':tag,
                    'reason':'Could not find this tag in the member list.'
                    }
                failedRemove.append(errD)
                continue

            if allianceJson['members'][tag]['is_member'] == False:
                errD = {
                    'tag':tag,
                    'reason':'Not currently an active member.'
                    }
                failedRemove.append(errD)
                continue

            try:
                p = await getPlayer(self,ctx,tag)
            except ClashPlayerError as err:
                p = None
                errD = {
                    'tag':tag,
                    'reason':'Unable to find a user with this tag.'
                    }
                failedRemove.append(errD)
                continue
            except:
                p = None
                errD = {
                    'tag':tag,
                    'reason':'Unknown error.'
                    }
                failedRemove.append(errD)
                continue

            fTitle, fStr = await player_shortfield(self,ctx,p)
            cEmbed.add_field(
                name=f"**{fTitle}**",
                value=f"\n{fStr}"
                    +f"\nHome Clan: {p.memberStatus} of {p.homeClan['name']}"
                    + f"\nLinked To: <@{p.discordUser}>",
                inline=False)
            processRemove.append(p)

        if len(processRemove) > 0:
            cMsg = await ctx.send(embed=cEmbed)
            if not await react_confirmation(self,ctx,cMsg):
                return

            for p in processRemove:
                p.removeMember()
                pAllianceJson,pMemberJson = p.toJson()
                    
                allianceJson['members'][p.player.tag] = pAllianceJson
                successRemove.append(
                    {
                    'player':p,
                    }
                )
            await datafile_save(self,'alliance',allianceJson)

        successStr = "\u200b"
        failStr = "\u200b"
        for success in successRemove:
            successStr += f"**{success['player'].player.tag} {success['player'].player.name}** removed from {p.homeClan['name']}.\n"

        for fail in failedRemove:
            failStr += f"{fail['tag']}: {fail['reason']}\n"

        aEmbed = await clash_embed(ctx=ctx,title=f"Operation: Remove Member(s)")

        aEmbed.add_field(name=f"**__Success__**",
                        value=successStr,
                        inline=False)

        aEmbed.add_field(name=f"**__Failed__**",
                        value=failStr,
                        inline=False)
        return await ctx.send(embed=aEmbed)

    @membermanage.command(name="promote")
    @commands.admin_or_permissions(administrator=True)
    async def membermanage_promote(self,ctx,user:discord.User, clan_abbreviation:str):
        """Promote all of a User's Accounts in the specified clan. This command will take the member's highest rank and promote it one level higher."""

        promoteClan = None
    
        processPromote = []
        successPromote = []
        failedPromote = []

        allianceJson = await datafile_retrieve(self,'alliance')

        currentClans = list(allianceJson['clans'].keys())
        currentMembers = list(allianceJson['members'].keys())

        if not len(currentClans) >= 1:
            return await ctx.send("No clans registered to the Alliance! Please first register a clan with `[p]clanset add`.")

        try:
            userID = user.id
        except:
            return await ctx.send("Unable to retrieve Discord User ID.")

        for clanTag in currentClans:
            if allianceJson['clans'][clanTag]['abbr'] == clan_abbreviation:
                try:
                    c, w = await getClan(self,ctx,tag)
                except:
                    eEmbed = await clash_embed(ctx=ctx,
                        message=f"An unknown error occurred.",
                        color="fail")
                    return await ctx.send(embed=eEmbed)
                else:
                    promoteClan = c

        if not promoteClan:
            return await ctx.send(f"The Clan abbreviation **{clan_abbreviation}** does not correspond to any registered clan.")

        cEmbed = await clash_embed(ctx,
            title=f"Please confirm that you would like to promote the below accounts.",
            message=f"Discord User: {user.mention}"
                + f"\nHome Clan: {promoteClan.clan.tag} {promoteClan.clan.name}")

        currentRank = "Member"
        for tag, member in allianceJson['members'].items(): 
            if member['discord_user'] == userID and member['is_member'] == True and member['home_clan'] == promoteClan.clan.tag:
                try:
                    p = await getPlayer(self,ctx,tag,force_member=True)
                except ClashPlayerError as err:
                    p = None
                    errD = {
                        'tag':tag,
                        'reason':'Unable to find a user with this tag.'
                        }
                    failedPromote.append(errD)
                    continue
                except:
                    p = None
                    errD = {
                        'tag':tag,
                        'reason':'Unknown error.'
                        }
                    failedPromote.append(errD)
                    continue

                fTitle, fStr = await player_shortfield(self,ctx,p)
                cEmbed.add_field(
                    name=f"**{fTitle}**",
                    value=f"{fStr}",
                    inline=False)
                processPromote.append(p)

                if membershipGrid.index(p.memberStatus) > membershipGrid.index(currentRank):
                    currentRank = p.memberStatus

        if len(processPromote) == 0:
            return await ctx.send(f"This user does not have any valid accounts for promotion.")

        if currentRank == "Leader":
            newRank = "Leader"
        else:
            newRankID = membershipGrid.index(currentRank) + 1
            newRank = membershipGrid[newRankID]

        cEmbed.add_field(
            name="**New Rank after Promotion**",
            value=f"{newRank} of {promoteClan.clan.name}")

        cMsg = await ctx.send(embed=cEmbed)
        if not await react_confirmation(self,ctx,cMsg):
            return

        for p in processPromote:
            p.updateRank(newRank)
            pAllianceJson, pMemberStatsJson = p.toJson()
            allianceJson['members'][p.player.tag] = pAllianceJson

            successPromote.append(p)

        await datafile_save(self,'alliance',allianceJson)

        successStr = "\u200b"
        failStr = "\u200b"
        for success in successPromote:
            successStr += f"**{success.player.tag} {success.player.name}** promoted to {newRank} of {promoteClan.clan.name}.\n"

        for fail in failedPromote:
            failStr += f"{fail['tag']}: {fail['reason']}\n"

        aEmbed = await clash_embed(ctx=ctx,title=f"Operation Report: Promote {user.name}#{user.discriminator}")

        aEmbed.add_field(name=f"**__Success__**",
                        value=successStr,
                        inline=False)

        aEmbed.add_field(name=f"**__Failed__**",
                        value=failStr,
                        inline=False)
        return await ctx.send(embed=aEmbed)

    @commands.command(name="profile")
    async def profile(self, ctx, user_or_tag=None):

        allianceJson = await datafile_retrieve(self,'alliance')
        accounts = []

        if not user_or_tag:
            user = ctx.author
            tag = None
        else:
            try:
                userID = re.search('@(.*)>',user_or_tag).group(1)
                user = ctx.bot.get_user(int(userID))
                tag = None
            except:
                tag = user_or_tag        
                user = None

        if user:
            for tag, member in allianceJson['members'].items():
                if member['discord_user'] == user.id:
                    try:
                        p = await getPlayer(self,ctx,tag)
                    except ClashPlayerError as err:
                        p = None
                        errD = {
                            'tag':tag,
                            'reason':'Unable to find a user with this tag.'
                            }
                        continue
                    except:
                        p = None
                        errD = {
                            'tag':tag,
                            'reason':'Unknown error.'
                            }
                        continue
                    else:
                        pEmbed = await player_embed(self,ctx,p)
                        accounts.append(pEmbed)
        elif tag:
            try:
                p = await getPlayer(self,ctx,tag)
            except ClashPlayerError as err:
                return await ctx.send(f'Unable to find a user with the tag {tag}.')
            except:
                return await ctx.send(f'Unable to find a user with the tag {tag}.')
            else:
                pEmbed = await player_embed(self,ctx,p)
                accounts.append(pEmbed)

        if len(accounts)>1:
            paginator = BotEmbedPaginator(ctx,accounts)
            return await paginator.run()
        elif len(accounts)==1:
            return await ctx.send(embed=embed)

    @commands.command(name="test")
    async def test(self, ctx):
        testwar = await self.cClient.get_clan_war('2yl99gc9l')

        await ctx.send(type(testwar))

        await ctx.send(f"{testwar.clan.name} {testwar.opponent.name} {testwar.state} {testwar.team_size}")

        tag = testwar.clan.tag

        epoch = testwar.start_time.time.timestamp()

        await ctx.send(epoch)
        await ctx.send(testwar.type)

        for member in testwar.members:
            if member.clan.tag == tag:
                await ctx.send(f"{member.map_position} {member.name}")

        for attack in testwar.attacks:
            await ctx.send(f"{attack.war} {attack.order} {attack.attacker_tag} vs {attack.defender_tag} {attack.stars} {attack.destruction} {attack.duration}")