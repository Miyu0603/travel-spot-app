"""Fill in missing location data on spots that were saved before Google Places
was wired up.

By default only empty fields are written, so anything edited by hand is left
alone. Pass --refresh to also replace address, hours and coordinates that were
guessed by the LLM.

    python backfill_places.py              # 只補空欄位
    python backfill_places.py --refresh    # 連既有值也用 Places 更新
    python backfill_places.py --dry-run    # 只顯示會改什麼，不寫入
"""

import argparse
import asyncio
import sys

from app.config import settings
from app.database import SessionLocal
from app.models.source import Source  # noqa: F401  (needed to configure mappers)
from app.models.spot import Spot
from app.services.geo_service import lookup_google_place, probe_places_access

# Fields the edit form exposes: only filled when empty, so a manual correction
# is never overwritten unless --refresh is asked for.
USER_EDITABLE = ("address", "business_hours")

# Fields no UI can change. Places is always the better source, and
# google_maps_url in particular is never empty — the old code always wrote a
# search URL — so fill-when-empty would never replace it with the real place link.
ALWAYS_REFRESH = ("latitude", "longitude", "google_maps_url")

FILLABLE = USER_EDITABLE + ALWAYS_REFRESH


def _current(spot: Spot, field: str):
    return getattr(spot, field)


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                        help="也覆寫已有的地址、營業時間與座標")
    parser.add_argument("--dry-run", action="store_true",
                        help="只顯示會變更什麼，不寫入資料庫")
    args = parser.parse_args()

    ok, detail = await probe_places_access()
    print(detail)
    if not ok:
        return 1
    print()

    db = SessionLocal()
    try:
        spots = db.query(Spot).order_by(Spot.id).all()
        print(f"共 {len(spots)} 筆景點，模式："
              f"{'覆寫既有的地址與營業時間' if args.refresh else '地址與營業時間只補空欄位'}"
              f"（座標與地圖連結一律更新）"
              f"{'（dry-run，不寫入）' if args.dry_run else ''}\n")

        updated = 0
        not_found = 0
        for spot in spots:
            query = f"{spot.title} {spot.address or ''}".strip()
            found = await lookup_google_place(query)
            if not found:
                not_found += 1
                print(f"  #{spot.id} {spot.title} → Places 查無結果，略過")
                continue

            changes = {}
            for field in FILLABLE:
                new_value = found.get(field)
                if new_value in (None, ""):
                    continue
                may_write = (
                    field in ALWAYS_REFRESH
                    or args.refresh
                    or _is_empty(_current(spot, field))
                )
                if may_write and _current(spot, field) != new_value:
                    changes[field] = new_value

            extras = found.get("place_extras")
            if extras and extras not in (spot.notes or ""):
                changes["notes"] = f"{spot.notes}；{extras}" if spot.notes else extras

            if not changes:
                print(f"  #{spot.id} {spot.title} → 已完整，無變更")
                continue

            updated += 1
            print(f"  #{spot.id} {spot.title} → 更新 {', '.join(changes)}")
            if not args.dry_run:
                for field, value in changes.items():
                    setattr(spot, field, value)

        if args.dry_run:
            db.rollback()
            print(f"\ndry-run 結束：{updated} 筆會被更新、{not_found} 筆查無結果，未寫入任何資料。")
        else:
            db.commit()
            print(f"\n完成：{updated} 筆已更新、{not_found} 筆查無結果。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
