"""Builds tomos/bienal-1.json (Año I, impar) and tomos/bienal-2.json (Año II, par)
from the deiverbum.org «Leccionario bienal bíblico-patrístico» epubs.
Output format = the app's tomo format: {vol, titulo, p:[[kind, html, label?]], sec:{'T:key': {s,e,n,h:{ol:[s,e]}}}}
Each day keeps only PRIMERA LECTURA (l1), SEGUNDA LECTURA (l2) and the Sunday/feast
«Tercera lectura» on the Gospel (l3, label l3A/l3B/l3C/l3 + variant name)."""
import sys, re, json, glob, os
sys.path.insert(0, os.path.dirname(__file__))
from ep import paras  # herramientas/ep.py

ROM = {'I': 1, 'V': 5, 'X': 10, 'L': 50}
def rom(s):
    s = s.upper(); n = 0
    for i, c in enumerate(s):
        v = ROM[c]; n += -v if i + 1 < len(s) and ROM[s[i + 1]] > v else v
    return n
DOW = {'domingo': 0, 'lunes': 1, 'martes': 2, 'miércoles': 3, 'miercoles': 3, 'jueves': 4, 'viernes': 5, 'sábado': 6, 'sabado': 6}
MES = {'diciembre': 'dic', 'enero': 'ene'}

def clean(t):
    return re.sub(r'\s+', ' ', t.replace('​', ' ')).strip()

def season_of(t):
    u = t.upper()
    if u in ('PROPIO DE LOS SANTOS', 'OFICIOS COMUNES'): return 'stop'
    if 'SOLEMNIDADES DEL SEÑOR' in u: return 'ordinario'
    if 'ADVIENTO' in u and ('SEMANA' in u or 'TIEMPO' in u or 'FERIAS' in u): return 'adviento'
    if 'NAVIDAD' in u and ('TIEMPO' in u or 'OCTAVA' in u) or 'EPIFAN' in u and 'FERIAS' in u: return 'navidad'
    if 'CENIZA' in u and 'SEMANA' in u or 'CUARESMA' in u and ('SEMANA' in u or 'TIEMPO' in u): return 'cuaresma'
    if u in ('SEMANA SANTA', 'TRIDUO PASCUAL'): return 'semana-santa'
    if 'PASCUA' in u and ('SEMANA' in u or 'TIEMPO' in u) or u == 'PENTECOSTÉS': return 'pascua'
    if 'TIEMPO ORDINARIO' in u and 'SEMANA' in u or u == 'TIEMPO ORDINARIO': return 'ordinario'
    return None

