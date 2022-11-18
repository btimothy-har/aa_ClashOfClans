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
        
        self.id = urllib.parse.quote_plus(urllib.parse.parse_qs(link_parse.query)['id'][0])
        try:
            self.town_hall = int(self.id.split('TH',1)[1][:2])
        except:
            self.town_hall = int(self.id.split('TH',1)[1][:1])
            
        self.base_link = f"https://link.clashofclans.com/en?action=OpenLayout&id={urllib.parse.quote_plus(self.id)}"

        self.defensive_cc_id = urllib.parse.quote(urllib.parse.parse_qs(cc_parse.query)['army'][0])
        self.defensive_cc_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={urllib.parse.quote_plus(self.defensive_cc_id)}"

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
        base_link = f"https://link.clashofclans.com/en?action=OpenLayout&id={json_data['id']}"
        defensive_cc_link = f"https://link.clashofclans.com/en?action=CopyArmy&army={json_data['defensive_cc']}"

        self = eWarBase(ctx,base_link,defensive_cc_link)

        self.id = json_data['id']
        self.base_link = base_link

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

    def add_claim(self,ctx,session):
        if session.user.id not in self.claims:
            self.claims.append(session.user.id)

    def remove_claim(self,ctx,session):
        if session.user.id in self.claims:
            self.claims.remove(session.user.id)

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
                + f"\n\nFrom: **{self.source}**\nBuilder: **{self.builder}**"
                + f"\n\n**Recommended Clan Castle:**\n{self.defensive_cc_str}")

        if self.notes:
            base_text += f"\n\n**Builder Notes**:\n{self.notes}"
        base_text += "\n\u200b"

        embed = await eclipse_embed(ctx,
            title=f"**TH{self.town_hall} {emotes_townhall[int(self.town_hall)]} {self.base_type}**",
            message=base_text)

        embed.set_image(url="attachment://image.png")

        return embed,image_file


class eWarArmy():
    def __init__(self,ctx,army_link,town_hall):
        self.ctx = ctx

        self.army_link = army_link

        parsed_army = ctx.bot.coc_client.parse_army_link(self.army_link)

        self.troops = []
        self.super_troops = []
        self.siege_machines = []
        self.spells = []

        for troop in parsed_army[0]:
            if troop[0].name in coc.HOME_TROOP_ORDER:
                self.troops.append(troop)
            if troop[0].name in coc.SUPER_TROOP_ORDER:
                self.super_troops.append(troop)
            if troop[0].name in coc.SIEGE_MACHINE_ORDER:
                self.siege_machines.append(troop)

        for spell in parsed_army[1]:
            self.spells.append(spell)

        self.army_str = "**Troops**"
        troop_ct = 0
        for troop in self.troops:
            troop_ct += 1
            if troop_ct % 2 == 0:
                self.army_str += "\u3000"
            else:
                self.army_str += "\n"
            self.army_str += f"`{troop[1]}x` {emotes_army[troop[0].name]}"

        if len(self.super_troops) > 0:
            troop_ct = 0
            self.army_str += "\n\n**Super Troops**"
            for troop in self.super_troops:
                troop_ct += 1
                if troop_ct % 2 == 0:
                    self.army_str += "\u3000"
                else:
                    self.army_str += "\n"
                self.army_str += f"`{troop[1]}x` {emotes_army[troop[0].name]}"

        if len(self.spells) > 0:
            troop_ct = 0
            self.army_str += "\n\n**Spells**"
            for spell in self.spells:
                troop_ct += 1
                if troop_ct % 2 == 0:
                    self.army_str += "\u3000"
                else:
                    self.army_str += "\n"
                self.army_str += f"`{spell[1]}x` {emotes_army[spell[0].name]}"
        
        if len(self.siege_machines) > 0:
            self.army_str += "\n\n**Siege Machines**"
            for siege in self.siege_machines:
                self.army_str += f"\n`{siege[1]}x` {emotes_army[siege[0].name]}"

        self.all_troops = self.troops + self.super_troops

        self.troop_count = 0

        all_hitpoints = []
        all_dps = []
        all_movement = []
        all_training_time = []
        
        #troop here is a tuple of (troop, qty)
        for troop in self.all_troops:
            if troop[0].name not in ['Wall Breaker','Super Wall Breaker','Healer']:
                troop_max_level = troop[0].get_max_level_for_townhall(int(town_hall))
                for x in range(0,troop[1]):
                    self.troop_count += 1
                    all_hitpoints.append(troop[0].hitpoints[troop_max_level])
                    all_dps.append(troop[0].dps[troop_max_level])
                    all_movement.append(troop[0].speed[troop_max_level])
                    all_training_time.append(troop[0].training_time[troop_max_level])

        self.hitpoints_total = sum(all_hitpoints)
        self.hitpoints_average = self.hitpoints_total / len(all_hitpoints)
        self.dps_min = min(all_dps)
        self.dps_max = max(all_dps)
        self.dps_average = sum(all_dps) / len(all_dps)
        self.movement_min = min(all_movement)
        self.movement_max = max(all_movement)
        self.movement_average = sum(all_movement) / len(all_movement)
        self.training_time = sum(all_training_time)

