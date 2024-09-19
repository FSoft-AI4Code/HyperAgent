import os

from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.completion.filesystem import PathCompleter
from rich.console import Console as RawConsole
from rich.markdown import Markdown


class Console:
    def __init__(self, history_dir=".history"):
        os.makedirs(history_dir, exist_ok=True)
        self.prompt_history = FileHistory(os.path.join(history_dir, "question"))
        self.prompt_file_history = FileHistory(os.path.join(history_dir, "file"))
        self.prompt_auto_suggest = AutoSuggestFromHistory()
        self.prompt_style = Style.from_dict({"prompt": "#7fff00 bold", "": "#ADD8E6"})
        self._console = RawConsole()

    def print(self, text, render=True):
        if render:
            self._console.print(Markdown(text))
        else:
            self._console.print(text)

    def info(self, text):
        self._console.print(f"[blue]{text}[/blue]")
    
    def info2(self, text):
        self._console.print(f"[cyan]{text}[/cyan]")

    def warning(self, text):
        self._console.print(f"[yellow]{text}[/yellow]")

    def error(self, text):
        self._console.print(f"[red]{text}[/red]")

    def bot_prompt(self):
        self._console.print(f"\n[green][bold]Bot: [/bold][/green]")

    def print_history_item(self, idx, entry):
        summary = entry[:self._console.width - 20]
        self._console.print(f"[bold]{idx:>4}: [/bold] {summary}...")

    def file_prompt(self):
        return prompt(
            "File: ",
            history=self.prompt_file_history,
            completer=PathCompleter(),
            auto_suggest=self.prompt_auto_suggest,
            style=self.prompt_style,
        )

    def user_prompt(self, long=False):
        if long:
            return prompt(
                "> ",
                multiline=True,
                history=self.prompt_history,
                auto_suggest=self.prompt_auto_suggest,
                style=self.prompt_style,
                prompt_continuation="> ",
            )
        else:
            return prompt(
                "You: ",
                history=self.prompt_history,
                auto_suggest=self.prompt_auto_suggest,
                style=self.prompt_style,
            )

    def prompt(self, text, is_password=False):
        return prompt(
            text,
            is_password=is_password,
            history=self.prompt_history if not is_password else None,
            auto_suggest=self.prompt_auto_suggest,
            style=self.prompt_style,
        )

    def gap(self):
        self._console.print("")