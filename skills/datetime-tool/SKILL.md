---
name: openakita/skills@datetime-tool
description: Get current time, format dates, calculate date differences, and convert timezones. Use this skill when the user asks about time, dates, timezone conversions, weekdays, or needs date calculations and formatting in any locale.
license: MIT
metadata:
  author: myagent
  version: "1.0.0"
---

# DateTime Tool

Handle time and date-related operations.

## When to Use

- User asks about current time or date
- Need to format date output
- Calculate the difference between two dates
- Timezone conversion
- Get day of week, month names, etc.

## Instructions

### Get Current Time

Run the script to get the current time:

```bash
python scripts/get_time.py
```

Supported parameters:
- `--timezone <tz>`: Specify timezone (e.g., Asia/Shanghai, UTC)
- `--format <fmt>`: Date format (e.g., %Y-%m-%d %H:%M:%S)

### Calculate Date Difference

```bash
python scripts/get_time.py --diff "2024-01-01" "2024-12-31"
```

### Timezone Conversion

```bash
python scripts/get_time.py --convert "2024-01-01 12:00:00" --from-tz UTC --to-tz Asia/Shanghai
```

## Output Format

Script outputs in JSON format:

```json
{
  "datetime": "2024-01-15 10:30:00",
  "date": "2024-01-15",
  "time": "10:30:00",
  "timezone": "Asia/Shanghai",
  "weekday": "Monday",
  "timestamp": 1705285800
}
```

## Common Formats

| Format | Example |
|--------|---------|
| ISO | 2024-01-15T10:30:00+08:00 |
| Chinese | 2024年01月15日 10:30:00 |
| US | 01/15/2024 |
| EU | 15/01/2024 |
