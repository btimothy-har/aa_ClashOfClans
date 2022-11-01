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

from .constants import confirmation_emotes
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
                reply_message = await ctx.bot.wait_for("message",timeout=60,check=chk_token)
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

    async def multiple_choice_select(self, ctx:commands.Context, sEmbed, selection_list:list):
        #prepare embed from parent function - allows for greater customisability
        #selection_list should be in format [{'title':str, 'description':str},{'title':str, 'description':str}].

        #Build List
        sel_text = ''
        sel_number = 0
        reaction_list = []
        for item in selection_list:
            if item['description']:
                sel_str = f"{selection_emotes[sel_number]} **{item['title']}**\n{item['description']}"
            else:
                sel_str = f"{selection_emotes[sel_number]} {item['title']}"
            reaction_list.append(selection_emotes[sel_number])
            sel_text += sel_str + "\n\u200b"
            sel_number += 1

        def chk_select(r,u):
            if str(r.emoji) in reaction_list and r.message.id == menu_message.id and u.id == ctx.author.id:
                return True
            else:
                return False

        sEmbed.add_field(
            name="Select an option from the menu below:",
            value=sel_text,
            inline=False)

        menu_message = await ctx.send(embed=sEmbed)
        for emoji in reaction_list:
            await menu_message.add_reaction(emoji)
        try:
            reaction, user = await ctx.bot.wait_for("reaction_add",timeout=60,check=chk_select)
        except asyncio.TimeoutError:
            await ctx.send("Confirmation sequence timed out. Please try again.")
            for emoji in reaction_list:
                await menu_message.remove_reaction(emoji,ctx.bot.user)
            return None
        else:
            sel_index = reaction_list.index(str(reaction.emoji))
            for emoji in reaction_list:
                await menu_message.remove_reaction(emoji,ctx.bot.user)
            return selection_list[sel_index]

    async def get_current_season():
        helsinkiTz = pytz.timezone("Europe/Helsinki")
        current_season = f"{datetime.now(helsinkiTz).month}-{datetime.now(helsinkiTz).year}"
        return current_season

    async def get_current_alliance(self):
        with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
            file_json = json.load(file)
        clansList = list(file_json['clans'].keys())
        memberList = list(file_json['members'].keys())
        return clansList,memberList

    async def season_file_handler(ctx,season):
        is_new_season = False
        current_season = None
        new_season = None
        with open(ctx.bot.clash_dir_path+'/seasons.json','w+') as file:
            s_json = json.load(file)
            current_season = s_json['current']
            if season != current_season:
                is_new_season = True
                new_season = season
                
                s_json['tracked'].append(currrent_season)
                s_json['current'] = new_season
                json.dump(s_json,file,indent=2)

        if is_new_season:
            clans, members = await get_current_alliance()

            new_path = ctx.bot.clash_dir_path+'/'+new_season
            os.makedirs(new_path)

            shutil.copy2(ctx.bot.clash_dir_path+'/members.json',new_path)
            with open(ctx.bot.clash_dir_path+'/members.json','w+') as file:
                json.dump({},file,indent=2)

            with open(ctx.bot.clash_dir_path+'/warlog.json','w+') as file:
                w_json = json.load(file)
                for key,item in w_json.items():
                    if item['state'] != "warEnded":
                        del w_json[key]
                new_w = {}
                for c in clans:
                    new_w[c] = {}
                json.dump(new_w,file,indent=2)
                file.truncate()
            with open(new_path+'/warlog.json','w+') as file:
                json.dump(w_json,file,indent=2)
                file.truncate()

            with open(ctx.bot.clash_dir_path+'/capitalraid.json','w+') as file:
                r_json = json.load(file)
                for key,item in r_json.items():
                    if item['state'] != "ended":
                        del r_json[key]
                new_r = {}
                for c in clans:
                    new_r[c] = {}
                json.dump(new_r,file,indent=2)
                file.truncate()
            with open(new_path+'/capitalraid.json','w+') as file:
                json.dump(r_json,file,indent=2)
                file.truncate()

        return is_new_season, current_season, new_season

    async def alliance_file_handler(ctx,entry_type,tag,new_data=None):
        with open(ctx.bot.clash_dir_path+'/alliance.json','w+') as file:
            file_json = json.load(file)
                if new_data:
                    file_json[entry_type][tag] = new_data
                    json.dump(file_json,file,indent=2)
                    file.truncate()
        try:
            rJson = file_json[entry_type][tag]
        except KeyError:
            rJson = None
        return rJson

    async def data_file_handler(ctx,file:str,tag:str,new_data=None,season=None):
        if file not in ['members','warlog','capitalraid']:
            return None

        file_name = {
            'members':'members.json',
            'warlog':'warlog.json',
            'capitalraid':'capitalraid.json',
            }

        file_path = self.cDirPath + file_name[file]

        with open(file_path,'w+') as file:
            file_json = json.load(file)
            if new_data:
                file_json[tag] = new_data
                json.dump(file_json,file,indent=2)
                file.truncate()
        try:
            response_json = file_json[tag]
        except KeyError:
            response_json = None
        return response_json