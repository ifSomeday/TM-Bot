import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
import os
import pickle

class Leaderboard(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.campaignId = 0
        self.leaderboardUid = None

        self.recordDict = {}
        self.updateChannel = 0
        self.zone = "Texas"

        self.pickle = "settings.pickle"
        self.pickleLock = asyncio.Lock()

        self.loadPickle()

        self.updater.start()

    @tasks.loop(minutes=15.0)
    async def updater(self):
        await self.update(None)


    @updater.before_loop
    async def beforeUpdater(self):
        await self.bot.wait_until_ready()


    @commands.Cog.listener()
    async def on_ready(self):
        self.session = aiohttp.ClientSession(headers={"User-Agent" : "Discord Record Tracker for specific regions"})


    ## updates the updateChannel and saves to pickle, all under lock
    async def savePickle(self):
        async with self.pickleLock:
            with open(self.pickle, "wb") as f:
                pickle.dump({
                    "updateChannel" : self.updateChannel,
                    "zone" : self.zone,
                    "recordDict" : self.recordDict
                }, f)


    ## Not under lock because we only call this in init
    def loadPickle(self):
        if os.path.exists(self.pickle):
            with open(self.pickle, "rb") as f:
                tmp = pickle.load(f)
                self.updateChannel = tmp.get("updateChannel", 0)
                self.recordDict = tmp.get("recordDict", {})
                self.zone = tmp.get("zone", "Texas")


    async def getCampaign(self):
        async with self.session.get("https://trackmania.io/api/campaigns/0") as response:
            if(response.status == 200):
                j = await response.json()
                campaign = j["campaigns"][0]
                self.campaignId = campaign["id"]
                print("Latest Campaign: {0}/{1}".format(campaign["name"], self.campaignId))
            else:
                print("Error getting campaign: {0}\n{1}".format(response.status, await response.text()))
    

    async def getTracks(self):
        if(self.campaignId != 0):
            async with self.session.get("https://trackmania.io/api/officialcampaign/{0}".format(self.campaignId)) as response:
                if(response.status == 200):
                    j = await response.json()
                    self.leaderboardUid = j["leaderboarduid"]
                    playlist = j["playlist"]
                    for track in playlist:
                        if track["mapUid"] not in self.recordDict.keys():
                            self.recordDict[track["mapUid"]] = {"record" : None,
                                                                "map" : track}
                    self.recordDict = {k : v for k, v in self.recordDict.items() if k in [x["mapUid"] for x in playlist]}
                    await self.savePickle()
                else:
                    print("Error getting tracks: {0}\n{1}".format(response.status, await response.text()))
        else:
            print("Unable to get tracks, campaign ID is 0")


    @commands.command()
    @commands.is_owner()
    async def setChannel(self, ctx, ch : discord.TextChannel):
        self.updateChannel = ch.id
        await self.savePickle()


    @commands.command()
    @commands.is_owner()
    async def setZone(self, ctx, zone : str):
        self.zone = zone
        await self.savePickle()


    @commands.command()
    @commands.is_owner()
    async def update(self, ctx):
        await self.getCampaign()
        await self.getTracks()

        for mapUid, entry in self.recordDict.items():
            new = await self.getTopZone(mapUid)
            if(new != None):
                if(entry["record"] == None):
                    print("No previous record found")
                    self.recordDict[mapUid]["record"] = new
                    await self.savePickle()
                else:
                    if(new["time"] < entry["record"]["time"]):
                        print("New record for {0}/{1}".format(entry["map"]["name"], mapUid))
                        emb = await self.buildEmbed(entry["map"], entry["record"], new)
                        ch = self.bot.get_channel(self.updateChannel)
                        await ch.send(embed=emb)
                    self.recordDict[mapUid]["record"] = new
            await asyncio.sleep(5)
        await self.savePickle()


    async def buildEmbed(self, map, old, new):
        emb = discord.Embed()
        emb.title = "New record by {0}".format(new["player"]["name"])
        emb.set_thumbnail(url=map["thumbnailUrl"])

        emb.add_field(name = "Time", value = self.msToTimestamp(new["time"]))
        emb.add_field(name = "Place", value = str(new["position"]))
        emb.add_field(name = "Diff", value = "-{0}".format(self.msToTimestamp(old["time"] - new["time"])))
        emb.add_field(name = "Previous Record", value = "{0} by {1}".format(self.msToTimestamp(old["time"]), old["player"]["name"]))
        emb.color = discord.Color.blurple()

        return(emb)


    def msToTimestamp(self, ms):
        tmp, milliseconds = divmod(ms, 1000)
        minutes, seconds = divmod(tmp, 60)
        return("{0}:{1:02}:{2:03}".format(minutes, seconds, milliseconds))


    async def getTopZone(self, mapUid):
        offset = 0
        length = 50
        while(offset <= 200):
            async with self.session.get("https://trackmania.io/api/leaderboard/{0}/{1}".format(self.leaderboardUid, mapUid), params={"offset" : offset, "length" : length}) as response:
                if(response.status == 200):
                    j = await response.json()
                    for player in j["tops"]:
                        if player["player"]["zone"]["name"] == self.zone:
                            return(player)
                else:
                    print("Error getting leaderboard ({0}, {1}, {2}): {3}\n{4}".format(mapUid, offset, length, response.status, await response.text()))
                    return(None)
            offset += 50
        return(None)

def setup(bot):
    bot.add_cog(Leaderboard(bot))
