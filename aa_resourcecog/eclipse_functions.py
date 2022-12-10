import discord
import random
import asyncio
import urllib

from string import ascii_letters, digits
from tabulate import tabulate

from redbot.core.utils.chat_formatting import box, humanize_list, humanize_number, humanize_timedelta, pagify

from .discordutils import eclipse_embed, multiple_choice_menu_generate_emoji, multiple_choice_menu_select
from .eclipse_classes import EclipseSession, eWarBase, eWarArmy
from .file_functions import eclipse_base_handler
from .constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league


async def eclipse_multiple_choice_select(ctx, session, sel_list, timeout=60, refresh_rxn=True):
    def chk_select(r,u):
        if str(r.emoji) in sel_emojis and r.message.id == session.message.id and u.id == session.user.id:
            return True
        else:
            return False

    sel_emojis = [i['emoji'] for i in sel_list]
    sel_emojis.append('<:red_cross:838461484312428575>')

    if refresh_rxn:
        for e in sel_emojis:
            try:
                get_id = e.split(':')[-1]
                emoji_id = int(''.join([str(i) for i in get_id if i.isdigit()]))
                e = ctx.bot.get_emoji(emoji_id)
            except:
                pass
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
        'description': "Bases saved from our AriX Base Vault will appear in your personal vault for you to refer in future.\nNote: This will open E.C.L.I.P.S.E. in your DMs."
        }
    base_vault_option = {
        'id': 'basevault',
        'title': "Browse the AriX Base Vault",
        'description': f"Get a new OP defense with our base collection from TH9 {emotes_townhall[9]} to TH15 {emotes_townhall[15]}."
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
        'description': f"Compare up to 3 army compositions side-by-side."
        }
    troop_encyclopedia = {
        'id': 'troopencyclopedia',
        'title': "Troop Encyclopedia",
        'description': f"In-game stats for all Troops, Spells, Heroes for all levels."
        }

    menu_options.append(army_analyzer)

    if ctx.bot.base_channel:
        if ctx.channel == ctx.bot.base_channel:
            menu_options.append(base_vault_option)

            menu_embed = await eclipse_embed(ctx,
                title="**Welcome to E.C.L.I.P.S.E.!**",
                message=f"\nAriX's ***E**xtraordinarily **C**ool **L**ooking **I**nteractive & **P**rofessional **S**earch **E**ngine*."
                    + f"\n\nWith E.C.L.I.P.S.E., you'll find an infinite source of Clash data, alongside exclusive AriX-only tools.\n\u200b")

        else:
            menu_embed = await eclipse_embed(ctx,
                title="**Welcome to E.C.L.I.P.S.E.!**",
                message=f"\nAriX's ***E**xtraordinarily **C**ool **L**ooking **I**nteractive & **P**rofessional **S**earch **E**ngine*."
                    + f"\n\nWith E.C.L.I.P.S.E., you'll find an infinite source of Clash data, alongside exclusive AriX-only tools."
                    + f"\n\n**To access the E.C.L.I.P.S.E. Base Vault, run `/eclipse` in the `{ctx.bot.base_channel.name}` channel (<#{ctx.bot.base_channel.id}>).** To get access to this channel, you must be a member for __at least 2 weeks__. If you meet this criteria, please contact a <@&733023831366697080>.\n\u200b")

    else:
        menu_embed = await eclipse_embed(ctx,
            title="**Welcome to E.C.L.I.P.S.E.!**",
            message=f"\nAriX's ***E**xtraordinarily **C**ool **L**ooking **I**nteractive & **P**rofessional **S**earch **E**ngine*."
                + f"\n\nWith E.C.L.I.P.S.E., you'll find an infinite source of Clash data, alongside exclusive AriX-only tools.\n\u200b")

    #menu_options.append(base_army_guides)
    #menu_options.append(strategy_guides)

    menu_options.append(personal_vault_option)

    menu_options = await multiple_choice_menu_generate_emoji(ctx,menu_options)



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
    selection = await eclipse_multiple_choice_select(ctx,session,menu_options,timeout=180)

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

    base_vault_intro = (f"Welcome to the **E.C.L.I.P.S.E. Base Vault**. "
        + f"Here in the Base Vault, we have a curated collection of bases ranging from TH9 {emotes_townhall[9]} to TH15 {emotes_townhall[15]}. "
        + f"\n\nThese are bases exclusively reserved for AriX Members. To ensure they remain fresh, **DO NOT SHARE ANY BASE LINKS WITH ANYONE, INCLUDING FELLOW MEMBERS**."
        + f"\n\n**It is your responsibility to ensure that no one else in Clan Wars are using the same base as you.**"
        + f"\n\n**__Base Claiming__**"
        + f"\n> - To get a Base Link, you must first claim a base. Claimed bases are added to your personal vault."
        + f"\n> - You may remove your claims from your vault."
        + f"\n> - Base Claims are public and other members will be able to see who has claimed a base."
        + f"\n> - There are no limits to claims."
        )

    if no_base:
        base_menu_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"**We don't have any bases currently for Townhall {no_base}.**\n\n{base_vault_intro}\n\u200b")
    else:
        base_menu_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"{base_vault_intro}\n\u200b")
    
    base_menu_embed.add_field(
        name="Please select a Townhall level to browse bases.",
        value=f"\n\u200b{th_str}\n\n<:backwards:1041976602420060240> Back to the Main Menu"
            + f"\n\n*The Base Vault is supported by our exclusive base building partner, <:RHBB:1041627382018211900> **RH Base Building***.\n\u200b")

    if session.message:
        await session.message.edit(content=session.user.mention,embed=base_menu_embed)
    else:
        session.message = await ctx.send(content=session.user.mention,embed=base_menu_embed)

    await session.message.clear_reactions()
    selection = await eclipse_multiple_choice_select(ctx,session,menu_options)

    if selection:
        return selection['id']
    else:
        return None

