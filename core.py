"""
core.py - Cerebro do gerador de relatorio do Vestibular UGB-FERP.
Le os 5 PDFs brutos, aplica as regras de limpeza, calcula os 10 numeros
e gera a arte (PNG) atualizada a partir do template.
"""
import os, re
from collections import defaultdict
import pdfplumber
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(BASE, "static", "template.png")
FONT_BOLD = os.path.join(BASE, "static", "fonts", "Poppins-Bold.ttf")
FONT_MED = os.path.join(BASE, "static", "fonts", "Poppins-Medium.ttf")

# ----------------------------------------------------------------------------
# 1) PARSING + REGRAS DE LIMPEZA
# ----------------------------------------------------------------------------
def _is_test(n):
    n = (n or "").upper()
    return "TEST" in n or "DTI" in n

def _digits(s):
    return re.sub(r"\D", "", s or "")

def _full_text(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)

def classify(path):
    """Identifica qual dos 5 relatorios e o PDF, pelo conteudo."""
    t = _full_text(path).upper()
    if "LISTA DE INSCRITOS" in t:
        return "inscritos"
    if "TOTALIZADOR" in t:
        return "totalizador"
    if "PRIMEIRA MENSALIDADE" in t or "CÓDIGO 422" in t or "CODIGO 422" in t:
        return "pagas"
    if "CANDIDATOS MATRICULADOS" in t:
        m = re.search(r"TOTAL POR UNIDADE:\s*\d+\s*/\s*TOTAL ATIVO:\s*(\d+)", t)
        ativo = int(m.group(1)) if m else 0
        return "matriculados" if ativo > 0 else "aprovados"
    return "desconhecido"

def parse_inscritos(path):
    rows = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for tb in pg.extract_tables():
                for r in tb:
                    if not r or not r[0]:
                        continue
                    insc = r[0].strip()
                    if not re.fullmatch(r"\d{5,6}", insc):
                        continue
                    nome = (r[1] or "").replace("\n", " ").strip()
                    cel = _digits(r[5]) if len(r) > 5 else ""
                    forma = (r[6] or "").replace("\n", " ").strip() if len(r) > 6 else ""
                    pago = (len(r) > 7 and "PAGO" in (r[7] or "").upper()
                            and "NÃO" not in (r[7] or "").upper())
                    rows.append(dict(insc=int(insc), nome=nome, cel=cel, forma=forma, pago=pago))
    return rows

def clean_inscritos(rows):
    """Remove testes e duplicidades (por celular)."""
    base = [r for r in rows if not _is_test(r["nome"])]
    n_test = len(rows) - len(base)
    grupos = defaultdict(list)
    for r in base:
        grupos[r["cel"]].append(r)
    kept = []
    for cel, g in grupos.items():
        if len(g) == 1:
            kept.append(g[0]); continue
        pagos = [x for x in g if x["pago"]]
        kept.append(max(pagos, key=lambda x: x["insc"]) if pagos
                    else max(g, key=lambda x: x["insc"]))
    pago = sum(1 for r in kept if r["pago"])
    return dict(total=len(kept), pago=pago, naopago=len(kept) - pago,
                n_test=n_test, n_dup=len(base) - len(kept))

def _count_rows(path):
    n = tests = 0
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for tb in pg.extract_tables():
                for r in tb:
                    if r and r[0] and re.fullmatch(r"\d{5,6}", r[0].strip()):
                        n += 1
                        if _is_test(r[1] if len(r) > 1 else ""):
                            tests += 1
    return n, tests

def _grep_num(path, pattern):
    m = re.search(pattern, _full_text(path))
    return int(m.group(1)) if m else None

def computar(paths_por_tipo):
    """
    paths_por_tipo: dict {tipo: caminho} com 'inscritos','aprovados','matriculados','pagas'.
    Retorna dict com os 10 valores + diagnostico.
    """
    ins = parse_inscritos(paths_por_tipo["inscritos"])
    c = clean_inscritos(ins)
    aprov_rows, aprov_tests = _count_rows(paths_por_tipo["aprovados"])
    aprovados = aprov_rows - aprov_tests
    matric = _grep_num(paths_por_tipo["matriculados"],
                       r"TOTAL POR UNIDADE:\s*\d+\s*/\s*TOTAL ATIVO:\s*(\d+)") or 0
    pagas = _grep_num(paths_por_tipo["pagas"], r"Total Geral:\s*(\d+)") or 0

    total, pago, naopago = c["total"], c["pago"], c["naopago"]
    precisa_prova = pago - aprovados
    precisa_mensal = aprov_rows - pagas      # 66 - 7 = 59 (igual a arte aprovada)
    total_geral = matric + pagas

    return dict(
        valores={
            1: total, 2: pago, 3: aprovados, 4: matric,
            5: naopago, 6: precisa_prova, 7: precisa_mensal, 8: pagas, 9: total_geral,
        },
        diag=dict(bruto=len(ins), testes=c["n_test"], duplicidades=c["n_dup"],
                  aprov_rows=aprov_rows, aprov_tests=aprov_tests),
    )

