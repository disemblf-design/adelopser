#!/usr/bin/env python3
"""独立 ALAC 修复工具 CLI"""

import sys

import click

from am_downloader.alacfix.alacfix import run as alacfix_run


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path(), required=False)
@click.option("-i", "--in-place", is_flag=True, help="Fix in place (modify original file)")
def main(input_file: str, output_file: str, in_place: bool):
    """修复损坏的 ALAC 包（TYPE_END 终止符补丁）

    \b
    用法:
        alacfix input.m4a
        alacfix -i input.m4a
        alacfix input.m4a output.m4a
    """
    if in_place and output_file:
        click.echo("Error: cannot use both -i/--in-place and output_file", err=True)
        sys.exit(1)

    try:
        if in_place or not output_file:
            alacfix_run(input_file, in_place=True)
            click.echo(f"Fixed (in place): {input_file}")
        else:
            import shutil
            shutil.copy2(input_file, output_file)
            alacfix_run(output_file, in_place=True)
            click.echo(f"Fixed: {input_file} → {output_file}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
