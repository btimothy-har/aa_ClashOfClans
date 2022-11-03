import time
import discord

class aNote():
	def __init__(self,ctx,inputJson):
		self.timestamp = inputJson.get('timestamp',0)
		self.author = ctx.bot.get_user(int(inputJson.get('author',0)))
		self.content = inputJson.get('content','')

	@classmethod
	async def create_new(cls,ctx,message):
		self.timestamp = time.time()
		self.author = ctx.author
		self.content = message

	def to_json(self):
		noteJson = {
			'timestamp': self.timestamp,
			'author': self.author.id,
			'content': self.content
			}
		return noteJson