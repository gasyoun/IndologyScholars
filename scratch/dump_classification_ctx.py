import os, re, glob, sys
sys.stdout.reconfigure(encoding='utf-8')
out=[]
def show(f, lo=None, hi=None):
    out.append("\n########## %s (lines %s-%s) ##########" % (f, lo, hi))
    try:
        with open(f, encoding='utf-8') as fh:
            lines = fh.readlines()
        a = (lo-1) if lo else 0
        b = hi if hi else len(lines)
        for i in range(a, min(b, len(lines))):
            out.append("%5d: %s" % (i+1, lines[i].rstrip()))
    except Exception as e:
        out.append("ERR %s" % e)

# 1) Find files mentioning deepseek / expanded classification
out.append("=== grep deepseek/expanded classification in .py ===")
for f in glob.glob('**/*.py', recursive=True):
    if '_site' in f: continue
    try:
        t=open(f,encoding='utf-8').read()
    except: continue
    for kw in ('deepseek','expanded_classification','expanded classification','classification_criteria','ledger_rows'):
        if kw.lower() in t.lower():
            out.append("  %s : %s" % (f, kw))
            break

# 2) Candidate data files for the classification
out.append("\n=== candidate classification data files ===")
for pat in ('**/*classification*','**/*deepseek*','**/*expanded*'):
    for f in glob.glob(pat, recursive=True):
        if '_site' in f or f.endswith('.py'): continue
        try: sz=os.path.getsize(f)
        except: sz=-1
        out.append("  %s (%d bytes)" % (f, sz))

# 3) validate_publication.py: the DeepSeek completeness check
try:
    t=open('validate_publication.py',encoding='utf-8').read().splitlines()
    for i,l in enumerate(t):
        if 'deepseek' in l.lower() or 'expanded' in l.lower() or 'classification' in l.lower():
            lo=max(0,i-3); hi=min(len(t),i+6)
            out.append("\n--- validate_publication.py around %d ---" % (i+1))
            for j in range(lo,hi): out.append("%5d: %s" % (j+1, t[j]))
except Exception as e:
    out.append("ERR validate %s"%e)

# 4) generate_publication_pages.py: classification loader + ledger area
try:
    t=open('generate_publication_pages.py',encoding='utf-8').read().splitlines()
    hits=[i for i,l in enumerate(t) if ('ledger_rows' in l or 'deepseek' in l.lower() or 'expanded_classification' in l.lower() or 'def generate_classification_criteria_page' in l)]
    seen=set()
    for i in hits:
        lo=max(0,i-4); hi=min(len(t),i+8)
        key=(lo//1)
        out.append("\n--- gen_pub_pages around %d ---"%(i+1))
        for j in range(lo,hi): out.append("%5d: %s"%(j+1,t[j]))
except Exception as e:
    out.append("ERR genpub %s"%e)

open('scratch/classification_ctx.txt','w',encoding='utf-8').write("\n".join(out))
print("done", len(out), "lines")
