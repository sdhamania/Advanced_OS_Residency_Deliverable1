#!/usr/bin/env python3
"""Record supplemental PTY sessions without overwriting native screenshots."""

from __future__ import annotations

import os
import pty
import re
import select
import shutil
import signal
import tempfile
import textwrap
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "build" / "os-shell"
OUTPUT = ROOT / "evidence" / "pty_sessions"
FONT_PATH = Path("/System/Library/Fonts/Menlo.ttc")
if not FONT_PATH.exists():
    FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
DEMO_DIR: Path

ANSI_PATTERN = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


class PtyShell:
    def __init__(self, cwd: Path):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(cwd)
            os.execl(str(BINARY), str(BINARY))
        self.buffer = bytearray()
        self.cursor = 0
        self.expect(rb"\$ ")

    def _read(self, timeout: float = 0.1) -> bool:
        readable, _, _ = select.select([self.fd], [], [], timeout)
        if not readable:
            return False
        try:
            data = os.read(self.fd, 4096)
        except OSError:
            return False
        if not data:
            return False
        self.buffer.extend(data)
        return True

    def expect(self, pattern: bytes, timeout: float = 5.0) -> bytes:
        expression = re.compile(pattern, re.DOTALL)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            match = expression.search(self.buffer, self.cursor)
            if match:
                self.cursor = match.end()
                return bytes(self.buffer[: self.cursor])
            self._read()
        raise RuntimeError(
            f"Timed out waiting for {pattern!r}:\n"
            + self.buffer.decode(errors="replace")
        )

    def command(self, command: str, timeout: float = 5.0) -> bytes:
        os.write(self.fd, command.encode() + b"\n")
        return self.expect(rb"\$ ", timeout)

    def send(self, data: bytes) -> None:
        os.write(self.fd, data)

    def text(self) -> str:
        raw = self.buffer.decode("utf-8", errors="replace").replace("\r\n", "\n")
        raw = ANSI_PATTERN.sub("", raw)
        raw = raw.replace("\x08", "")
        return raw.strip()

    def close(self) -> None:
        try:
            os.write(self.fd, b"exit\n")
        except OSError:
            pass

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            self._read(0.05)
            try:
                waited, _ = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                waited = self.pid
            if waited == self.pid:
                break
        else:
            try:
                os.kill(self.pid, signal.SIGHUP)
                os.waitpid(self.pid, 0)
            except (ChildProcessError, ProcessLookupError):
                pass
        try:
            os.close(self.fd)
        except OSError:
            pass


def capture_builtins() -> str:
    demo_dir = DEMO_DIR
    (demo_dir / "sample.txt").write_text("Process state became concrete during testing.\n")
    shell = PtyShell(demo_dir)
    try:
        commands = [
            "pwd",
            'echo "Advanced Shell built-ins"',
            "mkdir demo",
            "cd demo",
            "touch notes.txt",
            "ls",
            "cat ../sample.txt",
            "cat notes.txt",
            'echo "Empty cat did not disable output"',
            "cd ..",
            "rm demo/notes.txt",
            "rmdir demo",
            "ls",
        ]
        for command in commands:
            shell.command(command)
        return shell.text()
    finally:
        shell.close()


def capture_background_and_kill() -> str:
    shell = PtyShell(DEMO_DIR)
    try:
        shell.command("sleep 20 &")
        transcript = shell.text()
        match = re.search(r"\[1\]\s+(\d+)", transcript)
        if not match:
            raise RuntimeError("Could not read background PID from shell output")
        pid = match.group(1)
        shell.command("jobs")
        shell.command(f"ps -o pid=,pgid=,stat=,command= -p {pid}")
        shell.command(f"kill {pid}")
        shell.command("sleep 0.2")
        shell.command("jobs")
        return shell.text()
    finally:
        shell.close()


def capture_fg_bg_signals() -> str:
    shell = PtyShell(DEMO_DIR)
    try:
        shell.send(b"sleep 20\n")
        time.sleep(0.25)
        shell.send(b"\x1a")
        shell.expect(rb"Stopped.*\$ ")
        shell.command("jobs")
        shell.command("bg %1")
        shell.command("jobs")
        shell.send(b"fg %1\n")
        shell.expect(rb"fg %1\r?\n")
        shell.expect(rb"sleep 20\r?\n")
        time.sleep(0.25)
        shell.send(b"\x03")
        shell.expect(rb"Terminated by signal 2.*\$ ")
        return shell.text()
    finally:
        shell.close()


