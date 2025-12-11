def validate_cnpj(cnpj: int) -> bool:
    """Valida um CNPJ."""
    cnpj_str = str(cnpj)
    return len(cnpj_str) == 14


def validate_cpf(cpf: int) -> bool:
    """Valida um CPF."""
    cpf_str = str(cpf)
    return len(cpf_str) == 11
