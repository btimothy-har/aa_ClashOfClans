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
    elif color:
        color = color
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
        for e in confirmation_emotes:
            try:
                emoji_id = int(''.join([str(i) for i in e if i.isdigit()]))
            except:
                pass
            else:
                e = ctx.bot.get_emoji(emoji_id)
                if not e:
                    e = await ctx.bot.fetch_emoji(emoji_id)

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
        try:
            emoji_id = int(''.join([str(i) for i in e if i.isdigit()]))
        except:
            pass
        else:
            e = ctx.bot.get_emoji(emoji_id)
            if not e:
                e = await ctx.bot.fetch_emoji(emoji_id)
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


async def paginate_embed(ctx,output,add_instructions=True):
    nav_options = []
    nav_str = ""
    paginate_state = True

    prev_dict = {
        'id': 'previous',
        'emoji': '<:to_previous:1041988094943035422>'
        }
    next_dict = {
        'id': 'next',
        'emoji': '<:to_next:1041988114308137010>'
        }

    if len(output) == 0:
        return

    if len(output) == 1:
        return await ctx.send(embed=output[0])

    if len(output) > 1:
        nav_options.append(prev_dict)
        nav_options.append(next_dict)

        nav_str += f"<:to_previous:1041988094943035422> Previous page"
        nav_str += f"\u3000<:to_next:1041988114308137010> Next page"

        for embed in output:
            embed.set_footer(text=f"(Pg {output.index(embed)+1} of {len(output)}) -- AriX Alliance | Clash of Clans",icon_url="https://i.imgur.com/TZF5r54.png")
            if add_instructions:
                embed.add_field(name="**Navigation**",value=nav_str,inline=False)

    browse_index = 0
    message = None

    while paginate_state:

        if browse_index < 0:
            browse_index = (len(output)-1)
        if browse_index > (len(output)-1):
            browse_index = 0

        if message:
            await message.edit(embed=output[browse_index])
        else:
            message = await ctx.send(embed=output[browse_index])

        await message.clear_reactions()
        selection = await multiple_choice_menu_select(ctx,message,nav_options,timeout=300)

        if selection:
            response = selection['id']

            if response == 'previous':
                browse_index -= 1

            if response == 'next':
                browse_index += 1
        else:
            response = None
            paginate_state = False

    try:
        await message.clear_reactions()
    except:
        pass
    return response
