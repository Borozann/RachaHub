"""Classe Avaliacao: nota de 1 a 5 dada após a partida. Imutável depois de criada."""
import uuid
from datetime import datetime

from erros import DadosInvalidosError
from validacao import validar_inteiro, validar_texto


class Avaliacao:
    def __init__(self, partida, avaliador, avaliado, nota, comentario=None, agora=None):
        if avaliador.id == avaliado.id:
            raise DadosInvalidosError("Ninguém pode se autoavaliar.", "AUTOAVALIACAO")
        self.id = str(uuid.uuid4())
        self.partida = partida
        self.avaliador = avaliador
        self.avaliado = avaliado
        self._nota = validar_inteiro(nota, "Nota", 1, 5)
        self._comentario = validar_texto(comentario, "Comentário", 500, obrigatorio=False)
        self.criada_em = agora or datetime.now()

    @property
    def nota(self):
        return self._nota

    @property
    def comentario(self):
        return self._comentario
