import json
import pytz

from datetime import datetime

from .constants import clanRanks
from .player import aPlayer, aClan, aMember
from .clan_war import aClanWar
from .raid_weekend import aRaidWeekend
from .errors import TerminateProcessing, InvalidTag, no_clans_registered, error_not_valid_abbreviation, error_end_processing


async def get_user_profile(ctx,user_id):
    member = await aMember.create(ctx,user_id)

    return member.home_clans, member.accounts

async def get_alliance_clan(ctx,abbreviation=None):
    alliance_clans = [c for c in [ctx.bot.clan_cache[c_tag] for c_tag in list(ctx.bot.clan_cache)] if c.is_alliance_clan]

    if abbreviation:
        select_clan = [clan for clan in alliance_clans if clan.abbreviation==abbreviation.upper()]
    else:
        select_clan = clans

    if len(select_clan) == 0:
        return None

    ret_clans = sorted(select_clan, key=lambda x:(x.level,x.capital_hall),reverse=True)
    return ret_clans


async def get_clan_members(ctx,clan=None):
    alliance_members = [m for m in [ctx.bot.clan_cache[m_tag] for m_tag in list(ctx.bot.member_cache)] if m.is_member]

    if clan:
        clan_members = [m for m in alliance_members if m.home_clan.tag == clan.tag]
    else:
        clan_members = alliance_members

    ret_members = sorted(clan_members,key=lambda x:(clanRanks.index(x.arix_rank),x.exp_level,x.town_hall.level),reverse=True)

    return ret_members
