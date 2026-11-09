"""Exceções de domínio. Cada uma carrega o status HTTP e um código estável."""


class DadosInvalidosError(ValueError):
    """Formato ou valor inválido de um campo (HTTP 400)."""

    status = 400
    codigo = "DADOS_INVALIDOS"

    def __init__(self, mensagem, codigo=None):
        super().__init__(mensagem)
        if codigo:
            self.codigo = codigo


class NaoAutenticadoError(Exception):
    status = 401
    codigo = "NAO_AUTENTICADO"


class PermissaoNegadaError(Exception):
    """Recurso existe, mas pertence a outro usuário ou papel (HTTP 403)."""

    status = 403
    codigo = "SEM_PERMISSAO"

    def __init__(self, mensagem="Você não tem permissão para esta ação."):
        super().__init__(mensagem)


class NaoEncontradoError(Exception):
    status = 404
    codigo = "NAO_ENCONTRADO"

    def __init__(self, mensagem="Recurso não encontrado."):
        super().__init__(mensagem)


class ConflitoError(Exception):
    """Conflito de estado: transição inválida, duplicidade, sem vagas (HTTP 409)."""

    status = 409
    codigo = "CONFLITO"

    def __init__(self, mensagem, codigo=None):
        super().__init__(mensagem)
        if codigo:
            self.codigo = codigo


class RegraNegocioError(Exception):
    """Regra de negócio violada, como conflito de horário (HTTP 422)."""

    status = 422
    codigo = "REGRA_NEGOCIO"

    def __init__(self, mensagem, codigo=None):
        super().__init__(mensagem)
        if codigo:
            self.codigo = codigo
