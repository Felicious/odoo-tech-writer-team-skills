import sys, re, glob, os
d=sys.argv[1]
for f in sorted(glob.glob(os.path.join(d,'*.en.vtt'))):
    out=[]; prev=''
    for line in open(f, encoding='utf-8'):
        line=line.strip()
        if not line or '-->' in line or line.startswith(('WEBVTT','Kind:','Language:')): continue
        line=re.sub(r'<[^>]+>','',line).strip()
        if line and line!=prev and (not out or line!=out[-1]):
            out.append(line)
        prev=line
    txt=' '.join(out)
    open(f.replace('.en.vtt','.txt'),'w').write(txt)
    print(os.path.basename(f)[:11], len(txt.split()), 'words')
