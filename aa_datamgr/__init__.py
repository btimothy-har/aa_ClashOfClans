import os
import sys
import shutil
import discord
import coc

from os import path
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getenv("RESOURCEPATH"))

from redbot.core.bot import Red
from .coc_datamgr import AriXClashDataMgr

async def setup(bot:Red):
    shutil.copy("clash_resources.py",os.getenv("RESOURCEPATH"))
    cog = AriXClashDataMgr()
    await cog.cog_initialize()
    bot.add_cog(cog)