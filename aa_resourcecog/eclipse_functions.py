import discord
import random
import asyncio

from string import ascii_letters, digits

from .discordutils import eclipse_embed
from .eclipse_classes import EclipseSession, eWarBase
from .file_functions import eclipse_base_handler
from .constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league

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
    menu_options = []

    personal_vault_option = {
            'id': 'personalvault',
            'title': f"Visit your Personal Base Vault",
            'description': "Your personal base vault. This will open E.C.L.I.P.S.E. in your DMs."
            }
    base_vault_option = {
            'id': 'basevault',
            'title': "Browse the Base Vault",
            'description': f"We have bases covering TH9 {emotes_townhall[9]} to TH15 {emotes_townhall[15]}."
            }
    base_army_guides = {
            'id': 'armyguides',
            'title': "Browse the War Army Guide",
            'description': f"We have a compilation of war armies and variations from TH9 {emotes_townhall[9]} to TH15 {emotes_townhall[15]}."
            }
    strategy_guides = {
            'id': 'strategy',
            'title': "Browse the Strategy Guide",
            'description': f"We have a compilation of strategies and tactics in Clash of Clans applicable to all Townhall levels."
            }
    army_analyzer = {
            'id': 'armyanalyze',
            'title': "Army Analysis",
            'description': f"Compare up to 2 army compositions side-by-side."
            }

    menu_options.append(personal_vault_option)
    menu_options.append(base_vault_option)
    #menu_options.append(base_army_guides)
    #menu_options.append(strategy_guides)
    menu_options.append(army_analyzer)

    menu_options = await eclipse_menu_emoji(ctx,menu_options)

    menu_embed = await eclipse_embed(ctx,
        title="**Welcome to E.C.L.I.P.S.E.!**",
        message=f"\nAriX's ***E**xtraordinarily **C**ool **L**ooking **I**nteractive & **P**rofessional **S**earch **E**ngine*."
            + f"\n\nWith E.C.L.I.P.S.E., you'll find an infinite source of Clash data, ranging from War Bases to Army Compositions and Strategies. "
            + f"In addition, curate your own personal vault of information for your personal reference.\n\u200b")

    select_str = ""

    for i in menu_options:
        select_str += f"{i['emoji']} **{i['title']}**"
        select_str += f"\n{i['description']}"

        if menu_options.index(i) < (len(menu_options)-1):
            select_str += f"\n\n"

    menu_embed.add_field(
        name="**```To get started, select an option below.```**",
        value=f"\u200b\n{select_str}\n\n*Close your E.C.L.I.P.S.E. Session at any time by clicking on <:red_cross:838461484312428575>.*\n\u200b",
        inline=False
        )

    if session.message:
        await session.message.edit(content=session.user.mention,embed=menu_embed)
    else:
        session.message = await ctx.send(content=session.user.mention,embed=menu_embed)

    await session.message.clear_reactions()
    selection = await eclipse_menu_select(ctx,session,menu_options,timeout=180)

    if selection:
        return selection['id']
    else:
        return None


async def eclipse_base_vault(ctx,session,no_base=None):
    townhall_range = range(9,16)
    th_str = ""
    
    menu_options = []
    back_dict = {
        'id': 'menu',
        'emoji': "<:backwards:1041976602420060240>",
        'title': "",
        }
    menu_options.append(back_dict)

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

    if no_base:
        base_menu_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"**We don't have any bases currently for Townhall {no_base}.**\n\nPlease select a Townhall level to browse bases for.\n\n{th_str}\n\n<:backwards:1041976602420060240> Back to the Main Menu.\n\u200b")
    else:
        base_menu_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"Please select a Townhall level to browse bases for.\n\n{th_str}\n\n<:backwards:1041976602420060240> Back to the Main Menu\n\u200b")

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

    if len(list(categories.keys())) == 1 or len(bases) < 11:
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
                'title': f"**{category}** -- {qty} base(s) found"
                }
            category_options.append(category_dict)

        category_select = []
        back_dict = {
            'id': 'back',
            'emoji': '<:backwards:1041976602420060240>',
            'title': 'Back to Townhall selection'
            }
        category_select.append(back_dict)

        category_select += await eclipse_menu_emoji(ctx,category_options)
        
        for i in category_select:
            if i['id'] != 'back':
                category_str += f"{i['emoji']} {i['title']}"
                if category_select.index(i) < (len(category_select)-1):
                    category_str += f"\n\n"

        base_category_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"I found the following base types for **{emotes_townhall[base_th]} Townhall {base_th}**. Select a category to view."
                + f"\n\n{category_str}\n\n<:backwards:1041976602420060240> Back to Townhall selection\n\u200b")

        if session.message:
            await session.message.edit(content=session.user.mention,embed=base_category_embed)
        else:
            session.message = await ctx.send(content=session.user.mention,embed=base_category_embed)
        await session.message.clear_reactions()
        selection = await eclipse_menu_select(ctx,session,category_select)

        if not selection:
            return None

        if selection['id'] == 'back':
            return 'basevault'
        
        show_bases = [b for b in bases if b.base_type==selection['id']]

        response = await show_eclipse_bases(ctx,session,show_bases)

        if response:
            return 'basevaultselect'
        else:
            return None

    return None


