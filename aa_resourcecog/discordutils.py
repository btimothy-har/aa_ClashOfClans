import discord
import random
import asyncio

from string import ascii_letters, digits

from .constants import confirmation_emotes, selection_emotes, emotes_army

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
        embed.set_author(name=f"{ctx.author.display_name}",icon_url=ctx.author.avatar_url)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text="AriX Alliance | Clash of Clans",icon_url="https://i.imgur.com/TZF5r54.png")
    return embed

async def eclipse_embed(ctx, title=None, message=None, url=None, color=None, thumbnail=None, image=None):
    if not title:
        title = ""
    if not message:
        message = ""
    if color == "success":
        color = 0x00FF00
    elif color == "fail":
        color = 0xFF0000
    else:
        color = 0xFFFFFF
    if url:
        embed = discord.Embed(title=title,url=url,description=message,color=color)
    else:
        embed = discord.Embed(title=title,description=message,color=color)
    embed.set_author(name=f"E.C.L.I.P.S.E.",icon_url="https://i.imgur.com/TZF5r54.png")
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text="AriX Alliance | Clash of Clans")
    return embed

async def user_confirmation(ctx, cMsg, confirm_method=None) -> bool:
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


async def multiple_choice_menu_generate_emoji(ctx,options):
    sel_list = []
    num = 0
    for i in options:
        if 'emoji' not in list(i.keys()):
            hex_str = hex(224 + (6 + num))[2:]
            emoji = b"\\U0001f1a".replace(b"a", bytes(hex_str, "utf-8"))
            emoji = emoji.decode("unicode-escape")

            i['emoji'] = emoji
        sel_list.append(i)
        num += 1

    return sel_list


async def multiple_choice_menu_select(ctx, smsg, sel_list, timeout=60):
    def chk_select(r,u):
        if str(r.emoji) in sel_emojis and r.message.id == smsg.id and u.id == ctx.author.id:
            return True
        else:
            return False

    sel_emojis = [i['emoji'] for i in sel_list]
    sel_emojis.append('<:red_cross:838461484312428575>')

    for e in sel_emojis:
        await smsg.add_reaction(e)

    try:
        reaction, user = await ctx.bot.wait_for("reaction_add",timeout=timeout,check=chk_select)
    except asyncio.TimeoutError:
        return None
    else:
        if str(reaction.emoji) == '<:red_cross:838461484312428575>':
            return None
        else:
            ms = [i for i in sel_list if i['emoji'] == str(reaction.emoji)]
            return ms[0]
