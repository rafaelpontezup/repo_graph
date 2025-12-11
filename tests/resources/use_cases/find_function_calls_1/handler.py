from validator import validate_cnpj


class CompanyHandler:
    def process(self, cnpj: int) -> None:
        """Processa CNPJ da empresa."""
        if validate_cnpj(cnpj):
            print(f"CNPJ válido: {cnpj}")
        else:
            print(f"CNPJ inválido: {cnpj}")

    def batch_validate(self, cnpjs: list) -> list:
        """Valida uma lista de CNPJs."""
        return [cnpj for cnpj in cnpjs if validate_cnpj(cnpj)]
