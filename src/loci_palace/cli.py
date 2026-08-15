"""
Command-line interface for loci-palace.

    loci preflight [--vault PATH]   check the environment
    loci init [PATH] [--force]      scaffold a vault
    loci doctor [--vault PATH]      diagnose an existing vault

Design notes:

- No install-time side effects. Nothing touches the filesystem until the user
  explicitly runs `init`. Packages that write on install are a supply-chain
  smell, and a colleague evaluating this should not have to take it on trust.

- `init` scaffolds structure and prompts; it never invents content. Templates
  carry placeholders, not plausible defaults, because a plausible default is a
  fact nobody verified.

- The vault folder name has NO default. It is a choice, not a compiled value,
  so init asks. Automate what is compiled; never automate what is chosen.

- Two config files, deliberately:
    .loci.json        tracked    - vault_dir, machinery version. Vault-specific,
                                   must survive a clone.
    .loci-local.json  gitignored - absolute paths, private terms. Machine-specific,
                                   must never enter tracked memory.

- Zero third-party dependencies. Stdlib only.
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

__version__ = "0.1.0"

PKG_ROOT = Path(__file__).resolve().parent
TEMPLATES = PKG_ROOT / "templates"
VIEWS = PKG_ROOT / "views"
HOOKS = PKG_ROOT / "hooks"
SCRIPTS = PKG_ROOT / "scripts"

CONFIG_FILE = ".loci.json"
LOCAL_CONFIG_FILE = ".loci-local.json"

CONTENT_DIRS = ["Context", "Projects", "Sessions", "Archive"]
MACHINERY_DIRS = ["System", "System/hooks", "Views"]

RESERVED_NAMES = {".git", ".obsidian", "dist", "node_modules", "src", "__pycache__"}


def say(msg=""):
    print(msg)


def step(msg):
    print(f"  {msg}")


def die(msg, code=1):
    print(f"\nerror: {msg}", file=sys.stderr)
    sys.exit(code)


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def read_config(target: Path):
    path = target / CONFIG_FILE
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def resolve_vault_dir(target: Path):
    """Vault folder name from config, else detect a single candidate, else None."""
    cfg = read_config(target)
    if cfg.get("vault_dir"):
        return cfg["vault_dir"]

    if not target.is_dir():
        return None

    candidates = [
        d.name for d in sorted(target.iterdir())
        if d.is_dir()
        and d.name not in RESERVED_NAMES
        and not d.name.startswith(".")
        and (d / "System").is_dir()
    ]
    return candidates[0] if len(candidates) == 1 else None


def valid_dir_name(name):
    if not name or name != name.strip():
        return "cannot be empty or padded with spaces"
    if "/" in name or "\\" in name:
        return "cannot contain a path separator"
    if name.startswith("."):
        return "cannot start with a dot"
    if name in RESERVED_NAMES:
        return f"'{name}' is reserved"
    return None


def prompt_vault_dir():
    say("What should the vault folder be called?")
    say()
    say("  This is the directory holding your notes - Palace/, Notes/, Brain/,")
    say("  or your assistant's name. It appears in every path the assistant")
    say("  reads, so pick something you will not want to rename later.")
    say()
    say("  There is no default: this is your choice, not the tool's.")
    say()
    while True:
        try:
            name = input("  Vault folder name: ").strip()
        except (EOFError, KeyboardInterrupt):
            say()
            die("cancelled - nothing was written")
        problem = valid_dir_name(name)
        if problem:
            say(f"  -> {problem}")
            continue
        return name


# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------

def run_preflight(vault=None):
    script = SCRIPTS / "preflight.sh"
    if not script.is_file():
        say("  (preflight script not bundled - skipping environment checks)")
        return 0
    cmd = ["bash", str(script)]
    if vault:
        cmd += ["--vault", str(vault)]
    return subprocess.call(cmd)


def cmd_preflight(args):
    sys.exit(run_preflight(args.vault))


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------

def copy_tree(src: Path, dest: Path):
    if not src.is_dir():
        return 0
    count = 0
    for item in sorted(src.rglob("*")):
        if item.is_dir():
            continue
        out = dest / item.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, out)
        count += 1
    return count


def write_template(name, dest: Path, subst, force):
    src = TEMPLATES / name
    if not src.is_file():
        return None
    if dest.exists() and not force:
        return "kept"
    text = src.read_text(encoding="utf-8")
    for key, val in subst.items():
        text = text.replace("{{%s}}" % key, val)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return "wrote"


def cmd_init(args):
    target = Path(args.path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    say()
    say(f"Initialising a vault at {target}")
    say()

    vault_dir = args.vault_dir or resolve_vault_dir(target)
    if vault_dir:
        problem = valid_dir_name(vault_dir)
        if problem:
            die(f"vault folder name {problem}")
        say(f"Using vault folder: {vault_dir}/")
        say()
    else:
        vault_dir = prompt_vault_dir()
        say()

    vault = target / vault_dir

    if vault.exists() and not args.force:
        die(f"{vault} already exists\n"
            f"       re-run with --force to refresh machinery "
            f"(content is never touched)")

    if not args.skip_preflight:
        say("Checking environment...")
        if run_preflight(target) != 0:
            say()
            say("Preflight failed. Fix the failures above, or re-run with")
            say("--skip-preflight to scaffold anyway. The vault will not work")
            say("until they are resolved.")
            sys.exit(1)
        say()

    say("Creating structure...")
    for d in CONTENT_DIRS + MACHINERY_DIRS:
        (vault / d).mkdir(parents=True, exist_ok=True)
        step(f"{vault_dir}/{d}/")

    say()
    say("Installing machinery...")
    step(f"{copy_tree(SCRIPTS, vault / 'System')} script(s)")
    step(f"{copy_tree(VIEWS, vault / 'Views')} view(s)")
    step(f"{copy_tree(HOOKS, vault / 'System' / 'hooks')} hook(s)")

    hook = vault / "System" / "hooks" / "pre-commit"
    if hook.is_file():
        hook.chmod(0o755)

    subst = {"DATE": date.today().isoformat(), "VAULT_DIR": vault_dir}

    say()
    say("Writing templates...")
    for name, dest in (
        ("CRITICAL_FACTS.md", vault / "Context" / "CRITICAL_FACTS.md"),
        ("Decisions.md", vault / "Context" / "Decisions.md"),
        ("Index.md", vault / "Index.md"),
        ("Schema.md", vault / "System" / "Schema.md"),
        ("CLAUDE.md", target / "CLAUDE.md"),
        ("gitignore", target / ".gitignore"),
        ("loci-local.json.example", target / (LOCAL_CONFIG_FILE + ".example")),
    ):
        result = write_template(name, dest, subst, args.force)
        if result:
            step(f"{result} {dest.relative_to(target)}")

    config = read_config(target)
    config.update({"vault_dir": vault_dir, "machinery_version": __version__})
    (target / CONFIG_FILE).write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    step(f"wrote {CONFIG_FILE}")

    say()
    say("Setting up git...")
    if (target / ".git").is_dir():
        step("repository already initialised")
    else:
        subprocess.call(["git", "init", "-q"], cwd=target)
        step("git init")
    subprocess.call(
        ["git", "config", "core.hooksPath", f"{vault_dir}/System/hooks"],
        cwd=target,
    )
    step(f"core.hooksPath -> {vault_dir}/System/hooks")

    say()
    say("-" * 58)
    say("  Scaffolded. Three things left, and only you can do them:")
    say()
    say(f"  1. Fill in {vault_dir}/Context/CRITICAL_FACTS.md")
    say("     It ships as prompts, not defaults. An unfilled placeholder is")
    say("     worse than an absent fact - the assistant will believe it.")
    say()
    say("  2. Point your MCP server at this vault and open it in your editor.")
    say()
    say("  3. Then:")
    say(f"       cd {target}")
    say(f"       python3 {vault_dir}/System/manifest.py")
    say("       git add -A && git commit -m 'Initial vault'")
    say("-" * 58)
    say()


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------

def cmd_doctor(args):
    target = Path(args.vault or ".").expanduser().resolve()

    say()
    say(f"Diagnosing {target}")
    say()

    vault_dir = resolve_vault_dir(target)
    if not vault_dir:
        die(f"no vault found here. Expected {CONFIG_FILE}, or a single folder "
            f"containing System/.\n       Run `loci init` first.")

    vault = target / vault_dir
    if not vault.is_dir():
        die(f"{CONFIG_FILE} names '{vault_dir}' but that folder does not exist")

    say(f"Vault folder: {vault_dir}/")
    say()

    problems = 0

    say("Environment:")
    if run_preflight(target) != 0:
        problems += 1

    say()
    say("Vault:")
    for script, extra in (("lint.py", []), ("manifest.py", ["--check"])):
        path = vault / "System" / script
        if not path.is_file():
            step(f"[FAIL] {script} missing")
            problems += 1
            continue
        if subprocess.call([sys.executable, str(path)] + extra, cwd=target) != 0:
            problems += 1

    say()
    say("Git:")
    if (target / ".git").is_dir():
        out = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=target, capture_output=True, text=True,
        ).stdout.strip()
        expected = f"{vault_dir}/System/hooks"
        if out == expected:
            step("[ OK ] pre-commit hook active")
        else:
            step(f"[WARN] core.hooksPath is '{out or 'unset'}', expected '{expected}'")
            step(f"       fix: git config core.hooksPath {expected}")
            problems += 1
    else:
        step("[WARN] not a git repository - no rollback, no hook enforcement")
        problems += 1

    say()
    say("-" * 58)
    if problems:
        say(f"  {problems} problem area(s). See above.")
        say("-" * 58)
        sys.exit(1)
    say("  Healthy.")
    say("-" * 58)


# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="loci",
        description="Scaffold and maintain a structured Markdown memory vault.",
    )
    parser.add_argument("--version", action="version",
                        version=f"loci-palace {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("preflight", help="check the environment")
    p.add_argument("--vault", default=None)
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("init", help="scaffold a new vault")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--vault-dir", default=None,
                   help="vault folder name (skips the prompt)")
    p.add_argument("--force", action="store_true",
                   help="refresh machinery (never touches content)")
    p.add_argument("--skip-preflight", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("doctor", help="diagnose an existing vault")
    p.add_argument("--vault", default=None)
    p.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    main()
