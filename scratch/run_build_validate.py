import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from community_lenses import build as clbuild

fixtures = clbuild.load_all_fixtures()
conn = clbuild.build_database(fixtures)
errors = clbuild.validate_build(conn, fixtures)
if errors:
    print("ERRORS:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("build OK, no errors")

dump1 = clbuild.canonical_json(conn)
conn2 = clbuild.build_database(fixtures)
dump2 = clbuild.canonical_json(conn2)
print("deterministic rebuild identical:", dump1 == dump2)
