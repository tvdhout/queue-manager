from sys import stderr
from typing import List

import discord
import asyncio
from discord import Reaction, User, Member, Embed
from discord.ext import commands
import mysql.connector

from config import PREFIX, TOKEN


class QueueManager(commands.Bot):
    def __init__(self, dbconnection: mysql.connector.MySQLConnection, command_prefix: str):
        super().__init__(command_prefix)
        self.dbconnection = dbconnection
        self.question_channels = []

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message: discord.Message):
        # TODO: just in ?questions channels
        if message.author.id == self.user.id:
            return  # The bot should not react to its own message
        if len(message.author.roles) != 1:
            await self.process_commands(message)
            return  # The bot should not react to messages from roles other than @everyone
        try:
            previous_message = (await message.channel.history(limit=2).flatten())[1]
            if previous_message.author == message.author:
                return  # previous message was from the same user, don't react
        except IndexError:
            pass
        await message.add_reaction('📥')
        await self.process_commands(message)

    async def on_reaction_add(self, reaction: Reaction, user: Member):
        if isinstance(user, User) or user == self.user:
            return  # Reaction is in DM, or the bot added the reaction
        if len(user.roles) == 1:  # student added reaction
            await reaction.remove(user)
            return
        if reaction.emoji == '📥':
            await reaction.message.clear_reactions()
            await reaction.message.add_reaction('📤')
            cursor = self.dbconnection.cursor()
            cursor.execute("INSERT IGNORE INTO messages "
                           "(messageid, ownerid) VALUES (%s, %s)",
                           (str(reaction.message.id), str(user.id)))
            if cursor.rowcount > 0:
                reply = await reaction.message.reply(f"{user.mention} will answer your question.")
                await asyncio.sleep(5)
                await reply.delete()
            self.dbconnection.commit()
        elif reaction.emoji == '📤':
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
            if owner_id != str(user.id):
                await reaction.remove(user)
                return
            cursor.execute("SELECT archiveid FROM servers WHERE serverid = %s",
                           (str(user.guild.id),))
            try:
                archive_id = cursor.fetchall()[0][0]
                self.dbconnection.commit()
            except IndexError:
                print("Index Error 69")
                return
            embed = Embed(title=f"Question by {reaction.message.author.name}",
                          timestamp=reaction.message.created_at,
                          thumbnail=reaction.message.author.avatar_url,
                          colour=0xff0000)
            embed.add_field(name=f"Content:",
                            value=reaction.message.content)
            channel = user.guild.get_channel(int(archive_id))
            if channel is not None:
                await channel.send(embed=embed)
                await reaction.message.delete()


if __name__ == "__main__":
    try:
        connection = mysql.connector.connect(user='thijs',
                                             host='localhost',
                                             database='queuemanager')
        try:
            client = QueueManager(dbconnection=connection, command_prefix=PREFIX)
            client.load_extension('commands')
            client.run(TOKEN)
        except KeyboardInterrupt:
            print("Closing database connection.")
            connection.commit()
            connection.close()
    except mysql.connector.Error:
        print("Connection to database failed.", file=stderr)
        exit(-1)
