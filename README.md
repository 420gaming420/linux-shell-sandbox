# Linux Shell Sandbox

A simple demo showcasing a "Copy on Write" bash sandbox with podman isolation support.
This project is published for educational purposes and rather minimal on its own.
If you want to use this as a tool for your project, add it as a git submodule or fork it to build upon.
You (or your AI assistant) can also examine the source code and create your own version in whatever programming language or shell suits you.

## Purpose
Let AI agents run shell commands on a project in a sandbox that discards any modifications.

AI agents that run shell commands can be unpredictable — they may create files, modify code, or run scripts even when told not to. This tool gives agents a sandboxed shell where every change is thrown away when the session ends.

## Use Cases

- **Sandboxed exploration** — Run shell commands on your project without fear of accidentally breaking something.
- **Untrusted code execution** — Run untrusted scripts or git repos in a temporary podman container that discards everything on exit.
- **"Code Test" agents** — Agents that debug or find issues may end up making unwanted changes or fixes. The sandbox catches all of it.
- **"Logic Verification" agents** — Agents that run code directly in the shell as heredocs to verify logic sometimes ignore instructions to avoid file creation, using `cat >` to make files anyway. The sandbox catches that too.
- **Preserving sandbox work** — Since all changes are discarded on exit, the agent can include a snippet of its bug fix in its ending message for a human or coding agent to review and apply themselves. Alternatively, the agent can submit a pull request (via a git mcp for a local git server) to store their progress, which will be reviewed before merging to the actual project.

## Installation

### Environment
This was made and tested on debian linux x86_64 in a bash shell.
Other operating systems or shells may or may not work.

### Dependencies

The sandbox requires:

- **Python 3.10+** — for the CLI and logic layer
- **fuse-overlayfs** — for copy-on-write overlay mounts (works as non-root)
- **podman** — for container-based sandbox sessions (optional; only needed for `podman.py`)
- **Bash** — for command execution

## Configuration

Create a `.env` file from the example to override defaults:

```bash
cp .env.example .env
```

Available options:

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_CONTAINER_IMAGE` | `docker.io/library/python:latest` | Container image for podman sessions |
| `SANDBOX_CONTAINER_NAME` | `sandbox` | Default container name |
| `SANDBOX_PROJECT_DIR` | `./project/` | Default project directory |

The default project directory (`./project/`) is gitignored.
Point the sandbox at your own project with `--project-dir` or by setting `SANDBOX_PROJECT_DIR` in `.env`. You can also run the `sandbox_demo.sh` script to create a sample project for testing.

If the project directory does not exist, both `cli.py` and `podman.py` will exit with a clear error message.

## Usage

> **Note:** The demo script (`sandbox_demo.sh`) will create a 1GB test blob file (`project/blob` created with /dev/random) on disk when run. This is intentional — it's used to demonstrate the copy-on-write overlay's memory efficiency. The file is gitignored and not part of the repository but you may want to delete it afterwards to free up space.

### Python Shell (`cli.py`)

#### Interactive mode

```bash
python cli.py
```

Then type commands as usual. Exit with `exit`, `Ctrl+D`, or `Ctrl+C`.

You'll get an interactive bash prompt inside the sandbox:

```
=== Sandbox Active ===
Project: /path/to/your/project
Overlay: /tmp/sandbox_xxx
Type "exit" or press Ctrl+D to leave the sandbox.
======================

$ ls
code.py  src
$ touch test.py
$ ls
code.py  src  test.py
$ exit
exit

=== Sandbox exited. Overlay discarded. ===
```

Back in your real shell, the project is untouched:

```bash
$ ls
code.py  src
```

#### Non-interactive / scripted mode

```bash
echo -e "ls\ntouch test.py\nls\nexit" | python cli.py
```

Piping to cli.py is simply for testing purposes and is not recommended.

#### API usage

```python
from src.logic.sandbox import run_sandbox

