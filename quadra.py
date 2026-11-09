"""Classe Quadra: também cria partidas, com o local do próprio cadastro."""
from usuario import Papel, Usuario
from validacao import validar_texto, validar_valor


class Quadra(Usuario):
    def __init__(self, nome, email, senha, nome_fantasia, endereco, cidade,
                 bairro=None, tipo=None, preco_hora=None, telefone=None):
        super().__init__(nome, email, senha, telefone)
        self.nome_fantasia = nome_fantasia
        self.endereco = endereco
        self.cidade = cidade
        self.bairro = bairro
        self.tipo = tipo
        self.preco_hora = preco_hora

    @property
    def papel(self):
        return Papel.QUADRA

    @property
    def nome_fantasia(self):
        return self._nome_fantasia

    @nome_fantasia.setter
    def nome_fantasia(self, valor):
        self._nome_fantasia = validar_texto(valor, "Nome fantasia", 120)

    @property
    def endereco(self):
        return self._endereco

    @endereco.setter
    def endereco(self, valor):
        self._endereco = validar_texto(valor, "Endereço", 200)

    @property
    def cidade(self):
        return self._cidade

    @cidade.setter
    def cidade(self, valor):
        self._cidade = validar_texto(valor, "Cidade", 80)

    @property
    def bairro(self):
        return self._bairro

    @bairro.setter
    def bairro(self, valor):
        self._bairro = validar_texto(valor, "Bairro", 80, obrigatorio=False)

    @property
    def tipo(self):
        return self._tipo

    @tipo.setter
    def tipo(self, valor):
        self._tipo = validar_texto(valor, "Tipo", 40, obrigatorio=False)

    @property
    def preco_hora(self):
        return self._preco_hora

    @preco_hora.setter
    def preco_hora(self, valor):
        self._preco_hora = validar_valor(valor, "Preço por hora", obrigatorio=False)

    def perfil_completo(self):
        dados = self.dados_basicos()
        dados.update(
            {
                "nomeFantasia": self.nome_fantasia,
                "endereco": self.endereco,
                "cidade": self.cidade,
                "bairro": self.bairro,
                "tipo": self.tipo,
                "precoHora": float(self.preco_hora) if self.preco_hora is not None else None,
            }
        )
        return dados
