"""Regras de negócio, filtros, gráficos e exportação do dashboard.

Este módulo contém a parte que pode ser testada sem abrir o navegador. O
``streamlit_app.py`` cuida apenas da interface. A separação segue uma prática
comum em projetos profissionais: regra de negócio não deve ficar misturada
com botões, menus e estilos da tela.

As visualizações atendem às sete páginas executivas do produto:
Overview, Recrutamento, Treinamentos, Rotatividade, Desempenho, Financeiro e
Mapeamento populacional.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# 1. Constantes de calendário, páginas e identidade visual
# ---------------------------------------------------------------------------

# O número continua sendo usado nos filtros; o texto curto é exibido ao usuário.
MESES = {
    1: "JAN",
    2: "FEV",
    3: "MAR",
    4: "ABR",
    5: "MAI",
    6: "JUN",
    7: "JUL",
    8: "AGO",
    9: "SET",
    10: "OUT",
    11: "NOV",
    12: "DEZ",
}
ORDEM_MESES = list(MESES.values())

# A ordem abaixo também é a ordem dos botões da central de navegação.
PAGINAS = [
    "Overview",
    "Recrutamento",
    "Treinamentos",
    "Rotatividade",
    "Desempenho",
    "Financeiro",
    "Mapeamento",
]

# Cada paleta usa as mesmas chaves. As funções de gráfico não precisam saber
# qual tema foi escolhido; elas recebem o dicionário e consultam as chaves.
PALETAS: dict[str, dict[str, str]] = {
    "Azul executivo": {
        "fundo": "#0B1220",
        "painel": "#172033",
        "painel_2": "#1E2A40",
        "primaria": "#4EA8DE",
        "secundaria": "#31C48D",
        "destaque": "#D4A72C",
        "alerta": "#EF4444",
        "texto": "#E5EEF8",
        "texto_suave": "#AFC1D5",
        "grade": "#34425A",
    },
    "Claro corporativo": {
        "fundo": "#EDF2F7",
        "painel": "#FFFFFF",
        "painel_2": "#F7FAFC",
        "primaria": "#2563EB",
        "secundaria": "#059669",
        "destaque": "#B7791F",
        "alerta": "#DC2626",
        "texto": "#172033",
        "texto_suave": "#52637A",
        "grade": "#D1D9E6",
    },
    "Verde RH": {
        "fundo": "#071A17",
        "painel": "#0F2A24",
        "painel_2": "#173A32",
        "primaria": "#2DD4BF",
        "secundaria": "#22C55E",
        "destaque": "#FBBF24",
        "alerta": "#FB7185",
        "texto": "#ECFDF5",
        "texto_suave": "#A7D7C8",
        "grade": "#315A51",
    },
    "Roxo moderno": {
        "fundo": "#160D2B",
        "painel": "#251747",
        "painel_2": "#33205E",
        "primaria": "#A78BFA",
        "secundaria": "#34D399",
        "destaque": "#F59E0B",
        "alerta": "#F43F5E",
        "texto": "#F5F3FF",
        "texto_suave": "#CFC5EA",
        "grade": "#4C3A70",
    },
}


# ---------------------------------------------------------------------------
# 2. Estruturas de dados que documentam entradas e saídas
# ---------------------------------------------------------------------------

@dataclass
class BasesRH:
    """Agrupa as cinco tabelas do projeto em um único objeto nomeado."""

    cadastros: pd.DataFrame
    mensal: pd.DataFrame
    treinamentos: pd.DataFrame
    recrutamento: pd.DataFrame
    dicionario: pd.DataFrame


@dataclass
class FiltrosDashboard:
    """Representa as escolhas feitas na central de navegação."""

    ano: str
    mes: int | None
    filial: str
    departamento: str


@dataclass
class PaginaDashboard:
    """Contrato de saída de uma página pronta para a interface web."""

    titulo: str
    subtitulo: str
    kpis: list[dict[str, str]]
    graficos: list[dict[str, Any]]
    tabela: pd.DataFrame | None = None
    titulo_tabela: str | None = None


# Campos mínimos usados pelos cálculos e pelos gráficos.
CONTRATO_BASES: dict[str, set[str]] = {
    "cadastros": {
        "matricula",
        "genero",
        "idade",
        "formacao_academica",
        "filial",
        "departamento",
        "centro_custo",
        "cargo",
        "data_admissao",
        "data_desligamento",
        "pcd",
        "aprendiz",
        "estagiario",
        "lgbtqia",
        "tipo_rescisao",
    },
    "mensal": {
        "competencia",
        "matricula",
        "filial",
        "departamento",
        "cargo",
        "salario_mensal",
        "decimo_terceiro_provisionado",
        "beneficios_total",
        "custo_rescisao",
        "media_desempenho",
        "nota_assiduidade",
        "nota_criatividade",
        "nota_pontualidade",
        "nota_produtividade",
        "nota_resolucao_problemas",
        "nota_trabalho_equipe",
    },
    "treinamentos": {
        "id_treinamento",
        "data_treinamento",
        "matricula",
        "filial",
        "departamento",
        "nome_treinamento",
        "tipo_treinamento",
        "carga_horaria",
        "investimento_treinamento",
    },
    "recrutamento": {
        "id_vaga",
        "data_abertura",
        "filial",
        "departamento",
        "cargo",
        "quantidade_vagas",
        "inscricoes",
        "candidatos_banco",
        "salario_ofertado",
        "dias_fechamento",
    },
}


# ---------------------------------------------------------------------------
# 3. Leitura e validação das bases
# ---------------------------------------------------------------------------

def validar_campos(
    dataframe: pd.DataFrame,
    nome_base: str,
    campos_obrigatorios: set[str],
) -> dict[str, Any]:
    """Confere o contrato de dados e devolve evidência para auditoria.

    ``set`` elimina repetição e permite calcular a diferença entre o conjunto
    esperado e as colunas recebidas. Se faltar campo crítico, a execução para
    antes de publicar um indicador incorreto.
    """

    recebidos = set(dataframe.columns)
    faltantes = sorted(campos_obrigatorios - recebidos)
    if faltantes:
        raise ValueError(
            f"A base '{nome_base}' não atende ao contrato. "
            f"Campos ausentes: {', '.join(faltantes)}"
        )
    return {
        "base": nome_base,
        "status": "OK",
        "campos_obrigatorios": len(campos_obrigatorios),
        "campos_recebidos": len(recebidos),
        "campos_ausentes": 0,
    }


def incluir_calendario(dataframe: pd.DataFrame, coluna_data: str) -> pd.DataFrame:
    """Cria ano, mês, nome do mês e competência mensal em uma cópia."""

    copia = dataframe.copy()
    copia[coluna_data] = pd.to_datetime(copia[coluna_data], errors="coerce")
    copia["ano"] = copia[coluna_data].dt.year.astype("Int64")
    copia["mes"] = copia[coluna_data].dt.month.astype("Int64")
    copia["mes_nome"] = pd.Categorical(
        copia["mes"].map(MESES), categories=ORDEM_MESES, ordered=True
    )
    # MonthEnd(0) leva qualquer data para o último dia do próprio mês.
    copia["competencia"] = copia[coluna_data] + pd.offsets.MonthEnd(0)
    return copia


def carregar_bases(pasta_dados: str | Path) -> tuple[BasesRH, pd.DataFrame]:
    """Lê os CSVs, converte datas e executa os controles de qualidade."""

    pasta = Path(pasta_dados)
    arquivos = {
        "cadastros": pasta / "base_rh_colaboradores.csv",
        "mensal": pasta / "base_rh_mensal_2024_2026.csv",
        "treinamentos": pasta / "base_rh_treinamentos_2024_2026.csv",
        "recrutamento": pasta / "base_rh_recrutamento_2024_2026.csv",
        "dicionario": pasta / "dicionario_dados.csv",
    }

    ausentes = [str(caminho) for caminho in arquivos.values() if not caminho.exists()]
    if ausentes:
        raise FileNotFoundError("Arquivos obrigatórios ausentes:\n" + "\n".join(ausentes))

    # UTF-8-SIG aceita os arquivos com acentos e o marcador gerado pelo Excel.
    cadastros = pd.read_csv(
        arquivos["cadastros"],
        sep=";",
        encoding="utf-8-sig",
        parse_dates=["data_admissao", "data_desligamento", "data_nascimento"],
    )
    mensal = pd.read_csv(
        arquivos["mensal"],
        sep=";",
        encoding="utf-8-sig",
        parse_dates=["competencia"],
    )
    treinamentos = pd.read_csv(
        arquivos["treinamentos"],
        sep=";",
        encoding="utf-8-sig",
        parse_dates=["competencia", "data_treinamento"],
    )
    recrutamento = pd.read_csv(
        arquivos["recrutamento"],
        sep=";",
        encoding="utf-8-sig",
        parse_dates=["data_abertura", "data_fechamento"],
    )
    dicionario = pd.read_csv(arquivos["dicionario"], sep=";", encoding="utf-8-sig")

    # Normaliza a dimensão calendário em todas as bases de eventos.
    mensal = incluir_calendario(mensal, "competencia")
    treinamentos = incluir_calendario(treinamentos, "data_treinamento")
    recrutamento = incluir_calendario(recrutamento, "data_abertura")

    bases = BasesRH(cadastros, mensal, treinamentos, recrutamento, dicionario)
    mapa = {
        "cadastros": bases.cadastros,
        "mensal": bases.mensal,
        "treinamentos": bases.treinamentos,
        "recrutamento": bases.recrutamento,
    }
    diagnostico = pd.DataFrame(
        [
            validar_campos(mapa[nome], nome, campos)
            for nome, campos in CONTRATO_BASES.items()
        ]
    )

    # Controles críticos de período, unicidade e disponibilidade.
    anos = set(bases.mensal["ano"].dropna().astype(int).unique())
    if anos != {2024, 2025, 2026}:
        raise ValueError(f"Período inesperado na base mensal: {sorted(anos)}")
    if bases.mensal.duplicated(["competencia", "matricula"]).any():
        raise ValueError("Há matrícula duplicada na mesma competência mensal.")
    if bases.mensal.empty:
        raise ValueError("A base mensal está vazia.")

    return bases, diagnostico


# ---------------------------------------------------------------------------
# 4. Filtros reutilizáveis e fórmulas de RH
# ---------------------------------------------------------------------------

def filtrar_periodo(
    dataframe: pd.DataFrame,
    coluna_data: str,
    ano: str,
    mes: int | None,
) -> pd.DataFrame:
    """Filtra ano e mês; ``All`` e ``None`` significam não restringir."""

    filtrado = dataframe.copy()
    datas = pd.to_datetime(filtrado[coluna_data], errors="coerce")
    mascara = pd.Series(True, index=filtrado.index)
    if ano != "All":
        mascara &= datas.dt.year.eq(int(ano))
    if mes is not None:
        mascara &= datas.dt.month.eq(int(mes))
    return filtrado.loc[mascara].copy()


def filtrar_dimensoes(
    dataframe: pd.DataFrame,
    filtros: FiltrosDashboard,
) -> pd.DataFrame:
    """Aplica Filial e Departamento quando essas colunas estão disponíveis."""

    filtrado = dataframe.copy()
    if filtros.filial != "Todas" and "filial" in filtrado.columns:
        filtrado = filtrado.loc[filtrado["filial"].eq(filtros.filial)]
    if filtros.departamento != "Todos" and "departamento" in filtrado.columns:
        filtrado = filtrado.loc[
            filtrado["departamento"].eq(filtros.departamento)
        ]
    return filtrado


def obter_snapshot(mensal_filtrado: pd.DataFrame) -> pd.DataFrame:
    """Devolve a última competência do filtro para não somar estoque."""

    if mensal_filtrado.empty:
        return mensal_filtrado.copy()
    ultima_competencia = mensal_filtrado["competencia"].max()
    return mensal_filtrado.loc[
        mensal_filtrado["competencia"].eq(ultima_competencia)
    ].copy()


def preparar_contexto(bases: BasesRH, filtros: FiltrosDashboard) -> dict[str, pd.DataFrame]:
    """Monta todas as fatias de dados usadas pelas sete páginas."""

    mensal = filtrar_periodo(bases.mensal, "competencia", filtros.ano, filtros.mes)
    treinamentos = filtrar_periodo(
        bases.treinamentos, "data_treinamento", filtros.ano, filtros.mes
    )
    recrutamento = filtrar_periodo(
        bases.recrutamento, "data_abertura", filtros.ano, filtros.mes
    )
    admissoes = filtrar_periodo(
        bases.cadastros, "data_admissao", filtros.ano, filtros.mes
    )
    desligamentos = filtrar_periodo(
        bases.cadastros, "data_desligamento", filtros.ano, filtros.mes
    )

    mensal = filtrar_dimensoes(mensal, filtros)
    treinamentos = filtrar_dimensoes(treinamentos, filtros)
    recrutamento = filtrar_dimensoes(recrutamento, filtros)
    admissoes = filtrar_dimensoes(admissoes, filtros)
    desligamentos = filtrar_dimensoes(desligamentos, filtros)

    return {
        "mensal": mensal,
        "snapshot": obter_snapshot(mensal),
        "treinamentos": treinamentos,
        "recrutamento": recrutamento,
        "admissoes": admissoes,
        "desligamentos": desligamentos,
    }


def calcular_headcount_medio(mensal_filtrado: pd.DataFrame) -> float:
    """Calcula a média dos headcounts, um valor por competência mensal."""

    if mensal_filtrado.empty:
        return 0.0
    headcount_por_mes = mensal_filtrado.groupby("competencia")["matricula"].nunique()
    return float(headcount_por_mes.mean())


def calcular_turnover(admissoes: int, desligamentos: int, headcount_medio: float) -> float:
    """Aplica ``((admissões + desligamentos) / 2) / HC médio * 100``."""

    if headcount_medio == 0:
        return 0.0
    movimento_medio = (admissoes + desligamentos) / 2
    return float(movimento_medio / headcount_medio * 100)


def top_contagem(dataframe: pd.DataFrame, coluna: str, n: int = 10) -> pd.DataFrame:
    """Conta categorias, limita as maiores e devolve uma tabela limpa."""

    if dataframe.empty or coluna not in dataframe.columns:
        return pd.DataFrame(columns=[coluna, "quantidade"])
    return (
        dataframe[coluna]
        .fillna("Não informado")
        .value_counts(dropna=False)
        .head(n)
        .rename_axis(coluna)
        .reset_index(name="quantidade")
    )


def periodo_legivel(filtros: FiltrosDashboard) -> str:
    """Traduz os valores internos do filtro para o subtítulo do painel."""

    ano = "2024–2026" if filtros.ano == "All" else filtros.ano
    mes = "Todos os meses" if filtros.mes is None else MESES[filtros.mes]
    return f"{mes} | {ano} | {filtros.filial} | {filtros.departamento}"


def formatar_inteiro(valor: float | int) -> str:
    """Exibe milhar no padrão brasileiro sem casas decimais."""

    return f"{int(round(float(valor))):,.0f}".replace(",", ".")


def formatar_real(valor: float | int) -> str:
    """Exibe moeda brasileira com milhar e duas casas decimais."""

    numero = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {numero}"


def rotulo_tempo(dataframe: pd.DataFrame, ano: str) -> pd.Series:
    """Usa JAN–DEZ em um ano e JAN/AAAA quando ``All`` está ativo."""

    competencias = pd.to_datetime(dataframe["competencia"], errors="coerce")
    if ano == "All":
        return competencias.map(lambda data: f"{MESES[data.month]}/{data.year}")
    # Alguns agrupamentos preservam somente ``competencia``. Derivar o mês
    # dessa data evita depender de uma coluna auxiliar que pode ter sido agregada.
    return competencias.dt.month.map(MESES)


# ---------------------------------------------------------------------------
# 5. Fábrica de gráficos Plotly com o padrão visual do dashboard
# ---------------------------------------------------------------------------

def finalizar_figura(
    figura: go.Figure,
    titulo: str,
    paleta: dict[str, str],
    *,
    altura: int = 360,
    mostrar_legenda: bool = False,
) -> go.Figure:
    """Centraliza título, posiciona rótulos externos e aplica o tema."""

    for serie in figura.data:
        if serie.type == "bar":
            valores = serie.x if serie.orientation == "h" else serie.y
            serie.update(text=valores, textposition="outside", cliponaxis=False)
        elif serie.type == "scatter":
            modo = serie.mode or "lines"
            if "text" not in modo:
                modo += "+text"
            serie.update(mode=modo, text=serie.y, textposition="top center")
        elif serie.type == "pie":
            serie.update(textposition="outside", textinfo="label+percent", automargin=True)

    figura.update_layout(
        title={
            "text": titulo,
            "x": 0.5,
            "xanchor": "center",
            "y": 0.97,
            "yanchor": "top",
            "font": {"size": 18, "color": paleta["texto"]},
        },
        height=altura,
        autosize=True,
        paper_bgcolor=paleta["painel"],
        plot_bgcolor=paleta["painel"],
        font={"color": paleta["texto"], "family": "Arial"},
        margin={"l": 75, "r": 70, "t": 75, "b": 70},
        showlegend=mostrar_legenda,
        legend={
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": -0.18,
            "yanchor": "top",
            "title_text": "",
        },
        hoverlabel={"bgcolor": paleta["painel_2"], "font_color": paleta["texto"]},
        uniformtext={"minsize": 9, "mode": "show"},
    )
    figura.update_xaxes(gridcolor=paleta["grade"], zeroline=False, automargin=True)
    figura.update_yaxes(gridcolor=paleta["grade"], zeroline=False, automargin=True)
    return figura


def grafico_barras(
    dataframe: pd.DataFrame,
    categoria: str,
    valor: str,
    titulo: str,
    paleta: dict[str, str],
    *,
    cor: str = "primaria",
    horizontal: bool = False,
    moeda: bool = False,
    casas: int = 0,
) -> go.Figure:
    """Cria barras verticais ou horizontais com rótulos externos."""

    dados = dataframe.copy()
    if horizontal:
        dados = dados.sort_values(valor, ascending=True)
        figura = go.Figure(
            go.Bar(
                x=dados[valor],
                y=dados[categoria].astype(str),
                orientation="h",
                marker_color=paleta[cor],
                hovertemplate=f"%{{y}}<br>{valor}: %{{x:,.{casas}f}}<extra></extra>",
            )
        )
    else:
        figura = go.Figure(
            go.Bar(
                x=dados[categoria].astype(str),
                y=dados[valor],
                marker_color=paleta[cor],
                hovertemplate=f"%{{x}}<br>{valor}: %{{y:,.{casas}f}}<extra></extra>",
            )
        )

    # Valores financeiros mensais podem chegar a milhões. Nos rótulos externos,
    # a notação SI evita sobreposição: 2.2M ocupa menos espaço que 2,200,000.00.
    # O hover continua apresentando o número completo para uma conferência precisa.
    if moeda:
        figura.update_traces(texttemplate="R$ %{text:.2s}")
    else:
        figura.update_traces(texttemplate=f"%{{text:,.{casas}f}}")
    return finalizar_figura(figura, titulo, paleta)


def grafico_rosca(
    dataframe: pd.DataFrame,
    categoria: str,
    valor: str,
    titulo: str,
    paleta: dict[str, str],
) -> go.Figure:
    """Cria uma rosca para composição percentual com poucas categorias."""

    figura = go.Figure(
        go.Pie(
            labels=dataframe[categoria].astype(str),
            values=dataframe[valor],
            hole=0.55,
            marker={
                "colors": [
                    paleta["primaria"],
                    paleta["secundaria"],
                    paleta["destaque"],
                    paleta["alerta"],
                ]
            },
        )
    )
    return finalizar_figura(figura, titulo, paleta)


def grafico_duas_series(
    dataframe: pd.DataFrame,
    categoria: str,
    valor_1: str,
    valor_2: str,
    titulo: str,
    paleta: dict[str, str],
    nomes: tuple[str, str],
) -> go.Figure:
    """Compara duas medidas no mesmo eixo, como vagas e inscrições."""

    figura = go.Figure()
    figura.add_bar(
        x=dataframe[categoria].astype(str),
        y=dataframe[valor_1],
        name=nomes[0],
        marker_color=paleta["primaria"],
    )
    figura.add_bar(
        x=dataframe[categoria].astype(str),
        y=dataframe[valor_2],
        name=nomes[1],
        marker_color=paleta["secundaria"],
    )
    figura.update_layout(barmode="group")
    return finalizar_figura(figura, titulo, paleta, mostrar_legenda=True)


def grafico_rotatividade(
    evolucao: pd.DataFrame,
    paleta: dict[str, str],
) -> go.Figure:
    """Combina admissões, desligamentos e headcount com eixo secundário."""

    figura = go.Figure()
    figura.add_bar(
        x=evolucao["periodo"],
        y=evolucao["admissoes"],
        name="Admissões",
        marker_color=paleta["secundaria"],
    )
    figura.add_bar(
        x=evolucao["periodo"],
        y=evolucao["desligamentos"],
        name="Desligamentos",
        marker_color=paleta["alerta"],
    )
    figura.add_scatter(
        x=evolucao["periodo"],
        y=evolucao["headcount"],
        name="Headcount",
        mode="lines+markers",
        line={"color": paleta["primaria"], "width": 3},
        yaxis="y2",
    )
    figura.update_layout(
        barmode="group",
        yaxis2={"overlaying": "y", "side": "right", "showgrid": False},
    )
    return finalizar_figura(
        figura,
        "Admissões, desligamentos e headcount por mês",
        paleta,
        altura=420,
        mostrar_legenda=True,
    )


def item_grafico(figura: go.Figure, alt: str) -> dict[str, Any]:
    """Padroniza a estrutura consumida pelo ``streamlit_app.py``."""

    return {"figura": figura, "alt": alt}


def item_kpi(rotulo: str, valor: str, nota: str, icone: str) -> dict[str, str]:
    """Padroniza um cartão KPI sem acoplar a regra ao Streamlit."""

    return {"rotulo": rotulo, "valor": valor, "nota": nota, "icone": icone}


# ---------------------------------------------------------------------------
# 6. Preparação das sete páginas executivas
# ---------------------------------------------------------------------------

def construir_overview(
    contexto: dict[str, pd.DataFrame],
    bases: BasesRH,
    filtros: FiltrosDashboard,
    paleta: dict[str, str],
) -> PaginaDashboard:
    """Monta o retrato da população na última competência disponível."""

    snapshot = contexto["snapshot"]
    if snapshot.empty:
        return PaginaDashboard("Overview", periodo_legivel(filtros), [], [])

    data_referencia = snapshot["competencia"].max()
    base = snapshot.merge(
        bases.cadastros[["matricula", "data_admissao"]],
        on="matricula",
        how="left",
    )
    base["tempo_empresa_anos"] = (
        data_referencia - base["data_admissao"]
    ).dt.days / 365.25

    genero = base["genero"].value_counts()
    kpis = [
        item_kpi(
            "Colaboradores",
            formatar_inteiro(base["matricula"].nunique()),
            f"Snapshot {data_referencia:%d/%m/%Y}",
            "badge",
        ),
        item_kpi(
            "Mulheres",
            formatar_inteiro(genero.get("Feminino", 0)),
            "No snapshot",
            "female",
        ),
        item_kpi(
            "Homens",
            formatar_inteiro(genero.get("Masculino", 0)),
            "No snapshot",
            "male",
        ),
        item_kpi(
            "Idade média",
            f"{base['idade'].mean():.1f} anos",
            "Média aritmética",
            "cake",
        ),
        item_kpi(
            "Tempo médio",
            f"{base['tempo_empresa_anos'].mean():.1f} anos",
            "Desde a admissão",
            "schedule",
        ),
    ]

    por_departamento = top_contagem(base, "departamento", 10)
    por_cargo = top_contagem(base, "cargo", 10)
    por_formacao = top_contagem(base, "formacao_academica", 10)
    por_faixa = top_contagem(base, "faixa_etaria", 10)
    por_filial = top_contagem(base, "filial", 10)

    # ``pd.cut`` converte uma medida contínua em faixas de leitura gerencial.
    faixas_tempo = pd.cut(
        base["tempo_empresa_anos"],
        bins=[-1, 1, 2, 3, 5, 100],
        labels=["Até 1", "1–2", "2–3", "3–5", "5+"],
    )
    por_tempo = (
        faixas_tempo.value_counts(sort=False)
        .rename_axis("faixa")
        .reset_index(name="quantidade")
    )

    graficos = [
        item_grafico(
            grafico_barras(
                por_departamento,
                "departamento",
                "quantidade",
                "Colaboradores por departamento",
                paleta,
                horizontal=True,
            ),
            "Headcount por departamento no último snapshot.",
        ),
        item_grafico(
            grafico_barras(
                por_cargo,
                "cargo",
                "quantidade",
                "Colaboradores por cargo",
                paleta,
                horizontal=True,
                cor="secundaria",
            ),
            "Headcount por cargo no último snapshot.",
        ),
        item_grafico(
            grafico_barras(
                por_formacao,
                "formacao_academica",
                "quantidade",
                "Formação acadêmica",
                paleta,
                horizontal=True,
                cor="destaque",
            ),
            "Distribuição do headcount por formação acadêmica.",
        ),
        item_grafico(
            grafico_barras(
                por_faixa,
                "faixa_etaria",
                "quantidade",
                "Faixa etária",
                paleta,
                horizontal=True,
            ),
            "Distribuição do headcount por faixa etária.",
        ),
        item_grafico(
            grafico_barras(
                por_tempo,
                "faixa",
                "quantidade",
                "Tempo de empresa",
                paleta,
                cor="secundaria",
            ),
            "Colaboradores por faixa de tempo de empresa.",
        ),
        item_grafico(
            grafico_barras(
                por_filial,
                "filial",
                "quantidade",
                "Colaboradores por filial",
                paleta,
                cor="destaque",
            ),
            "Headcount por filial no último snapshot.",
        ),
    ]
    return PaginaDashboard(
        "Overview",
        f"Retrato da população em {data_referencia:%d/%m/%Y} | {periodo_legivel(filtros)}",
        kpis,
        graficos,
    )


def construir_recrutamento(
    contexto: dict[str, pd.DataFrame],
    filtros: FiltrosDashboard,
    paleta: dict[str, str],
) -> PaginaDashboard:
    """Monta as análises de vagas, inscrições, salário e fechamento."""

    base = contexto["recrutamento"]
    if base.empty:
        return PaginaDashboard("Recrutamento e seleção", periodo_legivel(filtros), [], [])

    kpis = [
        item_kpi(
            "Média salarial",
            formatar_real(base["salario_ofertado"].mean()),
            "Vagas filtradas",
            "payments",
        ),
        item_kpi(
            "Total de vagas",
            formatar_inteiro(base["quantidade_vagas"].sum()),
            "Soma das quantidades",
            "work",
        ),
        item_kpi(
            "Média de fechamento",
            f"{base['dias_fechamento'].mean():.1f} dias",
            "Tempo médio",
            "event_available",
        ),
        item_kpi(
            "Banco de talentos",
            formatar_inteiro(base["candidatos_banco"].sum()),
            "Candidatos aproveitáveis",
            "group",
        ),
    ]

    salario = (
        base.groupby("departamento", as_index=False)["salario_ofertado"]
        .mean()
        .nlargest(10, "salario_ofertado")
    )
    vagas_departamento = (
        base.groupby("departamento", as_index=False)["quantidade_vagas"]
        .sum()
        .nlargest(10, "quantidade_vagas")
    )
    vagas_cargo = (
        base.groupby("cargo", as_index=False)["quantidade_vagas"]
        .sum()
        .nlargest(15, "quantidade_vagas")
        .rename(columns={"cargo": "Cargo", "quantidade_vagas": "Vagas"})
        .reset_index(drop=True)
    )
    fechamento = (
        base.groupby("competencia", as_index=False)["dias_fechamento"].mean()
    )
    fechamento["periodo"] = rotulo_tempo(fechamento, filtros.ano)
    mensal = base.groupby("competencia", as_index=False).agg(
        vagas=("quantidade_vagas", "sum"),
        inscricoes=("inscricoes", "sum"),
    )
    mensal["periodo"] = rotulo_tempo(mensal, filtros.ano)

    graficos = [
        item_grafico(
            grafico_barras(
                salario,
                "departamento",
                "salario_ofertado",
                "Média salarial por departamento",
                paleta,
                horizontal=True,
                moeda=True,
                casas=2,
            ),
            "Média do salário ofertado por departamento.",
        ),
        item_grafico(
            grafico_barras(
                fechamento,
                "periodo",
                "dias_fechamento",
                "Tempo de fechamento por mês",
                paleta,
                cor="secundaria",
                casas=1,
            ),
            "Tempo médio mensal para fechamento das vagas.",
        ),
        item_grafico(
            grafico_barras(
                vagas_departamento,
                "departamento",
                "quantidade_vagas",
                "Vagas por departamento",
                paleta,
                horizontal=True,
                cor="destaque",
            ),
            "Quantidade de vagas por departamento.",
        ),
        item_grafico(
            grafico_duas_series(
                mensal,
                "periodo",
                "vagas",
                "inscricoes",
                "Inscrições x vagas",
                paleta,
                ("Vagas", "Inscrições"),
            ),
            "Comparação mensal entre vagas e inscrições.",
        ),
    ]
    return PaginaDashboard(
        "Recrutamento e seleção",
        periodo_legivel(filtros),
        kpis,
        graficos,
        vagas_cargo,
        "Detalhamento complementar — vagas por cargo",
    )


def construir_treinamentos(
    contexto: dict[str, pd.DataFrame],
    filtros: FiltrosDashboard,
    paleta: dict[str, str],
) -> PaginaDashboard:
    """Monta investimento, volume, carga horária, setores e temas."""

    base = contexto["treinamentos"]
    if base.empty:
        return PaginaDashboard("Treinamentos", periodo_legivel(filtros), [], [])

    kpis = [
        item_kpi(
            "Investimento",
            formatar_real(base["investimento_treinamento"].sum()),
            "Período filtrado",
            "savings",
        ),
        item_kpi(
            "Treinamentos",
            formatar_inteiro(base["id_treinamento"].nunique()),
            "Registros únicos",
            "school",
        ),
        item_kpi(
            "Horas",
            formatar_inteiro(base["carga_horaria"].sum()),
            "Carga horária total",
            "alarm",
        ),
        item_kpi(
            "Temas",
            formatar_inteiro(base["nome_treinamento"].nunique()),
            "Assuntos diferentes",
            "category",
        ),
    ]

    mensal = base.groupby("competencia", as_index=False).agg(
        investimento=("investimento_treinamento", "sum"),
        treinamentos=("id_treinamento", "nunique"),
    )
    mensal["periodo"] = rotulo_tempo(mensal, filtros.ano)
    por_departamento = (
        base.groupby("departamento", as_index=False)
        .agg(
            treinamentos=("id_treinamento", "nunique"),
            horas=("carga_horaria", "sum"),
        )
        .nlargest(10, "treinamentos")
    )
    temas = top_contagem(base, "nome_treinamento", 10)
    tipos = top_contagem(base, "tipo_treinamento", 10)

    graficos = [
        item_grafico(
            grafico_barras(
                mensal,
                "periodo",
                "investimento",
                "Investimento por mês",
                paleta,
                moeda=True,
                casas=2,
            ),
            "Investimento mensal em treinamento.",
        ),
        item_grafico(
            grafico_rosca(
                tipos,
                "tipo_treinamento",
                "quantidade",
                "Tipos de treinamento",
                paleta,
            ),
            "Participação dos tipos de treinamento.",
        ),
        item_grafico(
            grafico_barras(
                por_departamento,
                "departamento",
                "treinamentos",
                "Treinamentos por departamento",
                paleta,
                horizontal=True,
                cor="secundaria",
            ),
            "Quantidade de treinamentos por departamento.",
        ),
        item_grafico(
            grafico_barras(
                temas,
                "nome_treinamento",
                "quantidade",
                "Temas realizados",
                paleta,
                horizontal=True,
                cor="destaque",
            ),
            "Temas de treinamento mais realizados.",
        ),
    ]
    return PaginaDashboard("Treinamentos", periodo_legivel(filtros), kpis, graficos)


def construir_rotatividade(
    contexto: dict[str, pd.DataFrame],
    filtros: FiltrosDashboard,
    paleta: dict[str, str],
) -> PaginaDashboard:
    """Monta headcount, movimentos, turnover e causas de desligamento."""

    mensal = contexto["mensal"]
    if mensal.empty:
        return PaginaDashboard("Rotatividade", periodo_legivel(filtros), [], [])

    admissoes = contexto["admissoes"]
    desligamentos = contexto["desligamentos"]
    snapshot = contexto["snapshot"]
    headcount = snapshot["matricula"].nunique()
    headcount_medio = calcular_headcount_medio(mensal)
    turnover = calcular_turnover(len(admissoes), len(desligamentos), headcount_medio)
    kpis = [
        item_kpi("Headcount", formatar_inteiro(headcount), "Último snapshot", "badge"),
        item_kpi(
            "Admissões",
            formatar_inteiro(len(admissoes)),
            "Fluxo do período",
            "person_add",
        ),
        item_kpi(
            "Desligamentos",
            formatar_inteiro(len(desligamentos)),
            "Fluxo do período",
            "person_remove",
        ),
        item_kpi(
            "Turnover",
            f"{turnover:.2f}%".replace(".", ","),
            "Movimento médio ÷ HC médio",
            "sync_alt",
        ),
    ]

    headcount_mes = (
        mensal.groupby("competencia", as_index=False)["matricula"]
        .nunique()
        .rename(columns={"matricula": "headcount"})
    )
    admissoes_mes = (
        admissoes.assign(
            competencia=admissoes["data_admissao"] + pd.offsets.MonthEnd(0)
        )
        .groupby("competencia")
        .size()
        .rename("admissoes")
    )
    desligamentos_mes = (
        desligamentos.assign(
            competencia=desligamentos["data_desligamento"] + pd.offsets.MonthEnd(0)
        )
        .groupby("competencia")
        .size()
        .rename("desligamentos")
    )
    evolucao = (
        headcount_mes.merge(admissoes_mes, on="competencia", how="left")
        .merge(desligamentos_mes, on="competencia", how="left")
        .fillna({"admissoes": 0, "desligamentos": 0})
    )
    evolucao["periodo"] = rotulo_tempo(evolucao, filtros.ano)

    por_tipo = top_contagem(desligamentos, "tipo_rescisao", 10)
    por_cargo = top_contagem(admissoes, "cargo", 10)
    por_departamento = top_contagem(desligamentos, "departamento", 10)

    graficos = [
        item_grafico(
            grafico_rotatividade(evolucao, paleta),
            "Admissões, desligamentos e headcount ao longo do período.",
        ),
        item_grafico(
            grafico_barras(
                por_tipo,
                "tipo_rescisao",
                "quantidade",
                "Tipos de desligamento",
                paleta,
                horizontal=True,
                cor="destaque",
            ),
            "Desligamentos por tipo de rescisão.",
        ),
        item_grafico(
            grafico_barras(
                por_cargo,
                "cargo",
                "quantidade",
                "Contratações por cargo",
                paleta,
                horizontal=True,
                cor="secundaria",
            ),
            "Admissões por cargo.",
        ),
        item_grafico(
            grafico_barras(
                por_departamento,
                "departamento",
                "quantidade",
                "Desligamentos por departamento",
                paleta,
                horizontal=True,
                cor="alerta",
            ),
            "Desligamentos por departamento.",
        ),
    ]
    return PaginaDashboard("Rotatividade", periodo_legivel(filtros), kpis, graficos)


def construir_desempenho(
    contexto: dict[str, pd.DataFrame],
    filtros: FiltrosDashboard,
    paleta: dict[str, str],
) -> PaginaDashboard:
    """Monta médias de desempenho; notas de nível nunca são somadas."""

    base = contexto["mensal"]
    if base.empty:
        return PaginaDashboard("Avaliação de desempenho", periodo_legivel(filtros), [], [])

    kpis = [
        item_kpi(
            "Média geral",
            f"{base['media_desempenho'].mean():.2f}".replace(".", ","),
            "Escala de 1 a 5",
            "monitoring",
        ),
        item_kpi(
            "Assiduidade",
            f"{base['nota_assiduidade'].mean():.2f}".replace(".", ","),
            "Média do período",
            "event_available",
        ),
        item_kpi(
            "Criatividade",
            f"{base['nota_criatividade'].mean():.2f}".replace(".", ","),
            "Média do período",
            "lightbulb",
        ),
        item_kpi(
            "Pontualidade",
            f"{base['nota_pontualidade'].mean():.2f}".replace(".", ","),
            "Média do período",
            "alarm_on",
        ),
        item_kpi(
            "Produtividade",
            f"{base['nota_produtividade'].mean():.2f}".replace(".", ","),
            "Média do período",
            "manufacturing",
        ),
    ]

    por_mes = base.groupby("competencia", as_index=False)["media_desempenho"].mean()
    por_mes["periodo"] = rotulo_tempo(por_mes, filtros.ano)
    por_departamento = (
        base.groupby("departamento", as_index=False)["media_desempenho"]
        .mean()
        .nlargest(10, "media_desempenho")
    )
    por_cargo = (
        base.groupby("cargo", as_index=False)["media_desempenho"]
        .mean()
        .nlargest(10, "media_desempenho")
    )
    metricas = [
        "nota_assiduidade",
        "nota_criatividade",
        "nota_pontualidade",
        "nota_produtividade",
        "nota_resolucao_problemas",
        "nota_trabalho_equipe",
    ]
    tabela = (
        base.groupby("departamento")[metricas]
        .mean()
        .round(2)
        .reset_index()
        .rename(
            columns={
                "departamento": "Departamento",
                "nota_assiduidade": "Assiduidade",
                "nota_criatividade": "Criatividade",
                "nota_pontualidade": "Pontualidade",
                "nota_produtividade": "Produtividade",
                "nota_resolucao_problemas": "Resolução de problemas",
                "nota_trabalho_equipe": "Trabalho em equipe",
            }
        )
    )

    graficos = [
        item_grafico(
            grafico_barras(
                por_mes,
                "periodo",
                "media_desempenho",
                "Média geral por mês",
                paleta,
                casas=2,
            ),
            "Média de desempenho por mês.",
        ),
        item_grafico(
            grafico_barras(
                por_departamento,
                "departamento",
                "media_desempenho",
                "Média geral por departamento",
                paleta,
                horizontal=True,
                cor="secundaria",
                casas=2,
            ),
            "Média de desempenho por departamento.",
        ),
        item_grafico(
            grafico_barras(
                por_cargo,
                "cargo",
                "media_desempenho",
                "Média geral por cargo",
                paleta,
                horizontal=True,
                cor="destaque",
                casas=2,
            ),
            "Média de desempenho por cargo.",
        ),
    ]
    return PaginaDashboard(
        "Avaliação de desempenho",
        periodo_legivel(filtros),
        kpis,
        graficos,
        tabela,
        "Tabela de competências",
    )


def construir_financeiro(
    contexto: dict[str, pd.DataFrame],
    filtros: FiltrosDashboard,
    paleta: dict[str, str],
) -> PaginaDashboard:
    """Monta salários, provisões, benefícios e custos de rescisão."""

    base = contexto["mensal"]
    if base.empty:
        return PaginaDashboard("Financeiro", periodo_legivel(filtros), [], [])

    kpis = [
        item_kpi(
            "Salários",
            formatar_real(base["salario_mensal"].sum()),
            "Soma do período",
            "payments",
        ),
        item_kpi(
            "Décimo terceiro",
            formatar_real(base["decimo_terceiro_provisionado"].sum()),
            "Provisão",
            "account_balance_wallet",
        ),
        item_kpi(
            "Benefícios",
            formatar_real(base["beneficios_total"].sum()),
            "Pacote total",
            "health_and_safety",
        ),
        item_kpi(
            "Rescisões",
            formatar_real(base["custo_rescisao"].sum()),
            "Custo do período",
            "receipt_long",
        ),
    ]

    mensal = base.groupby("competencia", as_index=False).agg(
        salarios=("salario_mensal", "sum"),
        rescisoes=("custo_rescisao", "sum"),
        decimo=("decimo_terceiro_provisionado", "sum"),
    )
    mensal["periodo"] = rotulo_tempo(mensal, filtros.ano)
    por_departamento = (
        base.groupby("departamento", as_index=False)
        .agg(salarios=("salario_mensal", "sum"))
        .nlargest(10, "salarios")
    )
    colunas_beneficios = [
        "beneficio_transporte",
        "beneficio_idiomas",
        "beneficio_graduacao",
        "beneficio_pos_graduacao",
        "beneficio_saude",
    ]
    beneficios = (
        base[colunas_beneficios]
        .sum()
        .rename_axis("beneficio")
        .reset_index(name="valor")
    )
    beneficios["beneficio"] = (
        beneficios["beneficio"]
        .str.replace("beneficio_", "", regex=False)
        .str.replace("_", " ", regex=False)
        .str.title()
    )

    graficos = [
        item_grafico(
            grafico_barras(
                mensal,
                "periodo",
                "salarios",
                "Salários por mês",
                paleta,
                moeda=True,
                casas=2,
            ),
            "Folha salarial por mês.",
        ),
        item_grafico(
            grafico_barras(
                por_departamento,
                "departamento",
                "salarios",
                "Salários por departamento",
                paleta,
                horizontal=True,
                cor="secundaria",
                moeda=True,
                casas=2,
            ),
            "Folha salarial acumulada por departamento.",
        ),
        item_grafico(
            grafico_barras(
                mensal,
                "periodo",
                "rescisoes",
                "Rescisão por mês",
                paleta,
                cor="alerta",
                moeda=True,
                casas=2,
            ),
            "Custo de rescisões por mês.",
        ),
        item_grafico(
            grafico_barras(
                beneficios,
                "beneficio",
                "valor",
                "Composição dos benefícios",
                paleta,
                horizontal=True,
                cor="destaque",
                moeda=True,
                casas=2,
            ),
            "Composição do valor dos benefícios.",
        ),
    ]
    return PaginaDashboard("Financeiro", periodo_legivel(filtros), kpis, graficos)


def construir_mapeamento(
    contexto: dict[str, pd.DataFrame],
    filtros: FiltrosDashboard,
    paleta: dict[str, str],
) -> PaginaDashboard:
    """Monta as visões populacionais, exibindo dados sensíveis agregados."""

    base = contexto["snapshot"]
    if base.empty:
        return PaginaDashboard("Mapeamento populacional", periodo_legivel(filtros), [], [])

    kpis = [
        item_kpi(
            "PCDs",
            formatar_inteiro(base["pcd"].eq("Sim").sum()),
            "Declaração cadastrada",
            "accessible",
        ),
        item_kpi(
            "Aprendizes",
            formatar_inteiro(base["aprendiz"].eq("Sim").sum()),
            "No snapshot",
            "school",
        ),
        item_kpi(
            "Estagiários",
            formatar_inteiro(base["estagiario"].eq("Sim").sum()),
            "No snapshot",
            "badge",
        ),
        item_kpi(
            "LGBTQIA+",
            formatar_inteiro(base["lgbtqia"].eq("Sim").sum()),
            "Dado sensível agregado",
            "diversity_3",
        ),
    ]

    especificacoes = [
        ("genero", "Gênero", "primaria"),
        ("faixa_etaria", "Faixa etária", "secundaria"),
        ("geracao", "Geração", "destaque"),
        ("formacao_academica", "Formação acadêmica", "primaria"),
        ("centro_custo", "Centro de custo", "secundaria"),
        ("pcd", "PCDs", "destaque"),
    ]
    graficos: list[dict[str, Any]] = []
    for campo, titulo, cor in especificacoes:
        tabela = top_contagem(base, campo, 12)
        graficos.append(
            item_grafico(
                grafico_barras(
                    tabela,
                    campo,
                    "quantidade",
                    titulo,
                    paleta,
                    horizontal=True,
                    cor=cor,
                ),
                f"Distribuição agregada por {titulo.lower()}.",
            )
        )

    return PaginaDashboard(
        "Mapeamento populacional",
        f"{periodo_legivel(filtros)} | Dados sensíveis somente de forma agregada",
        kpis,
        graficos,
    )


def construir_pagina(
    nome_pagina: str,
    contexto: dict[str, pd.DataFrame],
    bases: BasesRH,
    filtros: FiltrosDashboard,
    nome_paleta: str,
) -> PaginaDashboard:
    """Funciona como um roteador entre o botão do menu e a função da página."""

    if nome_paleta not in PALETAS:
        raise ValueError(f"Paleta desconhecida: {nome_paleta}")
    paleta = PALETAS[nome_paleta]
    funcoes = {
        "Overview": lambda: construir_overview(contexto, bases, filtros, paleta),
        "Recrutamento": lambda: construir_recrutamento(contexto, filtros, paleta),
        "Treinamentos": lambda: construir_treinamentos(contexto, filtros, paleta),
        "Rotatividade": lambda: construir_rotatividade(contexto, filtros, paleta),
        "Desempenho": lambda: construir_desempenho(contexto, filtros, paleta),
        "Financeiro": lambda: construir_financeiro(contexto, filtros, paleta),
        "Mapeamento": lambda: construir_mapeamento(contexto, filtros, paleta),
    }
    if nome_pagina not in funcoes:
        raise ValueError(f"Página desconhecida: {nome_pagina}")
    return funcoes[nome_pagina]()


# ---------------------------------------------------------------------------
# 7. Exportação do relatório filtrado para Excel
# ---------------------------------------------------------------------------

def resumo_executivo(
    contexto: dict[str, pd.DataFrame],
    filtros: FiltrosDashboard,
) -> pd.DataFrame:
    """Calcula os principais números que acompanham o arquivo exportado."""

    mensal = contexto["mensal"]
    snapshot = contexto["snapshot"]
    admissoes = len(contexto["admissoes"])
    desligamentos = len(contexto["desligamentos"])
    headcount_medio = calcular_headcount_medio(mensal)
    turnover = calcular_turnover(admissoes, desligamentos, headcount_medio)
    linhas = [
        ("Período", periodo_legivel(filtros)),
        ("Headcount", snapshot["matricula"].nunique() if not snapshot.empty else 0),
        ("Headcount médio", round(headcount_medio, 2)),
        ("Admissões", admissoes),
        ("Desligamentos", desligamentos),
        ("Turnover (%)", round(turnover, 2)),
        ("Investimento em treinamento", round(contexto["treinamentos"]["investimento_treinamento"].sum(), 2)),
        ("Quantidade de vagas", int(contexto["recrutamento"]["quantidade_vagas"].sum())),
        ("Salários", round(mensal["salario_mensal"].sum(), 2)),
        ("Benefícios", round(mensal["beneficios_total"].sum(), 2)),
    ]
    return pd.DataFrame(linhas, columns=["Indicador", "Valor"])


def criar_relatorio_excel(
    contexto: dict[str, pd.DataFrame],
    filtros: FiltrosDashboard,
    diagnostico: pd.DataFrame,
) -> bytes:
    """Gera um arquivo Excel em memória com as tabelas já filtradas."""

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as escritor:
        resumo_executivo(contexto, filtros).to_excel(
            escritor, sheet_name="Resumo", index=False
        )
        diagnostico.to_excel(escritor, sheet_name="Qualidade", index=False)

        # Remove o nome do colaborador antes de enviar dados ao navegador.
        tabelas = {
            "Base_Mensal": contexto["mensal"],
            "Snapshot": contexto["snapshot"],
            "Admissoes": contexto["admissoes"].drop(
                columns=["colaborador"], errors="ignore"
            ),
            "Desligamentos": contexto["desligamentos"].drop(
                columns=["colaborador"], errors="ignore"
            ),
            "Treinamentos": contexto["treinamentos"],
            "Recrutamento": contexto["recrutamento"],
        }
        for aba, tabela in tabelas.items():
            exportavel = tabela.copy()
            # O Excel não conhece o dtype Categorical do pandas; texto é portátil.
            for coluna in exportavel.select_dtypes(include="category").columns:
                exportavel[coluna] = exportavel[coluna].astype(str)
            exportavel.to_excel(escritor, sheet_name=aba[:31], index=False)

        # Formatação simples: cabeçalho azul, filtro e primeira linha congelada.
        from openpyxl.styles import Font, PatternFill

        preenchimento = PatternFill("solid", fgColor="24527A")
        fonte = Font(color="FFFFFF", bold=True)
        for planilha in escritor.book.worksheets:
            planilha.freeze_panes = "A2"
            planilha.auto_filter.ref = planilha.dimensions
            for celula in planilha[1]:
                celula.fill = preenchimento
                celula.font = fonte
            for coluna in planilha.columns:
                largura = max(len(str(celula.value or "")) for celula in coluna)
                planilha.column_dimensions[coluna[0].column_letter].width = min(
                    max(largura + 2, 12), 40
                )

    buffer.seek(0)
    return buffer.getvalue()


def validar_dashboard(bases: BasesRH, diagnostico: pd.DataFrame) -> pd.DataFrame:
    """Executa os critérios de aceite que independem da interface visual."""

    testes = [
        (
            "Contrato de dados",
            diagnostico["status"].eq("OK").all(),
            "As quatro bases operacionais atendem aos campos obrigatórios.",
        ),
        (
            "Período 2024–2026",
            set(bases.mensal["ano"].dropna().astype(int).unique()) == {2024, 2025, 2026},
            "A base cobre os três anos definidos no projeto.",
        ),
        (
            "Chave mensal única",
            not bases.mensal.duplicated(["competencia", "matricula"]).any(),
            "Cada matrícula aparece no máximo uma vez por competência.",
        ),
        (
            "Sete páginas executivas",
            len(PAGINAS) == 7,
            "O menu contém todas as áreas definidas para a versão web.",
        ),
        (
            "Quatro temas",
            len(PALETAS) == 4,
            "A central oferece quatro opções de formatação.",
        ),
        (
            "Calendário legível",
            list(MESES.values()) == ORDEM_MESES,
            "Os meses mantêm a ordem JAN a DEZ.",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "teste": nome,
                "status": "OK" if bool(condicao) else "FALHOU",
                "detalhe": detalhe,
            }
            for nome, condicao, detalhe in testes
        ]
    )
