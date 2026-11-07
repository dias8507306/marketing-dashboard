"""Send the «тіркелдіңіз бе?» follow-up to people inside Meta's 24 h window.

    python broadcast.py <campaign>            # dry run: who would get it
    python broadcast.py <campaign> --send     # really send

Only people who got training links and wrote/tapped in the last 23 hours are
chosen; nobody gets the same campaign twice. Sends are spaced out so the
account never looks like a spam burst.
"""
import asyncio
import os
import sys

import app

PAUSE_SECONDS = 3


async def main(campaign: str, really: bool):
    exclude = [x for x in os.getenv("STATS_EXCLUDE", "").split(",") if x]
    people = app.followup_recipients(campaign, exclude)
    print(f"campaign {campaign!r}: {len(people)} recipient(s) inside the window")
    if not really:
        print("dry run — nothing sent. Add --send to send.")
        return
    await app.whoami()
    if not app.ME.get("id"):
        print("Instagram token not working — aborted, nothing sent.")
        return
    sent = failed = 0
    for i, igsid in enumerate(people, 1):
        if await app.send_followup(igsid, campaign):
            sent += 1
        else:
            failed += 1
            if failed >= 3 and sent == 0:
                print("first sends all failed — stopping to protect the account.")
                break
        print(f"  {i}/{len(people)} ..{igsid[-4:]}")
        await asyncio.sleep(PAUSE_SECONDS)
    print(f"done: sent {sent}, failed {failed}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], "--send" in sys.argv))
