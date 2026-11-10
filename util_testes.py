"""Apoio dos testes: relógio controlável e fábricas de usuários e partidas."""
from datetime import datetime, timedelta

from plataforma import Plataforma

SENHA = "senha1234"
BASE = datetime(2030, 6, 10, 12, 0)


class Relogio:
    def __init__(self, agora=BASE):
        self.agora = agora

    def __call__(self):
        return self.agora

    def avancar(self, **delta):
        self.agora += timedelta(**delta)


def nova_plataforma():
    relogio = Relogio()
    return Plataforma(relogio), relogio


def novo_jogador(plataforma, n, cidade="Uberlândia", bairro="Centro", posicoes=("ALA", "FIXO")):
    return plataforma.cadastrar_jogador({
        "nome": f"Jogador {n}", "email": f"j{n}@teste.com", "senha": SENHA, "cidade": cidade,
        "bairro": bairro,
        "posicoes": [{"posicao": p, "principal": i == 0} for i, p in enumerate(posicoes)],
    })


def novo_organizador(plataforma, n=1):
    return plataforma.cadastrar_organizador({
        "nome": f"Org {n}", "email": f"o{n}@teste.com", "senha": SENHA, "cidade": "Uberlândia"})


def nova_quadra(plataforma):
    return plataforma.cadastrar_quadra({
        "nome": "Dono", "email": "q@teste.com", "senha": SENHA, "nomeFantasia": "Arena",
        "endereco": "Rua A, 10", "cidade": "Uberlândia", "bairro": "Centro", "precoHora": 150})


def dados_partida(relogio, dias=2, hora=20, duracao=1, **extras):
    inicio = (relogio.agora + timedelta(days=dias)).replace(hour=hora, minute=0)
    dados = {
        "titulo": "Racha", "localNome": "Ginásio", "endereco": "Rua B, 20",
        "cidade": "Uberlândia", "bairro": "Centro", "inicio": inicio.isoformat(),
        "fim": (inicio + timedelta(hours=duracao)).isoformat(), "totalVagas": 4,
        "valorQuadra": 100,
    }
    dados.update(extras)
    return dados
