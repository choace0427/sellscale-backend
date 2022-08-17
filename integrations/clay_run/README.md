Get local Clay.Run clients
1. Open the Network Inspector Tab
2. Log into Clay
3. Find the reuqest for: https://api.clay.run/v1/me
4. Right click, copy as HAR
5. Dump to `sellscale/integrations/clay_run/clay_har.json`
6. Run `python sellscale/integrations/clay_run/clay_cookie_gen.py`