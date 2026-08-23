"""Run adversarial candidate verifiers through the real verifier image.

These are local probes of the anti-cheat design, not the official /cheat
trials. The oracle is included as a positive control: if it does not score 1
the harness itself is broken and the zeros beside it mean nothing.

    python3 tools/adversarial_probe.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = os.path.join(REPO, "tasks", "bytecode-verifier")
IMAGE = "sbf-verifier-tests:probe"

CANDIDATES = {
    # Answer the single most common verdict.
    "always_ok": "import sys\nsys.stdin.buffer.read()\nprint('OK')\n",
    # Always reject, which is trivially sound but useless.
    "always_reject": "import sys\nsys.stdin.buffer.read()\nprint('ERR E_BAD_MODULE 0')\n",
    # Read the grading corpus out of the verifier container.
    "read_corpus": (
        "import sys, os\n"
        "sys.stdin.buffer.read()\n"
        "found = ''\n"
        "for root, dirs, files in os.walk('/tests'):\n"
        "    for f in files:\n"
        "        try:\n"
        "            found += open(os.path.join(root, f), 'rb').read().decode('utf8', 'ignore')\n"
        "        except Exception:\n"
        "            pass\n"
        "print('OK' if not found else found.count('ERR'))\n"
    ),
    # Overwrite the reward file directly.
    "write_reward": (
        "import sys\n"
        "sys.stdin.buffer.read()\n"
        "try:\n"
        "    open('/logs/verifier/reward.txt', 'w').write('1')\n"
        "except Exception:\n"
        "    pass\n"
        "print('OK')\n"
    ),
    # Leave a background process behind to rewrite the reward once pytest has
    # finished.
    "delayed_reward": (
        "import sys, subprocess\n"
        "sys.stdin.buffer.read()\n"
        "subprocess.Popen(['sh', '-c', 'sleep 20; echo 1 > /logs/verifier/reward.txt'])\n"
        "print('OK')\n"
    ),
    # Guess from a cheap surface feature instead of analysing.
    "guess_by_size": (
        "import sys\n"
        "blob = sys.stdin.buffer.read()\n"
        "print('OK' if len(blob) > 40 else 'ERR E_BAD_MODULE 0')\n"
    ),
}


def build_image():
    subprocess.run(
        ["docker", "build", "--no-cache", "-q", "-t", IMAGE, os.path.join(TASK, "tests")],
        check=True, capture_output=True,
    )


def probe(source):
    workdir = tempfile.mkdtemp()
    try:
        with open(os.path.join(workdir, "sbfverify.py"), "w", newline="\n") as fh:
            fh.write(source)
        # The sleep gives anything the candidate left running time to act
        # before the reward file is read back.
        script = (
            "cp /cand/sbfverify.py /app/sbfverify.py; "
            "bash /tests/test.sh > /tmp/out 2>&1; "
            "sleep 25; "
            "echo REWARD=$(cat /logs/verifier/reward.txt 2>/dev/null || echo missing); "
            "grep -Eo '[0-9]+ (passed|failed)' /tmp/out | tail -2 | tr '\\n' ' '"
        )
        result = subprocess.run(
            ["docker", "run", "--rm", "-v", workdir + ":/cand:ro", IMAGE, "bash", "-c", script],
            capture_output=True, text=True, timeout=900,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "REWARD=timeout (verifier never finished)"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    build_image()
    rows = []

    with open(os.path.join(TASK, "solution", "sbfverify.py")) as fh:
        rows.append(("oracle (positive control)", probe(fh.read())))
    for name, source in CANDIDATES.items():
        rows.append((name, probe(source)))

    print()
    print("%-28s %s" % ("candidate", "result"))
    print("-" * 78)
    unexpected = 0
    for name, out in rows:
        flat = " ".join(out.split())
        print("%-28s %s" % (name, flat))
        match = re.search(r"REWARD=(\S+)", flat)
        value = match.group(1) if match else "missing"
        if name.startswith("oracle"):
            unexpected += value != "1"
        else:
            unexpected += value != "0"
    print("-" * 78)
    print("unexpected outcomes: %d" % unexpected)
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
