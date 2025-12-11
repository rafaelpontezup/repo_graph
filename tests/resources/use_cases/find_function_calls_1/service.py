from validator import validate_cnpj, validate_cpf


def register_company(name: str, cnpj: int) -> dict:
    """Registra uma empresa."""
    if not validate_cnpj(cnpj):
        raise ValueError("CNPJ inválido")
    return {"name": name, "cnpj": cnpj}


def register_person(name: str, cpf: int) -> dict:
    """Registra uma pessoa física."""
    if not validate_cpf(cpf):
        raise ValueError("CPF inválido")
    return {"name": name, "cpf": cpf}
