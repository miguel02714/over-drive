import asyncio
import aiohttp
import time
import random
import string
from flask import Flask, request, render_template_string

app = Flask(__name__)

# ========= HTML com formulário + resultado ==========
HTML_FORM = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Painel de Teste</title>
  <style>
    body {
      margin: 0;
      background: linear-gradient(135deg, #0d0d0d, #1a1a1a);
      color: #eaeaea;
      font-family: "Segoe UI", Tahoma, sans-serif;
      display: flex;
      justify-content: center;
      align-items: flex-start;
      padding: 40px;
    }
    .card {
      background: #1b1b1b;
      padding: 35px 30px;
      border-radius: 14px;
      width: 420px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.5);
      animation: fadeIn 0.4s ease;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    h2 {
      margin-bottom: 25px;
      text-align: center;
      color: #0d6efd;
      font-size: 22px;
    }
    label {
      font-size: 14px;
      margin-bottom: 6px;
      display: block;
      color: #bbb;
    }
    input, select, button {
      width: 100%;
      padding: 12px;
      margin-bottom: 18px;
      border-radius: 10px;
      border: none;
      outline: none;
      font-size: 15px;
      transition: all 0.2s ease;
    }
    input, select {
      background: #2a2a2a;
      color: #fff;
    }
    input:focus, select:focus {
      background: #333;
      box-shadow: 0 0 0 2px #0d6efd;
    }
    /* Corrige o amarelo do autocomplete */
    input:-webkit-autofill {
      -webkit-box-shadow: 0 0 0px 1000px #2a2a2a inset !important;
      -webkit-text-fill-color: #fff !important;
      transition: background-color 5000s ease-in-out 0s;
    }
    button {
      background: linear-gradient(90deg, #0d6efd, #00b4d8);
      color: #fff;
      font-weight: bold;
      cursor: pointer;
    }
    button:hover {
      transform: scale(1.03);
      box-shadow: 0 0 12px rgba(0,180,216,0.5);
    }
    .result {
      margin-top: 25px;
      padding: 18px;
      background: #222;
      border-radius: 10px;
      font-size: 14px;
      line-height: 1.6;
    }
    .result h3 {
      margin-top: 0;
      color: #0d6efd;
    }
  </style>
</head>
<body>
  <div class="card">
    <h2>🚀 Teste de Carga</h2>
    <form method="POST" action="/run">
      <label for="nome">Nome do teste</label>
      <input type="text" id="nome" name="nome" placeholder="Meu teste" required>

      <label for="url">URL alvo</label>
      <input type="url" id="url" name="url" placeholder="https://exemplo.com" required>

      <label for="metodo">Método</label>
      <select id="metodo" name="metodo">
        <option value="GET">GET</option>
        <option value="POST">POST</option>
      </select>

      <label for="total">Total de requisições</label>
      <input type="number" id="total" name="total" placeholder="1000" required>

      <label for="concorrencia">Concorrência</label>
      <input type="number" id="concorrencia" name="concorrencia" placeholder="100" required>

      <button type="submit">Iniciar Teste</button>
    </form>

    {% if resultado %}
    <div class="result">
      <h3>📊 Resultado</h3>
      <p><b>Nome:</b> {{nome}}</p>
      <p><b>URL:</b> {{url}}</p>
      <p><b>Método:</b> {{metodo}}</p>
      <p><b>Tempo total:</b> {{resultado.tempo | round(2)}}s</p>
      <p><b>Sucessos:</b> {{resultado.sucesso}}</p>
      <p><b>Falhas:</b> {{resultado.falhas}}</p>
    </div>
    {% endif %}
  </div>
</body>
</html>
"""

# ========= Funções de carga ==========
def generate_payload(size=1000):
    return {
        "id": random.randint(1, 10_000_000),
        "data": ''.join(random.choices(string.ascii_letters + string.digits, k=size))
    }

async def make_request(session, url, idx, metodo):
    try:
        if metodo == "POST":
            payload = generate_payload()
            async with session.post(
                url,
                json=payload,
                headers={"X-Test": "LoadTest"},
                ssl=False,
                timeout=10
            ) as response:
                return idx, response.status
        else:  # GET
            async with session.get(
                url,
                params={"q": random.randint(1, 1_000_000)},
                headers={"X-Test": "LoadTest"},
                ssl=False,
                timeout=10
            ) as response:
                return idx, response.status
    except Exception:
        return idx, None

async def run_load_test(url, total, concorrencia, metodo):
    connector = aiohttp.TCPConnector(limit=concorrencia, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        start = time.time()
        semaphore = asyncio.Semaphore(concorrencia)

        async def bound_task(i):
            async with semaphore:
                return await make_request(session, url, i, metodo)

        tasks = [bound_task(i) for i in range(1, total + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.time() - start
        success = sum(1 for _, r in results if isinstance(r, int) and 200 <= r < 300)
        fail = total - success

        return {"tempo": duration, "sucesso": success, "falhas": fail}

# ========= Rotas Flask ==========
@app.route("/")
def index():
    return render_template_string(HTML_FORM)

@app.route("/run", methods=["POST"])
def run_test():
    nome = request.form.get("nome")
    url = request.form.get("url")
    metodo = request.form.get("metodo", "GET").upper()
    total = int(request.form.get("total", 100))
    concorrencia = int(request.form.get("concorrencia", 10))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(run_load_test(url, total, concorrencia, metodo))
    loop.close()

    return render_template_string(HTML_FORM, nome=nome, url=url, metodo=metodo, resultado=result)

if __name__ == "__main__":
    app.run(debug=True, port=5200)
