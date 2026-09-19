"""
Discord MrBeast / Spam Cleanup Tool  (v8)
───────────────────────────────────────────────────────────────────────────────
Cleans up after account compromise (MrBeast scams, etc.).

CONFIG OPTIONS (edit these at the top of the file):

  TOKEN                  Your Discord user token (required)

  DRY_RUN = True/False
      True  → only show what would happen, change nothing
      False → actually delete messages, unignore, unmute, etc.

  ONLY_UNIGNORE = True/False
      True  → skip all DM scanning/deletion, only unignore + unmute open DMs
      False → full cleanup (scan + delete scam messages, then unignore + unmute)

  SKIP_OPEN_CLOSED_DMS = True/False
      True  → only scan currently open DMs (much faster)
      False → also reopen closed DMs for every relationship so nothing is missed
              (only used when ONLY_UNIGNORE = False)

  CHECK_LAST_N = 1
      How many of the most recent messages to check per channel.
      1 = only the absolute latest message (recommended for the classic scam)

  ALSO_UNBLOCK = True/False
      True  → also remove full blocks (relationship type 2)
      False → only unignore (recommended)

  DELETE_DELAY / PAGE_DELAY / OPEN_DM_DELAY / ACTION_DELAY
      Seconds to wait between requests (keep them ≥ 0.5 to avoid rate limits)

WHAT THE TOOL DOES
  1. (Optional) Reopens closed DMs and scans the latest message(s)
  2. Deletes any of YOUR messages that contain files/images/GIFs/embeds/links
     or match the scam keywords
  3. Unignores every ignored user
  4. Unmutes every currently open DM

⚠  Never share your token. Treat it like a password.
⚠  Change your password + enable 2FA before running this.
⚠  User-token automation is against Discord's ToS — use only for cleanup.
"""

import requests
import time
import json
import re
import sys

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
TOKEN = ""   # ← paste your token here

DRY_RUN = False
ONLY_UNIGNORE = False
SKIP_OPEN_CLOSED_DMS = False
CHECK_LAST_N = 1
ALSO_UNBLOCK = False

DELETE_DELAY   = 0.8
PAGE_DELAY     = 0.6
OPEN_DM_DELAY  = 0.6
ACTION_DELAY   = 0.5

SCAM_KEYWORDS: list[str] = [
    "mrbeast", "mr beast",
    "free nitro", "nitro giveaway",
    "free gift", "claim your",
    "click here", "you won",
    "prize", "giveaway",
    "bonus", "withdraw", "activate code",
]

# ══════════════════════════════════════════════════════════════════════════════
API = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

_URL_RE = re.compile(
    r"https?://[^\s<>\"']+|www\.[^\s<>\"']+|"
    r"discord\.gg/[^\s<>\"']+|discord\.com/invite/[^\s<>\"']+",
    re.IGNORECASE
)

# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _request(method: str, path: str, payload: dict | None = None,
             params: dict | None = None, retries: int = 5):
    url = f"{API}{path}"
    for attempt in range(retries):
        try:
            r = requests.request(
                method, url, headers=HEADERS,
                json=payload, params=params, timeout=15
            )
        except requests.RequestException as exc:
            print(f"  Network error: {exc}")
            time.sleep(4)
            continue
        if r.status_code in (200, 201, 204):
            return r.json() if r.content else True
        if r.status_code == 429:
            body = {}
            try:
                body = r.json()
            except Exception:
                pass
            wait = body.get("retry_after", 5) + 0.5
            print(f"  ⏳ Rate-limited — sleeping {wait:.1f}s")
            time.sleep(wait)
            continue
        if r.status_code in (401, 403):
            print(f"  ❌ Auth error {r.status_code}. Token invalid or expired.")
            sys.exit(1)
        if r.status_code == 404:
            return None
        print(f"  ⚠  {method} {path} → {r.status_code}: {r.text[:120]}")
        return None
    return None

def _get(path, params=None):
    return _request("GET", path, params=params)

def _post(path, payload):
    return _request("POST", path, payload=payload)

def _delete(path):
    return _request("DELETE", path)

def _patch(path, payload):
    return _request("PATCH", path, payload=payload)

# ── Helpers ───────────────────────────────────────────────────────────────────
def open_dm_channel(user_id: str) -> str | None:
    ch = _post("/users/@me/channels", {"recipient_id": user_id})
    if ch and isinstance(ch, dict):
        return ch.get("id")
    return None

