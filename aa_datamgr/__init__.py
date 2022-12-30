import os
import sys
import shutil
import discord
import coc

from os import path
from dotenv import load_dotenv

load_dotenv()

from redbot.core.bot import Red
from .aa_datamgr import AriXClashDataMgr

async def setup(bot:Red):
    cog = AriXClashDataMgr()
    bot.refresh_loop = 0
    bot.add_cog(cog)
    await cog.initialize_config(bot)
