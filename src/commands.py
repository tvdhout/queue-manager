import re
from typing import List, Set
from lazy_streams import stream
from discord import Embed, TextChannel, Role
from discord.ext import commands
from discord.ext.commands import Context

from QueueManager import QueueManager
from config import PREFIX
from server_conf import ServerConfiguration
from database_connection import execute_query


class CommandsCog(commands.Cog):
    def __init__(self, client: QueueManager):
        self.client = client

    @commands.command(name='archive', aliases=[' archive'])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_archive_channel(self, context: Context):
        """
        Set the channel in which this command is used as the archive channel for this server.
        @param context: discord.ext.commands.Context: The context of the command
        @return:
        """
        channel_id = str(context.channel.id)
        server_id = str(context.guild.id)
        execute_query("INSERT INTO servers "
                      "(serverid, archiveid) VALUES (%s, %s) "
                      "ON DUPLICATE KEY UPDATE  archiveid = VALUES(archiveid)",
                      (server_id, channel_id))
        self.client.get_server_conf(context.guild).set_archive(context.channel)
        embed = Embed(title="Archive channel", colour=0xffe400)
        embed.add_field(name="Success!", value=f"{context.channel.mention} is now set as the archive channel.")
        await context.send(embed=embed)

    @commands.command(name='queues', aliases=['queue'])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_queue_channels(self, context: Context):
        """
        Declare the channels given in the arguments of this command as queues.
        @param context: discord.ext.commands.Context: The context of the command
        @return:
        """
        content = context.message.content
        if len(content.split()[1:]) == 0:
            await context.send(f"Tag the channels to enable as queue channel the in command's arguments: "
                               f"`{PREFIX}questions #questions1 #questions2`.")
            return
        channel_ids: List[str] = re.findall(r'<#(\d+)>', content)  # Find all channel IDs in the message
        queues: Set[TextChannel] = set()
        for c_id in channel_ids:
            queue: TextChannel = context.guild.get_channel(int(c_id))
            if queue is not None:
                queues.add(queue)
        if len(queues) == 0:
            await context.send(f"Tag the channels to enable as queue channel the in command's arguments: "
                               f"`{PREFIX}questions #questions1 #questions2`.")
            return
        queue_ids_string = " ".join(stream(list(queues)).map(lambda c: c.id).map(str).to_list())
        server_id = str(context.guild.id)
        execute_query("INSERT INTO servers "
                      "(serverid, queues) VALUES (%s, %s) "
                      "ON DUPLICATE KEY UPDATE  queues = VALUES(queues)",
                      (server_id, queue_ids_string))
        self.client.get_server_conf(context.guild).set_queues(queues)
        embed = Embed(title="Queue channels", colour=0xffe400)
        embed.add_field(name="Success!", value=f"The channel(s) used as queues are: "
                                               f"{', '.join(list(map(lambda q: q.mention, queues)))}")
        await context.send(embed=embed)

    @commands.command(name='roles', aliases=['role'])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_manager_roles(self, context: Context):
        """
        Declare the roles given in the arguments of this command as queue managers.
        @param context: discord.ext.commands.Context: The context of the command
        @return:
        """
        content = context.message.content
        if len(content.split()[1:]) == 0:  # No arguments
            await context.send(f"Tag the roles to be allowed to manage queues in the command's arguments: "
                               f"`{PREFIX}roles @Role1 @Role2`.")
            return
        role_ids: List[str] = re.findall(r'<@&(\d+)>', content)  # Clear the tagging syntax around roles IDs
        roles: Set[Role] = set()
        for r_id in role_ids:
            role: Role = context.guild.get_role(int(r_id))
            if role is not None:
                roles.add(role)
        if len(roles) == 0:
            await context.send(f"Tag the roles to be allowed to manage queues in the command's arguments: "
                               f"`{PREFIX}roles @Role1 @Role2`.")
            return
        role_ids_string = " ".join(stream(list(roles)).map(lambda r: r.id).map(str).to_list())
        server_id = str(context.guild.id)
        execute_query("INSERT INTO servers "
                      "(serverid, roles) VALUES (%s, %s) "
                      "ON DUPLICATE KEY UPDATE  roles = VALUES(roles)",
                      (server_id, role_ids_string))
        self.client.get_server_conf(context.guild).set_roles(roles)
        embed = Embed(title="Queue manager roles", colour=0xffe400)
        embed.add_field(name="Success!", value=f"The role(s) that can manage queues are: "
                                               f"{', '.join(list(map(lambda r: r.mention, roles)))}")
        await context.send(embed=embed)

    @commands.command(name='config', aliases=['configuration'])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def show_configuration(self, context: Context):
        """
        Show the Queue Manager configuration for this channel: arhive channel, queue channel(s), and manager role(s)
        @param context: discord.ext.commands.Context: The context of the command
        @return:
        """
        configuration: ServerConfiguration = self.client.get_server_conf(context.guild)
        embed = Embed(title="Queue Manager configuration", colour=0xffe400)
        # Archive channel
        try:
            archive = configuration.archive.mention  # Raises AttributeError if None.
        except AttributeError:
            archive = f"Not yet defined. Use the `{PREFIX}archive` command in the channel you want to set as " \
                      f"archive channel"
        embed.add_field(name="Archive channel:", value=archive, inline=False)

        # Queue channels
        queues: Set[str] = set()
        for q in configuration.queues:
            try:
                queues.add(q.mention)
            except AttributeError:
                pass
        msg = ", ".join(queues) or f"None defined. Use the `{PREFIX}queues` command to declare channels as queues."
        embed.add_field(name="Queue channels:", value=msg, inline=False)

        # Manager roles
        roles: Set[str] = set()
        for r in configuration.roles:
            try:
                roles.add(r.mention)
            except AttributeError:
                pass
        msg = ", ".join(roles) or f"None defined. Use the `{PREFIX}roles` command to declare roles as managers."
        embed.add_field(name="Queue Manager roles:", value=msg, inline=False)
        await context.send(embed=embed)

    @commands.command(name='reset')
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def clear_configuration(self, context: Context):
        """
        Delete the configurations for this server.
        @param context: discord.ext.commands.Context: The context of the command
        @return:
        """
        execute_query("DELETE FROM servers WHERE serverid = %s",
                      (str(context.guild.id),))
        try:
            del self.client.server_confs[context.guild]  # Delete server configuration
        except KeyError:
            pass
        embed = Embed(title="Server configuration reset", colour=0xffe400)
        embed.add_field(name="Reset succesful", value="All configurations for this server are removed.")
        await context.send(embed=embed)

    @commands.command(name='help')
    async def help_command(self, context: Context):
        """
        Display the help message.
        @param context: discord.ext.commands.Context: The context of the command
        @return:
        """
        # Allow use by server admins and in DMs
        if context.guild is not None:
            if not context.message.author.guild_permissions.administrator:
                return
        embed = Embed(title="Help (click for docs)", colour=0xffff00,
                      url="https://github.com/tvdhout/queue-manager/blob/main/README.md",)
        embed.set_footer(text="Made by Thijs#9356",
                         icon_url="https://cdn.discordapp.com/avatars/289163010835087360"
                                  "/f7874fb1b63d84359307b8736f559355.webp?size=128")
        embed.add_field(name=f"Setup",
                        value="This bot is used to manage a queue of questions and archive them "
                              "when answered. This bot requires a small setup to be functional. You must set the "
                              "channel in which to archive messages, the channels which are treated as queues, "
                              "and the roles that can manage queues. See below on how to declare these.",
                        inline=False)
        embed.add_field(name="Command usage",
                        value=f"`{PREFIX}help` → Show this menu.\n"
                              f"`{PREFIX}archive` → Use this command in the channel you want to use as archive.\n"
                              f"`{PREFIX}queues #channels` → Declare channels as queues. You can "
                              f"tag one or multiple channels: `{PREFIX}queue #channel` / `{PREFIX}queues #channel1 "
                              f"#channel2 ...`\n"
                              f"`{PREFIX}roles` → Declare roles as queue managers. You can tag one or multiple roles:\n"
                              f"`{PREFIX}role @Role` / `{PREFIX}roles @Role1 @Role2 ...`\n"
                              f"`{PREFIX}config` → Show the current Queue Manager configurations for this server.\n"
                              f"`{PREFIX}reset` → Clear all configurations for this server.")
        embed.add_field(name="Queue management",
                        value="When a regular user sends a message in a queue channel, the bot wil reply with "
                              ":inbox_tray:. Consecutive messages by the same user (ignoring interruptions by "
                              "managers) are regarded as one. A queue manager can click on the :inbox_tray: reaction "
                              "to claim the question. Once answered it can be archived by clicking on the "
                              ":outbox_tray: reaction. Queue managers that are not the claimer of a question can "
                              "still archive it, after clicking on the :white_check_mark: for confirmation, "
                              "to avoid accidentally archiving a message they did not claim.",
                        inline=False)
        await context.send(embed=embed)


def setup(client: QueueManager):
    client.add_cog(CommandsCog(client))
