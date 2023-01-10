import os
import sys
import discord
import coc

from redbot.core.bot import Red
from .aa_clashutils import AriXClashUtils

async def setup(bot:Red):
    cog = AriXClashUtils()
    bot.add_cog(cog)