async def eclipse_army_analyzer(ctx,session):
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

    army_analyzer_embed = await eclipse_embed(ctx,
        title="**E.C.L.I.P.S.E. Army Analyzer**",
        message=f"This unique analysis tool allows you to compare up to **three (3)** army compositions next to each other. "
            + f"Troops statistics are compared at the max level for the selected townhall. "
            + f"\n\n*Note: If you are on a mobile device, the Army Analyzer works best with **2** armies.*"
            + f"\n\nThe following stats are compared by E.C.L.I.P.S.E.:"
            + f"\n > 1) Hitpoints (Total, Average)"
            + f"\n > 2) Damage per Second (Min, Max, Average)"
            + f"\n > 3) Movement Speed (Min, Max, Average)"
            + f"\n > 4) Training Time (Total)"
            + f"\n\n**Healers, (Super) Wall Breakers, Spells and Siege Machines will always be excluded from statistics.**"
            + "\n\u200b")

    army_analyzer_embed.add_field(
        name="**Select a Townhall level to get started.**",
        value=f"\n\u200b{th_str}\n\n<:backwards:1041976602420060240> Back to the Main Menu",
        inline=False)

    if session.message:
        await session.message.edit(content=session.user.mention,embed=army_analyzer_embed)
    else:
        session.message = await ctx.send(content=session.user.mention,embed=army_analyzer_embed)

    await session.message.clear_reactions()
    selection = await eclipse_multiple_choice_select(ctx,session,menu_options)

    if selection:
        return selection['id']
    else:
        return None


