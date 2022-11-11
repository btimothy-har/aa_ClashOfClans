from .discordutils import clash_embed, user_confirmation, multiple_choice_select

class TerminateProcessing(Exception):
    """Raise this exception when processing should be terminated."""
    def __init__(self, exc):
        self.message = exc.message
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message}'

class InvalidTag(Exception):
    """Raise this when a Clash Tag is invalid."""
    def __init__(self,tag):
        self.message = f'The tag `{tag}` is invalid.'
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message}'

async def no_clans_registered(ctx):
    eEmbed = await clash_embed(ctx=ctx,
        message=f"There are no clans registered to the Alliance.",
        color="fail")
    return await ctx.send(embed=eEmbed)


async def error_not_valid_abbreviation(ctx,abbr_input):
    eEmbed = await clash_embed(ctx=ctx,
        message=f"The abbreviation `{abbr_input}` does not correspond to any Alliance clan.",
        color="fail")
    return await ctx.send(embed=eEmbed)

async def error_end_processing(ctx,preamble,err):
    eEmbed = await clash_embed(ctx=ctx,
        message=f"{preamble}: {err}",
        color="fail")
    return await ctx.send(embed=eEmbed)