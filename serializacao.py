"""Conversão dos objetos de domínio para JSON (camelCase). Nunca expõe senha."""
from jogador import Jogador


def _iso(data):
    return data.isoformat(timespec="minutes") if data else None


def _numero(valor):
    return float(valor) if valor is not None else None


def resumo_usuario(usuario):
    return {"id": usuario.id, "nome": usuario.nome, "papel": usuario.papel.value}


def usuario_para_dict(usuario):
    if isinstance(usuario, Jogador):
        dados = usuario.perfil_publico()
        dados["email"], dados["telefone"] = usuario.email, usuario.telefone
        dados["nascimento"] = _iso(usuario.nascimento)
        return dados
    return usuario.perfil_completo()


def partida_para_dict(plataforma, partida):
    preenchidas = len(plataforma.aprovadas(partida))
    return {
        "id": partida.id,
        "titulo": partida.titulo,
        "descricao": partida.descricao,
        "localNome": partida.local_nome,
        "endereco": partida.endereco,
        "cidade": partida.cidade,
        "bairro": partida.bairro,
        "inicio": _iso(partida.inicio),
        "fim": _iso(partida.fim),
        "totalVagas": partida.total_vagas,
        "vagasPreenchidas": preenchidas,
        "vagasRestantes": partida.vagas_restantes(preenchidas),
        "valorQuadra": _numero(partida.valor_quadra),
        "notaMinima": _numero(partida.nota_minima),
        "status": partida.status.value,
        "posicoes": [{"posicao": p.value, "quantidade": q}
                     for p, q in partida.posicoes_pedidas.items()],
        "criador": resumo_usuario(partida.criador),
        "quadraId": partida.quadra.id if partida.quadra else None,
    }


def candidatura_para_dict(plataforma, candidatura):
    return {
        "id": candidatura.id,
        "status": candidatura.status.value,
        "posicao": candidatura.posicao.value if candidatura.posicao else None,
        "propostaId": candidatura.proposta.id if candidatura.proposta else None,
        "decididaEm": _iso(candidatura.decidida_em),
        "partida": partida_para_dict(plataforma, candidatura.partida),
        "jogador": candidatura.jogador.perfil_publico(),
    }


def proposta_para_dict(plataforma, proposta):
    return {
        "id": proposta.id,
        "status": proposta.status.value,
        "pontuacao": _numero(proposta.pontuacao),
        "expiraEm": _iso(proposta.expira_em),
        "respondidaEm": _iso(proposta.respondida_em),
        "partida": partida_para_dict(plataforma, proposta.partida),
    }


def avaliacao_para_dict(avaliacao):
    return {
        "id": avaliacao.id,
        "partidaId": avaliacao.partida.id,
        "partidaTitulo": avaliacao.partida.titulo,
        "avaliador": resumo_usuario(avaliacao.avaliador),
        "avaliadoId": avaliacao.avaliado.id,
        "nota": avaliacao.nota,
        "comentario": avaliacao.comentario,
        "criadaEm": _iso(avaliacao.criada_em),
    }
