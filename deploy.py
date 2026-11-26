"""One-time handoff for the published RC2 updater, which invokes python3 deploy.py."""
import os
from pathlib import Path
import sys

checkout = Path(__file__).resolve().parent
os.execv("/usr/bin/bash", [
    "bash", str(checkout / "bootstrap.sh"),
    "--channel", os.environ.get("DOROSHELL_UPDATE_CHANNEL", "development"),
    "--rc2-revision", checkout.name, *sys.argv[1:],
])
