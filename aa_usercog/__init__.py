import os
import sys
import discord
import coc

from redbot.core.bot import Red
from .aa_usercog import AriXClashMembers

async def setup(bot:Red):
    cog = AriXClashMembers()
    bot.add_cog(cog)