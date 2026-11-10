"""Classe Candidatura: pedido de um jogador para entrar em uma partida."""
import uuid
from datetime import datetime
from enum import Enum

from erros import ConflitoError
from posicao import Posicao


class StatusCandidatura(str, Enum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    REJEITADA = "REJEITADA"
    CANCELADA = "CANCELADA"


class Candidatura:
    def __init__(self, partida, jogador, posicao=None, proposta=None):
        self.id = str(uuid.uuid4())
        self.partida = partida
        self.jogador = jogador
        self.proposta = proposta
        self.posicao = Posicao.converter(posicao) if posicao else None
        self.status = StatusCandidatura.PENDENTE
        self.decidida_em = None

    def _decidir(self, novo, agora=None):
        if self.status != StatusCandidatura.PENDENTE:
            raise ConflitoError(
                f"A candidatura já está {self.status.value}.", "CANDIDATURA_JA_DECIDIDA"
            )
        self.status = novo
        self.decidida_em = agora or datetime.now()

    def aprovar(self, agora=None):
        self._decidir(StatusCandidatura.APROVADA, agora)

    def rejeitar(self, agora=None):
        self._decidir(StatusCandidatura.REJEITADA, agora)

    def cancelar(self, agora=None):
        if self.status not in (StatusCandidatura.PENDENTE, StatusCandidatura.APROVADA):
            raise ConflitoError(
                f"A candidatura já está {self.status.value}.", "CANDIDATURA_JA_DECIDIDA"
            )
        self.status = StatusCandidatura.CANCELADA
        self.decidida_em = agora or datetime.now()

    @property
    def ativa(self):
        return self.status in (StatusCandidatura.PENDENTE, StatusCandidatura.APROVADA)
