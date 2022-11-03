confirmation_emotes = ['<:green_check:838461472324583465>','<:red_cross:838461484312428575>']

selection_emotes = []

json_file_defaults = {
    'seasons': {
        'current': '',
        'tracked': [],
        },
    'alliance': {
        'clans': {},
        'members': {}
        },
    }

emotes_townhall = {
    1:"<:01:1037000998566240256>",
    2:"<:02:1037000999753228320>",
    3:"<:03:1037001001275752498>",
    4:"<:04:1037001002852827136>",
    5:"<:05:1037001004106907708>",
    6:"<:06:1037001005524590623>",
    7:"<:07:1037001006879354910>",
    8:"<:08:1037001008062140497>",
    9:"<:09:1037001009207201832>",
    10:"<:10:1037001010184454256>",
    11:"<:11:1037001011363074200>",
    12:"<:12:1037001012466176030>",
    13:"<:13:1037001013586038804>",
    14:"<:14:1037001014764638228>",
    15:"<:15:1037034679309697104>"
    }

emotes_builderhall = {
    1: "<:bb01:1037001017155395654>",
    2: "<:bb02:1037001018526945350>",
    3: "<:bb03:1037001020158513203>",
    4: "<:bb04:1037001021374865509>",
    5: "<:bb05:1037001022930952202>",
    6: "<:bb06:1037001024080199871>",
    7: "<:bb07:1037001025221054494>",
    8: "<:bb08:1037001026294788116>",
    9: "<:bb09:1037001027687297045>",
    }

emotes_league = {
    'Unranked': "<:Unranked:1037033299610185879>",
    'Bronze League I': "<:BronzeLeagueI:1037033265309155408>",
    'Bronze League II': "<:BronzeLeagueII:1037033266483576842>",
    'Bronze League III': "<:BronzeLeagueIII:1037033267519557632>",
    'Silver League I': "<:SilverLeagueI:1037033268471664830>",
    'Silver League II': "<:SilverLeagueII:1037033270048723065>",
    'Silver League III': "<:SilverLeagueIII:1037033271713865818>",
    'Gold League I': "<:GoldLeagueI:1037033273047650404>",
    'Gold League II': "<:GoldLeagueII:1037033274146570360>",
    'Gold League III': "<:GoldLeagueIII:1037033275711029328>",
    'Crystal League I': "<:CrystalLeagueI:1037033278970011658>",
    'Crystal League II': "<:CrystalLeagueII:1037033280643543131>",
    'Crystal League III': "<:CrystalLeagueIII:1037033283520831509>",
    'Master League I': "<:MasterLeagueI:1037033285290827816>",
    'Master League II': "<:MasterLeagueII:1037033286482014339>",
    'Master League III': "<:MasterLeagueIII:1037033287970992158>",
    'Champion League I': "<:ChampionLeagueI:1037033289564815430>",
    'Champion League II': "<:ChampionLeagueII:1037033291032821760>",
    'Champion League III': "<:ChampionLeagueIII:1037033292169478334>",
    'Titan League I': "<:TitanLeagueI:1037033293423587398>",
    'Titan League II': "<:TitanLeagueII:1037033295130656808>",
    'Titan League III': "<:TitanLeagueIII:1037033296720297995>",
    'Legend League': "<:LegendLeague:1037033298460954704>"
    }

