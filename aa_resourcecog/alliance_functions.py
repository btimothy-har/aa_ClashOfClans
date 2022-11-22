import json
import pytz

from datetime import datetime

from .constants import clanRanks
from .player import aPlayer
from .clan import aClan


async def get_user_profile(ctx,user_id):
    with ctx.bot.clash_file_lock.read_lock():
        with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
            file_json = json.load(file)

    member_accounts = [tag for (tag,account) in file_json['members'].items() if account['discord_user']==user_id]

    if len(select_account) == 0:
        return None
    else:
        user_home_clans = []
        user_accounts = []
        for tag in select_account:
            try:
                p = await aPlayer.create(ctx,tag)
            except Exception as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving data for Player Tag {tag}.",
                    err=e)

            user_accounts.append(p)
            if p.home_clan.tag not in [c.tag for c in user_home_clans]:
                user_home_clans.append(p.home_clan)

        home_clans = sorted(home_clans,key=lambda c:(c.level,c.capital_hall),reverse=True)

        members = [a for a in user_accounts if a.is_member]
        members = sorted(members,key=lambda x:(x.exp_level,x.town_hall.level),reverse=True)

        nonmembers = [a for a in user_accounts if not a.is_member]
        nonmembers = sorted(nonmembers,key=lambda x:(x.exp_level,x.town_hall.level),reverse=True)

        return_accounts = members + nonmembers

        return user_home_clans, return_accounts


async def get_alliance_clan(ctx,abbreviation=None):
    with ctx.bot.clash_file_lock.read_lock():
        with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
            file_json = json.load(file)

    clans = file_json['clans']

    if abbreviation:
        select_clan = [tag for (tag,clan) in clans.items() if clan['abbr']==abbreviation.upper()]
    else:
        select_clan = [tag for (tag,clan) in clans.items()]

    if len(select_clan) == 0:
        return None

    else:
        ret_clans = []
        for tag in select_clan:
            try:
                clan = await aClan.create(ctx,tag)
                ret_clans.append(clan)
            except Exception as e:
                return await error_end_processing(ctx,
                    preamble=f"Error encountered while retrieving clan {clan_abbreviation}",
                    err=e)

        ret_clans = sorted(ret_clans, key=lambda x:(x.level,x.capital_hall),reverse=True)
        return ret_clans
