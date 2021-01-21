from discord.ext import commands
from discord.ext.commands import Context
import re
from QueueManager import QueueManager


class CommandsCog(commands.Cog):
    def __init__(self, client: QueueManager):
        self.client = client

    @commands.command(name='archive')
    @commands.has_permissions(administrator=True)
    async def set_archive_channel(self, context: Context):
        channel_id = str(context.channel.id)
        server_id = str(context.guild.id)
        cursor = self.client.dbconnection.cursor()
        cursor.execute("INSERT INTO servers "
                       "(serverid, archiveid) VALUES (%s, %s) "
                       "ON DUPLICATE KEY UPDATE  archiveid = VALUES(archiveid)",
                       (server_id, channel_id))
        self.client.dbconnection.commit()
        await context.send(f"{context.channel.mention} is now set as the archive channel.")

    # @commands.command(name='questions')
    # @commands.has_permissions(administrator=True)
    # async def set_question_channels(self, context: Context):
    #     channels = context.message.content.split()[1:]
    #     if len(channels) == 0:
    #         await context.send("Tag the channels to select as question channels as arguments to this command.")
    #         return
    #     channels = list(map(lambda c: re.sub('[><#]', '', c), channels))
    #     channels_string = " ".join(channels)
    #     server_id = str(context.guild.id)
    #     cursor = self.client.dbconnection.cursor()
    #     cursor.execute("INSERT INTO servers "
    #                    "(serverid, questionschannels) VALUES (%s, %s) "
    #                    "ON DUPLICATE KEY UPDATE  questionschannels = VALUES(questionschannels)",
    #                    (server_id, channels_string))
    #     self.client.dbconnection.commit()


def setup(client: QueueManager):
    client.add_cog(CommandsCog(client))
