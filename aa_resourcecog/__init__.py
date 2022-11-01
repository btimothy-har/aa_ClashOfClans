import os
import sys
import discord
import coc
import fasteners

from dotenv import load_dotenv
from redbot.core.bot import Red
from coc.ext import discordlinks
from .aa_resourcecog import AriXClashResources

from .constants import json_file_defaults

load_dotenv()

async def setup(bot:Red):
    clash_client = coc.Client()
    await clash_client.login_with_keys(
        os.getenv("CLASH_DEV_KEY1"), 
        os.getenv("CLASH_DEV_KEY2"),
        os.getenv("CLASH_DEV_KEY3"),
        os.getenv("CLASH_DEV_KEY4"),
        os.getenv("CLASH_DEV_KEY5"),
        load_game_data=coc.LoadGameData(always=True))
    bot.coc_client = clash_client
    
    bot.discordlinks = await discordlinks.login(
        os.getenv("DISCORDLINKS_USER"),
        os.getenv("DISCORDLINKS_PASS"))

    bot.clash_dir_path = os.getenv("DATAPATH")
    bot.clash_file_lock = fasteners.InterProcessReaderWriterLock(os.getenv("DATAPATH") + "/clash.lock")

    if not os.path.exists(bot.clash_dir_path+'/seasons.json'):
        with bot.clash_file_lock.write_lock():
            with open(bot.clash_dir_path+'/seasons.json','w') as file:
                season_default = json_file_defaults['seasons']
                season_default['current'] = AriXClashResources.get_current_season()
                json.dump(json_file_defaults['seasons'],file,indent=2)

    if not os.path.exists(bot.clash_dir_path+'/alliance.json'):
        with bot.clash_file_lock.write_lock():
            with open(bot.clash_dir_path+'/alliance.json','w') as file:
                json.dump(json_file_defaults['alliance'],file,indent=2)

    if not os.path.exists(bot.clash_dir_path+'/members.json'):
        with bot.clash_file_lock.write_lock():
            with open(bot.clash_dir_path+'/members.json','w') as file:
                json.dump({},file,indent=2)

    if not os.path.exists(bot.clash_dir_path+'/warlog.json'):
        with bot.clash_file_lock.write_lock():
            with open(bot.clash_dir_path+'/warlog.json','w') as file:
                json.dump({},file,indent=2)

    if not os.path.exists(bot.clash_dir_path+'/capitalraid.json'):
        with bot.clash_file_lock.write_lock():
            with open(bot.clash_dir_path+'/capitalraid.json','w') as file:
                json.dump({},file,indent=2)
    
    cog = AriXClashResources()
    bot.add_cog(cog)

#Username: bakkutteh
#Password: t1qyYUkrvGdNE