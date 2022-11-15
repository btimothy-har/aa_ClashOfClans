import discord
import random
import asyncio

from string import ascii_letters, digits

from .constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league

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

async def eclipse_menu_emoji(ctx,options):
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

async def eclipse_menu_select(ctx, message, sel_list):
    def chk_select(r,u):
        if str(r.emoji) in sel_emojis and r.message.id == message.id and u.id == ctx.author.id:
            return True
        else:
            return False
    
    sel_emojis = [i['emoji'] for i in sel_list]
    sel_emojis.append('<:red_cross:838461484312428575>')

    for e in sel_emojis:
        await message.add_reaction(e)

    try:
        reaction, user = await ctx.bot.wait_for("reaction_add",timeout=60,check=chk_select)
    except asyncio.TimeoutError:
        return None
    else:
        if str(reaction.emoji) == '<:red_cross:838461484312428575>':
            return None
        else:
            ms = [i for i in sel_list if i['emoji'] == reaction.emoji]
            return ms[0]

async def eclipse_main_menu(ctx):
    menu_options = [
        {
            'id': 'personalbase',
            'title': f"{ctx.author.mention}'s Base Vault",
            'description': "Your personal base vault. The menu will continue in DMs."
            },
        {
            'id': 'personalarmy',
            'title': f"{ctx.author.mention}'s War Armies",
            'description': "Your personal army link archive."
            },
        {
            'id': 'basevault',
            'title': "E.C.L.I.P.S.E. Base Vault",
            'description': f"AriX's Members-only exclusive Base Vault. Covers TH9 {emotes_townhall[9]} to TH15 {emotes_townhall[15]}."
            },
        {
            'id': 'armyguides',
            'title': "E.C.L.I.P.S.E. Army Guides",
            'description': f"AriX's Members-only archive of War Bases. Covers TH9 {emotes_townhall[9]} to TH15 {emotes_townhall[15]}."
            },
        ]

    menu_options = await eclipse_menu_emoji(ctx,menu_options)

    menu_embed = await eclipse_embed(ctx,
        title="**Welcome to E.C.L.I.P.S.E.!**",
        message=f"\nAriX's ***E**xtraordinarily **C**ool **L**ooking **I**nteractive & **P**rofessional **S**earch **E**ngine*."
            + f"\n\nWith E.C.L.I.P.S.E., you'll find an infinite source of Clash data, ranging from War Bases to Army Compositions and Strategies."
            + f"In addition, curate your own personal vault of information for your personal reference.\n\u200b")

    select_str = ""

    for i in menu_options:
        select_str += f"{i['emoji']} **{i['title']}**"
        select_str += f"\n{i['description']}"

        if menu_options.index(i) < (len(menu_options)-1):
            select_str += f"\n\n"

    menu_embed.add_field(
        name="To get started, select an option below.",
        value=f"\u200b\n{select_str}\n\u200b",
        inline=False
        )

    main_menu = await ctx.send(content=ctx.author.mention,embed=menu_embed)

    selection = await eclipse_menu_select(ctx,main_menu,menu_options)

    if selection:
        return main_menu, selection['id']
    else:
        return main_menu, None


async def eclipse_base_vault(ctx,session,user=None):
    townhall_range = range(9,16)
    
    menu_options = []
    for n in townhall_range:
        n_dict = {
            'id':n,
            'emoji': f"{emotes_townhall[n]}",
            'title':f"Townhall {n}",
            }
        menu_options.append(n_dict)

    base_menu_embed = await eclipse_embed(ctx,
        title="**E.C.L.I.P.S.E. Base Vault**",
        message=f"Please select a Townhall level to browse bases for.")

    await session.edit(content=ctx.author.mention,embed=base_menu_embed)

    selection = await eclipse_menu_select(ctx,session,menu_options)

    if selection:
        return selection['id']
    else:
        return None



