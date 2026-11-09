"""Dados demonstrativos: 1 quadra, 2 organizadores, 30 jogadores e partidas em todos os status.

Todas as contas usam a senha SENHA_DEMO. O relógio da plataforma é adiantado/atrasado
temporariamente para montar partidas já encerradas, e restaurado no final.
"""
import random
from datetime import timedelta

SENHA_DEMO = "senha1234"

NOMES = [
    "Lucas Almeida", "Rafael Souza", "Gabriel Costa", "Mateus Ribeiro", "Pedro Lima",
    "Bruno Carvalho", "Thiago Martins", "Felipe Rocha", "Diego Barbosa", "Vinícius Araújo",
    "Rodrigo Nunes", "André Teixeira", "Gustavo Pires", "Leonardo Dias", "Eduardo Freitas",
    "Marcelo Cardoso", "Fernando Gomes", "Henrique Moreira", "Caio Ferreira", "Daniel Correia",
    "Renato Batista", "Igor Monteiro", "Samuel Duarte", "Danilo Campos", "Joaquim Vieira",
    "Ricardo Lopes", "Wesley Santos", "Murilo Cunha", "Otávio Neves", "Yuri Machado",
]
BAIRROS = ["Centro", "Santa Mônica", "Martins", "Tibery", "Lídice", "Brasil"]
PADROES = [
    ("GOLEIRO",), ("FIXO", "ALA"), ("ALA", "PIVO"), ("PIVO", "ALA"), ("FIXO",),
    ("ALA", "FIXO", "PIVO"), ("PIVO",), ("ALA",), ("GOLEIRO", "FIXO"), ("FIXO", "PIVO"),
]

CREDENCIAIS = {
    "quadra": "quadra@demo.com",
    "organizadores": ["organizador1@demo.com", "organizador2@demo.com"],
    "jogador": "jogador1@demo.com",
}


def _posicoes(*nomes):
    return [{"posicao": n, "principal": i == 0} for i, n in enumerate(nomes)]


