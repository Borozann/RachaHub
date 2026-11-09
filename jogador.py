"""Classe Jogador: posições, localização e nota média (estilo Uber)."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from erros import DadosInvalidosError
from posicao import Posicao
from usuario import Papel, Usuario
from validacao import validar_inteiro, validar_texto

MAX_POSICOES = 4
AVALIACOES_MINIMAS = 3  # abaixo disso o jogador é "novo" e não é barrado por nota


class Jogador(Usuario):
    def __init__(self, nome, email, senha, cidade, posicoes, bairro=None,
                 telefone=None, nascimento=None):
        super().__init__(nome, email, senha, telefone)
        self.cidade = cidade
        self.bairro = bairro
        self.nascimento = nascimento
        self.foto_url = None
        self._posicoes = []
        self.definir_posicoes(posicoes)
        self._soma_notas = 0
        self._total_avaliacoes = 0

    @property
    def papel(self):
        return Papel.JOGADOR

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
    def nascimento(self):
        return self._nascimento

    @nascimento.setter
    def nascimento(self, valor):
        if valor in (None, ""):
            self._nascimento = None
            return
        try:
            data = valor if isinstance(valor, date) else date.fromisoformat(str(valor))
        except ValueError as erro:
            raise DadosInvalidosError("Data de nascimento inválida.") from erro
        if data >= date.today():
            raise DadosInvalidosError("Data de nascimento deve estar no passado.")
        self._nascimento = data

    @property
    def posicoes(self):
        return tuple(self._posicoes)

    @property
    def posicao_principal(self):
        return self._posicoes[0]

    @property
    def total_avaliacoes(self):
        return self._total_avaliacoes

    @property
    def nota_media(self):
        if not self._total_avaliacoes:
            return Decimal("0.00")
        media = Decimal(self._soma_notas) / Decimal(self._total_avaliacoes)
        return media.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def eh_novato(self):
        return self._total_avaliacoes < AVALIACOES_MINIMAS

    def definir_posicoes(self, posicoes):
        """`posicoes` é uma lista de {posicao, principal}. Exige 1 a 4, sem repetição,
        com exatamente uma principal; a principal fica sempre na primeira posição."""
        if not isinstance(posicoes, (list, tuple)) or not 1 <= len(posicoes) <= MAX_POSICOES:
            raise DadosInvalidosError(
                f"Informe de 1 a {MAX_POSICOES} posições.", "POSICOES_INVALIDAS"
            )
        convertidas = []
        for item in posicoes:
            if isinstance(item, dict):
                convertidas.append((Posicao.converter(item.get("posicao")), bool(item.get("principal"))))
            else:
                convertidas.append((Posicao.converter(item), False))
        nomes = [p for p, _ in convertidas]
        if len(set(nomes)) != len(nomes):
            raise DadosInvalidosError("Posições não podem se repetir.", "POSICOES_INVALIDAS")
        principais = [p for p, principal in convertidas if principal]
        if len(principais) != 1:
            raise DadosInvalidosError(
                "Marque exatamente uma posição principal.", "POSICOES_INVALIDAS"
            )
        principal = principais[0]
        self._posicoes = [principal] + [p for p in nomes if p != principal]

    def registrar_avaliacao(self, nota):
        nota = validar_inteiro(nota, "Nota", 1, 5)
        self._soma_notas += nota
        self._total_avaliacoes += 1

    def atende_nota_minima(self, nota_minima):
        if nota_minima is None or self.eh_novato:
            return True
        return self.nota_media >= nota_minima

    def perfil_publico(self):
        dados = self.dados_basicos()
        dados.pop("email")
        dados.pop("telefone")
        dados.update(
            {
                "cidade": self.cidade,
                "bairro": self.bairro,
                "fotoUrl": self.foto_url,
                "posicoes": [
                    {"posicao": p.value, "principal": i == 0}
                    for i, p in enumerate(self._posicoes)
                ],
                "notaMedia": float(self.nota_media),
                "totalAvaliacoes": self.total_avaliacoes,
            }
        )
        return dados
