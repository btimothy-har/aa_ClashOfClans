import os
import sys
import discord
import coc

from redbot.core.bot import Red
from .aa_challengepass import AriXChallengePass

async def setup(bot:Red):
    if bot.refresh_loop >= 0:
        cog = AriXChallengePass()
        bot.add_cog(cog)
