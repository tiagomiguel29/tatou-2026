import argparse
import os
import re
import secrets

from sqlalchemy import URL, column, create_engine, select, table, update


def rotate_legacy_links(connection, *, apply=False):
    versions = table("Versions", column("id"), column("link"))
    query = select(versions.c.id, versions.c.link)
    if apply:
        query = query.with_for_update()
    rows = connection.execute(query).all()
    used = {row.link for row in rows}
    legacy = [row for row in rows if re.fullmatch(r"[0-9a-f]{40}", row.link)]
    if apply:
        for row in legacy:
            token = secrets.token_urlsafe(32)
            while token in used:
                token = secrets.token_urlsafe(32)
            result = connection.execute(update(versions).where(
                versions.c.id == row.id, versions.c.link == row.link).values(link=token))
            if result.rowcount != 1:
                raise RuntimeError("Version changed during rotation; transaction must be rolled back")
            used.add(token)
    return len(legacy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit link rotation; old URLs stop working")
    args = parser.parse_args()
    if not all(os.environ.get(key) for key in ("DB_USER", "DB_PASSWORD", "DB_HOST")):
        parser.exit(1, "DB_USER, DB_PASSWORD and DB_HOST must be configured.\n")
    try:
        url = URL.create("mysql+pymysql", username=os.environ["DB_USER"],
                         password=os.environ["DB_PASSWORD"], host=os.environ["DB_HOST"],
                         port=int(os.environ.get("DB_PORT", "3306")),
                         database=os.environ.get("DB_NAME", "tatou"))
        engine = create_engine(url)
        with engine.begin() as connection:
            count = rotate_legacy_links(connection, apply=args.apply)
        engine.dispose()
    except Exception:
        parser.exit(1, "Link rotation failed. Transaction was rolled back. Check database access.\n")
    print(f"{'Rotated' if args.apply else 'Would rotate'} {count} legacy version links.")


if __name__ == "__main__":
    main()
