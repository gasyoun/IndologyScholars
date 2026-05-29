import io, sys
sys.stdout.reconfigure(encoding='utf-8')
for f in ['pipeline/parser.py', 'pipeline/schema.py', 'import_json.py']:
    print("\n\n########## FILE:", f, "##########")
    try:
        with open(f, encoding='utf-8') as fh:
            for i, line in enumerate(fh, 1):
                print(f"{i:4}: {line.rstrip()}")
    except Exception as e:
        print("ERR", e)
