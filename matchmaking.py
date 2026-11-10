"""Regras puras do matchmaking: elegibilidade, pontuação (0 a 100) e seleção.

Nada aqui acessa a lista de usuários nem a data atual; quem chama fornece os dados.
"""
from decimal import Decimal

PONTOS_POSICAO_PRINCIPAL = 40
PONTOS_POSICAO_SECUNDARIA = 20
PONTOS_SEM_POSICAO_DEFINIDA = 20
PONTOS_BAIRRO = 20
PONTOS_NOTA_MAXIMO = 30
PONTOS_NOTA_NOVATO = 15
PONTOS_POR_PARTIDA = 2
PONTOS_HISTORICO_MAXIMO = 10
AVALIACOES_MINIMAS = 3
MULTIPLICADOR_VAGAS = 3
LIMITE_PROPOSTAS = 30


def _igual(a, b):
    return bool(a) and bool(b) and a.strip().casefold() == b.strip().casefold()


def pontuar_posicao(posicoes_jogador, posicoes_pedidas):
    """`posicoes_jogador`: a principal vem primeiro. `posicoes_pedidas`: conjunto."""
    if not posicoes_pedidas:
        return PONTOS_SEM_POSICAO_DEFINIDA
    if posicoes_jogador[0] in posicoes_pedidas:
        return PONTOS_POSICAO_PRINCIPAL
    if any(p in posicoes_pedidas for p in posicoes_jogador[1:]):
        return PONTOS_POSICAO_SECUNDARIA
    return 0


def pontuar_nota(nota_media, total_avaliacoes):
    if total_avaliacoes < AVALIACOES_MINIMAS:
        return Decimal(PONTOS_NOTA_NOVATO)
    return Decimal(str(nota_media)) / Decimal(5) * PONTOS_NOTA_MAXIMO


def pontuar_historico(partidas_jogadas):
    return min(partidas_jogadas * PONTOS_POR_PARTIDA, PONTOS_HISTORICO_MAXIMO)


def pontuar(posicoes_jogador, bairro_jogador, nota_media, total_avaliacoes,
            partidas_jogadas, posicoes_pedidas, bairro_partida):
    total = Decimal(pontuar_posicao(posicoes_jogador, set(posicoes_pedidas)))
    if _igual(bairro_jogador, bairro_partida):
        total += PONTOS_BAIRRO
    total += pontuar_nota(nota_media, total_avaliacoes)
    total += pontuar_historico(partidas_jogadas)
    return total.quantize(Decimal("0.01"))


def tem_posicao_pedida(posicoes_jogador, posicoes_pedidas):
    return not posicoes_pedidas or any(p in posicoes_pedidas for p in posicoes_jogador)


def eh_elegivel(jogador, partida, ja_vinculado, tem_conflito_horario):
    if not jogador.ativo or ja_vinculado or tem_conflito_horario:
        return False
    if not _igual(jogador.cidade, partida.cidade):
        return False
    if not jogador.atende_nota_minima(partida.nota_minima):
        return False
    return tem_posicao_pedida(jogador.posicoes, set(partida.posicoes_pedidas))


def limite_de_propostas(vagas_restantes):
    return min(MULTIPLICADOR_VAGAS * vagas_restantes, LIMITE_PROPOSTAS)


def escolher_melhores(pontuados, vagas_restantes):
    """`pontuados`: lista de (jogador, pontuacao). Empate: maior nota, depois nome."""
    ordenados = sorted(
        pontuados,
        key=lambda par: (-par[1], -par[0].nota_media, par[0].nome.casefold()),
    )
    return ordenados[: limite_de_propostas(vagas_restantes)]
