import os
import sys
import discord
import coc

from redbot.core.bot import Red
from .aa_usercog import AriXMemberCommands

async def setup(bot:Red):
    if bot.refresh_loop >= 0:
        cog = AriXMemberCommands()
        bot.add_cog(cog)
