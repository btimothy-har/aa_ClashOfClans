import json
import pytz

from datetime import datetime

async def get_current_season():
    helsinkiTz = pytz.timezone("Europe/Helsinki")
    current_season = f"{datetime.now(helsinkiTz).month}-{datetime.now(helsinkiTz).year}"
    return current_season

async def get_current_alliance(self):
    with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
        file_json = json.load(file)
    clansList = list(file_json['clans'].keys())
    memberList = list(file_json['members'].keys())
    return clansList,memberList

async def season_file_handler(ctx,season):
    is_new_season = False
    current_season = None
    new_season = None
    with open(ctx.bot.clash_dir_path+'/seasons.json','w+') as file:
        s_json = json.load(file)
        current_season = s_json['current']
        if season != current_season:
            is_new_season = True
            new_season = season
                
            s_json['tracked'].append(currrent_season)
            s_json['current'] = new_season
            json.dump(s_json,file,indent=2)

    if is_new_season:
        clans, members = await get_current_alliance()

        new_path = ctx.bot.clash_dir_path+'/'+new_season
        os.makedirs(new_path)

        shutil.copy2(ctx.bot.clash_dir_path+'/members.json',new_path)
        with open(ctx.bot.clash_dir_path+'/members.json','w+') as file:
            json.dump({},file,indent=2)

        with open(ctx.bot.clash_dir_path+'/warlog.json','w+') as file:
            w_json = json.load(file)
            for key,item in w_json.items():
                if item['state'] != "warEnded":
                    del w_json[key]
            new_w = {}
            for c in clans:
                new_w[c] = {}
            json.dump(new_w,file,indent=2)
            file.truncate()
        with open(new_path+'/warlog.json','w+') as file:
            json.dump(w_json,file,indent=2)
            file.truncate()

        with open(ctx.bot.clash_dir_path+'/capitalraid.json','w+') as file:
            r_json = json.load(file)
            for key,item in r_json.items():
                if item['state'] != "ended":
                    del r_json[key]
            new_r = {}
            for c in clans:
                new_r[c] = {}
            json.dump(new_r,file,indent=2)
            file.truncate()
        with open(new_path+'/capitalraid.json','w+') as file:
            json.dump(r_json,file,indent=2)
            file.truncate()

    return is_new_season, current_season, new_season

async def alliance_file_handler(ctx,entry_type,tag,new_data=None):
    with open(ctx.bot.clash_dir_path+'/alliance.json','w+') as file:
        file_json = json.load(file)
        if new_data:
            file_json[entry_type][tag] = new_data
            json.dump(file_json,file,indent=2)
            file.truncate()
    try:
        rJson = file_json[entry_type][tag]
    except KeyError:
        rJson = None
    return rJson

async def data_file_handler(ctx,file:str,tag:str,new_data=None,season=None):
    if file not in ['members','warlog','capitalraid']:
        return None

    file_name = {
        'members':'members.json',
        'warlog':'warlog.json',
        'capitalraid':'capitalraid.json',
        }

    file_path = self.cDirPath + file_name[file]

    with open(file_path,'w+') as file:
        file_json = json.load(file)
        if new_data:
            file_json[tag] = new_data
            json.dump(file_json,file,indent=2)
            file.truncate()
    try:
        response_json = file_json[tag]
    except KeyError:
        response_json = None
    return response_json