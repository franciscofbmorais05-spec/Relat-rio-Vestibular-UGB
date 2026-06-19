"""
app.py - Site do Gerador de Relatorio do Vestibular UGB-FERP.
Upload dos 5 PDFs -> calcula os numeros liquidos -> devolve a arte atualizada.
"""
import os, tempfile, base64
from flask import Flask, request, render_template, abort
import core

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # 60 MB

CAMPOS = {
    1: "Total geral de inscritos", 2: "Inscritos com pagamento de taxa",
    3: "Aprovados", 4: "Matriculados", 5: "Precisam pagar a taxa",
    6: "Precisam fazer prova", 7: "Precisam pagar 1ª mensalidade",
    8: "Matrículas pagos não finalizados", 9: "Total",
}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/gerar", methods=["POST"])
def gerar():
    files = request.files.getlist("pdfs")
    if not files or len(files) < 4:
        return render_template("index.html", erro="Envie os 5 relatórios em PDF."), 400

    ano = (request.form.get("ano_anterior") or "2025.2").strip()
    try:
        num_ant = int(request.form.get("num_anterior") or "0")
    except ValueError:
        num_ant = 0

    with tempfile.TemporaryDirectory() as tmp:
        tipos = {}
        for f in files:
            if not f.filename.lower().endswith(".pdf"):
                continue
            dest = os.path.join(tmp, f.filename)
            f.save(dest)
            tipo = core.classify(dest)
            if tipo in ("inscritos", "aprovados", "matriculados", "pagas"):
                tipos[tipo] = dest

        faltam = [t for t in ("inscritos", "aprovados", "matriculados", "pagas") if t not in tipos]
        if faltam:
            nomes = {"inscritos": "Lista de Inscritos", "aprovados": "Aprovados não Matriculados",
                     "matriculados": "Matriculados", "pagas": "1ª Mensalidade paga (não finalizados)"}
            return render_template("index.html",
                erro="Não reconheci estes relatórios: " + ", ".join(nomes[t] for t in faltam)), 400

        res = core.computar(tipos)
        valores = res["valores"]
        out = os.path.join(tmp, "saida.png")
        core.gerar_imagem(valores, ano, num_ant, out)
        with open(out, "rb") as fp:
            img_b64 = base64.b64encode(fp.read()).decode()

    linhas = [(CAMPOS[k], valores[k]) for k in range(1, 10)]
    linhas.append((f"Matriculados {ano} (anterior)", num_ant))
    return render_template("resultado.html", img_b64=img_b64, linhas=linhas, diag=res["diag"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
