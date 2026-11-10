"""Classe Partida: dados do jogo e máquina de estados."""
import uuid
from datetime import datetime, timedelta
from enum import Enum

from erros import ConflitoError, DadosInvalidosError
from posicao import Posicao
from validacao import (converter_data_hora, validar_inteiro, validar_texto,
                       validar_valor)

DURACAO_MAXIMA = timedelta(hours=4)
VAGAS_MINIMAS = 2
VAGAS_MAXIMAS = 30


class StatusPartida(str, Enum):
    ABERTA = "ABERTA"
    COMPLETA = "COMPLETA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    ENCERRADA = "ENCERRADA"
    CANCELADA = "CANCELADA"


class Partida:
    def __init__(self, criador, titulo, local_nome, endereco, cidade, inicio, fim,
                 total_vagas, valor_quadra, descricao=None, bairro=None,
                 nota_minima=None, posicoes=None, quadra=None, agora=None):
        agora = agora or datetime.now()
        self.id = str(uuid.uuid4())
        self.criador = criador
        self.quadra = quadra
        self.status = StatusPartida.ABERTA
        self._posicoes = {}
        self._total_vagas = VAGAS_MINIMAS
        self.preencher(titulo, descricao, local_nome, endereco, cidade, bairro,
                       inicio, fim, total_vagas, valor_quadra, nota_minima, posicoes)
        if self.inicio <= agora:
            raise DadosInvalidosError("O início da partida deve estar no futuro.")

    def preencher(self, titulo, descricao, local_nome, endereco, cidade, bairro,
                  inicio, fim, total_vagas, valor_quadra, nota_minima, posicoes):
        """Valida tudo antes de alterar o objeto, para a edição ser atômica."""
        titulo = validar_texto(titulo, "Título", 120)
        descricao = validar_texto(descricao, "Descrição", 2000, obrigatorio=False)
        local_nome = validar_texto(local_nome, "Local", 120)
        endereco = validar_texto(endereco, "Endereço", 200)
        cidade = validar_texto(cidade, "Cidade", 80)
        bairro = validar_texto(bairro, "Bairro", 80, obrigatorio=False)
        inicio = converter_data_hora(inicio, "Início")
        fim = converter_data_hora(fim, "Fim")
        if fim <= inicio:
            raise DadosInvalidosError("O fim deve ser depois do início.")
        if fim - inicio > DURACAO_MAXIMA:
            raise DadosInvalidosError("A partida pode durar no máximo 4 horas.")
        total_vagas = validar_inteiro(total_vagas, "Total de vagas", VAGAS_MINIMAS, VAGAS_MAXIMAS)
        valor_quadra = validar_valor(valor_quadra, "Valor da quadra")
        if nota_minima in (None, ""):
            nota_minima = None
        else:
            nota_minima = validar_valor(nota_minima, "Nota mínima")
            if nota_minima > 5:
                raise DadosInvalidosError("Nota mínima deve estar entre 0 e 5.")
        mapa = self._validar_posicoes(posicoes, total_vagas)
        self.titulo, self.descricao = titulo, descricao
        self.local_nome, self.endereco = local_nome, endereco
        self.cidade, self.bairro = cidade, bairro
        self.inicio, self.fim = inicio, fim
        self._total_vagas = total_vagas
        self.valor_quadra, self.nota_minima = valor_quadra, nota_minima
        self._posicoes = mapa

    @staticmethod
    def _validar_posicoes(posicoes, total_vagas):
        mapa = {}
        for item in posicoes or []:
            posicao = Posicao.converter(item.get("posicao"))
            quantidade = validar_inteiro(item.get("quantidade"), "Quantidade", 1, VAGAS_MAXIMAS)
            if posicao in mapa:
                raise DadosInvalidosError("Posição repetida na partida.")
            mapa[posicao] = quantidade
        if sum(mapa.values()) > total_vagas:
            raise DadosInvalidosError("A soma das posições passa do total de vagas.")
        return mapa

    @property
    def total_vagas(self):
        return self._total_vagas

    @property
    def posicoes_pedidas(self):
        return dict(self._posicoes)

    def editar(self, dados, aprovadas, agora=None):
        agora = agora or datetime.now()
        if self.status != StatusPartida.ABERTA:
            raise ConflitoError("Só é possível editar partidas abertas.", "PARTIDA_NAO_EDITAVEL")
        atuais = {
            "titulo": self.titulo, "descricao": self.descricao,
            "local_nome": self.local_nome, "endereco": self.endereco,
            "cidade": self.cidade, "bairro": self.bairro, "inicio": self.inicio,
            "fim": self.fim, "total_vagas": self.total_vagas,
            "valor_quadra": self.valor_quadra, "nota_minima": self.nota_minima,
            "posicoes": [{"posicao": p.value, "quantidade": q} for p, q in self._posicoes.items()],
        }
        atuais.update(dados)
        vagas = validar_inteiro(atuais["total_vagas"], "Total de vagas", VAGAS_MINIMAS, VAGAS_MAXIMAS)
        if vagas < aprovadas:
            raise DadosInvalidosError(
                "O total de vagas não pode ficar abaixo das candidaturas aprovadas.",
                "VAGAS_ABAIXO_APROVADAS",
            )
        novo_inicio = converter_data_hora(atuais["inicio"], "Início")
        if novo_inicio != self.inicio and novo_inicio <= agora:
            raise DadosInvalidosError("O início da partida deve estar no futuro.")
        self.preencher(**atuais)

    def vagas_restantes(self, aprovadas):
        return max(self.total_vagas - aprovadas, 0)

    def sobrepoe(self, outra):
        return self.inicio < outra.fim and outra.inicio < self.fim

    def aceita_candidaturas(self):
        return self.status == StatusPartida.ABERTA

    # --- máquina de estados -------------------------------------------------
    def _exigir(self, *permitidos, acao):
        if self.status not in permitidos:
            raise ConflitoError(
                f"Não é possível {acao} uma partida {self.status.value}.",
                "TRANSICAO_INVALIDA",
            )

    def completar(self):
        self._exigir(StatusPartida.ABERTA, acao="completar")
        self.status = StatusPartida.COMPLETA

    def reabrir(self):
        self._exigir(StatusPartida.COMPLETA, acao="reabrir")
        self.status = StatusPartida.ABERTA

    def iniciar(self, agora=None):
        self._exigir(StatusPartida.ABERTA, StatusPartida.COMPLETA, acao="iniciar")
        if (agora or datetime.now()) < self.inicio:
            raise ConflitoError("A partida só pode começar a partir do horário de início.",
                                "ANTES_DO_HORARIO")
        self.status = StatusPartida.EM_ANDAMENTO

    def encerrar(self):
        self._exigir(StatusPartida.EM_ANDAMENTO, acao="encerrar")
        self.status = StatusPartida.ENCERRADA

    def cancelar(self):
        self._exigir(StatusPartida.ABERTA, StatusPartida.COMPLETA, acao="cancelar")
        self.status = StatusPartida.CANCELADA
