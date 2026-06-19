# Gerador de Relatório — Vestibular UGB-FERP

Site que recebe os 5 PDFs do processo seletivo, calcula os números líquidos
(removendo testes e duplicidades) e devolve a arte do card atualizada.

## Rodar localmente
```
pip install -r requirements.txt
python app.py
# abra http://localhost:5000
```

## Uso
1. Arraste os 5 relatórios em PDF (Lista de Inscritos, Totalizador, Aprovados, Matriculados, 1ª Mensalidade).
2. Informe o semestre anterior (ex.: 2025.2) e quantos matriculados teve nele.
3. Clique em "Gerar relatório" e baixe o PNG.

## Deploy
- **Render/Railway (mais simples):** suba o repositório; o `Procfile` já está pronto (`gunicorn app:app`).
- **Vercel:** o `vercel.json` usa o runtime Python. Em caso de limite de tamanho/cold start, prefira Render.

Os números são calculados automaticamente — você só informa o número do semestre anterior.
