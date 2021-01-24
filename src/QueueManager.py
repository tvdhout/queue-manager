from typing import Set, Dict, Optional
import discord
import asyncio
from discord import Reaction, User, Member, Embed, Message, Guild, TextChannel, Role
from discord.ext import commands

from server_conf import ServerConfiguration
from database_connection import execute_query
from config import config

TOKEN, PREFIX = config(release=True)


class QueueManager(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Keeps track of server configurations in a session to limit the amount of database traffic.
        self.server_confs: Dict[Guild, ServerConfiguration] = {}

    def get_server_conf(self, server: Guild) -> ServerConfiguration:
        """
        Set the ServerConfiguration for the given server
        @param server: discord.Guild: The server for which to retrieve the configuration
        @return: ServerConfiguration: The configuration
        """
        if server not in self.server_confs:
            self.server_confs[server] = ServerConfiguration(server)
        return self.server_confs[server]

    def get_queue_channels(self, guild: Guild) -> Set[TextChannel]:
        """
        Get the channels that are declared as queues for this server.
        @param guild: discord.Guild: The server for which to retrieve the queue channels
        @return: Set[TextChannel]: a Set of channels
        """
        return self.get_server_conf(guild).queues

    def get_manager_roles(self, guild: Guild) -> Set[Role]:
        """
        Get the roles that are declared to be queue managers for this server.
        @param guild: discord.Guild: The server for which to retrieve the queue manager roles
        @return: Set[Role]: a Set of roles
        """
        return self.get_server_conf(guild).roles

    def is_manager(self, member: Member) -> bool:
        """
        Determine if member is a queue manager.
        @param member: discord.Member: The member to check
        @return: bool: Whether is member is a queue manager or not
        """
        manager_roles = self.get_manager_roles(member.guild)
        return len(set(member.roles) & manager_roles) > 0  # Intersect is non-empty means they have a manager role.

    async def archive(self, message: Message, reaction: Reaction) -> None:
        """
        Archive the given message by sending it in the archive channel and removing it from the queue.
        @param message: discord.Message: The message to archive
        @param reaction: discord.Reaction: Reaction that triggered the archive event
        @return:
        """
        # Get the archive channel
        try:
            channel = message.guild.get_channel(self.get_server_conf(message.guild).archive.id)
            if channel is None:
                self.get_server_conf(message.guild).set_archive(None)
                raise TypeError
        except (TypeError, AttributeError):
            reactor: Optional[Member] = None
            async for user in reaction.users():  # Find the manager that tried to archive this message to mention them.
                if user == self.user:
                    continue
                reactor = user
                break
            await reaction.remove(reactor)
            m = await message.channel.send(f"{reactor.mention} There is not yet an archive channel for this server. "
                                           f"Use the `{PREFIX}archive` command in the channel you wish to use as "
                                           f"archive.")
            await asyncio.sleep(7)
            await m.delete()
            return

        author = message.author
        embed = Embed(title=f"Question by {author.display_name} ({author.name}#{author.discriminator}) in "
                            f"#{message.channel}",
                      timestamp=message.created_at,
                      colour=0xeeeeee)
        embed.set_thumbnail(url=author.avatar_url)
        embed.add_field(name=f"{author.display_name}:", value=message.content, inline=False)

        # Look for message chain to include.
        async for m in message.channel.history(after=message, limit=25):  # Look in history from /message/ to now
            if m.author == author:  # Add messages from the same user to the chain
                embed.add_field(name=f"{m.author.display_name}:", value=m.content, inline=False)
                await m.delete()
            elif self.is_manager(m.author):  # Managers may interrupt, info may be useful, add to chain
                embed.add_field(name=f"{m.author.display_name}:", value=m.content, inline=False)
            else:
                break
        await message.delete()
        await channel.send(embed=embed)

        # Delete message from database
        execute_query("DELETE FROM messages WHERE messageid = %s", (str(message.id),))

    # Bot event handlers:

    async def on_ready(self):
        """
        Event handler. Triggered when the bot logs in.
        @return:
        """
        print(f"Logged in as {self.user}")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{PREFIX}help"))
        execute_query("DELETE FROM messages;")  # Delete all remaining messages from a previous session.

    async def on_command_error(self, context, exception):
        """
        Event handler. Triggered when a command raises an exception. Ignore CommandNotFound, raise exception otherwise.
        @param context: discord.ext.commands.Context: The context of the command
        @param exception: Exception: The exception that was raised
        @return:
        """
        if isinstance(exception, commands.CommandNotFound):
            return
        raise exception

    async def on_message(self, message: discord.Message):
        """
        Event handler. Triggered when a message is sent in a channel visible to the bot.
        @param message: discord.Message: The message that is sent.
        @return:
        """
        if message.author.id == self.user.id:  # The bot should not react to its own message
            return
        # The bot should not be concerned with any channel that is not a queue, and should not react to manager roles.
        if message.channel not in self.get_queue_channels(message.guild) or self.is_manager(message.author):
            await self.process_commands(message)
            return

        chain = False  # This is not the continuation of a previous message until proven otherwise
        async for prev_message in message.channel.history(limit=15):  # Look in message history for chain
            if prev_message == message:  # Don't look at the current message
                continue
            if prev_message.author == message.author:  # This is a continuation of a previous message.
                chain = True
                break
            member = message.guild.get_member(prev_message.author.id)
            if self.is_manager(member):
                continue
            break
        if chain:
            return

        await message.add_reaction('📥')
        await self.process_commands(message)

    async def on_reaction_add(self, reaction: Reaction, member: Member):
        """
        Event handler. Triggers when a reaction is added to the message
        @param reaction: discord.Reaction: Reaction object
        @param member: discord.Member: Member that added the reaction
        @return:
        """
        if isinstance(member, User) or member == self.user:  # Reaction is in a DM, or the bot added the reaction
            return
        # Don't care about reaction in non-queue channels.
        if reaction.message.channel not in self.get_queue_channels(reaction.message.guild):
            return
        if not self.is_manager(member):  # Not a manager
            await reaction.remove(member)
            return
        if reaction.emoji == '📥':  # Manager clicked to claim this message.
            await reaction.message.clear_reactions()
            await reaction.message.add_reaction('📤')
            result = execute_query("INSERT IGNORE INTO messages "
                                   "(messageid, ownerid) VALUES (%s, %s)",
                                   (str(reaction.message.id), str(member.id)),
                                   return_cursor_count=True)  # Set manager as owner of this question.
            if result > 0:  # Rows changed: message wasn't yet claimed; could happen in a split second.
                reply = await reaction.message.reply(f"{member.mention} will answer your question.")
                await asyncio.sleep(5)
                await reply.delete()
        elif reaction.emoji == '📤':  # Manager clicked to archive this message.
            result = execute_query("SELECT ownerid FROM messages WHERE messageid = %s",
                                   (str(reaction.message.id),),
                                   return_result=True)
            try:
                owner_id = result[0][0]
            except IndexError:
                await reaction.message.clear_reactions()
                await reaction.message.add_reaction('📥')
                return
            if owner_id != str(member.id):  # If the manager did not claim the message they need to confirm.
                await reaction.remove(member)
                await reaction.message.add_reaction('✅')
                await asyncio.sleep(4)
                try:
                    await reaction.message.remove_reaction('✅', self.user)  # They did not confirm.
                except discord.errors.NotFound:  # They confirmed.
                    pass
                return
            await self.archive(reaction.message, reaction)
        elif reaction.emoji == '✅':
            await self.archive(reaction.message, reaction)
        else:  # Remove any other reactions than those mentioned above.
            await reaction.remove(member)
            return


if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.members = True  # Need the members intent to use guild.get_member in on_message
    client = QueueManager(command_prefix=PREFIX, intents=intents)
    client.remove_command('help')  # Remove the default help command
    client.load_extension('commands')  # Load the commands defined in commands.py
    client.run(TOKEN)