emotes_army = {
    "Barbarian King": "<:BarbarianKing:1037000154173157397>",
    "Archer Queen": "<:ArcherQueen:1037000155561472096>",
    "Grand Warden": "<:GrandWarden:1037000157088206939>",
    "Royal Champion": "<:RoyalChampion:1037000158895943680>",
    "Battle Machine": "<:BattleMachine:1037002790305792072>",
    "L.A.S.S.I": "<:LASSI:1037000160246509639>",
    "Electro Owl": "<:ElectroOwl:1037000161378959410>",
    "Mighty Yak": "<:MightyYak:1037000164029767800>",
    "Unicorn": "<:Unicorn:1037000162540789813>",
    "Frosty": "<:Frosty:1037000165229350973>",
    "Diggy": "<:Diggy:1037000169360732220>",
    "Poison Lizard": "<:PoisonLizard:1037000167221629048>",
    "Phoenix": "<:Phoenix:1037000168035340360>",
    "Barbarian": "<:Barbarian:1036998335791382588>",
    "Archer": "<:Archer:1036998337343275028>",
    "Giant": "<:Giant:1036998341160087652>",
    "Goblin": "<:Goblin:1036998338089852970>",
    "Wall Breaker": "<:WallBreaker:1036998339629154367>",
    "Balloon": "<:Balloon:1036998342376427610>",
    "Wizard": "<:Wizard:1036998343789916200>",
    "Healer": "<:Healer:1036998345106919424>",
    "Dragon": "<:Dragon:1036998346323275826>",
    "Minion": "<:Minion:1036998347589959810>",
    "Hog Rider": "<:HogRider:1036998348852441098>",
    "P.E.K.K.A": "<:PEKKA:1036998349917802556>",
    "Valkyrie": "<:Valkyrie:1036998351268360192>",
    "Golem": "<:Golem:1036998352505671820>",
    "Baby Dragon": "<:BabyDragon:1036998353759785101>",
    "Witch": "<:Witch:1036998354921603202>",
    "Lava Hound": "<:LavaHound:1036998356125351976>",
    "Miner": "<:Miner:1036998357127798794>",
    "Bowler": "<:Bowler:1036998358604193852>",
    "Electro Dragon": "<:ElectroDragon:1036998359690522665>",
    "Ice Golem": "<:IceGolem:1036998361036890183>",
    "Yeti": "<:Yeti:1036998362454560768>",
    "Headhunter": "<:Headhunter:1036998363817717851>",
    "Dragon Rider": "<:DragonRider:1036998365122134057>",
    "Electro Titan": "<:ElectroTitan:1036998366237818890>",
    "Wall Wrecker": "<:WallWrecker:1036998801237475378>",
    "Battle Blimp": "<:BattleBlimp:1036998802013442100>",
    "Stone Slammer": "<:StoneSlammer:1036998803380764712>",
    "Siege Barracks": "<:SiegeBarracks:1036998804592939108>",
    "Log Launcher": "<:LogLauncher:1036998805775728660>",
    "Flame Flinger": "<:FlameFlinger:1036998807168237730>",
    "Battle Drill": "<:BattleDrill:1036998808397160458>",
    "Lightning Spell": "<:LightningSpell:1036999357255397497>",
    "Healing Spell": "<:HealingSpell:1036999358547230772>",
    "Rage Spell": "<:RageSpell:1036999360417898707>",
    "Poison Spell": "<:PoisonSpell:1036999361734901780>",
    "Earthquake Spell": "<:EarthquakeSpell:1036999363022565406>",
    "Jump Spell": "<:JumpSpell:1036999364356349982>",
    "Freeze Spell": "<:FreezeSpell:1036999366055047258>",
    "Haste Spell": "<:HasteSpell:1036999367304941610>",
    "Skeleton Spell": "<:SkeletonSpell:1036999368852647956>",
    "Clone Spell": "<:CloneSpell:1036999369863475210>",
    "Bat Spell": "<:BatSpell:1036999371008516237>",
    "Invisibility Spell": "<:InvisibilitySpell:1036999371985784885>",
    "Recall Spell": "<:recall:1036999373529296976>",
    "Super Barbarian": "<:SuperBarbarian:1037032254116995103>",
    "Super Archer": "<:SuperArcher:1037032256017010812>",
    "Super Giant": "<:SuperGiant:1037032258080608287>",
    "Sneaky Goblin": "<:SneakyGoblin:1037032259888365668>",
    "Super Wall Breaker": "<:SuperWallBreaker:1037032261859692544>",
    "Rocket Balloon": "<:RocketBalloon:1037032263302529065>",
    "Super Wizard": "<:superwizard:1037032265479360542>",
    "Super Dragon": "<:SuperDragon:1037032266704097281>",
    "Inferno Dragon": "<:InfernoDragon:1037032268159528980>",
    "Super Minion": "<:SuperMinion:1037032269711421481>",
    "Super Valkyrie": "<:SuperValkyrie:1037032272056033402>",
    "Super Witch": "<:SuperWitch:1037032273909915648>",
    "Ice Hound": "<:IceHound:1037032275310813276>",
    "Super Bowler": "<:SuperBowler:1037032276665585815>",
    }

clanRanks = ['Member','Elder','Co-Leader','Leader']

warTypeGrid = {
    'random':'classic',
    'friendly':'friendly',
    'cwl':'cwl'
    }

warResultGrid = {
    'winning':'won',
    'tied':'tie',
    'losing':'lost',
    'won':'won',
    'tie':'tie',
    'lost':'lost',
    '':'',
    }

hero_availability = {
    1: [],
    2: [],
    3: [],
    4: [],
    5: [],
    6: [],
    7: ['Barbarian King'],
    8: [],
    9: ['Archer Queen'],
    10: [],
    11: ['Grand Warden'],
    12: [],
    13: ['Royal Champion'],
    14: [],
    15: [],
    }

troop_availability = {
    1: ['Barbarian','Archer','Giant'],
    2: ['Goblin'],
    3: ['Wall Breaker'],
    4: ['Balloon'],
    5: ['Wizard'],
    6: ['Healer'],
    7: ['Dragon','Minion','Hog Rider'],
    8: ['P.E.K.K.A','Valkyrie','Golem'],
    9: ['Baby Dragon','Witch','Lava Hound'],
    10: ['Miner','Bowler'],
    11: ['Electro Dragon','Ice Golem'],
    12: ['Yeti','Headhunter','Wall Wrecker','Battle Blimp','Stone Slammer'],
    13: ['Dragon Rider','Siege Barracks','Log Launcher'],
    14: ['Electro Titan','Flame Flinger'],
    15: ['Battle Drill']
    }

spell_availability = {
    1: [],
    2: [],
    3: [],
    4: [],
    5: ['Lightning Spell'],
    6: ['Healing Spell'],
    7: ['Rage Spell'],
    8: ['Poison Spell', 'Earthquake Spell'],
    9: ['Jump Spell', 'Freeze Spell', 'Haste Spell', 'Skeleton Spell'],
    10: ['Clone Spell', 'Bat Spell'],
    11: ['Invisibility Spell'],
    12: [],
    13: ['Recall Spell'],
    14: [],
    15: []
    }