import os
import sys
import discord
import coc

from redbot.core.bot import Red
from .aa_leadercog import AriXClashLeaders

async def setup(bot:Red):
    cog = AriXClashLeaders()
    bot.add_cog(cog)