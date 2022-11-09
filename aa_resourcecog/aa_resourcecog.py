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

from .constants import confirmation_emotes, selection_emotes, emotes_army
from .file_functions import get_current_season, get_current_alliance, season_file_handler, alliance_file_handler, data_file_handler
from .notes import aNote
from .player import aPlayer, aTownHall, aPlayerStat, aHero, aHeroPet, aTroop, aSpell, aPlayerWarStats, aPlayerRaidStats
from .clan import aClan
from .clan_war import aClanWar, aWarClan, aWarPlayer, aWarAttack, aPlayerWarLog, aPlayerWarClan
from .raid_weekend import aRaidWeekend, aRaidClan, aRaidDistrict, aRaidMember, aRaidAttack, aPlayerRaidLog

load_dotenv()

class AriXClashResources(commands.Cog):
    """AriX Clash of Clans Resource Module."""

    def __init__(self):
        self.config = Config.get_conf(self,identifier=4654586202897940,force_registration=True)
        default_global = {}
        default_guild = {}
        defaults_user = {}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        self.config.register_user(**defaults_user)

    async def convert_seconds_to_str(ctx,seconds):
        dtime = seconds                      
        dtime_days,dtime = divmod(dtime,86400)
        dtime_hours,dtime = divmod(dtime,3600)
        dtime_minutes,dtime = divmod(dtime,60)

        return dtime_days, dtime_hours, dtime_minutes, dtime

    async def clash_embed(ctx, title=None, message=None, url=None, show_author=True, color=None, thumbnail=None, image=None):
        if not title:
            title = ""
        if not message:
            message = ""
        if color == "success":
            color = 0x00FF00
        elif color == "fail":
            color = 0xFF0000
        else:
            color = await ctx.embed_color()
        if url:
            embed = discord.Embed(title=title,url=url,description=message,color=color)
        else:
            embed = discord.Embed(title=title,description=message,color=color)
        if show_author:
            embed.set_author(name=f"{ctx.author.display_name}#{ctx.author.discriminator}",icon_url=ctx.author.avatar_url)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        if image:
            embed.set_image(url=image)
        embed.set_footer(text="AriX Alliance | Clash of Clans",icon_url="https://i.imgur.com/TZF5r54.png")
        return embed

    async def user_confirmation(self, ctx: commands.Context, cMsg, confirm_method=None) -> bool:
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

        def chk_reaction(r,u):
            if str(r.emoji) in confirmation_emotes and r.message.id == cMsg.id and u.id == ctx.author.id:
                return True
            else:
                return False

        if confirm_method in ['token','token_only']:
            confirm_token = "".join(random.choices((*ascii_letters, *digits), k=16))
            if confirm_method == 'token_only':
                token_msg = await ctx.send(f"```{confirm_token}```")
            else:
                token_msg = await ctx.send(content=f"{ctx.author.mention}, please confirm the above action by sending the token below as your next message. You have 60 seconds to confirm.```{confirm_token}```")
            try:
                reply_message = await ctx.bot.wait_for("message",timeout=60,check=response_check)
            except asyncio.TimeoutError:
                await token_msg.edit(content="Confirmation timed out. Please try again.")
                return False
            else:
                if reply_message.content.strip() == confirm_token:
                    await token_msg.edit(content="Confirmation successful.")
                    await reply_message.delete()
                    return True
                else:
                    await token_msg.edit(content="The response received was not valid. Please try again.")
                    return False
        else:
            for emoji in confirmation_emotes:
                await cMsg.add_reaction(emoji)
            try:
                reaction, user = await ctx.bot.wait_for("reaction_add",timeout=20,check=chk_reaction)
            except asyncio.TimeoutError:
                await ctx.send("Confirmation sequence timed out. Please try again.")
                await cMsg.remove_reaction('<:green_check:838461472324583465>',ctx.bot.user)
                await cMsg.remove_reaction('<:red_cross:838461484312428575>',ctx.bot.user)
                return False
            else:
                if str(reaction.emoji) == '<:green_check:838461472324583465>':
                    await cMsg.remove_reaction('<:green_check:838461472324583465>',ctx.bot.user)
                    await cMsg.remove_reaction('<:red_cross:838461484312428575>',ctx.bot.user)
                    return True
                else:
                    await ctx.send("Cancelling...")
                    await cMsg.remove_reaction('<:green_check:838461472324583465>',ctx.bot.user)
                    await cMsg.remove_reaction('<:red_cross:838461484312428575>',ctx.bot.user)
                    return False

    async def multiple_choice_select(self, ctx:commands.Context, sEmbed, selection_list:list, selection_text=None):
        #prepare embed from parent function - allows for greater customisability
        #selection_list should be in format [{'title':str, 'description':str},{'title':str, 'description':str}].

        selection_emojis = []

        if not selection_text:
            selection_text = "\u200b"

        #Build List
        sel_text = ''
        sel_number = 0
        for item in selection_list:
            #handle emojis

            custom_emoji = item.get('emoji',None)

            if custom_emoji:
                emoji = item['emoji']
            else:
                hex_str = hex(224 + (6 + sel_number))[2:]
                emoji = b"\\U0001f1a".replace(b"a", bytes(hex_str, "utf-8"))
                emoji = emoji.decode("unicode-escape")
            
            selection_emojis.append(emoji)

            if sel_number > 0:
                sel_text += "\n\n\u200b"
            if item['description']:
                sel_str = f"{emoji} **{item['title']}**\n{item['description']}"
            else:
                sel_str = f"{emoji} {item['title']}"
                
            sel_text += sel_str
            sel_number += 1

        sel_text += "\n\u200b"

        def chk_select(r,u):
            if str(r.emoji) in selection_emojis and r.message.id == menu_message.id and u.id == ctx.author.id:
                return True
            else:
                return False

        sEmbed.add_field(
            #name="Select an option from the menu below:",
            name=selection_text,
            value=sel_text,
            inline=False)

        menu_message = await ctx.send(embed=sEmbed)
        for emoji in selection_emojis:
            await menu_message.add_reaction(emoji)
        await menu_message.add_reaction('<:red_cross:838461484312428575>')
        try:
            reaction, user = await ctx.bot.wait_for("reaction_add",timeout=60,check=chk_select)
        except asyncio.TimeoutError:
            await ctx.send("Menu timed out.")
            for emoji in selection_emojis:
                await menu_message.remove_reaction(emoji,ctx.bot.user)
            return menu_message, None
        else:
            if str(reaction.emoji) == '<:red_cross:838461484312428575>':
                await ctx.send("Menu cancelled.")
                for emoji in selection_emojis:
                    await menu_message.remove_reaction(emoji,ctx.bot.user)
                return menu_message, None
            else:
                sel_index = selection_emojis.index(str(reaction.emoji))
                return menu_message, selection_list[sel_index]

    async def player_embed(self,ctx,player):
        if player.is_member:
            mStatus = f"***{self.arix_rank} of {self.home_clan.name}***\n\n"
        else:
            mStatus = ""

        if player.clan:
            clan_description = f"{player.role} of {player.clan.name}"
        else:
            clan_description = "No Clan"

        pEmbed = await clash_embed(
            ctx=ctx,
            title=f"{player.name} ({player.tag})",
            message=f"{mStatus}<:Exp:825654249475932170>{player.exp_level}\u3000<:Clan:825654825509322752> {clan_description}",
            url=f"https://www.clashofstats.com/players/{player.tag.replace('#','')}",
            thumbnail=player.league.icon.url)

        hero_description = ""
        if player.town_hall.level >= 7:
            hero_description = f"\n**Heroes**\n{emotes_army['Barbarian King']} {sum([h.level for h in player.heroes if h.name=='Barbarian King'])}"
        if player.town_hall.level >= 9:
            hero_description += f"\u3000{emotes_army['Archer Queen']} {sum([h.level for h in player.heroes if h.name=='Archer Queen'])}"
        if player.town_hall.level >= 11:
            hero_description += f"\u3000{emotes_army['Grand Warden']} {sum([h.level for h in player.heroes if h.name=='Grand Warden'])}"
        if player.town_hall.level >= 13:
            hero_description += f"\u3000{emotes_army['Royal Champion']} {sum([h.level for h in player.heroes if h.name=='Royal Champion'])}"

        troopStrength = f"<:TotalTroopStrength:827730290491129856> {player.troop_strength}"
        if player.town_hall.level >= 5:
            troopStrength += f"\n<:TotalSpellStrength:827730290294259793> {player.spell_strength}"                        
        if pObject.player.town_hall >= 7:
            troopStrength += f"\n<:TotalHeroStrength:827730291149635596> {player.hero_strength}"

        pEmbed.add_field(
            name="**Home Village**",
            value=f"{player.town_hall.emote} {player.town_hall.description}\u3000<:HomeTrophies:825589905651400704> {player.trophies}\u3000<:TotalStars:825756777844178944> {player.war_stars}"
                + f"{hero_description}"
                + "\n**Strength**"
                + f"\n{troopStrength}"
                + "\n\u200b",
                inline=False)

        return pEmbed

    async def player_summary(self,ctx,player):
        hero_description = ""
        if player.town_hall.level >= 7:
            hero_description = f"\n**Heroes**\n{emotes_army['Barbarian King']} {sum([h.level for h in player.heroes if h.name=='Barbarian King'])}"
        if player.town_hall.level >= 9:
            hero_description += f"\u3000{emotes_army['Archer Queen']} {sum([h.level for h in player.heroes if h.name=='Archer Queen'])}"
        if player.town_hall.level >= 11:
            hero_description += f"\u3000{emotes_army['Grand Warden']} {sum([h.level for h in player.heroes if h.name=='Grand Warden'])}"
        if player.town_hall.level >= 13:
            hero_description += f"\u3000{emotes_army['Royal Champion']} {sum([h.level for h in player.heroes if h.name=='Royal Champion'])}"

        title = f"{player.name} ({player.tag})"
        fieldStr = f"<:Exp:825654249475932170>{player.exp_level}\u3000{player.town_hall.emote} {player.town_hall.description}\u3000{hero_description}"

        return title,fieldStr

    async def get_welcome_embed(ctx,user):
        intro_embed = await self.clash_embed(ctx,
            title="Congratulations! You're an AriX Member!",
            message=f"Before going further, there are a few additional things you need to understand and do:"
                + f"\n\nThe **AriX Alliance** is made up of 4 active clans:\n- ArmyOf9YearOlds (AO9)\n- Phoenix Reborn (PR)\n- Project AriX (PA)\n- Assassins (AS)"
                + f"\n\nWe also have 3 event-only clans:\n- DawnOfPhoenix (DOP)\n- ArmyOf2YearOlds (AO2)\n- Don (DON)"
                + f"\n\nIn turn, AriX is also part of a larger alliance, the **Clash Without Limits Alliance (CWLA)**.\n\u200b")

        intro_embed.add_field(
            name="**About CWLA**",
            value=f"Through CWLA, our members are able to sign up for a specific league in the Clan War Leagues (CWL). During CWL week, you will be temporarily allocated a clan with which you can participate in CWL. "
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

    # if self.isMember:
    #     dtime = self.timestamp - self.arixLastUpdate                            
    #     dtime_days,dtime = divmod(dtime,86400)
    #     dtime_hours,dtime = divmod(dtime,3600)
    #     dtime_minutes,dtime = divmod(dtime,60)

    #     lastseen_text = ''
    #     if dtime_days > 0:
    #         lastseen_text += f"{int(dtime_days)} days "
    #     if dtime_hours > 0:
    #         lastseen_text += f"{int(dtime_hours)} hours "
    #     if dtime_minutes > 0:
    #         lastseen_text += f"{int(dtime_minutes)} mins "
    #     if lastseen_text == '':
    #         lastseen_text = "a few seconds "

    #     lootGold = numerize.numerize(self.arixLoot.gold_season,1)
    #     lootElixir = numerize.numerize(self.arixLoot.elixir_season,1)
    #     lootDarkElixir = numerize.numerize(self.arixLoot.darkelixir_season,1)

    #     if self.arixLoot.gold_lastupdate >= 2000000000:
    #         lootGold = "max"
    #     if self.arixLoot.elixir_lastupdate >= 2000000000:
    #         lootElixir = "max"
    #     if self.arixLoot.darkelixir_lastupdate >= 2000000000:
    #         lootDarkElixir = "max"

    #     clanCapitalGold = numerize.numerize(self.arixCapitalContribution.season,1)
    #     capitalGoldLooted = numerize.numerize(self.arixRaid_Resources,1)

    #     pEmbed.add_field(
    #         name=f"**Current Season Stats with AriX**",
    #         value=f":stopwatch: Last updated: {lastseen_text}ago"
    #             + f"\n<a:aa_AriX:1031773589231374407> {int(self.timeInHomeClan/86400)} day(s) spent in {self.homeClan.name}"
    #             + "\n**Donations**"
    #             + f"\n<:donated:825574412589858886> {self.arixDonations.sent_season:,}\u3000<:received:825574507045584916> {self.arixDonations.rcvd_season:,}"
    #             + "\n**Loot**"
    #             + f"\n<:gold:825613041198039130> {lootGold}\u3000<:elixir:825612858271596554> {lootElixir}\u3000<:darkelixir:825640568973033502> {lootDarkElixir}"
    #             + "\n**Clan Capital**"
    #             + f"\n<:CapitalGoldContributed:971012592057339954> {clanCapitalGold}\u3000<:CapitalRaids:1034032234572816384> {capitalGoldLooted}\u3000<:RaidMedals:983374303552753664> {self.arixRaid_Medals:,}"
    #             + "\n**War Performance**"
    #             + f"\n<:TotalWars:827845123596746773> {self.arixWar_Participated}\u3000<:TotalStars:825756777844178944> {self.arixWar_OffenseStars}\u3000<:Triple:1034033279411687434> {self.arixWar_Triples}\u3000<:MissedHits:825755234412396575> {self.arixWar_MissedAttacks}"
    #             + "\n*Use `;mywarlog` to view your War Log.*"
    #             + "\n\u200b",
    #         inline=False)
    # return pEmbed