import os
import sys
import discord
import coc

from redbot.core.bot import Red
from .aa_leadercog import AriXClashLeaders

async def setup(bot:Red):
    cog = AriXClashLeaders()
    await cog.cog_initialize()
    bot.add_cog(cog)