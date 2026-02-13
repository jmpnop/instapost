# Schedule Analysis Error and Fix

## What Went Wrong

During analysis of the Feb 9-13 daemon outage, I made several critical errors:

### Error 1: Manual Day-of-Week Calculation
```python
# WRONG - Manual calculation without checking actual weekly schedule
if crash_time < slot_time < restart_time:
    print("MISSED SLOT")
```

I manually assumed which days should have posts without reading the `WEEKLY_SCHEDULE` configuration:
- ❌ Claimed "Mon Feb 09, 18:00" was a missed slot
- ❌ Reality: Monday only has a 07:00 slot, not 18:00
- ❌ Sunday has the 18:00 slot, not Monday

### Error 2: Confusing Day Names
```python
# WRONG - Confusing output
print("Mon Feb 09 at 18:00 (Sunday 18:00)")
```

This is nonsensical - if the date is Feb 9 and Feb 9 is Monday, then it cannot be "Sunday 18:00".

### Error 3: Not Cross-Referencing With Actual Schedule
I didn't check if images were actually scheduled for the time slots I claimed were "missed":
- ❌ Said 3 slots were missed
- ✅ Reality: Only 1 valid slot existed during outage

## The Fix

### Created `instapost/schedule_analyzer.py`

This module prevents manual calculation errors by:

#### 1. Reading Actual Weekly Schedule
```python
def get_valid_posting_slots(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Calculate valid slots from WEEKLY_SCHEDULE, not manual assumptions."""
    for weekday in WEEKLY_SCHEDULE:  # Only iterate over configured days
        for time_str in WEEKLY_SCHEDULE[weekday]:  # Only use configured times
            # Create actual datetime for slot
```

#### 2. Cross-Referencing With Data Files
```python
def analyze_outage_period(crash_time, restart_time):
    """Cross-reference valid slots with schedule.json and processed.json."""
    valid_slots = get_valid_posting_slots(crash_time, restart_time)  # From config
    scheduled = get_scheduled_posts()  # From schedule.json
    processed = get_processed_posts()  # From processed.json

    # Match them up accurately
```

#### 3. Providing Verifiable Output
```python
POSTING SLOTS DURING OUTAGE:
  Total valid slots: 1              ← From WEEKLY_SCHEDULE + calendar
  Slots with posts scheduled: 1     ← From schedule.json
  Empty slots: 0                    ← Calculated difference
```

## Correct Analysis

### Weekly Schedule Configuration
```
WEEKLY_SCHEDULE="0:07:00,2:11:00,4:17:00,5:09:00,6:18:00"
```

Translates to:
- **Monday (0):** 07:00 only
- **Wednesday (2):** 11:00 only
- **Friday (4):** 17:00 only
- **Saturday (5):** 09:00 only
- **Sunday (6):** 18:00 only

**Tuesday and Thursday have NO posting slots.**

### Outage Period: Feb 9 13:00 → Feb 13 01:00

Valid posting slots during this window:
1. **Wed Feb 11, 11:00** ← Only valid slot

That's it. Only 1 slot.

### What Actually Happened

| Slot | Image | Outcome |
|------|-------|---------|
| Wed Feb 11, 11:00 | 92b17f3d-0257...jpg | Posted 38h late on Feb 13, 00:58 ✅ |

**Result:**
- ✅ 0 posts lost
- ✅ 0 posts missed permanently
- ✅ 1 post delayed (posted when daemon restarted)

## How to Use

### CLI Command
```bash
# Analyze any outage period
uv run instapost analyze-outage \
  --crash-time "2026-02-09 13:00" \
  --restart-time "2026-02-13 01:00"
```

### Python API
```python
from datetime import datetime
from instapost.schedule_analyzer import format_outage_report
from instapost.settings import TIMEZONE

crash = TIMEZONE.localize(datetime(2026, 2, 9, 13, 0))
restart = TIMEZONE.localize(datetime(2026, 2, 13, 1, 0))

report = format_outage_report(crash, restart)
print(report)
```

## Lessons Learned

1. **Never manually calculate schedules** - always read from configuration
2. **Always cross-reference data sources** - config, schedule.json, processed.json
3. **Verify day-of-week assumptions** - use actual calendar calculations
4. **Make analysis reproducible** - write code that can be re-run to verify
5. **Test with actual data** - don't assume, check against real files

## Prevention

The `schedule_analyzer.py` module is now the **single source of truth** for schedule analysis. Future analyses should:

1. Use `get_valid_posting_slots()` instead of manual calculation
2. Use `analyze_outage_period()` for outage analysis
3. Use `format_outage_report()` for formatted output
4. Use the CLI command `analyze-outage` for quick checks

This ensures all analyses are:
- ✅ Based on actual configuration
- ✅ Cross-referenced with real data
- ✅ Reproducible and verifiable
- ✅ Accurate and trustworthy
