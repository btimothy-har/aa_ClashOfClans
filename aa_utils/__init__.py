import os
import sys
import discord
import coc

from redbot.core.bot import Red
from .aa.clashutils import AriXClashUtils

async def setup(bot:Red):
    if bot.refresh_loop >= 0:
        cog = AriXClashUtils()
        bot.add_cog(cog)