result = run_sandbox(
    project_dir='/path/to/project',
    commands='ls\ntouch test.py\nls\n',
    interactive=False,
    timeout=10,
)
print(result.stdout)
```

This is a basic python based demonstration and may not be recommended for most situations.

### Podman Shell (`podman.py`)

Both `cli.py` and `podman.py` can be run directly as executables (they have shebangs):

```bash
chmod +x cli.py podman.py
./cli.py
./podman.py --status
```

Or via Python explicitly:

```bash
python cli.py
python podman.py --status
```

#### Initialize a sandbox session

```bash
# Create the container with an overlay mounted at the project path
podman.py -n conv_abc123 --init
```

#### Run a command

```bash
# Run commands in the sandbox (state persists across calls)
podman.py -n conv_abc123 "ls"
podman.py -n conv_abc123 "cat code.py"
podman.py -n conv_abc123 "touch testfile"
podman.py -n conv_abc123 "ls"
```

#### Show container status

```bash
podman.py -n conv_abc123 --status
```

Output includes memory usage:

```
Name: conv_abc123
Exists: True
Running: True
Status: Up 4 seconds
Memory: 311.3kB / 16.73GB
```

#### Track memory usage

```bash
# Prints memory before and after the command
podman.py -n conv_abc123 --mem "dd if=/dev/random of=bigfile bs=1M count=1000"
```

Output:

```
MEMORY BEFORE: 323.6kB / 16.73GB
1000+0 records in
1000+0 records out
1048576000 bytes (1.0 GB, 1000 MiB) copied, 3.52413 s, 298 MB/s
MEMORY AFTER: 2.753MB / 16.73GB
```

#### Auto-discard (remove container after each command)

```bash
# Container is removed automatically after the command finishes
podman.py -n conv_abc123 --init -a "python code.py"
```

#### Re-initialize (clear workspace)

```bash
# Removes the container and creates a fresh one
podman.py -n conv_abc123 --init
```

#### Delete the container

```bash
podman.py -n conv_abc123 --remove
```

#### All options

```
podman.py [global options] <command>

Global options:
  --sandbox-name, -n NAME    Container name (default: "sandbox")
  --project-dir, -d PATH     Project directory (default: ./project/)
  --image, -i IMAGE          Container image (default: docker.io/library/python:latest)
  --auto-discard, -a         Auto-remove container after each command
  --init, -I                 Initialize/recreate the container (clears workspace)
  --status, -S               Show container status (includes memory usage)
  --remove, -r               Remove the container
  --mem, -m                  Print memory usage before and after the command
```

## How It Works

### Python Shell (fuse-overlayfs)

1. **Mount** — A fuse-overlayfs is created with the project as the lower (read-only) layer and a small tmpfs-backed upper layer for deltas. The merged mount is at `/tmp/sandbox_xxx/merged`.
2. **Run** — An interactive `bash -i` shell is spawned inside the overlay using a pseudo-terminal (PTY). All commands run against the overlay.
3. **Discard** — On exit, the overlay is unmounted and the temp directory is deleted. Everything is gone.

### Podman Shell (containerized)

A fuse-overlayfs (with the project as the lower layer) is bind-mounted at the real source path, so the container never sees the live project files.

1. **Mount** — A fuse-overlayfs is created with the project as the lower (read-only) layer and a small tmpfs-backed upper/work layer for deltas. The merged mount is at `/tmp/sandbox_xxx/merged`.
2. **Create** — A podman container is created with:
    - Overlay directory bind-mounted at the real source path (e.g. `/path/to/project:rw`), so the container sees the overlay at the same path as the live source
    - Working directory set to the project path
    - `sleep infinity` as the main process (keeps container alive)
3. **Initialize** — The container starts and the overlay is mounted. No copy step is needed since the overlay is already mounted at the project path.
4. **Run** — Each command executes via `podman exec` inside the container: `bash -c "$command"`. Files persist across calls within the same session.
5. **Discard** — `podman rm -f` removes the container and the overlay is unmounted and cleaned up. Everything is gone.

**Source isolation** — Because the container only sees the fuse-overlayfs of the project (mounted at the real source path), a rogue command like `rm -rf /path/to/project` only deletes the overlay, not the live source. The real project is never mounted into the container.

**Memory efficiency** — Only modified or newly created files consume tmpfs memory (stored in the upper layer). Unmodified files are read from the original project on the real filesystem via the lower layer. For a 1 GB project with only a few kb of changes, the sandbox only consumes the few KB in the tmpfs mount instead of duplicating the entire 1GB project in memory.

## AI Agent Integration

The podman sandbox is designed to be used by AI agents as the container "spoofs" the sandbox path with the actual project path. The container isolation is also a nice bonus.

The AI agent backend will need to manage the chat session with their sandbox container. Each conversation session should get its own unique container name (e.g., a date or session UUID), giving each AI agent their own sandbox to avoid session conflicts.

```bash
# Agent backend starts a new session for multiple agents (session ID: conv_abc123)
podman.py -n conv_abc123 --init
podman.py -n conv_xyz123 --init

# Agent backend runs each tool call inside the container
podman.py -n conv_abc123 "cat code.py"
podman.py -n conv_xyz123 "touch testfile"

# Session ends — agent backend removes the container
podman.py -n conv_abc123 --remove

