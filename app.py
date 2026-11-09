"""
API Flask para o Matchmaking de Futsal.
Reaproveita as classes de domínio (Jogador, Organizador, Quadra, Partida, ...) e a
Plataforma, que guarda tudo em memória como a lista `ordens` do projeto original.
Executar: python app.py
"""
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from demo import carregar_demo
from erros import (DadosInvalidosError, NaoAutenticadoError,
                   PermissaoNegadaError)
from paginacao import Paginacao
from plataforma import PARTIDA_ORDENS, Plataforma
from serializacao import (avaliacao_para_dict, candidatura_para_dict,
                          partida_para_dict, proposta_para_dict,
                          usuario_para_dict)

TAMANHO_MAXIMO_FOTO = 2 * 1024 * 1024
ASSINATURAS_FOTO = {
    ".jpg": lambda b: b.startswith(b"\xff\xd8\xff"),
    ".png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    ".webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}

log = logging.getLogger("futsal")


def criar_app(plataforma, pasta_uploads=None, limite_auth=30):
    """`limite_auth`: requisições por minuto e por IP nas rotas de auth (None desliga)."""
    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config["MAX_CONTENT_LENGTH"] = TAMANHO_MAXIMO_FOTO + 512 * 1024
    pasta_uploads = pasta_uploads or os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(pasta_uploads, exist_ok=True)
    acessos = defaultdict(deque)

    # ------------------------------------------------------------- utilidades
    def corpo():
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict):
            raise DadosInvalidosError("Envie um corpo JSON válido.")
        return dados

    def paginacao(permitidos, padrao, sort_padrao=None):
        a = request.args
        return Paginacao(a.get("page"), a.get("limit"), a.get("sort") or sort_padrao,
                         permitidos, padrao)

    def lista_simples(itens):
        itens = list(itens)
        return jsonify({"dados": itens,
                        "meta": {"page": 1, "limit": len(itens) or 1, "total": len(itens)}})

    def pagina(resultado, conversor):
        return jsonify({"dados": [conversor(i) for i in resultado["dados"]],
                        "meta": resultado["meta"]})

    def criado(corpo_json, local):
        resposta = jsonify(corpo_json)
        resposta.status_code = 201
        resposta.headers["Location"] = local
        return resposta

    def autenticado(*papeis):
        def decorador(funcao):
            @wraps(funcao)
            def interna(*args, **kwargs):
                cabecalho = request.headers.get("Authorization", "")
                if not cabecalho.startswith("Bearer "):
                    raise NaoAutenticadoError("Informe o token no cabeçalho Authorization.")
                g.usuario = plataforma.autenticar(cabecalho[7:])
                if papeis and g.usuario.papel.value not in papeis:
                    raise PermissaoNegadaError("Seu perfil não pode acessar este recurso.")
                return funcao(*args, **kwargs)
            return interna
        return decorador

    def limitar_auth():
        if not limite_auth:
            return
        agora = time.monotonic()
        fila = acessos[request.remote_addr]
        while fila and agora - fila[0] > 60:
            fila.popleft()
        if len(fila) >= limite_auth:
            resposta = jsonify({"codigo": "MUITAS_REQUISICOES", "erro": "Muitas tentativas.",
                                "mensagem": "Muitas tentativas. Aguarde um minuto.",
                                "detalhes": [], "traceId": uuid.uuid4().hex[:12]})
            resposta.status_code = 429
            return resposta
        fila.append(agora)

    def p_dict(partida):
        return partida_para_dict(plataforma, partida)

    def c_dict(candidatura):
        return candidatura_para_dict(plataforma, candidatura)

    # ------------------------------------------------------------------ erros
    def erro_json(status, codigo, mensagem):
        resposta = jsonify({"codigo": codigo, "erro": mensagem, "mensagem": mensagem,
                            "detalhes": [], "traceId": uuid.uuid4().hex[:12]})
        resposta.status_code = status
        return resposta

    @app.errorhandler(Exception)
    def tratar(erro):
        if isinstance(erro, HTTPException):
            if erro.code == 413:
                return erro_json(413, "ARQUIVO_GRANDE", "A foto pode ter no máximo 2 MB.")
            return erro_json(erro.code, erro.name.upper().replace(" ", "_"), erro.description)
        status = getattr(erro, "status", None)
        if status:
            return erro_json(status, erro.codigo, str(erro) or erro.codigo)
        log.exception("Erro inesperado")
        return erro_json(500, "ERRO_INTERNO", "Erro interno do servidor.")

    @app.after_request
    def cabecalhos(resposta):
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("X-Frame-Options", "DENY")
        resposta.headers.setdefault("Referrer-Policy", "same-origin")
        return resposta

    # ------------------------------------------------------------------ rotas
    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/uploads/<nome>")
    def arquivo_enviado(nome):
        return send_from_directory(pasta_uploads, nome)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    # --- auth
    def cadastro(metodo, rotulo):
        bloqueio = limitar_auth()
        if bloqueio:
            return bloqueio
        usuario = metodo(corpo())
        return criado(usuario_para_dict(usuario), f"/api/{rotulo}/{usuario.id}")

    @app.post("/api/auth/cadastro/jogador")
    def cadastro_jogador():
        return cadastro(plataforma.cadastrar_jogador, "jogadores")

    @app.post("/api/auth/cadastro/organizador")
    def cadastro_organizador():
        return cadastro(plataforma.cadastrar_organizador, "organizadores")

    @app.post("/api/auth/cadastro/quadra")
    def cadastro_quadra():
        return cadastro(plataforma.cadastrar_quadra, "quadras")

    @app.post("/api/auth/login")
    def login():
        bloqueio = limitar_auth()
        if bloqueio:
            return bloqueio
        dados = corpo()
        return jsonify(plataforma.login(dados.get("email"), dados.get("senha")))

    @app.post("/api/auth/refresh")
    def refresh():
        bloqueio = limitar_auth()
        if bloqueio:
            return bloqueio
        return jsonify(plataforma.renovar(corpo().get("refreshToken")))

    @app.post("/api/auth/logout")
    @autenticado()
    def logout():
        plataforma.logout(g.usuario, (request.get_json(silent=True) or {}).get("refreshToken"))
        return "", 204

    # --- usuários e perfis
    @app.get("/api/usuarios/eu")
    @autenticado()
    def meu_usuario():
        return jsonify(usuario_para_dict(g.usuario))

    @app.patch("/api/usuarios/eu")
    @autenticado()
    def atualizar_usuario():
        return jsonify(usuario_para_dict(plataforma.atualizar_usuario(g.usuario, corpo())))

    @app.get("/api/jogadores")
    @autenticado("ORGANIZADOR", "QUADRA")
    def listar_jogadores():
        resultado = plataforma.listar_jogadores(
            g.usuario, request.args, paginacao(("nome", "notaMedia"), "nome"))
        return pagina(resultado, lambda j: j.perfil_publico())

    @app.get("/api/jogadores/<jogador_id>")
    @autenticado()
    def obter_jogador(jogador_id):
        return jsonify(plataforma.obter_jogador(jogador_id).perfil_publico())

    @app.patch("/api/jogadores/eu")
    @autenticado("JOGADOR")
    def atualizar_jogador():
        return jsonify(usuario_para_dict(plataforma.atualizar_jogador(g.usuario, corpo())))

    @app.put("/api/jogadores/eu/foto")
    @autenticado("JOGADOR")
    def enviar_foto():
        arquivo = request.files.get("foto")
        if arquivo is None:
            raise DadosInvalidosError("Envie o arquivo no campo 'foto'.")
        conteudo = arquivo.read(TAMANHO_MAXIMO_FOTO + 1)
        if len(conteudo) > TAMANHO_MAXIMO_FOTO:
            return erro_json(413, "ARQUIVO_GRANDE", "A foto pode ter no máximo 2 MB.")
        extensao = next((e for e, confere in ASSINATURAS_FOTO.items() if confere(conteudo)), None)
        if extensao is None:
            raise DadosInvalidosError("A foto deve ser JPEG, PNG ou WebP.", "FORMATO_INVALIDO")
        nome = f"{uuid.uuid4().hex}{extensao}"
        with open(os.path.join(pasta_uploads, nome), "wb") as saida:
            saida.write(conteudo)
        plataforma.definir_foto(g.usuario, f"/uploads/{nome}")
        return jsonify(usuario_para_dict(g.usuario))

    @app.get("/api/jogadores/<jogador_id>/avaliacoes")
    @autenticado()
    def avaliacoes_do_jogador(jogador_id):
        resultado = plataforma.avaliacoes_recebidas(
            jogador_id, paginacao(("criadaEm",), "criadaEm", "criadaEm:desc"))
        return pagina(resultado, avaliacao_para_dict)

    @app.patch("/api/organizadores/eu")
    @autenticado("ORGANIZADOR")
    def atualizar_organizador():
        return jsonify(usuario_para_dict(plataforma.atualizar_organizador(g.usuario, corpo())))

    @app.get("/api/quadras")
    @autenticado()
    def listar_quadras():
        resultado = plataforma.listar_quadras(
            request.args, paginacao(("nomeFantasia",), "nomeFantasia"))
        return pagina(resultado, lambda q: q.perfil_completo())

    @app.get("/api/quadras/<quadra_id>")
    @autenticado()
    def obter_quadra(quadra_id):
        return jsonify(plataforma.obter_quadra(quadra_id).perfil_completo())

    @app.patch("/api/quadras/eu")
    @autenticado("QUADRA")
    def atualizar_quadra():
        return jsonify(usuario_para_dict(plataforma.atualizar_quadra(g.usuario, corpo())))

    # --- partidas
    @app.post("/api/partidas")
    @autenticado("ORGANIZADOR", "QUADRA")
    def criar_partida():
        partida = plataforma.criar_partida(g.usuario, corpo())
        return criado(p_dict(partida), f"/api/partidas/{partida.id}")

    @app.get("/api/partidas")
    @autenticado()
    def listar_partidas():
        resultado = plataforma.listar_partidas(
            request.args, paginacao(PARTIDA_ORDENS, "inicio"))
        return pagina(resultado, p_dict)

    @app.get("/api/partidas/minhas")
    @autenticado()
    def minhas_partidas():
        resultado = plataforma.minhas_partidas(
            g.usuario, paginacao(PARTIDA_ORDENS, "inicio"))
        return pagina(resultado, p_dict)

    @app.get("/api/partidas/<partida_id>")
    @autenticado()
    def obter_partida(partida_id):
        return jsonify(p_dict(plataforma.obter_partida(partida_id)))

    @app.patch("/api/partidas/<partida_id>")
    @autenticado("ORGANIZADOR", "QUADRA")
    def editar_partida(partida_id):
        return jsonify(p_dict(plataforma.editar_partida(g.usuario, partida_id, corpo())))

    @app.post("/api/partidas/<partida_id>/inicio")
    @autenticado("ORGANIZADOR", "QUADRA")
    def iniciar_partida(partida_id):
        return jsonify(p_dict(plataforma.iniciar_partida(g.usuario, partida_id)))

    @app.post("/api/partidas/<partida_id>/encerramento")
    @autenticado("ORGANIZADOR", "QUADRA")
    def encerrar_partida(partida_id):
        return jsonify(p_dict(plataforma.encerrar_partida(g.usuario, partida_id)))

    @app.post("/api/partidas/<partida_id>/cancelamento")
    @autenticado("ORGANIZADOR", "QUADRA")
    def cancelar_partida(partida_id):
        return jsonify(p_dict(plataforma.cancelar_partida(g.usuario, partida_id)))

    @app.post("/api/partidas/<partida_id>/matchmaking")
    @autenticado("ORGANIZADOR", "QUADRA")
    def rodar_matchmaking(partida_id):
        criadas = plataforma.gerar_matchmaking(g.usuario, partida_id)
        return jsonify({"propostasGeradas": len(criadas)})

    @app.get("/api/partidas/<partida_id>/candidaturas")
    @autenticado("ORGANIZADOR", "QUADRA")
    def candidaturas_da_partida(partida_id):
        itens = plataforma.listar_candidaturas_partida(
            g.usuario, partida_id, request.args.get("status"))
        return lista_simples(c_dict(c) for c in itens)

    @app.get("/api/partidas/<partida_id>/participantes")
    @autenticado()
    def participantes(partida_id):
        return lista_simples(j.perfil_publico() for j in plataforma.participantes(partida_id))

    @app.post("/api/partidas/<partida_id>/candidaturas")
    @autenticado("JOGADOR")
    def candidatar(partida_id):
        dados = request.get_json(silent=True) or {}
        candidatura = plataforma.candidatar(g.usuario, partida_id, dados.get("posicao"))
        return criado(c_dict(candidatura), f"/api/candidaturas/{candidatura.id}")

    # --- propostas
    @app.get("/api/propostas")
    @autenticado("JOGADOR")
    def listar_propostas():
        itens = plataforma.listar_propostas(g.usuario, request.args.get("status"))
        return lista_simples(proposta_para_dict(plataforma, p) for p in itens)

    @app.post("/api/propostas/<proposta_id>/visualizacao")
    @autenticado("JOGADOR")
    def visualizar_proposta(proposta_id):
        plataforma.visualizar_proposta(g.usuario, proposta_id)
        return "", 204

    @app.post("/api/propostas/<proposta_id>/aceite")
    @autenticado("JOGADOR")
    def aceitar_proposta(proposta_id):
        dados = request.get_json(silent=True) or {}
        candidatura = plataforma.aceitar_proposta(g.usuario, proposta_id, dados.get("posicao"))
        return criado(c_dict(candidatura), f"/api/candidaturas/{candidatura.id}")

    @app.post("/api/propostas/<proposta_id>/recusa")
    @autenticado("JOGADOR")
    def recusar_proposta(proposta_id):
        plataforma.recusar_proposta(g.usuario, proposta_id)
        return "", 204

    # --- candidaturas
    @app.get("/api/candidaturas")
    @autenticado("JOGADOR")
    def minhas_candidaturas():
        itens = plataforma.minhas_candidaturas(g.usuario, request.args.get("status"))
        return lista_simples(c_dict(c) for c in itens)

    @app.post("/api/candidaturas/<candidatura_id>/aprovacao")
    @autenticado("ORGANIZADOR", "QUADRA")
    def aprovar(candidatura_id):
        return jsonify(c_dict(plataforma.aprovar_candidatura(g.usuario, candidatura_id)))

    @app.post("/api/candidaturas/<candidatura_id>/rejeicao")
    @autenticado("ORGANIZADOR", "QUADRA")
    def rejeitar(candidatura_id):
        return jsonify(c_dict(plataforma.rejeitar_candidatura(g.usuario, candidatura_id)))

    @app.post("/api/candidaturas/<candidatura_id>/cancelamento")
    @autenticado("JOGADOR")
    def cancelar(candidatura_id):
        return jsonify(c_dict(plataforma.cancelar_candidatura(g.usuario, candidatura_id)))

    # --- avaliações
    @app.post("/api/partidas/<partida_id>/avaliacoes")
    @autenticado()
    def avaliar(partida_id):
        dados = corpo()
        avaliacao = plataforma.avaliar(g.usuario, partida_id, dados.get("avaliadoId"),
                                       dados.get("nota"), dados.get("comentario"))
        return criado(avaliacao_para_dict(avaliacao),
                      f"/api/partidas/{partida_id}/avaliacoes/{avaliacao.id}")

    @app.get("/api/partidas/<partida_id>/avaliacoes/pendentes")
    @autenticado()
    def pendentes(partida_id):
        itens = plataforma.avaliacoes_pendentes(g.usuario, partida_id)
        return lista_simples(j.perfil_publico() for j in itens)

    return app


def criar_app_demo():
    plataforma = Plataforma()
    carregar_demo(plataforma)
    return criar_app(plataforma)


if __name__ == "__main__":
    criar_app_demo().run(debug=True, port=5000)
