# class MemberIneligible(Exception):
#     def __init__(self,message):
#         self.message = message

# class aChallengePass():
#     def __init__(self,bot,member):
#         self.member = member
#         self.season = season

#         self.track = ""
#         self.points = 0
#         self.tokens = 0
#         self.challenges = []

#     @classmethod
#     async def create(cls,bot,member):

#         if not member.is_member:
#             raise MemberIneligible
#             return None

#         if member.tag in list(bot.pass_cache.keys()):
#             self = bot.pass_cache[tag]



#         self = aChallengePass(ctx,member)


#     def updatePass(self,activeChallenge):
#         if activeChallenge['progress']['status'] == 'completed':
#             if activeChallenge['reward']['type'] == 'challengePoints':
#                 self.atxChaPoints += activeChallenge['reward']['reward']
#                 self.atxChaCommonStreak = 0
#             if activeChallenge['reward']['type'] != 'challengePoints':
#                 self.atxChaCommonStreak += 1
#             self.atxChaCompleted += 1
#             self.atxChaCompletedChalls.append(activeChallenge)
#             self.atxChaActiveChall = None

#         if activeChallenge['progress']['status'] == 'missed':
#             if activeChallenge['reward']['type'] != 'challengePoints':
#                 self.atxChaCommonStreak += 0
#             self.atxChaMissed += 1
#             self.atxChaCompletedChalls.append(activeChallenge)
#             self.atxChaActiveChall = None

#         if activeChallenge['progress']['status'] == 'trashed':
#             if activeChallenge['reward']['type'] != 'challengePoints':
#                 self.atxChaCommonStreak += 0
#             self.atxChaTrashed += 1
#             self.atxChaCompletedChalls.append(activeChallenge)
#             self.atxChaActiveChall = None

#         if activeChallenge['progress']['status'] == 'inProgress':
#             self.atxChaActiveChall = activeChallenge

#     async def savePass(self):
#         if self.season=='current':
#             async with clashJsonLock('challengepass'):
#                 with open(getFile('challengepass'),"r") as dataFile:
#                     challengeJson = json.load(dataFile)
#                 challengeJson['current'][self.tag] = {
#                     "tag": self.tag,
#                     "player": self.player,
#                     "track":self.atxChaTrack,
#                     "totalPoints":self.atxChaPoints,
#                     "completed":self.atxChaCompleted,
#                     "missed":self.atxChaMissed,
#                     "trashed":self.atxChaTrashed,
#                     "commonStreak": self.atxChaCommonStreak,
#                     "activeChallenge":self.atxChaActiveChall,
#                     "completedChallenges":self.atxChaCompletedChalls,
#                     }
#                 with open(getFile('challengepass'),"w") as dataFile:
#                     return json.dump(challengeJson,dataFile,indent=2)
