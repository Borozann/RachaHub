"""Classe abstrata Usuario: base de Jogador, Organizador e Quadra."""
import hashlib
import hmac
import os
import uuid
from abc import ABC, abstractmethod
from enum import Enum

from erros import DadosInvalidosError
from validacao import validar_email, validar_texto


class Papel(str, Enum):
    JOGADOR = "JOGADOR"
    ORGANIZADOR = "ORGANIZADOR"
    QUADRA = "QUADRA"


SENHA_MINIMA = 8


def _derivar(senha, sal):
    return hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=2**14, r=8, p=1, dklen=32)


class Usuario(ABC):
    def __init__(self, nome, email, senha, telefone=None):
        self.id = str(uuid.uuid4())
        self.nome = nome
        self.email = email
        self.telefone = telefone
        self.ativo = True
        self._sal = b""
        self._senha_hash = b""
        self.definir_senha(senha)

    @property
    @abstractmethod
    def papel(self):
        """Cada subclasse informa seu papel; ele não pode ser alterado depois."""

    @property
    def nome(self):
        return self._nome

    @nome.setter
    def nome(self, valor):
        self._nome = validar_texto(valor, "Nome", 120)

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, valor):
        self._email = validar_email(valor)

    @property
    def telefone(self):
        return self._telefone

    @telefone.setter
    def telefone(self, valor):
        self._telefone = validar_texto(valor, "Telefone", 20, obrigatorio=False)

    def definir_senha(self, senha):
        if not isinstance(senha, str) or len(senha) < SENHA_MINIMA:
            raise DadosInvalidosError(
                f"A senha deve ter no mínimo {SENHA_MINIMA} caracteres."
            )
        self._sal = os.urandom(16)
        self._senha_hash = _derivar(senha, self._sal)

    def verificar_senha(self, senha):
        if not isinstance(senha, str):
            return False
        return hmac.compare_digest(_derivar(senha, self._sal), self._senha_hash)

    def dados_basicos(self):
        # Nunca inclui o hash da senha.
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
            "telefone": self.telefone,
            "papel": self.papel.value,
        }

    def __str__(self):
        return f"{self.nome} ({self.papel.value})"
