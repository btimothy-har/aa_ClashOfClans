import json
import pytz

from datetime import datetime

from .constants import clanRanks

async def get_current_season():
    helsinkiTz = pytz.timezone("Europe/Helsinki")
    current_season = f"{datetime.now(helsinkiTz).month}-{datetime.now(helsinkiTz).year}"
    return current_season


async def season_file_handler(ctx,season):
    is_new_season = False
    current_season = None
    new_season = None
    with ctx.bot.clash_file_lock.read_lock():
        with open(ctx.bot.clash_dir_path+'/seasons.json','r+') as file:
            s_json = json.load(file)
            current_season = s_json['current']


    if season != current_season:
        is_new_season = True
        new_season = season
        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(ctx.bot.clash_dir_path+'/seasons.json','r+') as file:
                    s_json = json.load(file)
                    s_json['tracked'].append(currrent_season)
                    s_json['current'] = new_season
                    file.seek(0)
                    json.dump(s_json,file,indent=2)
                    file.truncate()

            clans, members = await get_current_alliance()

            new_path = ctx.bot.clash_dir_path+'/'+new_season
            os.makedirs(new_path)

            shutil.copy2(ctx.bot.clash_dir_path+'/members.json',new_path)
            #open in w+ as we are wiping out existing file
            with open(ctx.bot.clash_dir_path+'/members.json','w+') as file:
                json.dump({},file,indent=2)

            with open(ctx.bot.clash_dir_path+'/warlog.json','r+') as file:
                w_json = json.load(file)
                for key,item in w_json.items():
                    if item['state'] != "warEnded":
                        del w_json[key]
                    new_w = {}
                for c in clans:
                    new_w[c] = {}
                file.seek(0)
                json.dump(new_w,file,indent=2)
                file.truncate()

            #open in w+ as we are wiping out existing file
            with open(new_path+'/warlog.json','w+') as file:
                json.dump(w_json,file,indent=2)

            with open(ctx.bot.clash_dir_path+'/capitalraid.json','r+') as file:
                r_json = json.load(file)
                for key,item in r_json.items():
                    if item['state'] != "ended":
                        del r_json[key]
                new_r = {}
                for c in clans:
                    new_r[c] = {}
                file.seek(0)
                json.dump(new_r,file,indent=2)
                file.truncate()

            #open in w+ as we are wiping out existing file
            with open(new_path+'/capitalraid.json','w+') as file:
                json.dump(r_json,file,indent=2)
    return is_new_season, current_season, new_season


async def alliance_file_handler(ctx,entry_type,tag,new_data=None):
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
        rJson = file_json[entry_type][tag]
    except KeyError:
        rJson = {}
    return rJson


async def data_file_handler(ctx,file:str,tag:str,new_data=None,season=None):
    if file not in ['members','warlog','capitalraid']:
        return None

    file_name = {
        'members':'members.json',
        'warlog':'warlog.json',
        'capitalraid':'capitalraid.json',
        }
    if season:
        file_path = ctx.bot.clash_dir_path + '/' + season + '/' + file_name[file]
    else:
        file_path = ctx.bot.clash_dir_path + '/' + file_name[file]

    if new_data:
        async with ctx.bot.async_file_lock:
            with ctx.bot.clash_file_lock.write_lock():
                with open(file_path,'r+') as file:
                    file_json = json.load(file)
                    file_json[tag] = new_data
                    file.seek(0)
                    json.dump(file_json,file,indent=2)
                    file.truncate()
    else:
        with ctx.bot.clash_file_lock.read_lock():
            with open(file_path,'r') as file:
                file_json = json.load(file)
    try:
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
