import os

import click


class Repo(object):
    def __init__(self, home=None, debug=False):
        self.home = os.path.abspath(home or ".")
        self.debug = debug


@click.group()
@click.option("--repo-home", envvar="REPO_HOME", default=".repo")
@click.option("--debug/--no-debug", default=False, envvar="REPO_DEBUG")
@click.pass_context
def cli(ctx, repo_home, debug):
    ctx.obj = Repo(repo_home, debug)


pass_repo = click.make_pass_decorator(Repo)


@cli.command()
@click.argument("src")
@click.argument("dest", required=False)
@pass_repo
def clone(repo, src, dest):
    pass


@cli.command()
@pass_repo
def cp(repo):
    click.echo(isinstance(repo, Repo))


if __name__ == "__main__":
    cli()
