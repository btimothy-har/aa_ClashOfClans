import discord
import random
import asyncio

from string import ascii_letters, digits

from .discordutils import eclipse_embed
from .eclipse_bases import eWarBase
from .file_functions import eclipse_base_handler
from .constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league

class EclipseSession():
    def __init__(self,ctx):
        self.state = True
        self.user = ctx.author
        self.channel = ctx.channel
        self.message = None

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

async def eclipse_menu_select(ctx, session, sel_list, timeout=60):
    def chk_select(r,u):
        if str(r.emoji) in sel_emojis and r.message.id == session.message.id and u.id == session.user.id:
            return True
        else:
            return False
    
    sel_emojis = [i['emoji'] for i in sel_list]
    sel_emojis.append('<:red_cross:838461484312428575>')

    for e in sel_emojis:
        await session.message.add_reaction(e)

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

async def eclipse_main_menu(ctx,session):
    menu_options = [
        {
            'id': 'personalvault',
            'title': f"{ctx.author.mention}'s E.C.L.I.P.S.E.",
            'description': "Your personal vault of Army and Base Links. Your E.C.L.I.P.S.E. session will be transferred to your DMs."
            },
        {
            'id': 'basevault',
            'title': "Browse the Base Vault",
            'description': f"We have bases covering TH9 {emotes_townhall[9]} to TH15 {emotes_townhall[15]}."
            },
        {
            'id': 'armyguides',
            'title': "Browse the War Army Guide",
            'description': f"We have a compilation of war armies and variations from TH9 {emotes_townhall[9]} to TH15 {emotes_townhall[15]}."
            },
        {
            'id': 'strategy',
            'title': "Browse the Strategy Guide",
            'description': f"We have a compilation of strategies and tactics in Clash of Clans applicable to all Townhall levels."
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
        name="**```To get started, select an option below.```**",
        value=f"\u200b\n{select_str}\n\n*You may close your E.C.L.I.P.S.E. Session at any time by clicking on <:red_cross:838461484312428575>.*\n\u200b",
        inline=False
        )

    if session.message:
        await session.message.edit(content=session.user.mention,embed=menu_embed)
    else:
        session.message = await ctx.send(content=session.user.mention,embed=menu_embed)

    await session.message.clear_reactions()
    selection = await eclipse_menu_select(ctx,session,menu_options)

    if selection:
        return selection['id']
    else:
        return None


async def eclipse_base_vault(ctx,session,no_base=None):
    townhall_range = range(9,16)
    th_str = ""
    
    menu_options = []
    for n in townhall_range:
        n_dict = {
            'id':n,
            'emoji': f"{emotes_townhall[n]}",
            'title':f"TH {n}",
            }
        menu_options.append(n_dict)

        th_str += f"{n_dict['emoji']} {n_dict['title']}"
        if n < max(townhall_range):
            th_str += f"\n\n"

    back_dict = {
        'id': 'menu',
        'emoji': "<:backwards:1041976602420060240>",
        'title': "",
        }
    menu_options.append(back_dict)

    if no_base:
        base_menu_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"**We don't have any bases currently for Townhall {no_base}.**\n\nPlease select a Townhall level to browse bases for.\n\n{th_str}\n\n<:backwards:1041976602420060240> Back to the Main Menu.\n\u200b")
    else:
        base_menu_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"Please select a Townhall level to browse bases for.\n\n{th_str}\n\n<:backwards:1041976602420060240> Back to the Main Menu.\n\u200b")

    if session.message:
        await session.message.edit(content=session.user.mention,embed=base_menu_embed)
    else:
        session.message = await ctx.send(content=session.user.mention,embed=base_menu_embed)

    await session.message.clear_reactions()
    selection = await eclipse_menu_select(ctx,session,menu_options)

    if selection:
        return selection['id']
    else:
        return None


async def get_eclipse_bases(ctx,session,townhall_level):
    base_th = townhall_level
    bases = await eclipse_base_handler(ctx,base_th)

    bases = [eWarBase.from_json(ctx,b) for b in bases]

    categories = {}
    for b in bases:
        if b.base_type not in list(categories.keys()):
            categories[b.base_type] = 0
        categories[b.base_type] += 1

    if len(bases) == 0:
        return 'basevaultnone'

    if len(list(categories.keys())) == 1:
        show_bases = bases
        response = await show_eclipse_bases(ctx,session,show_bases)

        if response:
            return 'basevault'
        else:
            return None

    else:
        category_options = []
        category_str = ""
        for category, qty in categories.items():
            category_dict = {
                'id': category,
                'title': f"**{category}**: {qty} bases found."
                }
            category_options.append(category_dict)

        category_options = await eclipse_menu_emoji(ctx,category_options)
        
        for i in category_options:
            category_str += f"{i['emoji']} {i['title']}"
            if category_options.index(i) < (len(category_options)-1):
            category_str += f"\n\n"

        base_category_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"I found the following base types for {emotes_townhall[base_th]}Townhall {base_th}. Select a category to view."
                + f"\n\n{category_str}\n\u200b")

        if session.message:
            await session.message.edit(content=session.user.mention,embed=base_category_embed)
        else:
            session.message = await ctx.send(content=session.user.mention,embed=base_category_embed)

        await session.message.clear_reactions()
        
        selection = await eclipse_menu_select(ctx,session,category_options)

        show_bases = [b for b in bases if b.base_type==selection['id']]

        response = await show_eclipse_bases(ctx,session,show_bases)

        if response:
            return 'basevaultselect'
        else:
            return None

    return None


async def show_eclipse_bases(ctx,session,bases):
    browse_bases = True
    response = None

    base_navigation = [
        {
            'id': 'back',
            'emoji': '<:backwards:1041976602420060240>'
            },
        {
            'id': 'previous',
            'emoji': '<:to_previous:1041988094943035422>'
            },
        {
            'id': 'next',
            'emoji': '<:to_next:1041988114308137010>'
            },
        {
            'save': 'save',
            'emoji': '<:download:1040800550373044304>'
            }
        ]

    i = 0
    while browse_bases:
        if i < 0:
            i = (len(bases) - 1)
        if i > (len(bases) - 1):
            i = 0

        base_embed, image = await bases[i].base_embed(ctx)
        base_embed.set_image(url="attachment://image.png")

        base_embed.add_field(
            name="Navigation",
            value="<:backwards:1041976602420060240> to stop looking at bases (you will return to your previous menu)."
                + "\n<:to_previous:1041988094943035422> for the previous base in the list."
                + "\n<:to_next:1041988114308137010> for the next base in the list."
                + "\n<:download:1040800550373044304> to save this base to your personal vault.")
        
        #await session.message.clear_reactions()

        await session.message.delete()
        new_message = await session.channel.send(content=session.user.mention,embed=base_embed,file=image)
        session.message = new_message

        selection = await eclipse_menu_select(ctx,session,base_navigation,timeout=300)

        if selection:
            if selection['id'] == 'next':
                i += 1
            elif selection['id'] == 'previous':
                i -= 1
            elif selection['id'] == 'save':
                i = i
                #add save code here
            else:
                browse_bases = False
        else:
            browse_bases = False
    
    await session.message.delete()
    session.message = None

    if selection:
        response = True
    
    return response



        

