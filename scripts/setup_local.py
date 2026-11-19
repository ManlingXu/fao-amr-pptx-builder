"""Create an explicit local-only configuration without overwriting secrets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env"
if target.exists():
    print("Existing .env retained. Review AUTH_MODE before serving.")
else:
    target.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    print("Created .env for local_demo mode. No cloud credentials are needed.")