def carregar_demo(plataforma):
    relogio_real = plataforma.relogio
    agora = relogio_real().replace(minute=0, second=0, microsecond=0)
    sorteio = random.Random(7)

    def dia(deslocamento, hora):
        return (agora + timedelta(days=deslocamento)).replace(hour=hora)

    def horario(inicio, duracao=1):
        return {"inicio": inicio.isoformat(), "fim": (inicio + timedelta(hours=duracao)).isoformat()}

    def em(momento):
        plataforma.relogio = lambda: momento

    quadra = plataforma.cadastrar_quadra({
        "nome": "Arena Central", "email": CREDENCIAIS["quadra"], "senha": SENHA_DEMO,
        "nomeFantasia": "Arena Central Futsal", "endereco": "Av. Rondon Pacheco, 1200",
        "cidade": "Uberlândia", "bairro": "Santa Mônica", "tipo": "coberta", "precoHora": 180,
    })
    org1 = plataforma.cadastrar_organizador({
        "nome": "Carlos Organizador", "email": CREDENCIAIS["organizadores"][0],
        "senha": SENHA_DEMO, "cidade": "Uberlândia"})
    org2 = plataforma.cadastrar_organizador({
        "nome": "Marina Organizadora", "email": CREDENCIAIS["organizadores"][1],
        "senha": SENHA_DEMO, "cidade": "Uberlândia"})

    jogadores = []
    for i, nome in enumerate(NOMES):
        cidade = "Araguari" if i >= 26 else "Uberlândia"
        jogadores.append(plataforma.cadastrar_jogador({
            "nome": nome, "email": f"jogador{i + 1}@demo.com", "senha": SENHA_DEMO,
            "cidade": cidade, "bairro": BAIRROS[i % len(BAIRROS)],
            "posicoes": _posicoes(*PADROES[i % len(PADROES)]),
        }))
    uber = [j for j in jogadores if j.cidade == "Uberlândia"]

    def montar_historico(criador, titulo, dia_jogo, total, participantes, local):
        """Cria, lota, inicia, encerra e avalia uma partida no passado."""
        em(dia_jogo - timedelta(days=1))
        partida = plataforma.criar_partida(criador, {
            "titulo": titulo, "valorQuadra": 160, "totalVagas": total, **local,
            **horario(dia_jogo)})
        for jogador in participantes:
            candidatura = plataforma.candidatar(jogador, partida.id)
            plataforma.aprovar_candidatura(criador, candidatura.id)
        em(dia_jogo + timedelta(minutes=5))
        plataforma.iniciar_partida(criador, partida.id)
        plataforma.encerrar_partida(criador, partida.id)
        for jogador in participantes:
            plataforma.avaliar(criador, partida.id, jogador.id,
                               sorteio.choice([3, 4, 4, 5, 5]), "Boa partida.")
            for outro in sorteio.sample([j for j in participantes if j is not jogador], 2):
                plataforma.avaliar(jogador, partida.id, outro.id, sorteio.choice([3, 4, 5]))
        return partida

    local_org1 = {"localNome": "Ginásio Municipal", "endereco": "Rua das Palmeiras, 300",
                  "cidade": "Uberlândia", "bairro": "Centro"}
    local_org2 = {"localNome": "Quadra do Tibery", "endereco": "Av. Segismundo Pereira, 80",
                  "cidade": "Uberlândia", "bairro": "Tibery"}
    # jogador1 fica de fora do histórico para continuar elegível às partidas futuras.
    montar_historico(org1, "Pelada de domingo (passada)", dia(-7, 20), 8, uber[1:9], local_org1)
    montar_historico(org2, "Racha da semana (passado)", dia(-3, 19), 10, uber[5:15], local_org2)

    # Partida em andamento: criada antes do horário e iniciada depois dele.
    em(dia(0, 8))
    andamento = plataforma.criar_partida(org2, {
        "titulo": "Racha em andamento", "valorQuadra": 140, "totalVagas": 4,
        **local_org2, **horario(dia(0, 9), 2)})
    for jogador in uber[16:20]:
        candidatura = plataforma.candidatar(jogador, andamento.id)
        plataforma.aprovar_candidatura(org2, candidatura.id)
    em(dia(0, 9) + timedelta(minutes=10))
    plataforma.iniciar_partida(org2, andamento.id)

    plataforma.relogio = relogio_real
    futuro = max(agora, relogio_real())

    def diafut(n, hora):
        return (futuro + timedelta(days=n)).replace(hour=hora)

    aberta = plataforma.criar_partida(org1, {
        "titulo": "Racha de quinta no Centro", "descricao": "Nível intermediário, traga colete.",
        "valorQuadra": 200, "totalVagas": 10, "notaMinima": 3,
        "posicoes": [{"posicao": "GOLEIRO", "quantidade": 2}, {"posicao": "FIXO", "quantidade": 2},
                     {"posicao": "ALA", "quantidade": 4}, {"posicao": "PIVO", "quantidade": 2}],
        **local_org1, **horario(diafut(2, 20), 2)})
    for jogador in uber[12:15]:
        plataforma.candidatar(jogador, aberta.id)
    candidatura = plataforma.candidatar(uber[15], aberta.id)
    plataforma.aprovar_candidatura(org1, candidatura.id)

    plataforma.criar_partida(quadra, {
        "titulo": "Futsal da Arena Central", "descricao": "Quadra coberta, vestiário disponível.",
        "valorQuadra": 180, "totalVagas": 12, **horario(diafut(3, 21), 1)})

    plataforma.criar_partida(org2, {
        "titulo": "Racha de sábado no Tibery", "valorQuadra": 120, "totalVagas": 8,
        **local_org2, **horario(diafut(5, 16), 2)})

    completa = plataforma.criar_partida(org2, {
        "titulo": "Quarteto fechado", "valorQuadra": 100, "totalVagas": 4,
        **local_org2, **horario(diafut(4, 18), 1)})
    for jogador in uber[20:24]:
        candidatura = plataforma.candidatar(jogador, completa.id)
        plataforma.aprovar_candidatura(org2, candidatura.id)

    cancelada = plataforma.criar_partida(org1, {
        "titulo": "Racha cancelado pela chuva", "valorQuadra": 150, "totalVagas": 10,
        **local_org1, **horario(diafut(6, 19), 1)})
    plataforma.candidatar(uber[24], cancelada.id)
    plataforma.cancelar_partida(org1, cancelada.id)

    return plataforma
