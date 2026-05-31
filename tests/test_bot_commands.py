from __future__ import annotations

from pwrbot.bot.app import configure_bot_commands


class FakeBot:
    def __init__(self) -> None:
        self.commands = None

    async def set_my_commands(self, commands):
        self.commands = commands


async def test_configure_bot_commands_registers_slash_menu_commands() -> None:
    bot = FakeBot()

    await configure_bot_commands(bot)

    assert bot.commands is not None
    command_names = [command.command for command in bot.commands]
    assert command_names == [
        "help",
        "log",
        "today",
        "lastworkout",
        "week",
        "analyze",
        "stats",
        "1rm",
        "prs",
        "volume",
        "predict",
        "charts",
        "chart",
        "delete_last",
        "edit_last",
        "add",
        "append",
    ]
    assert all(command.description for command in bot.commands)
