import os
import sys
import discord
import coc

from redbot.core.bot import Red
from .aa_leadercog import AriXLeaderCommands

async def setup(bot:Red):
    if bot.refresh_loop >= 0:
        cog = AriXLeaderCommands()
        bot.add_cog(cog)
