import coc
import discord
import time
import urllib

from datetime import datetime

from .discordutils import eclipse_embed
from .file_functions import get_current_alliance, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler
from .constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league, clan_castle_size, army_campsize

class EclipseSession():
    def __init__(self,ctx):
        self.state = True
        self.user = ctx.author
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.response_path = []
        self.message = None

    def add_to_path(self,response):
        self.response_path.append(response)

    async def save_to_json(self):
        sessionJson = {}

class eWarBase():
    def __init__(self,ctx,base_link,defensive_cc_link):
        self.ctx = ctx

        link_parse = urllib.parse.urlparse(base_link)
        cc_parse = urllib.parse.urlparse(defensive_cc_link)
        
        self.id = urllib.parse.quote(urllib.parse.parse_qs(link_parse.query)['id'][0])
        self.town_hall = int(self.id.split('TH',1)[1][:2])
        self.base_link = f"https://link.clashofclans.com/en?action=OpenLayout&id={urllib.parse.quote(self.id)}"

        self.defensive_cc_id = urllib.parse.quote(urllib.parse.parse_qs(cc_parse.query)['army'][0])
        self.defensive_cc_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={urllib.parse.quote(self.defensive_cc_id)}"

        parsed_cc = ctx.bot.coc_client.parse_army_link(self.defensive_cc_link)
        self.defensive_cc_str = ""
        for troop in parsed_cc[0]:
            if self.defensive_cc_str != "":
                self.defensive_cc_str += "\u3000"
            self.defensive_cc_str += f"{emotes_army[troop[0].name]} x{troop[1]}"

        self.source = ""
        self.builder = None

        self.added_on = 0
        self.base_type = ""
        
        self.base_image = ""
        self.notes = ""

        self.claims = []

    @classmethod
    def from_json(cls,ctx,json_data):
        base_link = f"https://link.clashofclans.com/en?action=OpenLayout&id={urllib.parse.quote(json_data['id'])}"
        defensive_cc_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={urllib.parse.quote(json_data['defensive_cc'])}"

        self = eWarBase(ctx,base_link,defensive_cc_link)

        self.source = json_data.get('source',"")
        self.builder = json_data.get('builder',"")

        self.added_on = json_data.get('added_on',0)
        self.base_type = json_data.get('base_type',"")

        self.base_image = json_data['base_image']
        self.notes = json_data.get('notes',"")
        self.claims = json_data.get('claims',[])
        return self

    @classmethod
    async def new_base(cls,ctx,base_link,source,base_builder,base_type,defensive_cc,notes,image_attachment):
        self = eWarBase(ctx,base_link,defensive_cc)

        self.source = source
        if base_builder == "*":
            self.builder = "Not Specified"
        else:
            self.builder = base_builder

        if notes == "*":
            self.notes = None
        else:
            self.notes = notes

        self.added_on = time.time()
        self.base_type = base_type

        image_filename = self.id + '.' + image_attachment.filename.split('.')[-1]
        image_filepath = self.ctx.bot.eclipse_path + "/base_images/" + image_filename

        await image_attachment.save(image_filepath)
        self.base_image = image_filename

        return self

    async def save_to_json(self):
        baseJson = {
            'id': self.id,
            'townhall': self.town_hall,
            'source': self.source,
            'builder': self.builder,
            'added_on': self.added_on,
            'base_type': self.base_type,
            'defensive_cc': self.defensive_cc_id,
            'base_image': self.base_image,
            'notes': self.notes,
            'claims': self.claims
            }

        await eclipse_base_handler(
            ctx=self.ctx,
            base_town_hall=self.town_hall,
            base_json=baseJson
            )

    async def base_embed(self,ctx):
        image_file_path = f"{self.ctx.bot.eclipse_path}/base_images/{self.base_image}"
        image_file = discord.File(image_file_path,'image.png')

        base_text = (f"Date Added: {datetime.fromtimestamp(self.added_on).strftime('%d %b %Y')}"
                + f"\nClaimed By: {len(self.claims)} member(s)"
                + f"\n\nFrom: **{self.source}** (Builder: **{self.builder}**)"
                + f"\n\n**Defensive Clan Castle (Recommendation):**\n{self.defensive_cc_str}")

        if self.notes:
            base_text += f"\n\n**Builder Notes**:\n{self.notes}"
        base_text += "\n\u200b"

        embed = await eclipse_embed(ctx,
            title=f"**{emotes_townhall[int(self.town_hall)]} TH{self.town_hall} {self.base_type}**",
            message=base_text)

        embed.set_image(url="attachment://image.png")

        return embed,image_file


# class eWarArmy():
#     def __init__(self,ctx,army_link,cc_link):
#         self.ctx = ctx

#         army_parse = urllib.parse.urlparse(army_link)
#         cc_parse = urllib.parse.urlparse(cc_link)
        
#         self.army_id = urllib.parse.quote(urllib.parse.parse_qs(army_parse.query)['army'][0])
#         self.army_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={self.army_id}"

#         parsed_army = ctx.bot.coc_client.parse_army_link(self.army_link)
#         self.troop_count = 0
#         self.spell_count = 0

#         self.troop_comp_str = ""
#         self.supertroop_comp_str = ""
#         self.siege_comp_str = ""
#         self.spell_comp_str = ""
        
