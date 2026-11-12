from bumpass_bot.handlers import commands, forward

# Every event runs through these in order. A handler returns True to stop the ones after it,
# so anything that should keep a message from being forwarded goes before forward.handle.
HANDLERS = [commands.handle, forward.handle]
