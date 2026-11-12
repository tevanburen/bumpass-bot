from bumpass_bot.handlers import forward, members, status

# Every event runs through these in order. A handler returns True to stop the ones after it,
# so anything that should keep a message from being forwarded goes before forward.handle.
HANDLERS = [status.handle, members.handle, forward.handle]