def day_key(t, season):
    """Map a day heading to the app's temporal key(s). Returns list of keys or None."""
    t = clean(t); l = t.lower()
    m = re.match(r'^(\d+) de (diciembre|enero)\b(.*)$', l)
    if m and season in ('adviento', 'navidad'):
        d, mes, rest = int(m.group(1)), m.group(2), m.group(3)
        if 'epifan' in rest and 'después del domingo' in rest: return [f'post-epifania/{d - 6}']
        if 'epifanía del señor' in rest: return ['epifania']
        if mes == 'diciembre' and d == 25: return ['navidad']
        if mes == 'enero' and d == 1: return ['maria-madre']
        return [f"{MES[mes]}-{d:02d}" if mes == 'enero' else f'dic-{d}']
    if 'octava de navidad' in l and l.startswith('domingo'): return ['sagrada-familia']
    if l.startswith('domingo después del 6 de enero') or 'bautismo del señor' in l: return ['bautismo']
    if 'miércoles de ceniza' in l: return ['ceniza']
    m = re.match(r'^(jueves|viernes|sábado) después de ceniza', l)
    if m: return [f'cuaresma/0/{DOW[m.group(1)]}']
    if l.startswith('domingo de ramos'): return ['ramos']
    m = re.match(r'^(lunes|martes|miércoles) santo', l)
    if m: return [f'semana-santa/{DOW[m.group(1)]}']
    if l.startswith('jueves santo'): return ['jueves-santo']
    if l.startswith('viernes santo'): return ['viernes-santo']
    if l.startswith('sábado santo'): return ['sabado-santo']
    if l.startswith('domingo de pascua'): return ['pascua']
    m = re.match(r'^(lunes|martes|miércoles|jueves|viernes|sábado) de la octava de pascua', l)
    if m: return [f'pascua/1/{DOW[m.group(1)]}']
    if re.match(r'^la ascensión del señor', l): return ['ascension']
    if l.startswith('domingo de pentecostés'): return ['pentecostes']
    if 'cuerpo y sangre de cristo' in l: return ['corpus']
    if 'santísima trinidad' in l: return ['trinidad']
    if 'sagrado corazón de jesús' in l: return ['sagrado-corazon']
    if 'rey del universo' in l or 'jesucristo, rey' in l: return ['cristo-rey']
    m = re.match(r'^(domingo|lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado) ([ivxl]+)\b(.*)$', l)
    if m and season in ('adviento', 'cuaresma', 'pascua', 'ordinario'):
        w, d, rest = rom(m.group(2)), DOW[m.group(1)], m.group(3)
        key = f'{season}/{w}/{d}'
        if 'antes de la ascensión' in rest: return [key + '@ascDom']
        if 'después de la ascensión' in rest: return [key + '@ascJue']
        if rest.strip(' .') and not rest.strip().startswith(('de ', 'del ')): return None
        return [key]
    return None

SUBHEAD = re.compile(r'^(?:.*?\b)?(Año|Ciclo) ([ABC])\b|^Evangelio\b|^Pentecostés - Año ([ABC])', re.I)

