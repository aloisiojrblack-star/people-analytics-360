"""Testes de regressão do dashboard e de seus dados públicos."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.dashboard_core import (
    PAGINAS,
    FiltrosDashboard,
    carregar_bases,
    construir_pagina,
    criar_relatorio_excel,
    preparar_contexto,
    validar_dashboard,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
PASTA_DADOS = RAIZ_PROJETO / "dados"


@pytest.fixture(scope="session")
def recursos_dashboard():
    """Carrega os dados uma única vez para toda a suíte."""

    bases, diagnostico = carregar_bases(PASTA_DADOS)
    filtros = FiltrosDashboard(
        ano="2025",
        mes=None,
        filial="Todas",
        departamento="Todos",
    )
    contexto = preparar_contexto(bases, filtros)
    return bases, diagnostico, filtros, contexto


def test_contratos_e_controles_de_qualidade(recursos_dashboard):
    bases, diagnostico, _, _ = recursos_dashboard

    assert diagnostico["status"].eq("OK").all()
    validacoes = validar_dashboard(bases, diagnostico)
    assert validacoes["status"].eq("OK").all()


def test_identificadores_publicados_sao_artificiais(recursos_dashboard):
    bases, _, _, _ = recursos_dashboard

    assert bases.cadastros["colaborador"].str.fullmatch(
        r"Colaborador \d{4}"
    ).all()
    assert bases.cadastros["matricula"].str.fullmatch(r"RH-\d{5}").all()

    tabelas: tuple[pd.DataFrame, ...] = (
        bases.cadastros,
        bases.mensal,
        bases.treinamentos,
        bases.recrutamento,
    )
    nomes_colunas = {coluna.casefold() for tabela in tabelas for coluna in tabela}
    campos_pessoais_diretos = {"cpf", "email", "telefone", "endereco"}
    assert nomes_colunas.isdisjoint(campos_pessoais_diretos)


def test_sete_paginas_sao_construidas(recursos_dashboard):
    bases, _, filtros, contexto = recursos_dashboard

    paginas = [
        construir_pagina(
            nome,
            contexto,
            bases,
            filtros,
            "Azul executivo",
        )
        for nome in PAGINAS
    ]

    assert len(paginas) == 7
    assert all(pagina.titulo for pagina in paginas)
    assert all(pagina.kpis for pagina in paginas)
    assert all(pagina.graficos for pagina in paginas)


def test_exportacao_excel(recursos_dashboard):
    _, diagnostico, filtros, contexto = recursos_dashboard

    arquivo = criar_relatorio_excel(contexto, filtros, diagnostico)

    assert arquivo.startswith(b"PK")
    assert len(arquivo) > 100_000


def test_interface_streamlit_inicia_sem_excecoes():
    app = AppTest.from_file(
        str(RAIZ_PROJETO / "streamlit_app.py"),
        default_timeout=60,
    ).run()

    assert not app.exception
    assert len(app.segmented_control) >= 3
    assert len(app.selectbox) == 3
