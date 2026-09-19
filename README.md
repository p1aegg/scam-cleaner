# Discord MrBeast / Spam Cleanup Tool (v8)

A Python script that helps clean up after a Discord account compromise, particularly the common **MrBeast / free Nitro / giveaway** scam wave.

It can:

1. Scan your DMs for your own recent messages that look like scam spam (attachments, embeds, links, or known keywords)
2. Delete those messages
3. Unignore every ignored user
4. Unmute every currently open DM
5. Optionally unblock users (disabled by default)

---

## ⚠️ Critical Warnings

- **Never share your Discord user token.** Treat it exactly like a password.
- **Change your Discord password and enable 2FA** *before* running this tool.
- This tool uses a **user token**, which violates Discord’s Terms of Service. Use it **only** for legitimate account cleanup after a compromise.
- Run it at your own risk. The author is not responsible for any account action taken by Discord.

---

## Features

| Feature                    | Description |
|---------------------------|-------------|
| **Scam message detection** | Detects your own messages containing media, embeds, links, or common scam keywords |
| **Selective deletion**     | Only deletes *your* messages that match the criteria |
| **Unignore**               | Removes the “Ignore” flag from every ignored user |
| **Unmute open DMs**        | Unmutes all currently open direct message channels |
| **Optional unblock**       | Can also remove full blocks (off by default) |
| **Dry-run mode**           | Preview everything without making any changes |
| **Rate-limit friendly**    | Built-in delays to reduce the chance of hitting Discord rate limits |

---

## Requirements

- Python 3.10+
- `requests` library

```bash
pip install requests
```

---

## Configuration

Edit the variables at the top of the script:

| Variable              | Default | Description |
|-----------------------|---------|-------------|
| `TOKEN`               | `""`    | **Required.** Your Discord user token |
| `DRY_RUN`             | `False` | `True` = only print what would happen, change nothing |
| `ONLY_UNIGNORE`       | `False` | `True` = skip message scanning/deletion, only unignore + unmute |
| `SKIP_OPEN_CLOSED_DMS`| `False` | `True` = only scan currently open DMs (faster).<br>`False` = also reopen closed DMs so nothing is missed |
| `CHECK_LAST_N`        | `1`     | How many of the most recent messages to inspect per channel |
| `ALSO_UNBLOCK`        | `False` | `True` = also remove full blocks (relationship type 2) |
| `DELETE_DELAY`        | `0.8`   | Seconds to wait after each message deletion |
| `PAGE_DELAY`          | `0.6`   | Seconds to wait between channel scans |
| `OPEN_DM_DELAY`       | `0.6`   | Seconds to wait when reopening closed DMs |
| `ACTION_DELAY`        | `0.5`   | Seconds to wait between unignore / unmute / unblock actions |

You can also customize the `SCAM_KEYWORDS` list if needed.

---

## How to Use

1. **Secure your account first**
   - Change your Discord password
   - Enable two-factor authentication (2FA)
   - Review connected apps / authorized devices

2. **Get your user token**
   - Use the official Discord client or a trusted method to obtain your user token.
   - **Never** paste it into any website or share it with anyone.

3. **Configure the script**
   - Paste your token into the `TOKEN` variable.
   - Start with `DRY_RUN = True` to preview actions.
   - Decide whether you want full cleanup or only unignore + unmute.

4. **Run the script**

```bash
python discord_cleanup.py
```

5. **Review the output**
   - If everything looks correct, set `DRY_RUN = False` and run again.

---

## What the Tool Does (Step-by-Step)

When `ONLY_UNIGNORE = False` (full mode):

1. Authenticates with your token
2. Collects open DM channels
3. Optionally reopens closed DMs for every relationship
4. Scans the latest `CHECK_LAST_N` message(s) in each channel
5. Deletes any of **your** messages that contain:
   - Attachments / images / GIFs
   - Embeds
   - Links
   - Any of the configured scam keywords
6. Unignores every ignored user
7. Unmutes every currently open DM
8. Optionally unblocks users (if `ALSO_UNBLOCK = True`)

When `ONLY_UNIGNORE = True`:

- Skips all message scanning and deletion
- Only performs unignore + unmute (and optional unblock)

---

## Recommended First Run

```python
DRY_RUN = True
ONLY_UNIGNORE = False
SKIP_OPEN_CLOSED_DMS = False   # or True if you want it faster
CHECK_LAST_N = 1
ALSO_UNBLOCK = False
```

After reviewing the dry-run output, switch to:

```python
DRY_RUN = False
```

and run again.

---

## Notes

- The tool only deletes **your own** messages that match the scam heuristics.
- It does **not** delete other people’s messages.
- Keeping the delay values ≥ 0.5 seconds is strongly recommended to avoid rate limits.
- If you are rate-limited, the script will automatically wait and retry.

---

## Disclaimer

This tool is provided for educational and legitimate account-recovery purposes only.  
Using self-bots / user-token automation is against Discord’s Terms of Service and can result in account termination. Use at your own risk.
