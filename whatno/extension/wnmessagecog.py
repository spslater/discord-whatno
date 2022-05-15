"""Test and general functions Cog"""
import logging

from discord.ext.commands import Cog, group, is_owner

logger = logging.getLogger(__name__)


def setup(bot):
    """Add the Test Cog to the Bot"""
    bot.add_cog(WNMessageCog(bot))


class WNMessageCog(Cog, name="Manage Messages"):
    """Manage messages for the WhatnoBot"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @is_owner()
    @group(name="msg")
    async def msg(self, ctx):
        """Manage bot about extensions"""
        if ctx.invoked_subcommand:
            return
        msg = (
            "```\n"
            "reload(cid, *mids): reload multiple messages in "
            "the given channel by \"editing\" them\n"
            "delete(cid, *mids): delete multiple messages from the given channel\n"
            "edit(cid, mid, content): edit message to display new content, "
            "need to quote value to get full message\n"
            "send(cid, content): send content and any embeds and attachments to the given channel\n"
            "```"
        )
        await ctx.send(msg)

    @is_owner()
    @msg.command(name="reload")
    async def reload(self, ctx, cid, *mids):
        """reload a message"""
        try:
            channel = await self.bot.fetch_channel(int(cid))
        except ValueError:
            await ctx.send(f"\N{ANGRY FACE} invalid channel: {cid}")
            return

        invalid = []
        notown = []
        for mid in mids:
            try:
                msg = await channel.fetch_message(int(mid))
            except ValueError:
                invalid.append(mid)
                continue

            if msg.author.id != self.bot.user.id:
                notown.append(mid)
                continue

            await msg.edit(
                content=msg.content,
                embeds=msg.embeds,
                files=msg.attachments,
            )
        if invalid or notown:
            await ctx.send(f"\N{ANGRY FACE} invalid: {invalid} | not own: {notown}")
        else:
            await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @is_owner()
    @msg.command(name="delete")
    async def delete(self, ctx, cid, *mids):
        """delete a message"""
        try:
            channel = await self.bot.fetch_channel(int(cid))
        except ValueError:
            await ctx.send(f"\N{ANGRY FACE} invalid channel: {cid}")
            return

        invalid = []
        notown = []
        for mid in mids:
            try:
                msg = await channel.fetch_message(int(mid))
            except ValueError:
                invalid.append(mid)
                continue

            if msg.author.id != self.bot.user.id:
                notown.append(mid)
                continue

            await msg.delete()
        if invalid or notown:
            await ctx.send(f"\N{ANGRY FACE} invalid: {invalid} | not own: {notown}")
        else:
            await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @is_owner()
    @msg.command(name="edit")
    async def edit(self, ctx, cid, mid, content):
        """edit a message"""
        try:
            channel = await self.bot.fetch_channel(int(cid))
        except ValueError:
            await ctx.send(f"\N{ANGRY FACE} invalid channel: {cid}")
            return

        try:
            msg = await channel.fetch_message(int(mid))
        except ValueError:
            await ctx.send(f"\N{ANGRY FACE} Given message id is not valid: `{mid}`")
            return

        if msg.author.id != self.bot.user.id:
            await ctx.send("\N{ANGRY FACE} Can only edit the bot's messages")
            return

        await msg.edit(content=content)
        await ctx.message.add_reaction("\N{OK HAND SIGN}")

    @is_owner()
    @msg.command(name="send")
    async def send(self, ctx, cid, content):
        """send a new message"""
        try:
            channel = await self.bot.fetch_channel(int(cid))
        except ValueError:
            await ctx.send(f"\N{ANGRY FACE} invalid channel: {cid}")
            return

        print("embeds", ctx.message.embeds)
        print("attachments", ctx.message.attachments)

        attachments = [
            await attach.to_file(spoiler=attach.is_spoiler())
            for attach in ctx.message.attachments
        ]

        await channel.send(
            content=content,
            embeds=ctx.message.embeds,
            files=attachments,
        )
        await ctx.message.add_reaction("\N{OK HAND SIGN}")
