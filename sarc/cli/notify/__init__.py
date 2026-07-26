from dataclasses import dataclass

from simple_parsing import subparsers

from .usage import UsageNotifyCommand


@dataclass
class Notify:
    command: UsageNotifyCommand = subparsers(
        {"usage": UsageNotifyCommand}  # ty:ignore[invalid-argument-type]
    )

    def execute(self) -> int:
        return self.command.execute()
