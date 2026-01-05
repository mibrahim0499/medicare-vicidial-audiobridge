# Quick Fix: Add Stasis Routing to VICIdial Outbound Calls

## Problem
Your outbound calls are not entering the Stasis application, so the bridge doesn't detect them.

## Solution Steps

### Step 1: Check the Actual Dialplan That Was Executed

On your VICIdial server, run:

```bash
# Check the dialplan for the extension that was called
asterisk -rx "dialplan show 917786523395@default"

# Check extension 6000 (which should work)
asterisk -rx "dialplan show 6000@default"

# Check for any Stasis references
asterisk -rx "dialplan show" | grep -i stasis
```

### Step 2: Find Where VICIdial Generates Dialplan

VICIdial generates dialplans dynamically. Check these locations:

```bash
# Check VICIdial scripts
ls -la /usr/share/astguiclient/*dial*.pl
ls -la /usr/share/astguiclient/*exten*.pl

# Check for dialplan files
ls -la /etc/asterisk/extensions*.conf
```

### Step 3: Check the Dial() Command in Logs

From your Asterisk logs, the call executed:
```
-- Executing [917786523395@default:2] Dial("Local/8600051@default-00000000;1", "SIP/denovo/17786523395,,tToR")
```

This shows the Dial() command doesn't route to Stasis after answer.

### Step 4: Fix the Dialplan

You need to modify the dialplan generation so that after Dial() completes, it routes to Stasis.

**Option A: Modify Dial() to use 'b' option (Best)**

Change the Dial() command from:
```
Dial(SIP/denovo/${EXTEN:1},,tToR)
```

To:
```
Dial(SIP/denovo/${EXTEN:1},,tToR(b(audio-bridge-outbound^s^1)))
```

**Option B: Add priority after Dial()**

After the Dial() line, add:
```
exten => <pattern>,n,Goto(audio-bridge-outbound,s,1)
```

### Step 5: Create the Stasis Routing Context

Create `/etc/asterisk/extensions_audio_bridge.conf`:

```ini
[audio-bridge-outbound]
exten => s,1,NoOp(Routing call to Stasis audio-bridge)
exten => s,n,Stasis(audio-bridge,${UNIQUEID},${UNIQUEID})
exten => s,n,Hangup()
```

Then include it in `/etc/asterisk/extensions.conf`:
```ini
#include "extensions_audio_bridge.conf"
```

### Step 6: Reload and Test

```bash
# Reload dialplan
asterisk -rx "dialplan reload"

# Verify the context exists
asterisk -rx "dialplan show audio-bridge-outbound"

# Make a test call and check bridge logs
```

## Quick Commands to Run Now

Run these commands on your server to diagnose:

```bash
# 1. Check extension 6000 (working example)
asterisk -rx "dialplan show 6000@default"

# 2. Check for Stasis in dialplan
asterisk -rx "dialplan show" | grep -i stasis

# 3. Find VICIdial dialplan generation
find /usr/share/astguiclient -name "*dial*.pl" -o -name "*exten*.pl" | head -5

# 4. Check current extensions files
ls -la /etc/asterisk/extensions*.conf
```

Then share the output and we can provide the exact fix!