# Other agent continues un-interrupted
podman.py -n conv_xyz123 "ls"
```

To further sandbox the AI Agents, the entire Agent stack should run inside a secure and locked down VM:

```
[Secure and isolated VM] -> [Agent Backend Running Inside VM] -> [Podman Sandbox Shells Running Inside VM]
```

If needed, you will have to somehow proxy upstreams like apt (local apt-cacher-ng server), pip (local devpi server), etc. Or pre-install all dependencies beforehand.

You can also setup a local git server to securely sync the project commits made inside the isolated VM, maybe restricting the AI agents to only have pull request permission so that their commits can be manually reviewed.

## Project Structure

```
cli.py                          # Thin entry point (python shell)
podman.py                       # Thin entry point (podman shell)
src/
├── logic/                      # Backend modules (atomic, framework-agnostic)
│   ├── overlay.py              # Create/cleanup fuse-overlayfs overlay
│   ├── shell_runner.py         # Run shell commands (non-interactive or PTY-based)
│   ├── sandbox.py              # Shell sandbox: (create/run/cleanup)
│   ├── container_mgr.py        # Podman CLI helpers (create/exec/rm/status)
│   ├── podman_sandbox.py       # Podman sandbox: (init/run/cleanup)
│   ├── dependencies.py         # Distro detection and dependency checks
│   └── config.py               # .env configuration loader
└── ui/                         # Frontend UI (monolithic, framework-specific)
    ├── cli_app.py              # Interactive python shell app
    └── podman_cli.py           # Podman CLI app with argparse
```

## Testing

Run the full demo script to see all features in action:

```bash
./sandbox_demo.sh
```

This demonstrates:
1. Container lifecycle (create → run → remove)
2. File persistence across multiple commands
3. Host project isolation (no files leaked out of sandbox)
4. Copy-on-write overlay memory efficiency (1GB project, ~0KB tmpfs usage at init, ~100MB usage when 100MB written)
5. Auto-discard mode
6. Re-initialization (clear workspace)
7. Container memory tracking via podman stats
8. Error handling


## Limitations

### Git Integration

The fuse-overlayfs provides sufficient isolation for Git operations — commits, branches, and working tree changes made inside the sandbox are discarded when the session ends, and the host repository is untouched. Verified by testing: a sandbox session can create a new branch, commit changes, and exit, leaving the host repository unchanged.

What is **not** isolated:
- **`.git/config` inside the container** can be modified (e.g., adding remotes, changing credential helpers). These changes are sandbox-contained but could be used to exfiltrate data if the container has network access.
- **Global Git config** (`~/.gitconfig`) inside the container is separate from the host but still available to commands running inside it.
- **Pre-commit hooks, branch protection, and staging area manipulation** are not enforced — the sandbox does not restrict what Git operations can be performed.

### Security

The overlay filesystem protects the host from destructive file operations, but processes can still escape via container escape vectors or kernel vulnerabilities. When using the podman sandbox, it is recommended to apply security profiles if applicable:

```bash
podman.py -n conv_abc123 --init -- --security-opt seccomp=default
```

There are no explicit memory or CPU limits on containers. Resource limits can be added to `src/logic/container_mgr.py` via `--memory` and `--cpus` flags on `podman create`.

### Known Gaps

- **No command filtering** — Any shell command can run inside the sandbox. The overlay protects the host filesystem, but commands like `curl | sh` could install arbitrary software inside the container.
- **No concurrent session support** — Each container name maps to a single session. UUIDs or timestamps should be used for container names when running multiple sessions in parallel.
- **No integration tests** — The demo script (`sandbox_demo.sh`) covers the main flows, but a pytest suite for overlay mounting and container lifecycle would improve quality confidence.
- **No logging** — Failures are returned as exit codes but adding logging with session IDs in `src/logic/podman_sandbox.py` would help with debugging.

## AI Disclosure

This project was developed with [opencode](https://github.com/anomalyco/opencode/releases) using a locally hosted [llama.cpp server](https://github.com/ggml-org/llama.cpp) as the provider with 256k context size running Qwen3.5 35B quantized at 4-bit GGUF, later upgraded to Qwen3.6 35B [Myric/KAT-Coder-V2.5-Dev-MTP-APEX-GGUF](https://huggingface.co/Myric/KAT-Coder-V2.5-Dev-MTP-APEX-GGUF) i-quality version.

This repo may contain inaccuracies, hallucinated logic, or suboptimal patterns introduced by the model. Scripts were manually reviewed and tested by a human operator, and verified to work in practice. Contributions and pull requests fixing bugs or making improvements are welcome.

## Unlicense

This is free and unencumbered software released into the public domain.
