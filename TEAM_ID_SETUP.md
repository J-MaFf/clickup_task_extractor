# Finding Your ClickUp Team ID

Since the `/team` API endpoint is not accessible for your account (SHARD_006 error), you'll need to provide your Team ID directly.

## How to Find Your Team ID

1. **Log into ClickUp web interface**
   - Go to https://app.clickup.com

2. **Find your Team ID**
   
   **Option A: From Settings**
   - Click on your workspace name (top left)
   - Select "Workspace Settings" or similar
   - Look for "Team ID" or "Workspace ID" in the settings
   
   **Option B: From the URL**
   - Look at the URL when you're in your workspace
   - It will look something like: `https://app.clickup.com/v/wGk8qxl/v/team/...`
   - The team ID is often in the URL structure

## Using the Team ID

### Option 1: Set Environment Variable (Recommended for recurring use)

```powershell
$env:CLICKUP_TEAM_ID = "your_team_id_here"
.\.venv\Scripts\python.exe main.py
```

### Option 2: Prompt on Run

Simply run the script and it will prompt you for the Team ID:

```powershell
.\.venv\Scripts\python.exe main.py
```

When prompted, enter your Team ID.

## Example

If your Team ID is `123456`, you would run:

```powershell
$env:CLICKUP_TEAM_ID = "123456"
.\.venv\Scripts\python.exe main.py
```

## Troubleshooting

If you still get errors:
- Double-check the Team ID is correct
- Make sure you're using just the ID number, not any text
- Verify your API key has access to this workspace
