---
sidebar_position: 7
---

# Profile Commands Reference

This page covers all commands related to [Mercury profiles](../user-guide/profiles.md). For general CLI commands, see [CLI Commands Reference](./cli-commands.md).

## `mercury profile`

```bash
mercury profile <subcommand>
```

Top-level command for managing profiles. Running `mercury profile` without a subcommand shows help.

| Subcommand | Description |
|------------|-------------|
| `list` | List all profiles. |
| `use` | Set the active (default) profile. |
| `create` | Create a new profile. |
| `delete` | Delete a profile. |
| `show` | Show details about a profile. |
| `alias` | Regenerate the shell alias for a profile. |
| `rename` | Rename a profile. |
| `export` | Export a profile to a tar.gz archive. |
| `import` | Import a profile from a tar.gz archive. |

## `mercury profile list`

```bash
mercury profile list
```

Lists all profiles. The currently active profile is marked with `*`.

**Example:**

```bash
$ mercury profile list
  default
* work
  dev
  personal
```

No options.

## `mercury profile use`

```bash
mercury profile use <name>
```

Sets `<name>` as the active profile. All subsequent `mercury` commands (without `-p`) will use this profile.

| Argument | Description |
|----------|-------------|
| `<name>` | Profile name to activate. Use `default` to return to the base profile. |

**Example:**

```bash
mercury profile use work
mercury profile use default
```

## `mercury profile create`

```bash
mercury profile create <name> [options]
```

Creates a new profile.

| Argument / Option | Description |
|-------------------|-------------|
| `<name>` | Name for the new profile. Must be a valid directory name (alphanumeric, hyphens, underscores). |
| `--clone` | Copy `config.yaml`, `.env`, and `SOUL.md` from the current profile. |
| `--clone-all` | Copy everything (config, memories, skills, sessions, state) from the current profile. |
| `--clone-from <profile>` | Clone from a specific profile instead of the current one. Used with `--clone` or `--clone-all`. |
| `--no-alias` | Skip wrapper script creation. |

Creating a profile does **not** make that profile directory the default project/workspace directory for terminal commands. If you want a profile to start in a specific project, set `terminal.cwd` in that profile's `config.yaml`.

**Examples:**

```bash
# Blank profile — needs full setup
mercury profile create mybot

# Clone config only from current profile
mercury profile create work --clone

# Clone everything from current profile
mercury profile create backup --clone-all

# Clone config from a specific profile
mercury profile create work2 --clone --clone-from work
```

## `mercury profile delete`

```bash
mercury profile delete <name> [options]
```

Deletes a profile and removes its shell alias.

| Argument / Option | Description |
|-------------------|-------------|
| `<name>` | Profile to delete. |
| `--yes`, `-y` | Skip confirmation prompt. |

**Example:**

```bash
mercury profile delete mybot
mercury profile delete mybot --yes
```

:::warning
This permanently deletes the profile's entire directory including all config, memories, sessions, and skills. Cannot delete the currently active profile.
:::

## `mercury profile show`

```bash
mercury profile show <name>
```

Displays details about a profile including its home directory, configured model, gateway status, skills count, and configuration file status.

This shows the profile's Mercury home directory, not the terminal working directory. Terminal commands start from `terminal.cwd` (or the launch directory on the local backend when `cwd: "."`).

| Argument | Description |
|----------|-------------|
| `<name>` | Profile to inspect. |

**Example:**

```bash
$ mercury profile show work
Profile: work
Path:    ~/.mercury/profiles/work
Model:   anthropic/claude-sonnet-4 (anthropic)
Gateway: stopped
Skills:  12
.env:    exists
SOUL.md: exists
Alias:   ~/.local/bin/work
```

## `mercury profile alias`

```bash
mercury profile alias <name> [options]
```

Regenerates the shell alias script at `~/.local/bin/<name>`. Useful if the alias was accidentally deleted or if you need to update it after moving your Mercury installation.

| Argument / Option | Description |
|-------------------|-------------|
| `<name>` | Profile to create/update the alias for. |
| `--remove` | Remove the wrapper script instead of creating it. |
| `--name <alias>` | Custom alias name (default: profile name). |

**Example:**

```bash
mercury profile alias work
# Creates/updates ~/.local/bin/work

mercury profile alias work --name mywork
# Creates ~/.local/bin/mywork

mercury profile alias work --remove
# Removes the wrapper script
```

## `mercury profile rename`

```bash
mercury profile rename <old-name> <new-name>
```

Renames a profile. Updates the directory and shell alias.

| Argument | Description |
|----------|-------------|
| `<old-name>` | Current profile name. |
| `<new-name>` | New profile name. |

**Example:**

```bash
mercury profile rename mybot assistant
# ~/.mercury/profiles/mybot → ~/.mercury/profiles/assistant
# ~/.local/bin/mybot → ~/.local/bin/assistant
```

## `mercury profile export`

```bash
mercury profile export <name> [options]
```

Exports a profile as a compressed tar.gz archive.

| Argument / Option | Description |
|-------------------|-------------|
| `<name>` | Profile to export. |
| `-o`, `--output <path>` | Output file path (default: `<name>.tar.gz`). |

**Example:**

```bash
mercury profile export work
# Creates work.tar.gz in the current directory

mercury profile export work -o ./work-2026-03-29.tar.gz
```

## `mercury profile import`

```bash
mercury profile import <archive> [options]
```

Imports a profile from a tar.gz archive.

| Argument / Option | Description |
|-------------------|-------------|
| `<archive>` | Path to the tar.gz archive to import. |
| `--name <name>` | Name for the imported profile (default: inferred from archive). |

**Example:**

```bash
mercury profile import ./work-2026-03-29.tar.gz
# Infers profile name from the archive

mercury profile import ./work-2026-03-29.tar.gz --name work-restored
```

## `mercury -p` / `mercury --profile`

```bash
mercury -p <name> <command> [options]
mercury --profile <name> <command> [options]
```

Global flag to run any Mercury command under a specific profile without changing the sticky default. This overrides the active profile for the duration of the command.

| Option | Description |
|--------|-------------|
| `-p <name>`, `--profile <name>` | Profile to use for this command. |

**Examples:**

```bash
mercury -p work chat -q "Check the server status"
mercury --profile dev gateway start
mercury -p personal skills list
mercury -p work config edit
```

## `mercury completion`

```bash
mercury completion <shell>
```

Generates shell completion scripts. Includes completions for profile names and profile subcommands.

| Argument | Description |
|----------|-------------|
| `<shell>` | Shell to generate completions for: `bash` or `zsh`. |

**Examples:**

```bash
# Install completions
mercury completion bash >> ~/.bashrc
mercury completion zsh >> ~/.zshrc

# Reload shell
source ~/.bashrc
```

After installation, tab completion works for:
- `mercury profile <TAB>` — subcommands (list, use, create, etc.)
- `mercury profile use <TAB>` — profile names
- `mercury -p <TAB>` — profile names

## See also

- [Profiles User Guide](../user-guide/profiles.md)
- [CLI Commands Reference](./cli-commands.md)
- [FAQ — Profiles section](./faq.md#profiles)
