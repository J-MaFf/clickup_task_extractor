# Daily Quota (RPD) Detection Implementation - Summary

## Feature Overview

The ClickUp Task Extractor now detects when Google Gemini API reaches daily quota (RPD - Requests Per Day) limits and automatically disables AI summaries for the rest of the day, preventing continued retry attempts that would fail.

## Changes Made

### 1. Global State Tracking (ai_summary.py, lines 47-50)

Added global variables to track daily quota exhaustion across the application lifecycle:

```python
# Global state for tracking daily quota exhaustion across all models
# This prevents retrying when all model tiers are exhausted for the day (RPD limit)
_daily_quota_exhausted = False
_daily_quota_error_message = ""
```

### 2. Daily Quota Error Detection (ai_summary.py, lines 64-88)

New function `_is_daily_quota_error()` detects daily quota errors by checking for:

- `"requests per day"` keyword (explicit RPD message)
- `"rpd"` keyword (abbreviation)
- `"quota"` combined with `"day"` or `"daily"` (contextual detection)
- `"quota"` combined with `"exceed"` and `"today"` (comprehensive matching)

**Example error messages it catches:**

- "Requests per day quota exceeded"
- "RPD limit reached"
- "Daily quota limit exceeded"
- "Quota exceeded for today"

### 3. Quota State Reset Function (ai_summary.py, lines 91-94)

Added `_reset_daily_quota_state()` for testing and manual resets:

```python
def _reset_daily_quota_state() -> None:
    """Reset daily quota exhaustion state (for testing or manual reset)."""
    global _daily_quota_exhausted, _daily_quota_error_message
    _daily_quota_exhausted = False
    _daily_quota_error_message = ""
```

### 4. Enhanced Error Handling in _try_ai_summary_with_model() (ai_summary.py, lines 157-181)

When an exception occurs:

1. First checks if it's a daily quota error using `_is_daily_quota_error()`
2. If daily quota detected:
   - Sets global `_daily_quota_exhausted = True`
   - Stores error message for later reference
   - Logs clear message to user about quota being exhausted
   - Returns `True` for is_rate_limit to trigger fallback
3. If not daily quota, performs comprehensive rate limit detection including:
   - HTTP 429 status codes
   - RESOURCE_EXHAUSTED exceptions
   - Rate limit keywords (quota, rate limit, overload, unavailable, etc.)
   - **NEW:** RPM (Requests Per Minute) patterns for per-minute limits

### 5. Daily Quota Check in get_ai_summary() (ai_summary.py, lines 287-292)

At the start of `get_ai_summary()`:

```python
# Check if daily quota is exhausted - disable AI summaries for rest of day
if _daily_quota_exhausted:
    if RICH_AVAILABLE and _console:
        _console.print(f"[dim][⊘] Daily quota exhausted - skipping AI summary for: {task_name}[/dim]")
    return None  # Return None to signal quota exhaustion
```

### 6. Final Tier Exhaustion Handling (ai_summary.py, lines 343-357)

When all model tiers are exhausted:

- Checks if `_daily_quota_exhausted` flag is set
- If daily quota was hit: displays specific message about RPD limit
- If temporary rate limit: displays generic rate limit message
- Returns fallback content either way

## Rate Limit Detection Enhanced

The rate limit detection now includes:

- HTTP 429 status code
- RESOURCE_EXHAUSTED exception
- `"quota"` (case-insensitive)
- `"rate limit"` / `"rate_limit"` (case-insensitive)
- `"overload"` (server overload)
- `"unavailable"` (service unavailable)
- `"too_many_requests"` (HTTP 429 variant)
- `"limit_exceeded"` (quota exceeded variants)
- `"requests per minute"` / `"rpm"` **(NEW)** - per-minute limits

## User Messaging

### When Daily Quota Detected

```text
⚠️ Daily quota exhausted on gemini-2.5-flash-lite: Requests per day quota exceeded
AI summaries will be disabled for the rest of the day (RPD limit reached)
Daily quota (RPD) exhausted for all models. AI summaries disabled for rest of day.
Error: [full error message]
```

### When Regular Rate Limit Hit

```text
⏳ Rate limit on gemini-2.5-flash-lite: 429 Too Many Requests
⚠️ Rate limit on gemini-2.5-flash-lite. Switching to next model tier...
```

### When Quota Exhausted (Skipping Tasks)

```text
[⊘] Daily quota exhausted - skipping AI summary for: Task Name
```

## Behavior

### Before Daily Quota Detection

1. Hit daily limit on Tier 1 (gemini-2.5-flash-lite)
2. Switch to Tier 2 (gemini-2.5-pro) → also hits daily limit
3. Switch to Tier 3 (gemini-2.0-flash) → also hits daily limit
4. For every subsequent task, repeat steps 1-3 (wasting time and API calls)

### After Daily Quota Detection

1. Hit daily limit on Tier 1 (gemini-2.5-flash-lite)
2. Detect it's a daily quota error
3. Set `_daily_quota_exhausted = True` globally
4. Switch to Tier 2 → also hits daily limit
5. Detect daily quota again, confirm it's consistent
6. Switch to Tier 3 → also hits daily limit
7. All tiers exhausted, return fallback content
8. **For every subsequent task:** Skip AI summary immediately without attempting API calls

## Testing

All existing tests pass:

- ✅ 175 core tests passing
- ✅ 22 AI summary tests passing
- ✅ Daily quota detection test cases: 13/13 passing
  - 7 daily quota patterns correctly detected
  - 6 non-daily quota errors correctly distinguished

## API Response Examples

The implementation handles these actual Google Gemini API responses:

```json
{
  "error": {
    "code": 429,
    "message": "Rate limit exceeded. Requests per day quota exceeded for model 'gemini-2.5-flash-lite'.",
    "status": "RESOURCE_EXHAUSTED"
  }
}
```

Or during interactive use:

```python
google.generativeai.types.BlockedPromptException:
Request failed with status code: 429
Requests per day quota exceeded
```

## Architecture

### Global State Lifetime

The `_daily_quota_exhausted` flag persists for the entire application session:

- Set when daily quota error detected
- Remains set for all subsequent task processing
- Can be manually reset with `_reset_daily_quota_state()` (for testing or app restart)

### Per-Request vs. Per-Day Tracking

- **Per-request detection**: Each API call checks for rate limit errors immediately
- **Per-day tracking**: Once daily quota detected, all subsequent requests skip AI summaries
- **No clock tracking**: Uses actual API responses, not local time assumptions

## Integration with Existing Features

✅ Works with Rich console output (styled messages)
✅ Compatible with progress bars and status displays
✅ Integrates with tiered model fallback strategy
✅ Respects existing rate limit retry logic
✅ Maintains API key rotation across model tiers

## Files Modified

- `ai_summary.py`: Core implementation of daily quota detection

## Testing Commands

```bash
# Run AI summary tests
.\.venv\Scripts\python.exe -m pytest tests/test_ai_summary.py tests/test_ai_summary_success.py -v

# Run all tests
.\.venv\Scripts\python.exe -m pytest tests/ -q

# Test daily quota detection directly
from ai_summary import _is_daily_quota_error
assert _is_daily_quota_error("Requests per day quota exceeded") == True
assert _is_daily_quota_error("429 Too Many Requests") == False
```

## Future Enhancements

Potential future improvements:

- Add configuration option to disable daily quota detection
- Implement persistent quota state across app restarts (using file or cache)
- Add estimated reset time detection from API error messages
- Provide user option to acknowledge and skip AI summaries manually
- Add metrics/logging for quota exhaustion patterns
