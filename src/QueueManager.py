from sys import stderr
from typing import List, Set
import discord
import asyncio
from discord import Reaction, User, Member, Embed, Message, Guild
from discord.ext import commands
import mysql.connector

from config import PREFIX, TOKEN


class QueueManager(commands.Bot):
    def __init__(self, dbconnection: mysql.connector.MySQLConnection, **kwargs):
        super().__init__(**kwargs)
        self.dbconnection = dbconnection

    def get_queue_channels(self, guild: Guild) -> List[int]:
        server_id = str(guild.id)
        cursor = self.dbconnection.cursor()
        cursor.execute("SELECT queues FROM servers WHERE serverid = %s",
                       (server_id,))
        try:
            channels_string = cursor.fetchall()[0][0]
            channels = channels_string.split()
            channels = list(map(int, channels))  # cast to ints
            return channels
        except (IndexError, AttributeError):  # server not in database or question channels not set
            return []

    def get_manager_roles(self, guild: Guild) -> Set[int]:
        server_id = str(guild.id)
        cursor = self.dbconnection.cursor()
        cursor.execute("SELECT roles FROM servers WHERE serverid = %s",
                       (server_id,))
        try:
            roles_string = cursor.fetchall()[0][0]
            roles = roles_string.split()
            roles = set(map(int, roles))  # cast to ints
            return roles
        except (IndexError, AttributeError):  # server not in database or question channels not set
            return set()

    def is_manager(self, member: Member, manager_roles: Set[int] = None):
        if manager_roles is None:
            manager_roles = self.get_manager_roles(member.guild)
        member_roles = set(map(lambda r: r.id, member.roles))
        return len(member_roles & manager_roles) > 0  # Intersect is non-empty means they have a manager role.

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="?help"))

    async def archive(self, message: Message):
        """
        Archive this message and those in the same chain
        """
        # Get the archive channel
        cursor = self.dbconnection.cursor()
        cursor.execute("SELECT archiveid FROM servers WHERE serverid = %s",
                       (str(message.guild.id),))
        try:
            archive_id = cursor.fetchall()[0][0]
            self.dbconnection.commit()
            channel = message.guild.get_channel(int(archive_id))
            if channel is None:
                raise TypeError
        except (IndexError, TypeError):  # No archive channel set
            m = await message.channel.send(f"There is not yet an archive channel for this server. Use the "
                                           f"`{PREFIX}archive` command in the channel you wish to use as archive.")
            await asyncio.sleep(8)
            await m.delete()
            return

        author = message.author
        embed = Embed(title=f"Question by {author.display_name} ({author.name}#{author.discriminator})",
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

    async def on_message(self, message: discord.Message):
        if message.author.id == self.user.id:  # The bot should not react to its own message
            return
        # The bot should not be concerned with any channel that is not a queue, and should not react to manager roles.
        if message.channel.id not in self.get_queue_channels(message.guild) or self.is_manager(message.author):
            await self.process_commands(message)
            return

        chain = False  # This is not the continuation of a previous message until proven otherwise
        manager_roles = self.get_manager_roles(message.author.guild)
        async for prev_message in message.channel.history(limit=30):  # Look in message history for chain
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
        if isinstance(member, User) or member == self.user:  # Reaction is in a DM, or the bot added the reaction
            return
        if not self.is_manager(member):  # Not a manager
            await reaction.remove(member)
            return
        if reaction.emoji == '📥':  # TA clicked to claim this message.
            await reaction.message.clear_reactions()
            await reaction.message.add_reaction('📤')
            cursor = self.dbconnection.cursor()
            cursor.execute("INSERT IGNORE INTO messages "
                           "(messageid, ownerid) VALUES (%s, %s)",
                           (str(reaction.message.id), str(member.id)))  # Set that TA as owner of this question.
            if cursor.rowcount > 0:
                reply = await reaction.message.reply(f"{member.mention} will answer your question.")
                await asyncio.sleep(5)
                await reply.delete()
            self.dbconnection.commit()
        elif reaction.emoji == '📤':  # TA clicked to archive this message.
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
            if owner_id != str(member.id):  # If the TA did not claim the message, they need to confirm their request.
                await reaction.remove(member)
                await reaction.message.add_reaction('✅')
                await asyncio.sleep(4)
                try:
                    await reaction.message.remove_reaction('✅', self.user)  # Okay, never mind.
                except discord.errors.NotFound:  # They confirmed.
                    pass
                return
            await self.archive(reaction.message)
        elif reaction.emoji == '✅':
            await self.archive(reaction.message)
        else:  # remove any other reactions than those mentioned above.
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
            client.remove_command('help')
            client.load_extension('commands')
            client.run(TOKEN)
        except KeyboardInterrupt:
            print("Closing database connection.")
            connection.commit()
            connection.close()
    except mysql.connector.Error:
        print("Connection to database failed.", file=stderr)
        exit(-1)