async def eclipse_army_analyzer_main(ctx,session,town_hall):

    def armylink_check(m):
        msg_check = False
        if m.author.id == session.user.id and m.channel.id == session.channel.id:
            if m.content.lower() == 'back':
                msg_check = True
            elif m.content.lower() == 'exit':
                msg_check = True
            elif m.content.lower() == 'stop':
                msg_check = True
            else:
                link = m.content
                try:
                    link_parse = urllib.parse.urlparse(link)
                    link_action = urllib.parse.parse_qs(link_parse.query)['action'][0]
                except:
                    pass
                else:
                    if link_parse.netloc == "link.clashofclans.com" and link_action == "CopyArmy":
                        msg_check = True
        return msg_check

    army_links_num = 0
    army_compare = []

    get_army = True
    while get_army:
        army_links_num += 1
        army_analysis_embed = await eclipse_embed(ctx,
            title=f"**E.C.L.I.P.S.E. Army Analyzer**: Army {army_links_num}/3",
            message=f"**Please provide Army Link __{army_links_num} of 3__ in your next message.**"
                + f"\n\nIf you've sent all your Army Links, send `stop` to proceed with the analysis."
                + f"\n\nTo go back to the previous menu, send `back`."
                + f"\nTo close E.C.L.I.P.S.E., send `exit`.")

        if session.message:
            await session.message.edit(content=session.user.mention,embed=army_analysis_embed)
        else:
            session.message = await ctx.send(content=session.user.mention,embed=army_analysis_embed)
        await session.message.clear_reactions()

        try:
            army_links = await ctx.bot.wait_for("message",timeout=300,check=armylink_check)
        except asyncio.TimeoutError:
            response = 'armyanalyze'
            return response

        if army_links.content.lower() == 'back':
            await army_links.delete()
            response = 'armyanalyze'
            return response

        elif army_links.content.lower() == 'exit':
            await army_links.delete()
            return None

        elif army_links.content.lower() == 'stop':
            await army_links.delete()
            get_army = False

        else:
            army = eWarArmy(ctx,army_links.content,town_hall)
            army_compare.append(army)
            await army_links.delete()

        if army_links_num >= 3:
            get_army = False

    wait_embed = await eclipse_embed(ctx,
        title="**E.C.L.I.P.S.E. Army Analyzer**",
        message="<a:loading:1042769157248262154> Please wait... calculating.")
    await session.message.edit(content=session.user.mention,embed=wait_embed)

    compare_table = {'\u200b':['# of Units','Trg Time (mins)','HP (total)','HP (avg)','DPS (min)','DPS (max)','DPS (avg)','Speed (min)','Speed (max)','Speed (avg)']}

    link_num = 0
    for army in army_compare:
        link_num += 1
        army_key = f"Army {link_num}"

        compare_table[army_key] = [
            f"{int(army.troop_count):,}",
            f"{int(army.training_time/60):,}",
            f"{int(army.hitpoints_total):,}",
            f"{int(army.hitpoints_average):,}",
            f"{int(army.dps_min):,}",
            f"{int(army.dps_max):,}", 
            f"{int(army.dps_average):,}", 
            f"{int(army.movement_min):,}", 
            f"{int(army.movement_max):,}", 
            f"{int(army.movement_average):,}"]

    army_comparison_embed = await eclipse_embed(ctx,
        title="**E.C.L.I.P.S.E. Army Analyzer**",
        message=f"**Armies analyzed for: {emotes_townhall[town_hall]} TH {town_hall}**"
            + f"\n*Note: Healers, (Super) Wall Breakers, Spells and Siege Machines are excluded from army statistics.*"
            + box(tabulate(compare_table, headers="keys",tablefmt='simple')))

    dm_embed = await eclipse_embed(ctx,
        title="**E.C.L.I.P.S.E. Army Analyzer**",
        message=f"**Armies analyzed for: {emotes_townhall[town_hall]} TH {town_hall}**"
            + f"\n*Note: Healers, (Super) Wall Breakers, Spells and Siege Machines are excluded from army statistics.*"
            + box(tabulate(compare_table, headers="keys",tablefmt='simple')))

    army_num = 0
    for army in army_compare:
        army_num += 1
        army_comparison_embed.add_field(
            name=f"**Army {army_num}**",
            value=f"[Open in-game]({army.army_link})"
                + f"\n\n{army.army_str}\n\u200b",
            inline=True)
        dm_embed.add_field(
            name=f"**Army {army_num}**",
            value=f"[Open in-game]({army.army_link})"
                + f"\n\n{army.army_str}\n\u200b",
            inline=True)

    army_comparison_embed.add_field(
        name="Navigation",
        value=f"<:backwards:1041976602420060240> to restart the Army Analyzer"
            + f"\n<:download:1040800550373044304> to send this analysis to your DMs",
        inline=False)

    menu_options = []
    back_dict = {
        'id': 'armyanalyze',
        'emoji': "<:backwards:1041976602420060240>",
        'title': "",
        }
    save_dict = {
        'id': 'save',
        'emoji': "<:download:1040800550373044304>",
        'title': "",
        }
    menu_options.append(back_dict)
    menu_options.append(save_dict)

    if session.message:
        await session.message.edit(content=session.user.mention,embed=army_comparison_embed)
    else:
        session.message = await ctx.send(content=session.user.mention,embed=army_comparison_embed)
    
    while True:
        selection = await eclipse_multiple_choice_select(ctx,session,menu_options,timeout=300)

        if selection:
            if selection['id'] == 'save':
                try:
                    await session.user.send(embed=dm_embed)
                except:
                    no_dm_embed = await eclipse_embed(ctx,
                        message="I couldn't send you a DM! Please ensure your DM's are open.")
                    await session.channel.send(content=session.user.mention,embed=no_dm_embed,delete_after=40)
                else:
                    menu_options.remove(save_dict)
                    await session.message.remove_reaction("<:download:1040800550373044304>",ctx.bot.user)
                await session.message.remove_reaction("<:download:1040800550373044304>",session.user)
            else:
                break
        else:
            break

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

        category_select += await multiple_choice_menu_generate_emoji(ctx,category_options)
        
        for i in category_select:
            if i['id'] != 'back':
                category_str += f"{i['emoji']} {i['title']}"
                if category_select.index(i) < (len(category_select)-1):
                    category_str += f"\n\n"

        base_category_embed = await eclipse_embed(ctx,
            title="**E.C.L.I.P.S.E. Base Vault**",
            message=f"I found the following base types for **{emotes_townhall[base_th]} Townhall {base_th}**. "
                + f"*For performance reasons, bases are only shown in blocks of 5. Use the <:refresh:1048916418466426941> button to get the next block of 5.*"
                + f"\n\n**__Select a category to view bases.__**"
                + f"\n\n{category_str}\n\n<:backwards:1041976602420060240> Back to Townhall selection\n\u200b")

        if session.message:
            await session.message.edit(content=session.user.mention,embed=base_category_embed)
        else:
            session.message = await ctx.send(content=session.user.mention,embed=base_category_embed)
        await session.message.clear_reactions()
        selection = await eclipse_multiple_choice_select(ctx,session,category_select)

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