# ----------------------------------------------------------------------------
# 2) MOTOR DE IMAGEM (substitui os 10 numeros no template, mantendo o design)
# ----------------------------------------------------------------------------
LEFT, RIGHT = 606, 1396
ROWY = {1: 421, 2: 629, 3: 831, 4: 1026}
CLEANY = {1: 493, 2: 684, 3: 898, 4: 1076}
F18 = {1: (LEFT, 1), 2: (LEFT, 2), 3: (LEFT, 3), 4: (LEFT, 4),
       5: (RIGHT, 1), 6: (RIGHT, 2), 7: (RIGHT, 3), 8: (RIGHT, 4)}
F10_X, F10_BASE, F10_H = 1675, 1268, 27  # rodape (semestre anterior)

def _fit(text, th, path):
    lo, hi = 20, 150
    for _ in range(18):
        mid = (lo + hi) / 2
        b = ImageFont.truetype(path, int(round(mid))).getbbox(text)
        if (b[3] - b[1]) < th: lo = mid
        else: hi = mid
    return ImageFont.truetype(path, int(round((lo + hi) / 2)))

def _pad(x):
    s = str(x)
    return s.zfill(2) if len(s) == 1 else s

def gerar_imagem(valores, label_anterior, num_anterior, out_path):
    """valores: dict {1..9: int}; label_anterior ex '2025.2'; num_anterior ex 32."""
    import numpy as np
    base = Image.open(TEMPLATE).convert("RGB")
    A0 = np.array(base)

    def wm(t):
        return (A0[:, :, 0] > t[0]) & (A0[:, :, 1] > t[1]) & (A0[:, :, 2] > t[2])

    def iso(yt, yb, x0, x1, gap, t):
        m = wm(t); col = m[yt:yb, x0:x1].any(0); xs = np.where(col)[0]
        grp = [[xs[0]]]
        for x in xs[1:]:
            (grp[-1].append(x) if x - grp[-1][-1] < gap else grp.append([x]))
        g = grp[-1]; bx0, bx1 = x0 + g[0], x0 + g[-1]
        sub = m[yt:yb, bx0:bx1 + 1]; ys = np.where(sub.any(1))[0]
        return (int(bx0), int(yt + ys.min()), int(bx1), int(yt + ys.max()))

    bb9 = iso(1122, 1183, 790, 1290, 20, (200, 205, 205))  # "29"
    arr = A0.copy()

    def erase_row(x0, y0, x1, y1, clean_y):
        row = arr[clean_y, x0:x1].copy()
        arr[y0:y1, x0:x1] = row[None, :, :]

    for f, (cx, r) in F18.items():
        cy = ROWY[r]; erase_row(cx - 178, cy - 52, cx + 178, cy + 50, CLEANY[r])
    cy9 = (bb9[1] + bb9[3]) // 2
    erase_row(bb9[0] - 10, cy9 - 50, min(bb9[2] + 95, 1320), cy9 + 48, 1196)
    erase_row(1665, 1236, 1732, 1272, 1231)  # rodape "32" (abaixo da linha)

    img = Image.fromarray(arr); d = ImageDraw.Draw(img); col = (248, 251, 255)
    for f, (cx, r) in F18.items():
        d.text((cx, ROWY[r]), _pad(valores[f]), font=_fit(_pad(valores[f]), 57, FONT_BOLD),
               fill=col, anchor="mm")
    d.text((bb9[0], cy9), _pad(valores[9]), font=_fit(_pad(valores[9]), bb9[3] - bb9[1], FONT_BOLD),
           fill=col, anchor="lm")
    d.text((F10_X, F10_BASE), _pad(num_anterior), font=_fit(_pad(num_anterior), F10_H, FONT_MED),
           fill=(247, 251, 254), anchor="ls")
    img.save(out_path)
    return out_path