async def show_eclipse_bases(ctx,session,bases):
    browse_bases = True
    display_bases = bases
    response = None

    base_navigation = [
        {
            'id': 'back',
            'emoji': '<:backwards:1041976602420060240>'
            },
        {
            'save': 'save',
            'emoji': '<:download:1040800550373044304>'
            }
        ]

    if len(bases) > 1:
        prev_dict = {
            'id': 'previous',
            'emoji': '<:to_previous:1041988094943035422>'
            }
        base_navigation.append(prev_dict)
        next_dict = {
            'id': 'next',
            'emoji': '<:to_next:1041988114308137010>'
            }
        base_navigation.append(next_dict)

    i = 0
    while browse_bases:
        display_bases = [b for b in bases if len(b.claims)< 6 or session.user.id in b.claims]
        if i < 0:
            i = (len(display_bases) - 1)
        if i > (len(display_bases) - 1):
            i = 0

        base_embed, image = await display_bases[i].base_embed(ctx)

        dump_channel = ctx.bot.get_channel(1042064532480217130)
        dump_message = await dump_channel.send(content=f"{session.user.name}@{session.channel.name}",file=image)
        image_attachment = dump_message.attachments[0]
        
        base_embed.set_image(url=image_attachment.url)
        base_embed.set_footer(text=f"(Displaying base {i+1} of {len(display_bases)}) -- AriX Alliance | Clash of Clans")

        if session.user.id in display_bases[i].claims and session.guild:
            base_embed.add_field(
                name="Base Link",
                value="You have added this base to your Vault. To get the Base Link, visit your Personal Vault from the main menu.",
                inline=False)
        elif session.user.id in display_bases[i].claims and not session.guild:
            base_embed.add_field(
                name="Base Link",
                value=f"[Click here to open in-game.]({display_bases[i].base_link})",
                inline=False)
        else:
            base_embed.add_field(
                name="Get this Base",
                value="Get the link to this base by clicking on <:download:1040800550373044304>."
                    + f"\n\n*You will always be able to access your saved bases from your personal vault.*",
                inline=False)

        if len(bases) > 1:
            base_embed.add_field(
                name="Navigation",
                value="<:backwards:1041976602420060240> back to the previous menu"
                    + "\n<:to_previous:1041988094943035422> for the previous base"
                    + "\n<:to_next:1041988114308137010> for the next base",
                inline=False)
        else:
            base_embed.add_field(
                name="Navigation",
                value="<:backwards:1041976602420060240> back to the previous menu",
            inline=False)
        
        if not session.guild:
            await session.message.delete()
            session.message = await session.channel.send(content=session.user.mention,embed=base_embed)
        else:
            await session.message.edit(content=session.user.mention,embed=base_embed)
            await session.message.clear_reactions()

        selection = await eclipse_menu_select(ctx,session,base_navigation,timeout=300)

        await dump_message.delete()

        if selection:
            if selection['id'] == 'next':
                i += 1
            elif selection['id'] == 'previous':
                i -= 1
            elif selection['id'] == 'save':
                display_bases[i].claims.append(session.user.id)
                async with ctx.bot.async_eclipse_lock:
                    with ctx.bot.clash_eclipse_lock.write_lock():
                        await bases[i].save_to_json()
                i = i
            else:
                browse_bases = False
        else:
            browse_bases = False

    if selection:
        response = True
    
    return response


