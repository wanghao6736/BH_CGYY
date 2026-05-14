# CGYY Venue Reference

## Venue Table

| siteId | Campus | Venue | Sport | Slot |
|--------|--------|-------|-------|:----:|
| 38 | 学院路 | 体育馆主馆 | 羽毛球 | 1h |
| 39 | 学院路 | 体育馆训练馆(副馆) | 羽毛球 | 1h |
| 55 | 沙河 | 综合馆 | 台球厅 | 1h |
| 56 | 沙河 | 综合馆 | 乒乓球 | 1h |
| 57 | 沙河 | 综合馆 | 羽毛球 | 1h |
| 59 | 沙河 | 综合馆 | 游泳馆 | 2h |
| 70 | 学院路 | 体育馆主馆 | 乒乓球 | 1h |
| 72 | 学院路 | 体育馆主馆 | 台球 | 1h |
| 76 | 学院路 | 体育馆主馆 | 多功能厅 | — |
| 164 | 学院路 | 体育馆主馆 | 激光射击 | — |
| 43 | 学院路 | 游泳馆 | 游泳馆 | 2h |
| 123 | 学院路 | 游泳馆 | 体能训练空间 | — |
| 60 | 沙河 | 文艺馆 | 钢琴房 | — |

> Whether a venue needs buddies is shown in the `cgyy info` output header (`👥 需要同伴`). Do not rely on static rules.

Confirm with `cgyy catalog` if uncertain — this table may be outdated.

## Date → YYYY-MM-DD

Today's date is provided in the system prompt. Map user language:

| User says | Meaning |
|-----------|---------|
| 今天 | Today's date |
| 明天 | Today + 1 day |
| 后天 | Today + 2 day |
| 这周五 | This Friday in current week |
| 下周一 | Next Monday |

Always compute the exact `YYYY-MM-DD` before running any command that takes `-d`.

## User Language → Time

| User says | Map to `-s` |
|-----------|-------------|
| 早上 / 上午 | `08:00` |
| 中午 | `12:00` |
| 下午 | `14:00` |
| 傍晚 | `17:00` |
| 晚上 | `19:00` |

## Strategy

| Strategy | Meaning |
|----------|---------|
| `same_first_digit` | Same zone (A/B side) |
| `same_venue` | Same court number |
| `cheapest` | Lowest price |

Default: `same_first_digit,same_venue,cheapest`. Peak demand: `cheapest` only.
