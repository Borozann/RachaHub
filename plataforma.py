"""Plataforma: guarda os dados em memória e aplica as regras de negócio.

Equivale à lista `ordens` do projeto original, mas com as regras de orquestração
entre as classes de domínio. Um único RLock protege toda alteração; é isso que
garante que duas aprovações simultâneas da última vaga não passem as duas.
"""
import secrets
import threading
from datetime import datetime, timedelta

import matchmaking
from avaliacao import Avaliacao
from candidatura import Candidatura, StatusCandidatura
from erros import (ConflitoError, DadosInvalidosError, NaoAutenticadoError,
                   NaoEncontradoError, PermissaoNegadaError, RegraNegocioError)
from jogador import Jogador
from organizador import Organizador
from partida import Partida, StatusPartida
from posicao import Posicao
from proposta import Proposta, StatusProposta
from quadra import Quadra
from usuario import Papel
from validacao import converter_data_hora, validar_valor

DURACAO_ACCESS = timedelta(minutes=15)
DURACAO_REFRESH = timedelta(days=7)


class Plataforma:
    def __init__(self, relogio=datetime.now):
        self.relogio = relogio
        self._trava = threading.RLock()
        self.usuarios = {}
        self.partidas = {}
        self.candidaturas = {}
        self.propostas = {}
        self.avaliacoes = []
        self._acessos = {}
        self._refreshes = {}

    # ------------------------------------------------------------------ busca
    def _usuario_por_email(self, email):
        email = (email or "").strip().lower()
        return next((u for u in self.usuarios.values() if u.email == email), None)

    def _buscar(self, colecao, identificador, nome):
        item = colecao.get(identificador)
        if item is None:
            raise NaoEncontradoError(f"{nome} não encontrado(a).")
        return item

    def obter_partida(self, partida_id):
        return self._buscar(self.partidas, partida_id, "Partida")

    def obter_jogador(self, jogador_id):
        usuario = self.usuarios.get(jogador_id)
        if not isinstance(usuario, Jogador):
            raise NaoEncontradoError("Jogador não encontrado.")
        return usuario

    def obter_quadra(self, quadra_id):
        usuario = self.usuarios.get(quadra_id)
        if not isinstance(usuario, Quadra):
            raise NaoEncontradoError("Quadra não encontrada.")
        return usuario

    @staticmethod
    def _exigir_papel(ator, *papeis):
        if ator.papel not in papeis:
            raise PermissaoNegadaError("Seu perfil não pode realizar esta ação.")

    @staticmethod
    def _exigir_criador(ator, partida):
        if partida.criador.id != ator.id:
            raise PermissaoNegadaError("Só o criador da partida pode realizar esta ação.")

    # --------------------------------------------------------------- cadastro
    def _registrar(self, usuario):
        self.usuarios[usuario.id] = usuario
        return usuario

    def _garantir_email_livre(self, email):
        if self._usuario_por_email(email):
            raise ConflitoError("Este e-mail já está cadastrado.", "EMAIL_JA_CADASTRADO")

    def cadastrar_jogador(self, dados):
        with self._trava:
            self._garantir_email_livre(dados.get("email"))
            jogador = Jogador(
                dados.get("nome"), dados.get("email"), dados.get("senha"),
                dados.get("cidade"), dados.get("posicoes"), dados.get("bairro"),
                dados.get("telefone"), dados.get("nascimento"),
            )
            return self._registrar(jogador)

    def cadastrar_organizador(self, dados):
        with self._trava:
            self._garantir_email_livre(dados.get("email"))
            return self._registrar(Organizador(
                dados.get("nome"), dados.get("email"), dados.get("senha"),
                dados.get("cidade"), dados.get("telefone"),
            ))

    def cadastrar_quadra(self, dados):
        with self._trava:
            self._garantir_email_livre(dados.get("email"))
            return self._registrar(Quadra(
                dados.get("nome"), dados.get("email"), dados.get("senha"),
                dados.get("nomeFantasia"), dados.get("endereco"), dados.get("cidade"),
                dados.get("bairro"), dados.get("tipo"), dados.get("precoHora"),
                dados.get("telefone"),
            ))

    # ------------------------------------------------------------------- auth
    def _emitir_tokens(self, usuario):
        agora = self.relogio()
        acesso, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self._acessos[acesso] = (usuario.id, agora + DURACAO_ACCESS, refresh)
        self._refreshes[refresh] = (usuario.id, agora + DURACAO_REFRESH, acesso)
        return {"accessToken": acesso, "refreshToken": refresh,
                "expiraEmSegundos": int(DURACAO_ACCESS.total_seconds())}

    def login(self, email, senha):
        with self._trava:
            usuario = self._usuario_por_email(email)
            if not usuario or not usuario.ativo or not usuario.verificar_senha(senha):
                raise NaoAutenticadoError("E-mail ou senha inválidos.")
            return self._emitir_tokens(usuario)

    def autenticar(self, token):
        with self._trava:
            registro = self._acessos.get(token)
            if not registro or registro[1] <= self.relogio():
                raise NaoAutenticadoError("Sessão inválida ou expirada.")
            usuario = self.usuarios.get(registro[0])
            if not usuario or not usuario.ativo:
                raise NaoAutenticadoError("Sessão inválida ou expirada.")
            return usuario

    def renovar(self, refresh):
        """Refresh rotativo: o token usado deixa de valer."""
        with self._trava:
            registro = self._refreshes.pop(refresh, None)
            if not registro or registro[1] <= self.relogio():
                raise NaoAutenticadoError("Sessão inválida ou expirada.")
            self._acessos.pop(registro[2], None)
            return self._emitir_tokens(self.usuarios[registro[0]])

    def logout(self, usuario, refresh=None):
        with self._trava:
            for token, (dono, _, par) in list(self._acessos.items()):
                if dono == usuario.id and (refresh is None or par == refresh):
                    self._acessos.pop(token, None)
                    self._refreshes.pop(par, None)
            if refresh:
                self._refreshes.pop(refresh, None)

    # ----------------------------------------------------------------- perfis
    def atualizar_usuario(self, ator, dados):
        with self._trava:
            nome = dados.get("nome", ator.nome)
            telefone = dados.get("telefone", ator.telefone)
            ator.nome, ator.telefone = nome, telefone
            return ator

    def atualizar_jogador(self, ator, dados):
        with self._trava:
            self._exigir_papel(ator, Papel.JOGADOR)
            posicoes = dados.get("posicoes")
            if posicoes is not None:
                ator.definir_posicoes(posicoes)
            for campo in ("cidade", "bairro", "nascimento"):
                if campo in dados:
                    setattr(ator, campo, dados[campo])
            return ator

    def atualizar_organizador(self, ator, dados):
        with self._trava:
            self._exigir_papel(ator, Papel.ORGANIZADOR)
            if "cidade" in dados:
                ator.cidade = dados["cidade"]
            return ator

    def atualizar_quadra(self, ator, dados):
        with self._trava:
            self._exigir_papel(ator, Papel.QUADRA)
            mapa = {"nomeFantasia": "nome_fantasia", "endereco": "endereco", "cidade": "cidade",
                    "bairro": "bairro", "tipo": "tipo", "precoHora": "preco_hora"}
            for chave, atributo in mapa.items():
                if chave in dados:
                    setattr(ator, atributo, dados[chave])
            return ator

    def definir_foto(self, ator, url):
        with self._trava:
            self._exigir_papel(ator, Papel.JOGADOR)
            ator.foto_url = url
            return ator

    def listar_jogadores(self, ator, filtros, paginacao):
        self._exigir_papel(ator, Papel.ORGANIZADOR, Papel.QUADRA)
        cidade, bairro = _norm(filtros.get("cidade")), _norm(filtros.get("bairro"))
        posicao = Posicao.converter(filtros["posicao"]) if filtros.get("posicao") else None
        minima = validar_valor(filtros.get("notaMinima"), "Nota mínima", obrigatorio=False)
        with self._trava:
            itens = [
                j for j in self.usuarios.values()
                if isinstance(j, Jogador) and j.ativo
                and (not cidade or _norm(j.cidade) == cidade)
                and (not bairro or _norm(j.bairro) == bairro)
                and (not posicao or posicao in j.posicoes)
                and (minima is None or j.nota_media >= minima)
            ]
        return paginacao.aplicar(itens, {
            "nome": lambda j: j.nome.casefold(),
            "notaMedia": lambda j: j.nota_media,
        })

    def listar_quadras(self, filtros, paginacao):
        cidade, bairro = _norm(filtros.get("cidade")), _norm(filtros.get("bairro"))
        tipo = _norm(filtros.get("tipo"))
        with self._trava:
            itens = [
                q for q in self.usuarios.values()
                if isinstance(q, Quadra)
                and (not cidade or _norm(q.cidade) == cidade)
                and (not bairro or _norm(q.bairro) == bairro)
                and (not tipo or _norm(q.tipo) == tipo)
            ]
        return paginacao.aplicar(itens, {"nomeFantasia": lambda q: q.nome_fantasia.casefold()})

    # --------------------------------------------------------------- consultas
    def aprovadas(self, partida):
        return [c for c in self.candidaturas.values()
                if c.partida.id == partida.id and c.status == StatusCandidatura.APROVADA]

    def vagas_restantes(self, partida):
        return partida.vagas_restantes(len(self.aprovadas(partida)))

    def _aprovada_em_conflito(self, jogador, partida):
        return any(
            c.jogador.id == jogador.id and c.status == StatusCandidatura.APROVADA
            and c.partida.id != partida.id and c.partida.sobrepoe(partida)
            and c.partida.status not in (StatusPartida.CANCELADA, StatusPartida.ENCERRADA)
            for c in self.candidaturas.values()
        )

    def _partidas_jogadas(self, jogador):
        return sum(
            1 for c in self.candidaturas.values()
            if c.jogador.id == jogador.id and c.status == StatusCandidatura.APROVADA
            and c.partida.status == StatusPartida.ENCERRADA
        )

    def _candidatura_de(self, partida, jogador):
        return next((c for c in self.candidaturas.values()
                     if c.partida.id == partida.id and c.jogador.id == jogador.id), None)

    # ---------------------------------------------------------------- partidas
    def criar_partida(self, ator, dados):
        with self._trava:
            self._exigir_papel(ator, Papel.ORGANIZADOR, Papel.QUADRA)
            quadra = None
            if ator.papel == Papel.QUADRA:
                quadra = ator
                local = {"local_nome": ator.nome_fantasia, "endereco": ator.endereco,
                         "cidade": ator.cidade, "bairro": ator.bairro}
            else:
                local = {"local_nome": dados.get("localNome"), "endereco": dados.get("endereco"),
                         "cidade": dados.get("cidade"), "bairro": dados.get("bairro")}
            partida = Partida(
                ator, dados.get("titulo"), local["local_nome"], local["endereco"],
                local["cidade"], dados.get("inicio"), dados.get("fim"),
                dados.get("totalVagas"), dados.get("valorQuadra"),
                descricao=dados.get("descricao"), bairro=local["bairro"],
                nota_minima=dados.get("notaMinima"), posicoes=dados.get("posicoes"),
                quadra=quadra, agora=self.relogio(),
            )
            self.partidas[partida.id] = partida
            self._gerar_propostas(partida)
            return partida

    def editar_partida(self, ator, partida_id, dados):
        with self._trava:
            partida = self.obter_partida(partida_id)
            self._exigir_criador(ator, partida)
            mapa = {"titulo": "titulo", "descricao": "descricao", "localNome": "local_nome",
                    "endereco": "endereco", "cidade": "cidade", "bairro": "bairro",
                    "inicio": "inicio", "fim": "fim", "totalVagas": "total_vagas",
                    "valorQuadra": "valor_quadra", "notaMinima": "nota_minima",
                    "posicoes": "posicoes"}
            if partida.quadra:  # o local de uma quadra vem sempre do cadastro dela
                for chave in ("localNome", "endereco", "cidade", "bairro"):
                    dados = {k: v for k, v in dados.items() if k != chave}
            novos = {mapa[k]: v for k, v in dados.items() if k in mapa}
            partida.editar(novos, len(self.aprovadas(partida)), self.relogio())
            return partida

    def iniciar_partida(self, ator, partida_id):
        with self._trava:
            partida = self.obter_partida(partida_id)
            self._exigir_criador(ator, partida)
            partida.iniciar(self.relogio())
            self._expirar_propostas(partida)
            return partida

    def encerrar_partida(self, ator, partida_id):
        with self._trava:
            partida = self.obter_partida(partida_id)
            self._exigir_criador(ator, partida)
            partida.encerrar()
            return partida

    def cancelar_partida(self, ator, partida_id):
        with self._trava:
            partida = self.obter_partida(partida_id)
            self._exigir_criador(ator, partida)
            partida.cancelar()
            self._expirar_propostas(partida)
            agora = self.relogio()
            for c in self.candidaturas.values():
                if c.partida.id == partida.id and c.ativa:
                    c.cancelar(agora)
            return partida

    def _expirar_propostas(self, partida):
        for p in self.propostas.values():
            if p.partida.id == partida.id:
                p.expirar_se_preciso(self.relogio())

    def listar_partidas(self, filtros, paginacao):
        cidade, bairro = _norm(filtros.get("cidade")), _norm(filtros.get("bairro"))
        de = converter_data_hora(filtros["dataDe"], "dataDe") if filtros.get("dataDe") else None
        ate = converter_data_hora(filtros["dataAte"], "dataAte") if filtros.get("dataAte") else None
        posicao = Posicao.converter(filtros["posicao"]) if filtros.get("posicao") else None
        maximo = validar_valor(filtros.get("valorMaximo"), "Valor máximo", obrigatorio=False)
        try:
            status = StatusPartida(filtros["status"].upper()) if filtros.get("status") else None
        except ValueError as erro:
            raise DadosInvalidosError("Status inválido.") from erro
        with self._trava:
            itens = [
                p for p in self.partidas.values()
                if (not cidade or _norm(p.cidade) == cidade)
                and (not bairro or _norm(p.bairro) == bairro)
                and (not de or p.inicio >= de)
                and (not ate or p.inicio <= ate)
                and (not posicao or posicao in p.posicoes_pedidas)
                and (maximo is None or p.valor_quadra <= maximo)
                and (not status or p.status == status)
            ]
        return paginacao.aplicar(itens, _ORDEM_PARTIDA)

    def minhas_partidas(self, ator, paginacao):
        with self._trava:
            if ator.papel == Papel.JOGADOR:
                itens = [c.partida for c in self.candidaturas.values()
                         if c.jogador.id == ator.id and c.status == StatusCandidatura.APROVADA]
            else:
                itens = [p for p in self.partidas.values() if p.criador.id == ator.id]
        return paginacao.aplicar(itens, _ORDEM_PARTIDA)

    def participantes(self, partida_id):
        with self._trava:
            partida = self.obter_partida(partida_id)
            return [c.jogador for c in self.aprovadas(partida)]

    # ------------------------------------------------------------ candidaturas
    def _criar_candidatura(self, partida, jogador, posicao=None, proposta=None):
        if not partida.aceita_candidaturas():
            raise ConflitoError("A partida não está aberta para candidaturas.", "PARTIDA_FECHADA")
        if self._candidatura_de(partida, jogador):
            raise ConflitoError("Você já se candidatou a esta partida.", "CANDIDATURA_DUPLICADA")
        if not jogador.atende_nota_minima(partida.nota_minima):
            raise RegraNegocioError("Sua nota é menor que a mínima exigida.", "NOTA_INSUFICIENTE")
        if self._aprovada_em_conflito(jogador, partida):
            raise RegraNegocioError("Você já tem partida aprovada nesse horário.",
                                    "CONFLITO_HORARIO")
        candidatura = Candidatura(partida, jogador, posicao, proposta)
        self.candidaturas[candidatura.id] = candidatura
        return candidatura

    def candidatar(self, ator, partida_id, posicao=None):
        with self._trava:
            self._exigir_papel(ator, Papel.JOGADOR)
            return self._criar_candidatura(self.obter_partida(partida_id), ator, posicao)

    def listar_candidaturas_partida(self, ator, partida_id, status=None):
        with self._trava:
            partida = self.obter_partida(partida_id)
            self._exigir_criador(ator, partida)
            alvo = _status(StatusCandidatura, status)
            return [c for c in self.candidaturas.values()
                    if c.partida.id == partida.id and (not alvo or c.status == alvo)]

    def minhas_candidaturas(self, ator, status=None):
        with self._trava:
            self._exigir_papel(ator, Papel.JOGADOR)
            alvo = _status(StatusCandidatura, status)
            return [c for c in self.candidaturas.values()
                    if c.jogador.id == ator.id and (not alvo or c.status == alvo)]

    def _candidatura_do_criador(self, ator, candidatura_id):
        candidatura = self._buscar(self.candidaturas, candidatura_id, "Candidatura")
        self._exigir_criador(ator, candidatura.partida)
        return candidatura

    def aprovar_candidatura(self, ator, candidatura_id):
        with self._trava:  # equivale ao select ... for update da linha da partida
            candidatura = self._candidatura_do_criador(ator, candidatura_id)
            partida = candidatura.partida
            if candidatura.status != StatusCandidatura.PENDENTE:
                raise ConflitoError(f"A candidatura já está {candidatura.status.value}.",
                                    "CANDIDATURA_JA_DECIDIDA")
            if not partida.aceita_candidaturas() or not self.vagas_restantes(partida):
                raise ConflitoError("A partida não tem mais vagas.", "PARTIDA_SEM_VAGAS")
            if self._aprovada_em_conflito(candidatura.jogador, partida):
                raise RegraNegocioError("O jogador já tem partida aprovada nesse horário.",
                                        "CONFLITO_HORARIO")
            candidatura.aprovar(self.relogio())
            if not self.vagas_restantes(partida):
                partida.completar()
            return candidatura

    def rejeitar_candidatura(self, ator, candidatura_id):
        with self._trava:
            candidatura = self._candidatura_do_criador(ator, candidatura_id)
            candidatura.rejeitar(self.relogio())
            return candidatura

    def cancelar_candidatura(self, ator, candidatura_id):
        with self._trava:
            candidatura = self._buscar(self.candidaturas, candidatura_id, "Candidatura")
            if candidatura.jogador.id != ator.id:
                raise PermissaoNegadaError("Só o próprio jogador cancela sua candidatura.")
            partida = candidatura.partida
            if partida.status not in (StatusPartida.ABERTA, StatusPartida.COMPLETA):
                raise ConflitoError("Esta partida não aceita mais cancelamentos.",
                                    "PARTIDA_FECHADA")
            candidatura.cancelar(self.relogio())
            if partida.status == StatusPartida.COMPLETA and self.vagas_restantes(partida):
                partida.reabrir()
            return candidatura

    # --------------------------------------------------------------- propostas
    def listar_propostas(self, ator, status=None):
        with self._trava:
            self._exigir_papel(ator, Papel.JOGADOR)
            alvo = _status(StatusProposta, status)
            agora = self.relogio()
            minhas = [p for p in self.propostas.values() if p.jogador.id == ator.id]
            for p in minhas:
                p.expirar_se_preciso(agora)
            return sorted([p for p in minhas if not alvo or p.status == alvo],
                          key=lambda p: -p.pontuacao)

    def _proposta_do_jogador(self, ator, proposta_id):
        self._exigir_papel(ator, Papel.JOGADOR)
        proposta = self._buscar(self.propostas, proposta_id, "Proposta")
        if proposta.jogador.id != ator.id:
            raise PermissaoNegadaError("Esta proposta é de outro jogador.")
        return proposta

    def _proposta_viva(self, proposta):
        if proposta.expirar_se_preciso(self.relogio()):
            raise ConflitoError("A proposta expirou.", "PROPOSTA_EXPIRADA")

    def visualizar_proposta(self, ator, proposta_id):
        with self._trava:
            proposta = self._proposta_do_jogador(ator, proposta_id)
            self._proposta_viva(proposta)
            proposta.visualizar()
            return proposta

    def aceitar_proposta(self, ator, proposta_id, posicao=None):
        with self._trava:
            proposta = self._proposta_do_jogador(ator, proposta_id)
            self._proposta_viva(proposta)
            if not proposta.aberta:
                raise ConflitoError(f"A proposta está {proposta.status.value}.",
                                    "PROPOSTA_FINALIZADA")
            # Valida e cria a candidatura antes de mudar a proposta: se falhar, nada muda.
            candidatura = self._criar_candidatura(
                proposta.partida, ator, posicao or proposta.jogador.posicao_principal, proposta)
            proposta.aceitar(self.relogio())
            return candidatura

    def recusar_proposta(self, ator, proposta_id):
        with self._trava:
            proposta = self._proposta_do_jogador(ator, proposta_id)
            self._proposta_viva(proposta)
            proposta.recusar(self.relogio())
            return proposta

    #------------------------------------------------------------- matchmaking
    def gerar_matchmaking(self, ator, partida_id):
        with self._trava:
            partida = self.obter_partida(partida_id)
            self._exigir_criador(ator, partida)
            if not partida.aceita_candidaturas():
                raise ConflitoError("Só partidas abertas geram propostas.", "PARTIDA_FECHADA")
            return self._gerar_propostas(partida)

    def _gerar_propostas(self, partida):
        vagas = self.vagas_restantes(partida)
        if not vagas:
            return []
        pedidas = partida.posicoes_pedidas
        vinculados = {p.jogador.id for p in self.propostas.values() if p.partida.id == partida.id}
        vinculados |= {c.jogador.id for c in self.candidaturas.values()
                       if c.partida.id == partida.id}
        pontuados = []
        for jogador in self.usuarios.values():
            if not isinstance(jogador, Jogador):
                continue
            if not matchmaking.eh_elegivel(
                    jogador, partida, jogador.id in vinculados,
                    self._aprovada_em_conflito(jogador, partida)):
                continue
            pontos = matchmaking.pontuar(
                jogador.posicoes, jogador.bairro, jogador.nota_media,
                jogador.total_avaliacoes, self._partidas_jogadas(jogador),
                pedidas.keys(), partida.bairro)
            pontuados.append((jogador, pontos))
        criadas = []
        for jogador, pontos in matchmaking.escolher_melhores(pontuados, vagas):
            proposta = Proposta(partida, jogador, pontos)
            self.propostas[proposta.id] = proposta
            criadas.append(proposta)
        return criadas

    # --------------------------------------------------------------- avaliações
    def _participa(self, usuario, partida):
        if partida.criador.id == usuario.id:
            return True
        return any(c.jogador.id == usuario.id for c in self.aprovadas(partida))

    def avaliar(self, ator, partida_id, avaliado_id, nota, comentario=None):
        with self._trava:
            partida = self.obter_partida(partida_id)
            if not self._participa(ator, partida):
                raise PermissaoNegadaError("Só quem participou da partida pode avaliar.")
            if partida.status != StatusPartida.ENCERRADA:
                raise ConflitoError("A avaliação só é liberada após o encerramento.",
                                    "PARTIDA_NAO_ENCERRADA")
            avaliado = self.obter_jogador(avaliado_id)
            if avaliado.id == ator.id:
                raise DadosInvalidosError("Ninguém pode se autoavaliar.", "AUTOAVALIACAO")
            if not any(c.jogador.id == avaliado.id for c in self.aprovadas(partida)):
                raise RegraNegocioError("O avaliado não jogou esta partida.", "AVALIADO_INVALIDO")
            if any(a.partida.id == partida.id and a.avaliador.id == ator.id
                   and a.avaliado.id == avaliado.id for a in self.avaliacoes):
                raise ConflitoError("Você já avaliou este jogador nesta partida.",
                                    "AVALIACAO_DUPLICADA")
            avaliacao = Avaliacao(partida, ator, avaliado, nota, comentario, self.relogio())
            avaliado.registrar_avaliacao(avaliacao.nota)  # mesma "transação" do lock
            self.avaliacoes.append(avaliacao)
            return avaliacao

    def avaliacoes_pendentes(self, ator, partida_id):
        with self._trava:
            partida = self.obter_partida(partida_id)
            if not self._participa(ator, partida):
                raise PermissaoNegadaError("Só quem participou da partida pode avaliar.")
            if partida.status != StatusPartida.ENCERRADA:
                return []
            ja = {a.avaliado.id for a in self.avaliacoes
                  if a.partida.id == partida.id and a.avaliador.id == ator.id}
            return [c.jogador for c in self.aprovadas(partida)
                    if c.jogador.id != ator.id and c.jogador.id not in ja]

    def avaliacoes_recebidas(self, jogador_id, paginacao):
        with self._trava:
            jogador = self.obter_jogador(jogador_id)
            itens = [a for a in self.avaliacoes if a.avaliado.id == jogador.id]
        return paginacao.aplicar(itens, {"criadaEm": lambda a: a.criada_em})


_ORDEM_PARTIDA = {
    "inicio": lambda p: p.inicio,
    "valorQuadra": lambda p: p.valor_quadra,
    "titulo": lambda p: p.titulo.casefold(),
}
PARTIDA_ORDENS = tuple(_ORDEM_PARTIDA)


def _norm(texto):
    return texto.strip().casefold() if isinstance(texto, str) and texto.strip() else None


def _status(enum, valor):
    if not valor:
        return None
    try:
        return enum(str(valor).upper())
    except ValueError as erro:
        raise DadosInvalidosError("Status inválido.") from erro
