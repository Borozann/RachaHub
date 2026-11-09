"""Funções de validação reaproveitadas pelas classes de domínio."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from erros import DadosInvalidosError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_texto(valor, campo, maximo, obrigatorio=True):
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obrigatorio:
            raise DadosInvalidosError(f"{campo} é obrigatório.")
        return None
    if not isinstance(valor, str):
        raise DadosInvalidosError(f"{campo} deve ser um texto.")
    texto = valor.strip()
    if len(texto) > maximo:
        raise DadosInvalidosError(f"{campo} deve ter no máximo {maximo} caracteres.")
    return texto


def validar_email(valor):
    email = validar_texto(valor, "E-mail", 180).lower()
    if not _EMAIL.match(email):
        raise DadosInvalidosError("E-mail inválido.")
    return email


def validar_valor(valor, campo="Valor", obrigatorio=True):
    if valor is None or valor == "":
        if obrigatorio:
            raise DadosInvalidosError(f"{campo} é obrigatório.")
        return None
    try:
        numero = Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError) as erro:
        raise DadosInvalidosError(f"{campo}: informe um valor numérico.") from erro
    if not numero.is_finite() or numero < 0:
        raise DadosInvalidosError(f"{campo} não pode ser negativo.")
    return numero.quantize(Decimal("0.01"))


def validar_inteiro(valor, campo, minimo, maximo):
    if isinstance(valor, bool):
        raise DadosInvalidosError(f"{campo} deve ser um número inteiro.")
    try:
        numero = int(valor)
    except (ValueError, TypeError) as erro:
        raise DadosInvalidosError(f"{campo} deve ser um número inteiro.") from erro
    if not minimo <= numero <= maximo:
        raise DadosInvalidosError(f"{campo} deve estar entre {minimo} e {maximo}.")
    return numero


def converter_data_hora(valor, campo):
    if isinstance(valor, datetime):
        return valor
    try:
        data = datetime.fromisoformat(str(valor).strip().replace("Z", ""))
    except (ValueError, TypeError) as erro:
        raise DadosInvalidosError(f"{campo}: data/hora inválida.") from erro
    return data.replace(tzinfo=None)
