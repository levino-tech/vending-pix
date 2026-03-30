from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TOKEN = os.getenv("MERCADO_PAGO_TOKEN")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PRODUTOS = {
    0.5:  "Teste",
    3.0:  "Chocolate",
    5.0:  "Bala",
    6.0:  "Drops",
    8.0:  "Biscoito",
    10.0: "Suco",
}

pagamento_pendente = None
ultimo_acesso = datetime.now()

def tempo_offline():
    return (datetime.now() - ultimo_acesso).total_seconds()

@app.get("/status")
def status():
    offline = tempo_offline() >= 10
    return {
        "status": "offline" if offline else "online",
        "ultimo_acesso": ultimo_acesso.strftime("%d/%m/%Y %H:%M:%S")
    }

@app.get("/consulta")
def consulta():
    global pagamento_pendente, ultimo_acesso
    ultimo_acesso = datetime.now()
    if pagamento_pendente:
        resposta = pagamento_pendente.copy()
        pagamento_pendente = None
        return {"aprovado": True, **resposta}
    return {"aprovado": False}

@app.post("/webhook")
async def webhook(request: Request):
    global pagamento_pendente
    body = await request.json()
    payment_id = body.get("resource") or request.query_params.get("id")
    if not payment_id:
        return {"erro": "ID não encontrado"}

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {TOKEN}"}
        )

    data = response.json()
    valor = data.get("transaction_amount")
    status_pag = data.get("status")

    print(f"[PAGAMENTO] Status: {status_pag} | Valor: R${valor}")

    if status_pag != "approved":
        return {"mensagem": "ok"}

    if tempo_offline() >= 10:
        print("[ESTORNO] Máquina offline")
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.mercadopago.com/v1/payments/{payment_id}/refunds",
                headers={"Authorization": f"Bearer {TOKEN}"}
            )
        return {"mensagem": "ok"}

    produto = PRODUTOS.get(float(valor))
    if not produto:
        print("[ESTORNO] Valor não reconhecido")
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.mercadopago.com/v1/payments/{payment_id}/refunds",
                headers={"Authorization": f"Bearer {TOKEN}"}
            )
        return {"mensagem": "ok"}

    pagamento_pendente = {"produto": produto, "valor": valor}
    print(f"[LIBERANDO] {produto}")
    return {"mensagem": "ok"}