def build(book_dirs, vol, titulo):
    p, sec = [], {}
    for bd in book_dirs:
        P = [x for x in paras(bd) if clean(x['text'])]
        season, started = None, False
        cur = None            # current day: dict(keys, name, items)
        mode = None           # 'l1','l2','l3' or None
        sub = None            # current l3 variant label
        def close():
            nonlocal cur
            if cur and cur['parts']:
                s = len(p); p.append(['h', cur['name']]); p.append(['hh', 'Oficio de lectura'])
                for it in cur['parts']: p.append(it)
                for k in cur['keys']:
                    if 'T:' + k not in sec: sec['T:' + k] = {'s': s, 'e': len(p), 'n': cur['name'], 'h': {'ol': [s + 2, len(p)]}}
            cur = None
        for i, x in enumerate(P):
            t = clean(x['text'])
            link = '<a ' in x['inner'] and 'href' in x['inner']
            if link and (not started or len(t) < 90): continue
            if re.sub(r'^A(?=PROPIO)','',t.upper()) == 'PROPIO DEL TIEMPO': started = True; continue
            s = season_of(t) if len(t) < 90 else None
            if not started and x['head'] and s and s != 'stop' and '<a ' not in x['inner']: started = True
            if not started: continue
            if s == 'stop': close(); break
            nxt = ' | '.join(clean(y['text']) for y in P[i + 1:i + 5])
            dk = day_key(t, s or season) if len(t) < 160 and (x['head'] or len(t) < 45 and re.search(r'(^|\| )(V\. |PRIMERA LECTURA)', nxt, re.I)) else None
            if s and not dk:
                season = s; continue
            if dk:
                close(); cur = {'keys': dk, 'name': t, 'parts': [], 'n': {}}; mode = None; sub = None; continue
            if not cur: continue
            u = re.sub(r'^PRIMER LECTURA$', 'PRIMERA LECTURA', re.sub(r'^SECUNDA', 'SEGUNDA', t.upper()))
            if u == 'PRIMERA LECTURA': mode = 'l1'; cur['parts'].append(['l', 'PRIMERA LECTURA', 'l1']); cur['n'] = {'pos': 0}; continue
            if u == 'SEGUNDA LECTURA': mode = 'l2'; cur['parts'].append(['l', 'SEGUNDA LECTURA', 'l2']); cur['n'] = {'pos': 0}; continue
            if u == 'TERCERA LECTURA':
                mode = 'l3'; lab = sub or 'l3'; cur['parts'].append(['l', 'TERCERA LECTURA', lab]); cur['n'] = {'pos': 0}
                if cur.get('subname'): cur['parts'].append(['r', cur['subname']])
                continue
            if u in ('ORACIÓN', 'ORACION') or u.startswith('DESPUÉS DEL ÚLTIMO RESPONSORIO') or u.startswith('HIMNO TE DEUM'):
                mode = None; continue
            if len(t) < 90 and SUBHEAD.search(t) and not t.startswith(('R.', 'V.')):
                m = SUBHEAD.search(t); yr = (m.group(2) or m.group(3) or '').upper()
                sub = 'l3' + yr if yr else 'l3'
                cur['subname'] = t; cur['pending'] = True
                mode = None; continue
            if mode is None and cur.get('pending') and re.match(r'^(De|Del|Comienza|Sermón|Homilía)\b', t):
                mode = 'l3'; cur['parts'].append(['l', 'TERCERA LECTURA', sub or 'l3']); cur['parts'].append(['r', cur['subname']]); cur['n'] = {'pos': 0}
            if u == 'TERCERA LECTURA' or mode is not None: cur['pending'] = False
            if mode is None: continue
            n = cur['n']; pos = n['pos']; n['pos'] += 1
            html_ = re.sub(r'<br\s*/?>', '<br>', x['inner'])
            html_ = re.sub(r'<(?!br>)[^>]+>', '', html_)
            import html as H
            html_ = clean(H.unescape(html_).replace('\xa0', ' ')).replace('<', '&lt;').replace('&lt;br>', '<br>')
            if t.startswith('Responsorio'): kind = 'v'; n['resp'] = True
            elif n.get('resp'): kind = 'r'
            elif pos == 0: kind = 'r'                                   # «Del libro…» / «De los sermones…»
            elif t.startswith('(') and not n.get('title'): kind = 'v'   # fuente patrística
            elif not n.get('title'): kind = 'ti'; n['title'] = True
            elif re.match(r'^O bien\b', t): kind = 'r'; n.clear(); n['pos'] = 0
            else: kind = 't'
            cur['parts'].append([kind, html_])
        close()
    REF = re.compile(r'^(Comienza|Del?\b|De la|De los|De las|Lectura|Sermón|Homilía|Carta|Tratado|Comentario)', re.I)
    for i in range(len(p) - 2):
        if p[i][0] == 'l' and p[i][2] in ('l1', 'l2') and p[i + 1][0] == 'r' and p[i + 2][0] == 'ti':
            a, b = re.sub('<[^>]+>', '', p[i + 1][1]), re.sub('<[^>]+>', '', p[i + 2][1])
            if not REF.match(a) and REF.match(b.capitalize()) and re.search(r'\d', b):
                p[i + 1], p[i + 2] = ['r', p[i + 2][1]], ['ti', p[i + 1][1]]
    for it in p:
        if it[0] == 'ti': it[1] = it[1].upper()
    return {'formato': 1, 'vol': vol, 'titulo': titulo, 'p': p, 'sec': sec, 'santos': [], 'otp': {}, 'regiones': {}}

if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    ds = sorted(glob.glob(src + '/*/'))
    impar = [d.rstrip('/') for d in ds if re.search(r'^\d\d-impar', os.path.basename(d.rstrip('/')), re.I)]
    par = [d.rstrip('/') for d in ds if re.search(r'^\d\d-par', os.path.basename(d.rstrip('/')), re.I)]
    for vol, books, tit in ((11, impar, 'LECCIONARIO BIENAL · AÑO I (IMPAR)'), (12, par, 'LECCIONARIO BIENAL · AÑO II (PAR)')):
        d = build(books, vol, tit)
        json.dump(d, open(f'{out}/bienal-{vol - 10}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
        print(vol, len(d['p']), 'days', len(d['sec']))
