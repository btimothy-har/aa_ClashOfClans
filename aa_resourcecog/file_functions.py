import json
import pytz

from datetime import datetime
from .constants import clanRanks

async def get_current_season():
    helsinkiTz = pytz.timezone("Europe/Helsinki")
    current_season = f"{datetime.now(helsinkiTz).month}-{datetime.now(helsinkiTz).year}"
    return current_season

async def get_current_alliance(ctx):
    with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
        file_json = json.load(file)

    clans = file_json['clans']
    try:
        clan_list = sorted(clans, key=lambda x: (clans[x]['level'],clans[x]['capital_hall']),reverse=True)
    except:
        clan_list = list(clans.keys())
    
    member_list = list(file_json['members'].keys())

    return clan_list,member_list

async def get_alliance_clan(ctx,abbreviation):
    with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
        file_json = json.load(file)

    clans = file_json['clans']
    select_clan = [tag for (tag,clan) in clans.items() if clan['abbr']==abbreviation.upper()]

    if len(select_clan) == 0:
        return None
    else:
        return select_clan[0]

async def get_alliance_members(ctx,clan):
    with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
        file_json = json.load(file)

    members = file_json['members']
    select_members = [tag for (tag,member) in members.items() if member['is_member']==True and member['home_clan']['tag']==clan.tag]

    return select_members

async def get_user_accounts(ctx,user_id,clan_tag=None):
    with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
        file_json = json.load(file)

    if clan_tag:
        select_account = [tag for (tag,account) in file_json['members'].items() if account['discord_user']==user_id and (account['is_member']==True or account['rank']=='Guest') and account['home_clan']['tag']==clan_tag]
    else:
        select_account = [tag for (tag,account) in file_json['members'].items() if account['discord_user']==user_id and (account['is_member']==True or account['rank']=='Guest')]

    if len(select_account) == 0:
        return []
    else:
        return select_account

async def get_staff_position(ctx,user_id,rank_or_higher):

    i = clanRanks.index(rank_or_higher)
    t_rank = clanRanks[i:]

    with open(ctx.bot.clash_dir_path+'/alliance.json','r') as file:
        file_json = json.load(file)

    clans = file_json['clans']
    c_tags = sorted(clans, key=lambda x: (clans[x]['level'],clans[x]['capital_hall']),reverse=True)

    ret_tags = []
    for c in c_tags:
        if "Leader" in t_rank and user_id==clans[c]['leader']:
            ret_tags.append(c)
        if "Co-Leader" in t_rank and user_id in clans[c]['co_leaders']:
            ret_tags.append(c)
        if "Elder" in t_rank and user_id in clans[c]['elders']:
            ret_tags.append(c)

    return ret_tags

async def season_file_handler(ctx,season):
    is_new_season = False
    current_season = None
    new_season = None
    with open(ctx.bot.clash_dir_path+'/seasons.json','r+') as file:
        s_json = json.load(file)
        current_season = s_json['current']
        if season != current_season:
            is_new_season = True
            new_season = season
                
            s_json['tracked'].append(currrent_season)
            s_json['current'] = new_season
            file.seek(0)
            json.dump(s_json,file,indent=2)
            file.truncate()

    if is_new_season:
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
    with open(ctx.bot.clash_dir_path+'/alliance.json','r+') as file:
        file_json = json.load(file)
        if new_data:
            file_json[entry_type][tag] = new_data
            file.seek(0)
            json.dump(file_json,file,indent=2)
            file.truncate()
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
    file_path = ctx.bot.clash_dir_path + '/' + file_name[file]

    with open(file_path,'r+') as file:
        file_json = json.load(file)
        if new_data:
            file_json[tag] = new_data
            file.seek(0)
            json.dump(file_json,file,indent=2)
            file.truncate()
    try:
        response_json = file_json[tag]
    except KeyError:
        response_json = {}
    return response_json

async def eclipse_base_handler(ctx,base_town_hall=None,base_json=None):
    with open(ctx.bot.eclipse_path+'/warbases.json','r+') as file:
        file_json = json.load(file)

        if base_json:
            existing_base = [b for b in th_bases if b['id']==base_json['id']]

            if existing_base:
                existing_index = th_bases.index(existing_base[0])
                del th_bases[existing_index]

            file_json['vault'].append(base_json)
            file.seek(0)
            json.dump(file_json,file,indent=2)
            file.truncate()

        if base_town_hall:
            th_bases = [b for b in file_json['vault'] if b['town_hall'] == base_town_hall]
        else:
            th_bases = [b for b in file_json['vault']]

    return th_bases

async def eclipse_army_handler(ctx,army_town_hall,army_json=None):
    with open(ctx.bot.eclipse_path+'/wararmies.json','r+') as file:
        file_json = json.load(file)

        if army_json:
            existing_army = [a for a in file_json if a['id']==army_json['id']]

            if existing_army:
                existing_index = file_json.index(existing_army[0])
                del file_json[existing_index]

            file_json.append(army_json)
            file.seek(0)
            json.dump(file_json,file,indent=2)
            file.truncate()

        war_armies = [a for a in file_json if a['town_hall'] == army_town_hall]     

    return war_armies











