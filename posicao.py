"""Posições de futsal."""
from enum import Enum

from erros import DadosInvalidosError


class Posicao(str, Enum):
    GOLEIRO = "GOLEIRO"
    FIXO = "FIXO"
    ALA = "ALA"
    PIVO = "PIVO"

    @classmethod
    def converter(cls, valor):
        try:
            return valor if isinstance(valor, cls) else cls(str(valor).strip().upper())
        except ValueError as erro:
            raise DadosInvalidosError(f"Posição inválida: {valor}.") from erro
