# How to Get the ARI Password

Since the ARI configuration already exists, you need to view the password from the configuration file.

## On Your VICIdial Server (via SSH)

Run this command to view the ARI configuration file:

```bash
sudo cat /etc/asterisk/ari.conf
```

You'll see something like:

```ini
[general]
enabled = yes
pretty = yes
allowed_origins = *

[asterisk]
type = user
read_only = no
password = YOUR_PASSWORD_HERE
```

**Copy the password** from the line that says `password = ...`

## Alternative: View Just the Password

If you want to see only the password line:

```bash
sudo grep "password" /etc/asterisk/ari.conf
```

This will show just:
```
password = YOUR_PASSWORD_HERE
```

## Security Note

- The password is stored in plain text in the config file
- Make sure to copy it exactly (including any special characters)
- Don't share this password publicly

## Next Step

Once you have the password, update your `.env` file on your local machine:

```bash
cd /Users/pc/Documents/Sales-Prompt-App/marsons-projects/phase1-audio-bridge
nano .env
```

Set:
```env
ASTERISK_PASSWORD=YOUR_PASSWORD_HERE
```