def capture_errors() -> str:
    demo_dir = DEMO_DIR
    shell = PtyShell(demo_dir)
    try:
        commands = [
            "no_such_command_xyz",
            "cat missing.txt",
            "cd missing-directory",
            "mkdir occupied",
            "touch occupied/item.txt",
            "rmdir occupied",
            "rm occupied",
            "kill abc",
            'echo "unfinished',
            "ls | cat",
            "mkdir",
        ]
        for command in commands:
            shell.command(command)
        return shell.text()
    finally:
        shell.close()


def capture_clear_and_exit() -> str:
    shell = PtyShell(DEMO_DIR)
    try:
        shell.command("clear")
        shell.command('echo "clear returned control to the prompt"')
        shell.command("echo background-builtin &")
        shell.command("sleep 0.1")
        shell.send(b"exit 0\n")
        shell.expect(rb"exit 0\r?\n")
        return shell.text()
    finally:
        shell.close()


def wrap_terminal_line(line: str, width: int = 100) -> list[str]:
    if len(line) <= width:
        return [line]
    return textwrap.wrap(
        line,
        width=width,
        subsequent_indent="  ",
        replace_whitespace=False,
        drop_whitespace=False,
    )


def render_transcript(title: str, transcript: str, output_path: Path) -> None:
    font = ImageFont.truetype(str(FONT_PATH), 22)
    title_font = ImageFont.truetype(str(FONT_PATH), 18)
    lines: list[str] = []
    for source_line in transcript.splitlines():
        lines.extend(wrap_terminal_line(source_line.rstrip()))

    width = 1440
    top_bar = 58
    margin_x = 34
    margin_y = 26
    line_height = 34
    height = top_bar + margin_y * 2 + max(1, len(lines)) * line_height

    image = Image.new("RGB", (width, height), "#0b1020")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, top_bar), fill="#171c2d")
    for x, color in ((28, "#ff5f57"), (54, "#febc2e"), (80, "#28c840")):
        draw.ellipse((x - 7, 22, x + 7, 36), fill=color)
    draw.text((110, 18), title, font=title_font, fill="#e8edf7")

    y = top_bar + margin_y
    for line in lines:
        if line.startswith("os-shell:") and "$" in line:
            prompt, _, command = line.partition("$")
            command = command.lstrip()
            draw.text((margin_x, y), prompt + "$ ", font=font, fill="#7dd3fc")
            prompt_width = draw.textlength(prompt + "$ ", font=font)
            draw.text((margin_x + prompt_width, y), command, font=font, fill="#f8fafc")
        elif line.startswith("os-shell:"):
            draw.text((margin_x, y), line, font=font, fill="#fca5a5")
        elif re.match(r"\[\d+\]", line):
            draw.text((margin_x, y), line, font=font, fill="#86efac")
        else:
            draw.text((margin_x, y), line, font=font, fill="#d6deeb")
        y += line_height

    image.save(output_path, optimize=True)


def main() -> None:
    global DEMO_DIR
    if not BINARY.exists():
        raise SystemExit("Build the shell with 'make' before generating screenshots")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="osh-", dir="/tmp") as temporary:
        DEMO_DIR = Path(temporary)
        sessions = [
        ("Built-in file and directory commands", capture_builtins(), "01_builtins.png"),
        ("Background process, process group, and kill", capture_background_and_kill(), "02_background_and_kill.png"),
        ("Foreground and background job control", capture_fg_bg_signals(), "03_fg_bg_signals.png"),
        ("Invalid commands and defensive error handling", capture_errors(), "04_error_handling.png"),
        ("Clear, background built-in, and exit", capture_clear_and_exit(), "05_clear_and_exit.png"),
        ]
    for title, transcript, filename in sessions:
        path = OUTPUT / filename
        render_transcript(title, transcript, path)
        path.with_suffix(".txt").write_text(transcript + "\n")
        print(f"created {path}")


if __name__ == "__main__":
    main()

