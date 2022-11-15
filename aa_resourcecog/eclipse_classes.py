import coc
import discord
import time
from datetime import datetime

from .discordutils import eclipse_embed
from .file_functions import get_current_alliance, season_file_handler, alliance_file_handler, data_file_handler, eclipse_base_handler
from .constants import emotes_townhall, emotes_army, emotes_capitalhall, hero_availability, troop_availability, spell_availability, emotes_league

class EclipseSession():
    def __init__(self,ctx):
        self.state = True
        self.user = ctx.author
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

        self.town_hall = int(base_link.split('id=TH',1)[1][:2])
        self.id = base_link.split('id=',1)[1]
        self.base_link = f"https://link.clashofclans.com/en?action=OpenLayout&id={self.id}"

        self.defensive_cc_id = defensive_cc_link.split('&army=',1)[1]
        self.defensive_cc_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={self.defensive_cc_id}"
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
        
        base_link = f"https://link.clashofclans.com/en?action=OpenLayout&id={json_data['base_id']}"
        defensive_cc_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={json_data['defensive_cc']}"

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
            'base_id': self.id,
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
                + f"\n\nFrom: **{self.source}** (Builder: **{self.builder}**)"
                + f"\n\n**Defensive Clan Castle (Recommendation):**\n{self.defensive_cc_str}")

        if self.notes:
            base_text =+ f"\n\n**Builder Notes**:\n{self.notes}"
        base_text += "\n\u200b"

        embed = await eclipse_embed(ctx,
            title=f"**{emotes_townhall[int(self.town_hall)]} TH{self.town_hall} {self.base_type}**",
            message=base_text)

        embed.set_image(url="attachment://image.png")

        return embed,image_file


class eWarArmy():
    def __init__(self,ctx,army_links,cc_links):