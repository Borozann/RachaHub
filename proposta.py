"""Classe Proposta: convite gerado pelo matchmaking. Receber não inscreve o jogador."""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from erros import ConflitoError


class StatusProposta(str, Enum):
    ENVIADA = "ENVIADA"
    VISUALIZADA = "VISUALIZADA"
    ACEITA = "ACEITA"
    RECUSADA = "RECUSADA"
    EXPIRADA = "EXPIRADA"


class Proposta:
    def __init__(self, partida, jogador, pontuacao):
        self.id = str(uuid.uuid4())
        self.partida = partida
        self.jogador = jogador
        self.pontuacao = Decimal(str(pontuacao)).quantize(Decimal("0.01"))
        self.status = StatusProposta.ENVIADA
        self.expira_em = partida.inicio
        self.respondida_em = None

    @property
    def aberta(self):
        return self.status in (StatusProposta.ENVIADA, StatusProposta.VISUALIZADA)

    def expirar_se_preciso(self, agora=None):
        """Expiração é verificada na leitura e na resposta (não há job agendado)."""
        from partida import StatusPartida

        agora = agora or datetime.now()
        if self.aberta and (agora >= self.expira_em
                            or self.partida.status != StatusPartida.ABERTA):
            self.status = StatusProposta.EXPIRADA
        return self.status == StatusProposta.EXPIRADA

    def visualizar(self):
        if self.status == StatusProposta.ENVIADA:
            self.status = StatusProposta.VISUALIZADA
        elif self.status != StatusProposta.VISUALIZADA:
            raise ConflitoError(f"A proposta está {self.status.value}.", "PROPOSTA_FINALIZADA")

    def _responder(self, novo, agora=None):
        if not self.aberta:
            raise ConflitoError(f"A proposta está {self.status.value}.", "PROPOSTA_FINALIZADA")
        self.status = novo
        self.respondida_em = agora or datetime.now()

    def aceitar(self, agora=None):
        self._responder(StatusProposta.ACEITA, agora)

    def recusar(self, agora=None):
        self._responder(StatusProposta.RECUSADA, agora)
