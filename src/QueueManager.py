from sys import stderr
from typing import List, Set, Dict, Optional
import discord
import asyncio
from discord import Reaction, User, Member, Embed, Message, Guild
from discord.ext import commands
import mysql.connector

from server_conf import ServerConfiguration
from config import config
TOKEN, PREFIX = config(release=False)


class QueueManager(commands.Bot):
    def __init__(self, dbconnection: mysql.connector.MySQLConnection, **kwargs):
        super().__init__(**kwargs)
        self.dbconnection = dbconnection
        self.server_confs: Dict[int, ServerConfiguration] = {}  # server_id : server configuration

    def get_server_conf(self, guild: Guild) -> ServerConfiguration:
        guild_id = guild.id
        if guild_id not in self.server_confs:
            self.server_confs[guild_id] = ServerConfiguration(guild_id, self.dbconnection)
        return self.server_confs[guild_id]

    def get_queue_channels(self, guild: Guild) -> List[int]:
        """
        Get the channels that are declared as queues for this server.
        @param guild: discord.Guild: The server for which to retrieve the queue channels
        @return: List[int]: a List of channel IDs
        """
        return self.get_server_conf(guild).queue_ids

    def get_manager_roles(self, guild: Guild) -> Set[int]:
        """
        Get the roles that are declared to be queue managers for this server.
        @param guild: discord.Guild: The server for which to retrieve the queue manager roles
        @return: Set[int]: a Set of roles IDs
        """
        return self.get_server_conf(guild).role_ids

    def is_manager(self, member: Member, manager_roles: Set[int] = None) -> bool:
        """
        Determine if member is a queue manager.
        @param member: discord.Member: The member to check
        @param manager_roles: Optional[Set[int]]: The roles of queue managers. If None, it will be requested
        @return: bool: Whether is member is a queue manager or not
        """
        if manager_roles is None:
            manager_roles = self.get_manager_roles(member.guild)
        member_roles = set(map(lambda r: r.id, member.roles))
        return len(member_roles & manager_roles) > 0  # Intersect is non-empty means they have a manager role.

    async def archive(self, message: Message, reaction: Reaction):
        """
        Archive the given message by sending it in the archive channel and removing it from the queue.
        @param message: discord.Message: The message to archive
        @param reaction: discord.Reaction: Reaction that triggered the archive event
        @return:
        """
        # Get the archive channel
        try:
            archive_id = self.get_server_conf(message.guild).archive_id  # int or None
            channel = message.guild.get_channel(int(archive_id))
        except TypeError:
            reactor: Optional[Member] = None
            async for user in reaction.users():  # Find the manager that tried to archive this message
                if user == self.user:
                    continue
                reactor = user
                break
            await reaction.remove(reactor)
            m = await message.channel.send(f"{reactor.mention} There is not yet an archive channel for this server. "
                                           f"Use the `{PREFIX}archive` command in the channel you wish to use as "
                                           f"archive.")
            await asyncio.sleep(8)
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
        manager_roles = self.get_manager_roles(author.guild)
        async for m in message.channel.history(after=message, limit=25):  # Look in history from /message/ to now
            if m.author == author:  # Add messages from the same user to the chain
                embed.add_field(name=f"{m.author.display_name}:", value=m.content, inline=False)
                await m.delete()
            elif self.is_manager(m.author, manager_roles):  # Managers may interrupt, info may be useful, add to chain
                embed.add_field(name=f"{m.author.display_name}:", value=m.content, inline=False)
            else:
                break
        await message.delete()
        await channel.send(embed=embed)

        # Delete message from database
        cursor = self.dbconnection.cursor()
        cursor.execute("DELETE FROM messages WHERE messageid = %s",
                       (str(message.id),))
        self.dbconnection.commit()

    # Bot event handlers:

    async def on_ready(self):
        """
        Event handler. Triggered when the bot logs in.
        @return:
        """
        print(f"Logged in as {self.user}")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{PREFIX}help"))

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
        if message.channel.id not in self.get_queue_channels(message.guild) or self.is_manager(message.author):
            await self.process_commands(message)
            return

        chain = False  # This is not the continuation of a previous message until proven otherwise
        manager_roles = self.get_manager_roles(message.author.guild)
        async for prev_message in message.channel.history(limit=15):  # Look in message history for chain
            if prev_message == message:  # Don't look at the current message
                continue
            if prev_message.author == message.author:  # This is a continuation of a previous message.
                chain = True
                break
            member = message.guild.get_member(prev_message.author.id)
            if self.is_manager(member, manager_roles):
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
        if reaction.message.channel.id not in self.get_queue_channels(reaction.message.guild):
            return
        if not self.is_manager(member):  # Not a manager
            await reaction.remove(member)
            return
        if reaction.emoji == '📥':  # Manager clicked to claim this message.
            await reaction.message.clear_reactions()
            await reaction.message.add_reaction('📤')
            cursor = self.dbconnection.cursor()
            cursor.execute("INSERT IGNORE INTO messages "
                           "(messageid, ownerid) VALUES (%s, %s)",
                           (str(reaction.message.id), str(member.id)))  # Set that manager as owner of this question.
            if cursor.rowcount > 0:  # Rows changed -> message was not yet claimed (can only happen in a split second)
                reply = await reaction.message.reply(f"{member.mention} will answer your question.")
                await asyncio.sleep(5)
                await reply.delete()
            self.dbconnection.commit()
        elif reaction.emoji == '📤':  # Manager clicked to archive this message.
            cursor = self.dbconnection.cursor()
            cursor.execute("SELECT ownerid FROM messages WHERE messageid = %s",
                           (str(reaction.message.id),))
            try:
                owner_id = cursor.fetchall()[0][0]
                self.dbconnection.commit()
            except IndexError:
                await reaction.message.clear_reactions()
                await reaction.message.add_reaction('📥')
                return
            if owner_id != str(member.id):  # If the manager did not claim the message they need to confirm the request.
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
    try:
        connection = mysql.connector.connect(user='thijs',
                                             host='localhost',
                                             database='queuemanager')
        try:
            intents = discord.Intents.default()
            intents.members = True  # Need the members intent to use guild.get_member in on_message
            client = QueueManager(dbconnection=connection, command_prefix=PREFIX, intents=intents)
            client.remove_command('help')  # Remove the default help command
            client.load_extension('commands')  # Load the commands defined in commands.py
            client.run(TOKEN)
        except KeyboardInterrupt:
            print("Closing database connection.")
            connection.commit()
            connection.close()
    except mysql.connector.Error:
        print("Connection to database failed.", file=stderr)
        exit(-1)