async def eclipse_personal_vault(ctx,session):
    session.channel = ctx.author
    session.guild = None
    await session.message.delete()
    session.message = None

    menu_options = []

    war_base_option = {
        'id': 'mybases',
        'title': f"My War Bases",
        'description': "Bases saved from our Base Vault. You can save up to a maximum of **3** bases per Townhall level."
        }
    armies_option = {
        'id': 'myarmies',
        'title': f"My Army Compositions",
        'description': "Your personal army compositions saved on E.C.L.I.P.S.E. ."
        }

    menu_options.append(war_base_option)
    menu_options.append(armies_option)

    menu_options = await eclipse_menu_emoji(ctx,menu_options)

    menu_embed = await eclipse_embed(ctx,
        title=f"{session.user.display_name}'s Personal Vault",
        message=f"\nWelcome to your personal E.C.L.I.P.S.E. Vault."
            + f"\n\nHere, you can access any of the War Bases that you've saved from the member's Vault. "
            + f"In addition, E.C.L.I.P.S.E. also offers a personal Army Composition Database for your use."
            + f"\n\n**All data saved in your E.C.L.I.P.S.E. Vault is only accessible by you.**\n\u200b")

    select_str = ""
    for i in menu_options:
        select_str += f"{i['emoji']} **{i['title']}**"
        select_str += f"\n{i['description']}"

        if menu_options.index(i) < (len(menu_options)-1):
            select_str += f"\n\n"

    menu_embed.add_field(
        name="**```To get started, select an option below.```**",
        value=f"\u200b\n{select_str}\n\n**To go back to E.C.L.I.P.S.E. Home Screen, end this session and restart from the AriX Server.**\n\u200b",
        inline=False
        )

    if session.message:
        await session.message.edit(content=session.user.mention,embed=menu_embed)
    else:
        session.message = await session.channel.send(content=session.user.mention,embed=menu_embed)
    selection = await eclipse_menu_select(ctx,session,menu_options)

    if selection:
        return selection['id']
    else:
        return None


async def eclipse_personal_bases(ctx,session):
    session.channel = ctx.author
    session.guild = None
    await session.message.delete()
    session.message = None

    menu_options = []
    #back_dict = {
    #    'id': 'back',
    #    'emoji': '<:backwards:1041976602420060240>',
    #    'title': 'Back to Personal Vault menu'
    #    }
    #menu_options.append(back_dict)
    
    bases = await eclipse_base_handler(ctx)
    user_bases = [eWarBase.from_json(ctx,b) for b in bases if session.user.id in b['claims']]

    vault_intro = f"This is where your saved bases will be stored, with base links made available. You can save up to a maximum of **3** bases per Townhall level."

    if len(user_bases) > 0:
        base_count = {}
        for b in user_bases:
            if b.town_hall not in list(base_count.keys()):
                base_count[b.town_hall] == 0
            base_count[b.town_hall] += 1

        townhall_levels = sorted(list(base_count.keys()),reverse=True)

        for th in townhall_levels:
            n_dict = {
                'id':th,
                'emoji': f"{emotes_townhall[th]}",
                'title':f"**TH {th}** -- {base_count[th]} bases",
                }
            menu_options.append(n_dict)

            th_str += f"{n_dict['emoji']} {n_dict['title']}"
            if th < max(townhall_levels):
                th_str += f"\n\n"

        base_select_embed = await eclipse_embed(ctx,
            title="**Welcome to your Personal Base Vault**",
            message=f"{vault_intro}"
                + f"\n\nI found a total of {len(user_bases)} in your personal vault.\n\u200b")

        base_select_embed.add_field(
            name="Select a Townhall level below to view your bases.",
            value=f"\n{th_str}",
            inline=False)

    else:
        base_select_embed = await eclipse_embed(ctx,
            title="**Welcome to your Personal Base Vault**",
            message=f"{vault_intro}"
                + f"\n\n**You don't have any bases in your personal vault.** Start by saving some bases from our Members' Vault."
            #    + f"\n\n<:backwards:1041976602420060240> to return to your Personal Vault."
                + f"\n<:red_cross:838461484312428575> to close this E.C.L.I.P.S.E. session.")

    if session.message:
        await session.message.edit(content=session.user.mention,embed=base_select_embed)
    else:
        session.message = await session.channel.send(content=session.user.mention,embed=base_select_embed)
    selection = await eclipse_menu_select(ctx,session,menu_options)

    if not selection:
        return None

    if selection['id'] == 'back':
        return 'personalvault'
        
    show_bases = [b for b in user_bases if b.town_hall==selection['id']]
    response = await show_eclipse_bases(ctx,session,show_bases)

    if response:
        return 'mybases'
    else:
        return None