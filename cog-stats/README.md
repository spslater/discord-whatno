# Stats Cog
This cog tracks when and how long a user's voice state changes.

## Stats Tracked
- voice
- mute
- deaf
- stream
- video

# todo
- check if exists is failing, inserting instead of updating data

- running sums not working? (kui deaf for 182 min)
- get all messages (walk xela thru unique minutes)
- historic sums audit

```sql
SELECT strftime('%Y-%m-%dT%H:%M:%f', starttime, 'unixepoch', 'localtime') as h_time
FROM History
WHERE channel = 248732519204126721 AND voicestate = voice;

SELECT *, strftime('%Y-%m-%dT%H:%M:%f', starttime, 'unixepoch', 'localtime') as h_time
FROM History
WHERE channel = 248732519204126721 AND historic = 1
ORDER BY duration DESC;

SELECT user, channel, voicestate, starttime, max(duration)
FROM History
GROUP BY user, channel, voicestate, starttime;
```
