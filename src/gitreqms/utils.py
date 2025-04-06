from rich.console import Console

console = Console()

def pprint(what: str):
    console.print(what)  # type: ignore