def unmute_dm(channel_id: str) -> bool:
    """Unmute a DM channel."""
    payload = {
        "channel_overrides": {
            channel_id: {
                "muted": False,
                "mute_config": None
            }
        }
    }
    return _patch("/users/@me/guilds/%40me/settings", payload) is not None

def _is_scam_message(msg: dict, my_id: str) -> bool:
    if msg.get("author", {}).get("id") != my_id:
        return False
    content = msg.get("content") or ""
    has_media = bool(msg.get("attachments")) or bool(msg.get("embeds"))
    has_link  = bool(_URL_RE.search(content))
    lower     = content.lower()
    has_kw    = any(kw in lower for kw in SCAM_KEYWORDS)
    return has_media or has_link or has_kw

def _preview(msg: dict) -> str:
    c = (msg.get("content") or "").strip()
    if c:
        return repr(c[:80])
    atts = msg.get("attachments") or []
    if atts:
        return f"[attachment: {atts[0].get('filename', '?')}]"
    if msg.get("embeds"):
        return "[embed / image collage]"
    return "[empty]"

def scan_channel(ch_id: str, my_id: str) -> tuple[int, int]:
    found = deleted = 0
    batch = _get(f"/channels/{ch_id}/messages", params={"limit": max(CHECK_LAST_N, 5)})
    if not batch or not isinstance(batch, list):
        return 0, 0
    for msg in batch[:CHECK_LAST_N]:
        if _is_scam_message(msg, my_id):
            found += 1
            ts   = msg.get("timestamp", "")[:19].replace("T", " ")
            prev = _preview(msg)
            if DRY_RUN:
                print(f"      [DRY RUN] {ts}  {prev}")
            else:
                ok = _delete(f"/channels/{ch_id}/messages/{msg['id']}")
                if ok:
                    deleted += 1
                    print(f"      ✓ deleted  {ts}  {prev}")
                else:
                    print(f"      ✗ failed   {ts}  {prev}")
                time.sleep(DELETE_DELAY)
    return found, deleted

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   Discord MrBeast Scam Cleanup  (v8 + unmute)       ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    if not TOKEN or TOKEN.strip() == "" or TOKEN == "PASTE_YOUR_TOKEN_HERE":
        print("❌  TOKEN not set. Paste your Discord token at the top of this file.")
        sys.exit(1)

    if DRY_RUN:
        print("┌─ DRY RUN ─────────────────────────────────────────────┐")
        print("│  Nothing will be changed.                             │")
        print("│  Set DRY_RUN = False to perform real actions.         │")
        print("└───────────────────────────────────────────────────────┘")
        print()

    if ONLY_UNIGNORE:
        print("┌─ ONLY UNIGNORE + UNMUTE MODE ─────────────────────────┐")
        print("│  Skipping message scanning / deletion.                │")
        print("└───────────────────────────────────────────────────────┘")
        print()

    # Auth
    me = _get("/users/@me")
    if not me or "id" not in me:
        print("❌  Authentication failed. Check your token.")
        sys.exit(1)
    my_id = me["id"]
    tag   = f"{me['username']}#{me.get('discriminator', '0')}"
    print(f"✓  Authenticated as {tag}  (id: {my_id})")
    print()

    # Relationships
    relationships = _get("/users/@me/relationships") or []
    print(f"  Total relationships: {len(relationships)}")

    ignored_users = [r for r in relationships if r.get("user_ignored")]
    blocked_users = [r for r in relationships if r.get("type") == 2]

    print(f"    ├─ Ignored users:  {len(ignored_users)}")
    print(f"    └─ Blocked users:  {len(blocked_users)}")
    print()

    # Open DMs map
    open_channels = _get("/users/@me/channels") or []
    user_to_channel: dict[str, str] = {}
    channel_to_name: dict[str, str] = {}
    for ch in open_channels:
        if ch.get("type") == 1:  # DM
            for r in ch.get("recipients", []):
                user_to_channel[r["id"]] = ch["id"]
                channel_to_name[ch["id"]] = r.get("username", r["id"])

    # ── Optional full cleanup (skipped when ONLY_UNIGNORE = True) ─────────────
    if not ONLY_UNIGNORE:
        print("━" * 56)
        print("  STEP 1 — Collecting DM channels")
        print("━" * 56)
        print()

        all_channels: dict[str, tuple[str, str]] = {}
        for uid, chid in user_to_channel.items():
            all_channels[chid] = (uid, channel_to_name.get(chid, ""))

        if not SKIP_OPEN_CLOSED_DMS:
            print("  Reopening closed DMs…")
            for rel in relationships:
                user  = rel.get("user", {})
                uid   = user.get("id", "")
                uname = user.get("username", "unknown")
                if not uid or uid in user_to_channel:
                    continue
                chid = open_dm_channel(uid)
                if chid:
                    all_channels[chid] = (uid, uname)
                    user_to_channel[uid] = chid
                    channel_to_name[chid] = uname
                    print(f"    ↻ reopened: {uname}")
                time.sleep(OPEN_DM_DELAY)

        print(f"  Channels to scan: {len(all_channels)}\n")

        print("━" * 56)
        print("  STEP 2 — Scanning latest message(s)")
        print("━" * 56)
        print()

        total_found = total_deleted = 0
        for chid, (uid, uname) in all_channels.items():
            label = uname or uid or chid
            print(f"  ▸ {label}")
            found, deleted = scan_channel(chid, my_id)
            total_found += found
            total_deleted += deleted
            if found:
                status = f"found {found}" if DRY_RUN else f"deleted {deleted}/{found}"
                print(f"      → {status}")
            else:
                print(f"      → clean")
            time.sleep(PAGE_DELAY)

        print()
        if DRY_RUN:
            print(f"  Scan summary: {total_found} message(s) would be deleted")
        else:
            print(f"  Scan summary: {total_deleted}/{total_found} message(s) deleted")
        print()

    # ── Unignore ──────────────────────────────────────────────────────────────
    print("━" * 56)
    print("  Unignoring users")
    print("━" * 56)
    print()

    if not ignored_users and not (ALSO_UNBLOCK and blocked_users):
        print("  No ignored (or blocked) users found — nothing to do.")
    else:
        if ignored_users:
            print(f"  {len(ignored_users)} ignored user(s):\n")
            unignored = 0
            for rel in ignored_users:
                user  = rel.get("user", {})
                uname = user.get("username", "unknown")
                uid   = user.get("id")
                if DRY_RUN:
                    print(f"    [DRY RUN] would unignore: {uname}")
                else:
                    ok = _delete(f"/users/@me/relationships/{uid}/ignore")
                    if ok:
                        unignored += 1
                        print(f"    ✓ unignored: {uname}")
                    else:
                        print(f"    ✗ failed:    {uname}")
                    time.sleep(ACTION_DELAY)
            if not DRY_RUN:
                print(f"\n  Unignored {unignored}/{len(ignored_users)} user(s)")
            print()

        if ALSO_UNBLOCK and blocked_users:
            print(f"  {len(blocked_users)} blocked user(s):\n")
            unblocked = 0
            for rel in blocked_users:
                user  = rel.get("user", {})
                uname = user.get("username", "unknown")
                uid   = user.get("id")
                if DRY_RUN:
                    print(f"    [DRY RUN] would unblock: {uname}")
                else:
                    ok = _delete(f"/users/@me/relationships/{uid}")
                    if ok:
                        unblocked += 1
                        print(f"    ✓ unblocked: {uname}")
                    else:
                        print(f"    ✗ failed:    {uname}")
                    time.sleep(ACTION_DELAY)
            if not DRY_RUN:
                print(f"\n  Unblocked {unblocked}/{len(blocked_users)} user(s)")
            print()

    # ── Unmute all open DMs (added after unignore) ────────────────────────────
    print("━" * 56)
    print("  Unmuting all open DMs")
    print("━" * 56)
    print()

    open_dms = []
    for ch in open_channels:
        if ch.get("type") == 1:
            recipients = ch.get("recipients") or []
            name = recipients[0].get("username", ch["id"]) if recipients else ch["id"]
            open_dms.append((ch["id"], name))

    if not open_dms:
        print("  No open DMs found.")
    else:
        print(f"  {len(open_dms)} open DM(s):\n")
        for cid, name in open_dms:
            if DRY_RUN:
                print(f"    [DRY RUN] would unmute: {name}")
            else:
                ok = unmute_dm(cid)
                print(f"    {'✓ unmuted' if ok else '✗ failed'}: {name}")
                time.sleep(ACTION_DELAY)
    print()

    # Done
    print("╔══════════════════════════════════════════════════════╗")
    if DRY_RUN:
        print("║  Dry run done. Set DRY_RUN = False and run again.   ║")
    else:
        print("║  ✅  Done!                                           ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

if __name__ == "__main__":
    main()
