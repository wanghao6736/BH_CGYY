---
name: cgyy
description: Use when the user wants to reserve BUAA sports venues (羽毛球/游泳/乒乓球/台球), check venue availability, poll for open slots, cancel or pay for orders, manage CGYY profiles, or run cgyy/poll scripts. Triggers on any mention of 北航/场地/预约/体育馆/抢场地/订场/CGYY/cgyy/venue booking/poll_reserve — even if the user doesn't say "cgyy" explicitly.
---

# CGYY Venue Reservation

`cgyy` is a CLI for BUAA sports venue booking. Run all commands from the project root directory.

**Environment check (before any command):** verify `cgyy --help` succeeds. If "command not found", remind user to activate their venv/conda environment and run `pip install -e ".[ocr,ui]"`. Do not proceed until `cgyy` is available.

Before reserve/poll/pay, run `cgyy config-doctor`. If auth expired → `cgyy login`.

## Commands

| Intent | Command |
|--------|---------|
| List venues | `cgyy catalog` |
| Check slots + buddies | `cgyy info -d DATE -v SITE_ID -p` |
| Reserve | `cgyy reserve -d DATE -v SITE_ID -s HH:MM -n N -b ID1,ID2 -S STRATEGY` |
| Poll until success | `bash scripts/poll_reserve.sh -d DATE [-i SECONDS] [-p "HH:MM/N,..."] [-v SITE_ID]` |
| Monitor poll | `tail -f poll.log` |
| Stop poll | `jobs` then `kill %N` |
| Order detail / cancel | `cgyy order-detail -t TRADE_NO` / `cgyy cancel-order -t TRADE_NO` |
| Payment link | `cgyy pay -t TRADE_NO --mode mobile` |
| Refresh auth | `cgyy login` |
| Config check | `cgyy config-doctor --probe` |
| Profiles | `cgyy profile list\|show\|add\|modify\|remove` |

`cgyy-lite` omits OCR — never use for `reserve`.

## Options

| Flag | Meaning | Notes |
|------|---------|-------|
| `-d YYYY-MM-DD` | Date | Compute from "明天"/"周五" etc. (see `references/venues.md`) |
| `-v SITE_ID` | Venue ID | See `references/venues.md` |
| `-s HH:MM` | Start time | Omit to show all slots |
| `-n N` | Slot count | Default 2; 1 slot = 1h (badminton) / 2h (swimming) |
| `-b ID1,ID2` | Buddy IDs | Run `info -p` to get buddies |
| `-S STRATEGY` | Filter | `cheapest` for peak; `same_first_digit,cheapest` otherwise |
| `-p` | Show buddy list | `info` only; run first to get buddy IDs |
| `-P NAME` | Profile | Multi-user; map "帮Alice约" → `-P alice` |
| `-i SECONDS` | Poll interval | Default 1800 (30 min); recommend 300–900 |

## Workflow

```
catalog → info -p → reserve (one shot)
                  → if unavailable → poll_reserve.sh
```

**Poll by platform:**
- macOS: `caffeinate -i nohup bash scripts/poll_reserve.sh -d DATE -i 600 -p "17:00/2,19:00/2" -v SITE_ID >> poll.log 2>&1 &`
- Linux: same without `caffeinate`
- Windows: same as Linux, in Git Bash

**After success:** payment within 1 minute. Payment via `cgyy pay -t TRADE_NO --mode mobile` or i北航 app. Users notified via configured channels.

## Reading Output

- `catalog`: table with `siteId / 校区 / 场馆 / 项目` columns. Grab the siteId.
- `info`: venue header shows `👥 需要同伴` if buddies required. Time-slot table follows; missing price = slot taken. With `-p`, buddy list at bottom — use the numeric **ID** (not userID).
- `reserve`: look for `✅ [成功] 提交订单`. Save the trade number.
- `poll.log`: `✅` = success, `❌` = failure. Repeated identical failures → stop and fix root cause.

## Errors

| Symptom | Fix |
|---------|-----|
| `鉴权失效` / `401` | `cgyy login` then retry |
| No available slots / empty table | Try different `-s` or `-d` |
| Missing buddy error | `cgyy info -p` to get IDs, then add `-b` |
| Captcha failure | Retry; if persistent, `pip install -e ".[ocr]"` |

## Examples

**Check availability:**
User: "帮我看明天下午沙河羽毛球有没有空"
→ `cgyy info -d <tomorrow> -v 57 -s 14:00 -p`

**One-shot reserve:**
User: "帮我约后天17点沙河羽毛球2小时，同伴89889和89899"
→ `cgyy config-doctor && cgyy reserve -d <day-after-tomorrow> -v 57 -s 17:00 -n 2 -b 89889,89899 -S same_first_digit,cheapest`

**Polling (macOS):**
User: "帮我抢下周一沙河羽毛球"
→ `cgyy config-doctor && caffeinate -i nohup bash scripts/poll_reserve.sh -d <next-monday> -i 600 -p "15:00/2,17:00/2,19:00/1" -v 57 -S cheapest >> poll.log 2>&1 &`

**Polling (Linux / Windows Git Bash):**
Same without `caffeinate -i`:
```bash
nohup bash scripts/poll_reserve.sh -d DATE -i 600 -p "15:00/2,17:00/2,19:00/1" -v SITE_ID -S cheapest >> poll.log 2>&1 &
```

**Payment:**
→ `cgyy pay -t <trade-no> --mode mobile`

**Cancel:**
→ `cgyy cancel-order -t <trade-no>` (confirm with user first)

## Rules

- Never modify .env unless user explicitly asks
- `config-doctor` before reserve/poll — stale auth wastes cycles
- Check `jobs` before starting new poll — duplicates may trigger rate limits
- Confirm destructive actions (cancel, profile remove) before executing
- Warn: infinite poll runs forever; suggest `-n 200`
- Remind: 1-minute payment window; unpaid orders auto-cancel
