#!/usr/bin/env python3
"""Deploy the staging stack without leaking parameter values.

Loads .env.deploy from the repo root, falling back to .env so only one
environment file needs maintaining. Runs `sam deploy` with
--parameter-overrides, and scrubs any secret value from captured output
before printing. Exit code mirrors sam's.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

SAM = r"C:\PROGRA~1\Amazon\AWSSAMCLI\bin\sam.cmd"
ENV_FILE = pathlib.Path(__file__).resolve().parents[1] / ".env.deploy"
FALLBACK_ENV_FILE = pathlib.Path(__file__).resolve().parents[1] / ".env"


def main() -> int:
    env_path = ENV_FILE if ENV_FILE.exists() else FALLBACK_ENV_FILE
    if not env_path.exists():
        print("missing .env.deploy (or .env)", file=sys.stderr)
        return 2
    vals: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    # Real environment variables win over file values: lets a single deploy
    # target a test guardian chat without touching anyone's .env.
    import os

    vals.update({k: v for k, v in os.environ.items() if k.startswith("GATEHOUSE_")})
    required = [
        "GATEHOUSE_TELEGRAM_WEBHOOK_SECRET",
        "GATEHOUSE_GRAPH_SALT",
    ]
    missing = [k for k in required if not vals.get(k)]
    if missing:
        print(f"missing values in .env.deploy: {missing}", file=sys.stderr)
        return 2

    overrides = [
        "Environment=staging",
        f"TelegramWebhookSecret={vals['GATEHOUSE_TELEGRAM_WEBHOOK_SECRET']}",
        f"GraphSalt={vals['GATEHOUSE_GRAPH_SALT']}",
        # SAM rejects empty parameter values; placeholders keep the stack
        # deployable before the real token/chat land, and notifier logic
        # treats unknown tokens as absent (falls back to logging sink).
        f"TelegramBotToken={vals.get('GATEHOUSE_TELEGRAM_BOT_TOKEN') or 'PENDING-ROTATION'}",
        f"GuardianChatId={vals.get('GATEHOUSE_GUARDIAN_TELEGRAM_CHAT_ID') or '0'}",
        "WhatsAppAppSecret=pending-meta-review",
        "WhatsAppVerifyToken=pending-meta-review",
    ]
    cmd = [
        SAM,
        "deploy",
        "--template-file",
        "build/packaged.yaml",
        "--stack-name",
        "gatehouse-staging",
        "--capabilities",
        "CAPABILITY_NAMED_IAM",
        "CAPABILITY_AUTO_EXPAND",
        "--region",
        "ap-south-1",
        "--parameter-overrides",
        *overrides,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    out = (proc.stdout or "") + (proc.stderr or "")
    secret_values = [v for v in vals.values() if len(v) > 12]
    for sv in secret_values:
        out = out.replace(sv, "***REDACTED***")
    tail = "\n".join(out.splitlines()[-25:])
    print(tail)
    print(f"SAM_EXIT={proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
