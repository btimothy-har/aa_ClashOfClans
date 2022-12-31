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
    cog = AriXClashDataMgr(bot)

    bot.load_cache = False
    bot.current_season = None

    bot.tracked_seasons = []
    bot.user_cache = {}
    bot.member_cache = {}
    bot.clan_cache = {}

    bot.pass_cache = {}
    bot.war_cache = {}
    bot.raid_cache = {}

    bot.refresh_loop = -1
    bot.master_refresh = False
    bot.clan_refresh_status = False
    bot.member_refresh_status = False

    bot.add_cog(cog)
    await cog.initialize_config(bot)

    bot.load_cache = True
    bot.data_log_channel = bot.get_channel(1033390608506695743)
