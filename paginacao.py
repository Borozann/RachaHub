"""Filtro de listagem (página, limite, ordenação) e resposta paginada."""
from erros import DadosInvalidosError

LIMITE_MAXIMO = 50
LIMITE_PADRAO = 20


class Paginacao:
    """Objeto de valor imutável: normaliza e valida os próprios valores."""

    __slots__ = ("page", "limit", "campo", "decrescente")

    def __init__(self, page=1, limit=LIMITE_PADRAO, sort=None, permitidos=(), padrao=None):
        try:
            page = int(page or 1)
            limit = int(limit or LIMITE_PADRAO)
        except (ValueError, TypeError) as erro:
            raise DadosInvalidosError("page e limit devem ser números inteiros.") from erro
        if page < 1 or limit < 1:
            raise DadosInvalidosError("page e limit devem ser maiores que zero.")
        object.__setattr__(self, "page", page)
        object.__setattr__(self, "limit", min(limit, LIMITE_MAXIMO))
        campo, direcao = self._interpretar(sort, permitidos, padrao)
        object.__setattr__(self, "campo", campo)
        object.__setattr__(self, "decrescente", direcao == "desc")

    def __setattr__(self, nome, valor):
        raise AttributeError("Paginacao é imutável.")

    @staticmethod
    def _interpretar(sort, permitidos, padrao):
        if not sort:
            return padrao, "asc"
        campo, _, direcao = str(sort).partition(":")
        direcao = (direcao or "asc").lower()
        if campo not in permitidos or direcao not in ("asc", "desc"):
            raise DadosInvalidosError(f"Ordenação inválida. Permitidos: {', '.join(permitidos)}.")
        return campo, direcao

    def aplicar(self, itens, chaves):
        """`chaves`: dict campo -> função que extrai o valor de ordenação."""
        itens = list(itens)
        if self.campo:
            itens.sort(key=chaves[self.campo], reverse=self.decrescente)
        total = len(itens)
        inicio = (self.page - 1) * self.limit
        return {
            "dados": itens[inicio: inicio + self.limit],
            "meta": {"page": self.page, "limit": self.limit, "total": total},
        }
