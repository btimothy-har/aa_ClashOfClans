import time
import discord

class aNote():
	def __init__(self,ctx):
		self.timestamp = 0
		self.author = None
		self.content = ''

	@classmethod
	def create_new(cls,ctx,message):
		self = aNote(ctx)
		self.timestamp = time.time()
		self.author = ctx.author
		self.content = message
		return self

	@classmethod
	def from_json(cls,ctx,inputJson):
		self = aNote(ctx)
		self.timestamp = inputJson.get('timestamp',0)
		self.author = ctx.bot.get_user(int(inputJson.get('author',0)))
		self.content = inputJson.get('content','')
		return self

	def to_json(self):
		noteJson = {
			'timestamp': self.timestamp,
			'author': self.author.id,
			'content': self.content
			}
		return noteJson