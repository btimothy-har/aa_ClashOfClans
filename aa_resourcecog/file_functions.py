import os
import sys
import shutil

import json
import pytz
import calendar

from datetime import datetime

async def get_current_season():
    helsinkiTz = pytz.timezone("Europe/Helsinki")
    current_season = f"{datetime.now(helsinkiTz).month}-{datetime.now(helsinkiTz).year}"

    if params == 'readable':
        current_season = f"{calendar.month_name[datetime.now(helsinkiTz).month]} {datetime.now(helsinkiTz).year}"

    return current_season

async def save_war_cache(ctx):
    war_cache = ctx.bot.war_cache
    for (war_id,war) in war_cache.items():
        if war:
            await war.save_to_json(ctx)

async def save_raid_cache(ctx):
    raid_cache = ctx.bot.raid_cache
    for (raid_id,raid) in raid_cache.items():
        if raid:
            await raid.save_to_json(ctx)

async def save_clan_cache(ctx):
    clan_cache = ctx.bot.clan_cache
    for (c_tag,clan) in clan_cache.items():
        if clan.is_alliance_clan:
            await clan.save_to_json(ctx)

async def save_member_cache(ctx):
    member_cache = ctx.bot.member_cache
    for (m_tag,member) in member_cache.items():
        if member.is_arix_account:
            await member.save_to_json(ctx)


def filename_handler(ctx,name_input,**kwargs):
    season = kwargs.get('season',None)

    if name_input not in ['alliance','meminfo','members','warlog','capitalraid','challengepass']:
        return None

    file_name = {
        'alliance':'clans.json',
        'meminfo':'membership.json',
        'members':'players.json',
        'warlog':'warlog.json',
        'capitalraid':'capitalraid.json',
        'challengepass':'challengepass.json'
        }

    if season:
        file_path = ctx.bot.clash_dir_path + '/' + season + '/' + file_name[name_input]
    else:
        file_path = ctx.bot.clash_dir_path + '/' + file_name[name_input]

    return file_path

async def read_file_handler(ctx,file:str,tag:str,**kwargs):
    season = kwargs.get('season',None)

    file_path = filename_handler(ctx,name_input=file,season=season)
    if not file_path:
        return None

    with ctx.bot.clash_file_lock.read_lock():
        with open(file_path,'r') as file:
            file_json = json.load(file)

            try:
                return_data = file_json[tag]
            except KeyError:
                return_data = None

    return return_data

async def write_file_handler(ctx,file:str,tag:str,new_data,**kwargs):
    season = kwargs.get('season',None)

    file_path = filename_handler(ctx,name_input=file,season=season)
    if not file_path:
        return None

    async with ctx.bot.async_file_lock:
        with ctx.bot.clash_file_lock.write_lock():
            with open(file_path,'r+') as file:
                file_json = json.load(file)

                file_json[tag] = new_data
                return_data = file_json[tag]

                file.seek(0)
                json.dump(file_json,file,indent=2)
                file.truncate()

    return return_data

async def eclipse_base_handler(ctx,base_town_hall=None,base_json=None):
    eclipse_base_file = ctx.bot.eclipse_path+'/warbases.json'

    if base_json:
        async with ctx.bot.async_eclipse_lock:
            with ctx.bot.clash_eclipse_lock.write_lock():
                with open(eclipse_base_file,'r+') as file:
                    file_json = json.load(file)
                    file_json[base_json['id']] = base_json
                    file.seek(0)
                    json.dump(file_json,file,indent=2)
                    file.truncate()
    else:
        with ctx.bot.clash_eclipse_lock.read_lock():
            with open(eclipse_base_file,'r') as file:
                file_json = json.load(file)

    if base_town_hall:
        th_bases = [b for i,b in file_json.items() if b['townhall'] == base_town_hall]
    else:
        th_bases = [b for i,b in file_json.items()]
    return th_bases