async def show_eclipse_bases(ctx,session,bases,vault_mode=False):
    browse_bases = True
    display_bases = []
    response = None

    base_navigation = []

    back_dict = {
        'id': 'back',
        'emoji': '<:backwards:1041976602420060240>'
        }
    prev_dict = {
        'id': 'previous',
        'emoji': '<:to_previous:1041988094943035422>'
        }
    next_dict = {
        'id': 'next',
        'emoji': '<:to_next:1041988114308137010>'
        }
    save_navigation = {
        'id': 'save',
        'emoji': '<:download:1040800550373044304>'
        }
    remove_navigation = {
        'id': 'unsave',
        'emoji': '<:trashcan:1042829064345497742>'
        }
    refresh_bases = {
        'id': 'refresh',
        'emoji': '<:refresh:1048916418466426941>',
        }
    view_claims = {
        'id': 'viewclaims',
        'emoji': '🔍',
        }

    base_navigation.append(back_dict)
    if len(bases) > 1:
        base_navigation.append(prev_dict)
        base_navigation.append(next_dict)

    if len(bases) > 5 and not vault_mode:
        base_navigation.append(refresh_bases)
        display_bases = random.sample(bases, 5)
    else:
        display_bases = bases

    i = 0
    refresh_rxn = True

    while browse_bases:
        if vault_mode:
            display_bases = [b for b in bases if session.user.id in b.claims]

            if len(display_bases) == 0:
                return 'personalvault'
        
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

        if session.user.id in display_bases[i].claims and not session.guild:
            base_embed.add_field(
                name="Base Link",
                value=f"[Click here to open in-game.]({display_bases[i].base_link})\n\u200b",
                inline=False)
            base_embed.add_field(
                name="Base Claim Status",
                value=f"Claimed by: {len(display_bases[i].claims)} member(s)"
                    + "\n🔍 to view all base claims"
                    + f"\n\n**You have claimed this base.** To remove your claim, click on <:trashcan:1042829064345497742>.",
                inline=False)
            base_navigation.append(remove_navigation)
            base_navigation.append(view_claims)

        elif session.user.id in display_bases[i].claims and session.guild:
            base_embed.add_field(
                name="Base Claim Status",
                value=f"Claimed by: {len(display_bases[i].claims)} member(s)"
                    + "\n🔍 to view all base claims"
                    + "\n\n**You have claimed this base.** To get the Base Link, click on <:download:1040800550373044304>. "
                    + f"\nThe Base Link will be sent to your DMs.",
                inline=False)
            base_navigation.append(save_navigation)
            base_navigation.append(view_claims)
            
        else:
            base_embed.add_field(
                name="Base Claim Status",
                value=f"Claimed by: {len(display_bases[i].claims)} member(s)"
                    + "\n🔍 to view all base claims"
                    + f"\n\nTo get the Base Link, first claim this base by clicking on <:download:1040800550373044304>. You will receive the Base Link in your DMs."
                    + f"\n*Your claimed bases will be accessible from your personal vault.*",
                inline=False)
            base_navigation.append(save_navigation)
            base_navigation.append(view_claims)

        if len(bases) > 5 and not vault_mode:
            base_embed.add_field(
                name="Navigation",
                value="<:backwards:1041976602420060240> back to the previous menu"
                    + "\n<:to_previous:1041988094943035422> for the previous base"
                    + "\n<:to_next:1041988114308137010> for the next base"
                    + "\n<:refresh:1048916418466426941> get more bases",
                inline=False)
        elif len(bases) > 1:
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
            if refresh_rxn:
                await session.message.clear_reactions()

        while True:
            selection = await eclipse_multiple_choice_select(ctx,session,base_navigation,timeout=300,refresh_rxn=refresh_rxn)
            if selection:
                if selection['id'] == 'next':
                    i += 1
                    if not vault_mode:
                        await session.message.remove_reaction("<:to_next:1041988114308137010>",session.user)
                        refresh_rxn = False

                    try:
                        await claim_msg.delete()
                    except:
                        pass
                    break
                elif selection['id'] == 'previous':
                    i -= 1
                    if not vault_mode:
                        await session.message.remove_reaction("<:to_previous:1041988094943035422>",session.user)
                        refresh_rxn = False

                    try:
                        await claim_msg.delete()
                    except:
                        pass
                    break
                elif selection['id'] == 'refresh':
                    i = 0
                    display_bases = random.sample(bases, 5)
                    if not vault_mode:
                        await session.message.remove_reaction("<:refresh:1048916418466426941>",session.user)
                        refresh_rxn = False

                    try:
                        await claim_msg.delete()
                    except:
                        pass
                    break

                elif selection['id'] == 'save':
                    await display_bases[i].add_claim(ctx,session)

                    dm_embed, image = await display_bases[i].base_embed(ctx)
                    dm_embed.add_field(
                        name="Base Link",
                        value=f"[Click here to open in-game.]({display_bases[i].base_link})",
                        inline=False)
                    try:
                        await session.user.send(embed=dm_embed,file=image)
                    except:
                        no_dm_embed = await eclipse_embed(ctx,
                            message="I couldn't send you a DM! Please ensure your DM's are open.")
                        await session.channel.send(content=session.user.mention,embed=no_dm_embed,delete_after=40)

                    if not vault_mode:
                        await session.message.remove_reaction("<:download:1040800550373044304>",session.user)
                        refresh_rxn = False

                    try:
                        await claim_msg.delete()
                    except:
                        pass
                    break

                elif selection['id'] == 'viewclaims':
                    if len(display_bases[i].claims) == 0:
                        claim_embed = await eclipse_embed(ctx,
                            message="This base hasn't been claimed by anyone.\n\n*This message will self-destruct in 40 seconds.*")
                    else:
                        member_str = ''
                        for c in display_bases[i].claims:
                            member_str += f"<@{c}>\n"

                        claim_embed = await eclipse_embed(ctx,
                            message=f"This base has been claimed by **{len(display_bases[i].claims)} members**:\n{member_str}"
                                + "\n*This message will self-destruct in 40 seconds.*")

                    claim_msg = await ctx.send(embed=claim_embed,delete_after=40)
                    if not vault_mode:
                        await session.message.remove_reaction('🔍', session.user)
                    else:
                        break

                elif selection['id'] == 'unsave':
                    await display_bases[i].remove_claim(ctx,session)
                    refresh_rxn = True

                    delete_embed = await eclipse_embed(ctx,
                        message="You have removed your claim from this base.")
                    await session.channel.send(embed=delete_embed,delete_after=40)
                    i = 0
                    try:
                        await claim_msg.delete()
                    except:
                        pass
                    break

                else:
                    browse_bases = False
                    refresh_rxn = True
                    try:
                        await claim_msg.delete()
                    except:
                        pass

                    break
            else:
                browse_bases = False
                refresh_rxn = True
                try:
                    await claim_msg.delete()
                except:
                    pass
                break
        try:
            await dump_message.delete()
        except:
            pass

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

    menu_options = await multiple_choice_menu_generate_emoji(ctx,menu_options)

    menu_embed = await eclipse_embed(ctx,
        title=f"{session.user.display_name}'s Personal Vault",
        message=f"\nWelcome to your personal E.C.L.I.P.S.E. Vault."
            + f"\n\nHere, you can access any of the War Bases that you've saved from the AriX Base Vault, with Base Links made available to you.\n\u200b")

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
    selection = await eclipse_multiple_choice_select(ctx,session,menu_options)

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

    vault_intro = f"This is where your saved bases will be stored, with base links made available."

    if len(user_bases) > 0:
        base_count = {}
        for b in user_bases:
            if b.town_hall not in list(base_count.keys()):
                base_count[b.town_hall] = 0
            base_count[b.town_hall] += 1

        townhall_levels = sorted(list(base_count.keys()),reverse=True)

        th_str = ""
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
                + f"\n\nI found a total of {len(user_bases)} base(s) in your personal vault.\n\u200b")

        base_select_embed.add_field(
            name="Select a Townhall level below to view your bases.",
            value=f"\n\n{th_str}",
            inline=False)

    else:
        base_select_embed = await eclipse_embed(ctx,
            title="**Welcome to your Personal Base Vault**",
            message=f"{vault_intro}"
                + f"\n\n**You don't have any bases in your personal vault.** Start by saving some bases from our Members' Vault."
            #    + f"\n\n<:backwards:1041976602420060240> to return to your Personal Vault."
                + f"\n\n<:red_cross:838461484312428575> to close this E.C.L.I.P.S.E. session.")

    if session.message:
        await session.message.edit(content=session.user.mention,embed=base_select_embed)
    else:
        session.message = await session.channel.send(content=session.user.mention,embed=base_select_embed)
    selection = await eclipse_multiple_choice_select(ctx,session,menu_options)

    if not selection:
        return None

    if selection['id'] == 'back':
        return 'personalvault'
        
    show_bases = [b for b in user_bases if b.town_hall==selection['id']]
    response = await show_eclipse_bases(ctx,session,show_bases,True)

    if response:
        return 'mybases'
    else:
        return None












