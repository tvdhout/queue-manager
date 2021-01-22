from discord import Embed
from discord.ext import commands
from discord.ext.commands import Context
import re
from QueueManager import QueueManager
from config import PREFIX


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

    @commands.command(name='queue')
    @commands.has_permissions(administrator=True)
    async def set_queue_channels(self, context: Context):
        channels = context.message.content.split()[1:]
        if len(channels) == 0:
            await context.send(f"Tag the channels to enable as queue channel the in command's arguments: "
                               f"`{PREFIX}questions #questions1 #questions2`.")
            return
        channels = list(map(lambda c: re.sub('[><#]', '', c), channels))
        channels_string = " ".join(channels)
        server_id = str(context.guild.id)
        cursor = self.client.dbconnection.cursor()
        cursor.execute("INSERT INTO servers "
                       "(serverid, queues) VALUES (%s, %s) "
                       "ON DUPLICATE KEY UPDATE  queues = VALUES(queues)",
                       (server_id, channels_string))
        self.client.dbconnection.commit()
        self.client.get_queue_channels(context.guild)
        await context.send(f"The channels used as queues are: {', '.join(context.message.content.split()[1:])}")

    @commands.command(name='roles')
    @commands.has_permissions(administrator=True)
    async def set_manager_roles(self, context: Context):
        roles = context.message.content.split()[1:]
        if len(roles) == 0:
            await context.send(f"Tag the roles to be allowed to manage queues in the command's arguments: "
                               f"`{PREFIX}roles @Role1 @Role2`.")
            return
        roles = list(map(lambda r: re.sub('[><@&]', '', r), roles))
        roles_string = " ".join(roles)
        server_id = str(context.guild.id)
        cursor = self.client.dbconnection.cursor()
        cursor.execute("INSERT INTO servers "
                       "(serverid, roles) VALUES (%s, %s) "
                       "ON DUPLICATE KEY UPDATE  roles = VALUES(roles)",
                       (server_id, roles_string))
        self.client.dbconnection.commit()
        self.client.get_queue_channels(context.guild)
        await context.send(f"The roles that can manage queues are: {', '.join(context.message.content.split()[1:])}")

    @commands.command(name='help')
    @commands.has_permissions(administrator=True)
    async def help_command(self, context: Context):
        embed = Embed(title="Help", colour=0xffff00)
        embed.add_field(name=f"Setup",
                        value="This bot is used to manage a queue of questions and archive them "
                              "when answered. This bot requires a small setup to be functional. You must set the "
                              "channel in which to archive messages, the channels which are treated as queues, "
                              "and the roles that can manage queues. See below on how to declare these.",
                        inline=False)
        embed.add_field(name="Command usage",
                        value=f"`{PREFIX}help` → Show this menu.\n"
                              f"`{PREFIX}archive` → Use this command in the channel you want to use as archive.\n"
                              f"`{PREFIX}queue #channels` → Declare channels as queues. You can "
                              f"tag one or multiple channels: `{PREFIX}queue #channel` / `{PREFIX}queue #channel1 "
                              f"#channel2 ...`\n"
                              f"`{PREFIX}roles` → Declare roles as queue managers. You can tag one or multiple roles:\n"
                              f"`{PREFIX}roles @Role` / `{PREFIX}roles @Role1 @Role2 ...`")
        embed.add_field(name="Queue management",
                        value="When a regular user sends a message in a queue channel, the bot wil reply with "
                              ":inbox_tray:. Consecutive messages by the same user (ignoring interruptions by "
                              "managers) are regarded as one. A queue manager can click on the :inbox_tray: reaction "
                              "to claim the question. Once answered it can be archived by clicking on the "
                              ":outbox_tray:. Queue managers that are not the claimer of a question can still archive "
                              "it, after clicking on the :white_check_mark: for confirmation, to avoid accidentally "
                              "archiving a message you did not claim.",
                        inline=False)
        await context.send(embed=embed)


def setup(client: QueueManager):
    client.add_cog(CommandsCog(client))
