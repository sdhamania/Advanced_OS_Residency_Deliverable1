# Advanced Shell Simulation Deliverable 1

This project implements a small Unix-like shell in C++17. It demonstrates process creation, foreground and background execution, process groups, terminal ownership, signal handling, job state tracking, and filesystem-oriented built-in commands. The implementation targets POSIX environments and is designed to compile on macOS and modern Linux distributions.

## Build and run

Requirements:

- A C++17 compiler (`clang++` or `g++`)
- GNU Make
- Python 3 for the automated integration tests
- A POSIX terminal for interactive `Ctrl-C` and `Ctrl-Z` job-control tests

```bash
make
./build/os-shell
```

The prompt includes the current directory:

```text
os-shell:/path/to/project$ 
```

Run the complete test suite with:

```bash
make test
```

Remove build artifacts with `make clean`.

## Commands

| Command | Behavior |
|---|---|
| `cd [directory]` | Changes the shell process's working directory; with no argument, uses `HOME`. |
| `pwd` | Prints the current working directory. |
| `exit [status]` | Exits with an optional status from 0 to 255. |
| `echo [text]` | Prints its arguments separated by spaces. |
| `clear` | Clears an ANSI-compatible terminal. |
| `ls [path]` | Lists non-hidden directory entries in sorted order. |
| `cat file...` | Displays one or more files. |
| `mkdir directory...` | Creates directories. |
| `rmdir directory...` | Removes empty directories only. |
| `rm file...` | Removes files and refuses directories. |
| `touch file...` | Creates files or updates their modification times. |
| `kill pid` | Sends `SIGTERM` to a positive process ID. |
| `jobs` | Lists tracked jobs with job ID, state, process-group ID, and command. |
| `fg [job_id]` | Moves a job to the foreground; accepts `1` or `%1`. |
| `bg [job_id]` | Continues a stopped job in the background. |

Commands not implemented as built-ins are launched through `fork()` and `execvp()`, so normal programs found through `PATH` can run. Add `&` at the end of an external command to run it in the background:

```text
sleep 30 &
jobs
fg %1
```

While a foreground program runs, `Ctrl-C` sends `SIGINT` to that job and `Ctrl-Z` sends `SIGTSTP`. The shell itself ignores those terminal signals, records stopped jobs, and uses `SIGCONT` for `fg` and `bg`.

## Design

- `CommandParser` tokenizes whitespace, single and double quotes, backslash escapes, and a final background operator.
- `Shell` owns the read-evaluate loop and executes stateful built-ins in the parent process.
- Each external command receives its own process group. The parent transfers the controlling terminal to a foreground group with `tcsetpgrp()` and reclaims it after `waitpid()` reports completion or a stop.
- A job table records the shell job ID, PID, process-group ID, original command, state, and stopped-job terminal settings. A signal-safe self-pipe wakes the `poll()` input loop to reap background children even while the prompt is idle. The foreground wait also collects background statuses.
- A launch gate assigns the foreground terminal before releasing a new child. An exec confirmation pipe closes during program replacement before the shell accepts another command. `fg` restores a stopped job's terminal settings.
- Child processes restore default terminal-signal behavior immediately before `execvp()`.

## Intentional Deliverable 1 boundaries

The parser reports pipes (`|`), redirection (`<` and `>`), command lists (`;`), and a non-final `&` as unsupported. Environment expansion, wildcard expansion, command substitution, pipelines, and persistent command history are not required for this deliverable. Foreground built-ins run in the parent; a built-in followed by `&` runs in a child and cannot modify parent state. `fg` and `bg` reject `&` because they must control parent-owned jobs.

`exit` without an explicit status and EOF return the last command status. Parsing failures return 2, built-in failures generally return 1, and external execution failures return 126 or 127. Active jobs receive SIGHUP when the shell exits; stopped groups also receive SIGCONT. The shell uses the host kernel's real processes and filesystem, rather than providing a sandbox or an internal CPU scheduler.

## Submission evidence and report

The report uses APA 7 student-paper formatting, six cited primary technical references, a performance table, five figures in Appendix A, and a command coverage matrix in Appendix B. The PNGs in `screenshots/` render recorded PTY transcripts; the matching `.txt` files preserve that evidence. They are not photographs of a native Terminal window. `clear` is demonstrated in a transcript and checked by its exact ANSI bytes in the tests.

The reviewed implementation passes parser assertions and 20 integration tests on macOS. The full integration suite also passes under AddressSanitizer and UndefinedBehaviorSanitizer. Clang static analysis reports no findings. Linux source compatibility is intended, but Linux execution has not been verified here.

In batch mode, background commands receive `/dev/null` as standard input so they cannot consume subsequent shell commands. Interactive background jobs retain terminal job-control behavior. Within double quotes, ordinary backslashes remain literal; backslash still escapes a double quote, backslash, dollar sign, or backquote. Full variable expansion and multiline command continuation remain outside this parser's supported subset.

To reproduce the performance measurements after building, run `python3 scripts/benchmark.py`; it saves all nine samples per workload in `report/benchmark_results.json`. To regenerate the evidence images, install Pillow in a local environment and run `python3 scripts/generate_screenshots.py`. Rebuilding the Word report requires `python-docx` and uses `python3 report/build_report.py`. These optional authoring dependencies are not needed to compile or run the shell.

The later project topics—simulated scheduling policies, memory management, synchronization primitives, and expanded security controls—are not included in Deliverable 1.

## Project layout

```text
include/      Public C++ headers and job model
src/          Parser, shell, built-ins, and entry point
tests/        Parser, batch-mode, and PTY job-control tests
screenshots/  Demonstration evidence used by the report
report/       Report builder and final Word report
```

