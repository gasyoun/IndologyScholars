import csv, json, io, sys
sys.stdout.reconfigure(encoding='utf-8')
out=[]
def head(path, n=2):
    out.append("\n#### %s" % path)
    try:
        with open(path, encoding='utf-8') as f:
            r=csv.reader(f)
            rows=[]
            for i,row in enumerate(r):
                rows.append(row)
                if i>n: break
        out.append("COLS: %r" % (rows[0] if rows else None))
        for row in rows[1:]:
            out.append("ROW : %r" % row)
        # total rows
        with open(path, encoding='utf-8') as f:
            total=sum(1 for _ in f)-1
        out.append("ROWS(excl header): %d" % total)
    except Exception as e:
        out.append("ERR %s"%e)

head('analytics_output/expanded_classification_deepseek.csv')
head('analytics_output/meso_codes_deepseek.csv')
head('analytics_output/expanded_gumilyov_elevated_audit.csv')
head('analytics_output/presentation_id_manifest.csv')

# unique_presentations from summary
try:
    s=json.load(open('site_data_summary.json',encoding='utf-8'))
    out.append("\nsummary.unique_presentations=%r total_presentations=%r" % (s.get('unique_presentations'), s.get('total_presentations')))
except Exception as e:
    out.append("ERR summary %s"%e)

# CLASSIFICATION_OVERRIDES source location & count
try:
    import classification_overrides as co
    keys=[k for k in dir(co) if not k.startswith('_')]
    out.append("\nclassification_overrides module attrs: %r" % keys)
    if hasattr(co,'CLASSIFICATION_OVERRIDES'):
        d=co.CLASSIFICATION_OVERRIDES
        out.append("CLASSIFICATION_OVERRIDES entries: %d; sample keys: %r" % (len(d), list(d)[:5]))
except Exception as e:
    out.append("ERR co %s"%e)

open('scratch/classif_schema.txt','w',encoding='utf-8').write("\n".join(out))
print("done")
