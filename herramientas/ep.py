import re,html,os,sys,glob
def spine(d):
    opf=glob.glob(d+'/OPS/*.opf')[0]; s=open(opf,encoding='utf-8').read()
    man=dict(re.findall(r'<item[^>]*id="([^"]+)"[^>]*href="([^"]+)"',s))
    man.update({a:b for b,a in re.findall(r'<item[^>]*href="([^"]+)"[^>]*id="([^"]+)"',s)})
    ids=re.findall(r'<itemref[^>]*idref="([^"]+)"',s)
    return [os.path.join(os.path.dirname(opf),man[i]) for i in ids if man.get(i,'').endswith('html')]
def paras(d):
    out=[]
    for f in spine(d):
        s=open(f,encoding='utf-8').read()
        s=s[s.find('<body'):]
        for m in re.finditer(r'<(p|h[1-6])\b([^>]*)>(.*?)</\1>',s,re.S):
            tag,attr,inner=m.groups()
            head = tag.startswith('h') or 'role="heading"' in attr or 'role="heading"' in inner
            cls=re.search(r'class="([^"]*)"',attr); cls=cls.group(1) if cls else ''
            out.append(dict(f=os.path.basename(f),tag=tag,cls=cls,head=head,inner=inner,text=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','',inner))).replace('\xa0',' ').strip()))
    return out
