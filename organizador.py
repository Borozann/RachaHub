"""Classe Organizador: cria partidas e analisa candidaturas."""
from usuario import Papel, Usuario
from validacao import validar_texto


class Organizador(Usuario):
    def __init__(self, nome, email, senha, cidade, telefone=None):
        super().__init__(nome, email, senha, telefone)
        self.cidade = cidade

    @property
    def papel(self):
        return Papel.ORGANIZADOR

    @property
    def cidade(self):
        return self._cidade

    @cidade.setter
    def cidade(self, valor):
        self._cidade = validar_texto(valor, "Cidade", 80)

    def perfil_completo(self):
        dados = self.dados_basicos()
        dados["cidade"] = self.cidade
        return dados