#         for troop in parsed_army[0]:
#             if troop[0].name in coc.HOME_TROOP_ORDER:
#                 self.troop_comp_str += f"`{troop[1]}x` {emotes_army[troop[0].name]} {troop[0].name}\n"
#                 self.troop_count += army_campsize[troop[0].name]
#             if troop[0].name in coc.SUPER_TROOP_ORDER:
#                 self.supertroop_comp_str += f"`{troop[1]}x` {emotes_army[troop[0].name]} {troop[0].name}\n"
#                 self.troop_count += army_campsize[troop[0].name]
#             if troop[0].name in coc.SIEGE_MACHINE_ORDER:
#                 self.siege_comp_str += f"`{troop[1]}x` {emotes_army[troop[0].name]} {troop[0].name}\n"

#         for spell in parsed_army[1]:
#             if spell[0].name in coc.SPELL_ORDER:
#                 self.spell_comp_str += f"`{spell[1]}x` {emotes_army[spell[0].name]} {spell[0].name}\n"
#                 self.spell_count += army_campsize[spell[0].name]

#         self.cc_troops = urllib.parse.quote(urllib.parse.parse_qs(cc_parse.query)['army'][0])
#         self.cc_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={self.cc_troops}"

#         parsed_cc = ctx.bot.coc_client.parse_army_link(self.cc_link)
#         self.cc_troops_str = ""
#         self.cc_siege_str = ""
#         self.cc_spell_str = ""
#         for troop in parsed_cc[0]:
#             if troop[0].name in (coc.HOME_TROOP_ORDER + coc.SUPER_TROOP_ORDER):
#                 self.cc_troops_str += f"`{troop[1]}x` {emotes_army[troop[0].name]} {troop[0].name}\n"
#             if troop[0].name in coc.SIEGE_MACHINE_ORDER:
#                 self.cc_siege_str += f"`{troop[1]}x` {emotes_army[troop[0].name]} {troop[0].name}\n"

#         for spell in parsed_cc[1]:
#             if spell[0].name in coc.SPELL_ORDER:
#                 self.cc_spell_str += f"`{spell[1]}x` {emotes_army[spell[0].name]} {spell[0].name}\n"

#         self.name = ""
#         self.author = ""
#         self.town_hall = 0

#         self.difficulty = 0
#         self.video = []

#         self.description = ""
#         self.status = ""
#         self.votes = (0,0)

#     @classmethod
#     async def new_army(cls,ctx,name,town_hall,author,difficulty,video,army_link,cc_link,description):
#         self = eWarArmy(ctx,army_link,cc_link)

#         self.name = name
#         self.author = author
#         self.town_hall = town_hall

#         self.difficulty = int(difficulty)
#         self.video = video

#         self.description = description

#         return self

#     @classmethod
#     def from_json(cls,ctx,json_data):
#         army_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={urllib.parse.quote(json_data['army_id'])}"
#         cc_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={urllib.parse.quote(json_data['army_cc'])}"

#         self = eWarArmy(ctx,army_link,cc_link)

#         self.name = json_data['name']
#         self.author = json_data['author']
#         self.town_hall = json_data['town_hall']

#         self.difficulty = json_data['difficulty']
#         self.video = json_data['video']

#         self.description = json_data['description']

#         return self

#     async def save_to_json(self):
#         armyJson = {
#             'id': self.army_id,
#             'army_cc': self.cc_troops,
#             'town_hall': self.town_hall,
#             'name': self.name,
#             'author': self.author,
#             'difficulty': self.difficulty,
#             'video': self.video,
#             'description': self.description,
#             'status': self.status,
#             'votes': self.votes,
#             }

#         await eclipse_army_handler(
#             ctx=self.ctx,
#             army_town_hall=self.town_hall,
#             army_json=armyJson
#             )

#     async def army_embed(self,ctx):
#         army_text = f"*Contributed by: {self.author}*"

#         army_text += f"\n\n**Difficulty:**\n"
#         for n in range(1,6):
#             if n <= self.difficulty:
#                 army_text += ":star:\u200b"
#             else:
#                 army_text += "<:star_empty:1042337290904670270>\u200b"

#         army_text += "\n\n**Video Links**"
#         for v in self.videos:
#             army_text += "> " + v +"\n"

#         army_text += f"\n\n**<:barracks:1042336340072738847> {self.troop_count}\u3000<:spellfactory:1042336364789768273> {self.spell_count}**"

#         embed = await eclipse_embed(ctx,
#             title=f"**{self.name} [{emotes_townhall[int(self.town_hall)]} TH {self.town_hall}]**",
#             message=army_text)

#         #if self.description:
#         #    embed.add_field(
#         #        name=f"**__Description__**",
#         #        value=f"{self.description}\n\u200b",
#         #        inline=False)

#         embed.add_field(
#             name=f"**Troops**",
#             value=self.troop_comp_str + "\n\u200b",
#             inline=False
#             )

#         if self.supertroop_comp_str:
#             embed.add_field(
#                 name=f"**Super Troops**",
#                 value=self.supertroop_comp_str + "\n\u200b",
#                 inline=False
#                 )

#         if self.siege_comp_str:
#             embed.add_field(
#                 name=f"**Siege Machines**",
#                 value=self.siege_comp_str + "\n\u200b",
#                 inline=False
#                 )

#         if self.siege_comp_str:
#             embed.add_field(
#                 name=f"**Spells**",
#                 value=self.spell_comp_str + "\n\u200b",
#                 inline=False
#                 )

#         embed.add_field(
#             name=f"**Clan Castle**",
#             value=self.cc_troops_str + self.cc_spell_str + self.cc_siege_str,
#             inline=False
#             )

#         return embed
