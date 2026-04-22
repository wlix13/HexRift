import sys

import rich

from hexrift.app import cli
from hexrift.errors import Error


def main() -> None:
    try:
        cli()
    except Error as e:
        rich.print(str(e))
        sys.exit(1)
    except Exception as e:
        rich.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
