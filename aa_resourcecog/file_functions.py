import os
import sys
import shutil

import json
import pytz
import calendar

from datetime import datetime

async def get_current_season(params=None):
    helsinkiTz = pytz.timezone("Europe/Helsinki")
    current_season = f"{datetime.now(helsinkiTz).month}-{datetime.now(helsinkiTz).year}"

    if params == 'readable':
        current_season = f"{calendar.month_name[datetime.now(helsinkiTz).month]} {datetime.now(helsinkiTz).year}"

    return current_season


async def alliance_file_handler(ctx,entry_type,tag,new_data=None,season=None):
    if season:
        alliance_file = ctx.bot.clash_dir_path+'/' + season + '/alliance.json'
    else:
        alliance_file = ctx.bot.clash_dir_path+'/alliance.json'

    if new_data:
        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(alliance_file,'r+') as file:
                    file_json = json.load(file)
                    file_json[entry_type][tag] = new_data
                    file.seek(0)
                    json.dump(file_json,file,indent=2)
                    file.truncate()
    else:
        with ctx.bot.clash_file_lock.read_lock():
            with open(alliance_file,'r') as file:
                file_json = json.load(file)
    try:
        if tag == "**":
            rJson = file_json[entry_type]
        else:
            rJson = file_json[entry_type][tag]
    except KeyError:
        rJson = {}
    return rJson


async def data_file_handler(ctx,action:str,file:str,tag:str,new_data=None,season=None):
    if action not in ['read','write']:
        return None

    if file not in ['members','warlog','capitalraid','challengepass']:
        return None

    file_name = {
        'members':'members.json',
        'warlog':'warlog.json',
        'capitalraid':'capitalraid.json',
        'challengepass':'challengepass.json'
        }
    if season:
        file_path = ctx.bot.clash_dir_path + '/' + season + '/' + file_name[file]
    else:
        file_path = ctx.bot.clash_dir_path + '/' + file_name[file]


    ch = ctx.bot.get_channel(856433806142734346)

    if action == 'write' and new_data:
        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(file_path,'r+') as file:
                    file_json = json.load(file)
                    file_json[tag] = new_data
                    file.seek(0)
                    json.dump(file_json,file,indent=2)
                    file.truncate()

    elif action == 'read':
        with ctx.bot.clash_file_lock.read_lock():
            with open(file_path,'r') as file:
                file_json = json.load(file)
    try:
        if tag == "**":
            response_json = file_json
        else:
            response_json = file_json[tag]
    except KeyError:
        response_json = {}
    return response_json


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
