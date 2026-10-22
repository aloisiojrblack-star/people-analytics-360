r"""People Analytics 360: dashboard executivo desenvolvido em Streamlit.

Execute com:

    .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
"""

from __future__ import annotations

# ``escape`` protege os cartões HTML contra caracteres interpretados como tags.
from html import escape
from pathlib import Path

import streamlit as st

from src.dashboard_core import (
    MESES,
    PAGINAS,
    PALETAS,
    FiltrosDashboard,
    carregar_bases,
    construir_pagina,
    criar_relatorio_excel,
    preparar_contexto,
)


# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------

# ``set_page_config`` precisa aparecer antes dos outros elementos visuais.
# ``layout="wide"`` usa a largura da tela, apropriada para dashboards.
st.set_page_config(
    page_title="People Analytics 360",
    page_icon=":material/analytics:",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": (
            "People Analytics 360. Dados sintéticos de 2024 a 2026 "
            "para estudo e portfólio."
        )
    },
)

# Caminhos relativos tornam o projeto portátil: a pasta pode ser copiada para
# outra máquina sem trocar caminhos absolutos do Windows.
PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_PROJETO / "dados"


# ---------------------------------------------------------------------------
# Carga em cache e estado da sessão
# ---------------------------------------------------------------------------

@st.cache_data(
    ttl="1h",
    max_entries=4,
    show_spinner="Validando e carregando as bases de RH...",
)
def carregar_bases_web(pasta_dados: str):
    """Lê os CSVs uma vez e reutiliza o resultado nos próximos cliques.

    O cache evita reler milhares de linhas a cada mudança de filtro. O prazo de
    uma hora permite atualizar arquivos locais sem manter uma cópia
    antiga indefinidamente.
    """

    return carregar_bases(Path(pasta_dados))


# Em Streamlit, cada interação executa o script novamente do início ao fim.
# ``session_state`` preserva as escolhas do usuário durante a sessão do navegador.
st.session_state.setdefault("pagina", "Overview")
st.session_state.setdefault("ano", "2025")
st.session_state.setdefault("mes", "Total")
st.session_state.setdefault("filial", "Todas")
st.session_state.setdefault("departamento", "Todos")
st.session_state.setdefault("tema", "Azul executivo")

# A versão de portfólio trabalha com um ano por vez. Se uma URL antiga ainda
# possuir ``?ano=All``, normalizamos o estado antes de criar o controle.
ANOS_NAVEGACAO = ["2024", "2025", "2026"]
if st.session_state["ano"] not in ANOS_NAVEGACAO:
    st.session_state["ano"] = "2025"

# O valor armazenado continua sendo o nome completo da paleta. Apenas a
# apresentação foi reduzida a círculos para deixar a barra de filtros compacta.
CIRCULOS_TEMAS = {
    "Azul executivo": "🔵",
    "Claro corporativo": "⚪",
    "Verde RH": "🟢",
    "Roxo moderno": "🟣",
}

try:
    bases, diagnostico = carregar_bases_web(str(PASTA_DADOS))
except (FileNotFoundError, ValueError) as erro:
    # ``st.error`` explica o bloqueio; ``st.stop`` impede cálculos incompletos.
    st.error(str(erro), title="Não foi possível publicar o dashboard")
    st.stop()


# ---------------------------------------------------------------------------
# Estilos do menu fixo e da página selecionada
# ---------------------------------------------------------------------------

def css_aplicacao(paleta: dict[str, str]) -> str:
    """Cria estilos limitados aos componentes que possuem ``key``.

    O Streamlit transforma ``key="fixed_menu"`` em uma classe CSS chamada
    ``st-key-fixed_menu``. Assim evitamos depender de nomes internos frágeis.
    O CSS implementa o comportamento ``sticky`` e uma
    linha dourada sob a página selecionada, recursos que não são parâmetros
    nativos dos widgets.
    """

    return f"""
    <style>
      .st-key-fixed_menu {{
        position: sticky;
        top: 0.25rem;
        z-index: 999;
        background: {paleta['fundo']};
        border: 1px solid {paleta['grade']};
        border-radius: 12px;
        padding: 0.75rem 1rem 0.65rem;
        margin-bottom: 1rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);
      }}
      .st-key-fixed_menu p,
      .st-key-fixed_menu label,
      .st-key-fixed_menu h1,
      .st-key-fixed_menu h2 {{ color: {paleta['texto']} !important; }}

      /* Controles compactos: cada classe nasce da key pública do widget. */
      .st-key-ano {{
        display: flex;
        flex-direction: column;
        align-items: center;
      }}
      .st-key-ano button {{
        min-width: 4.4rem !important;
        height: 2.35rem !important;
        padding: 0.35rem 0.8rem !important;
      }}
      .st-key-tema button {{
        min-width: 2.8rem !important;
        height: 2.35rem !important;
        padding: 0.25rem 0.55rem !important;
        font-size: 1.05rem !important;
      }}
      .st-key-export_report {{
        display: flex;
        justify-content: flex-end;
        padding-top: 1.55rem;
      }}
      .st-key-export_report button {{
        min-width: 10rem !important;
        height: 2.35rem !important;
        padding: 0.35rem 0.9rem !important;
      }}

      /* Página ativa: linha dourada inspirada no painel SPC indicado. */
      .st-key-pagina button {{
        border-radius: 0 !important;
        border: 0 !important;
        border-bottom: 3px solid transparent !important;
        background: transparent !important;
        color: {paleta['texto_suave']} !important;
        font-weight: 650 !important;
      }}
      .st-key-pagina button[aria-checked="true"],
      .st-key-pagina button[data-selected="true"] {{
        border-bottom-color: {paleta['destaque']} !important;
        color: {paleta['texto']} !important;
      }}

      /* Ano ativo: botão preenchido, semelhante ao seletor 1Y/3Y/5Y. */
      .st-key-ano button[aria-checked="true"],
      .st-key-ano button[data-selected="true"],
      .st-key-tema button[aria-checked="true"],
      .st-key-tema button[data-selected="true"] {{
        background: {paleta['primaria']} !important;
        color: {paleta['fundo']} !important;
        border-color: {paleta['primaria']} !important;
      }}

      .st-key-dashboard_body {{
        background: {paleta['fundo']};
        border: 1px solid {paleta['grade']};
        border-radius: 14px;
        padding: 1rem;
      }}
      .rh-page-title {{
        color: {paleta['texto']};
        font-size: 1.75rem;
        font-weight: 750;
        margin: 0;
      }}
      .rh-page-subtitle {{
        color: {paleta['texto_suave']};
        margin: 0.15rem 0 1rem;
      }}
      .rh-kpi-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
        gap: 0.75rem;
        margin-bottom: 1rem;
      }}
      .rh-kpi {{
        background: linear-gradient(135deg, {paleta['painel']}, {paleta['painel_2']});
        border: 1px solid {paleta['grade']};
        border-radius: 12px;
        padding: 0.9rem;
        min-height: 118px;
      }}
      .rh-kpi-icon {{
        color: {paleta['destaque']};
        font-family: "Material Symbols Rounded";
        font-size: 1.35rem;
      }}
      .rh-kpi-label {{ color: {paleta['texto_suave']}; font-size: 0.82rem; }}
      .rh-kpi-value {{ color: {paleta['texto']}; font-size: 1.55rem; font-weight: 760; }}
      .rh-kpi-note {{ color: {paleta['texto_suave']}; font-size: 0.76rem; }}
      .rh-brand {{ color: {paleta['texto']}; font-size: 1.5rem; font-weight: 800; }}

      /* Tablet: reduz densidade e evita que o menu ocupe a tela durante a rolagem. */
      @media (max-width: 768px) {{
        .st-key-fixed_menu {{
          position: static;
          top: auto;
          padding: 0.75rem;
          box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22);
        }}
        .rh-brand {{ text-align: center; }}
        .st-key-ano {{ align-items: center; }}
        .st-key-ano [role="radiogroup"] {{
          width: min(100%, 22rem);
          margin-inline: auto;
        }}
        .st-key-ano [role="radiogroup"] button {{
          flex: 1 1 0;
        }}
        .st-key-export_report {{
          justify-content: center;
          padding-top: 0;
          width: 100% !important;
        }}
        .st-key-export_report button {{
          width: min(100%, 22rem) !important;
          min-width: 0 !important;
        }}
        .st-key-pagina [role="radiogroup"] {{
          display: grid !important;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 0.25rem;
          width: 100%;
        }}
        .st-key-pagina [role="radiogroup"] button {{
          justify-content: center;
          min-width: 0 !important;
          width: 100%;
        }}
        .st-key-tema {{ align-items: center; }}
        .st-key-tema [role="radiogroup"] {{
          justify-content: center;
          margin-inline: auto;
        }}
        .rh-kpi {{
          display: flex;
          min-height: 110px;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 0.8rem;
          text-align: center;
        }}
        .st-key-dashboard_body {{ padding: 0.75rem; }}
        .rh-page-title {{ font-size: 1.45rem; }}
        .rh-page-subtitle {{ font-size: 0.88rem; }}
        .rh-kpi-grid {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 0.6rem;
        }}
      }}

      /* Celular: cartões e ações ocupam uma coluna para facilitar a leitura. */
      @media (max-width: 480px) {{
        .rh-brand {{ font-size: 1.25rem; }}
        .st-key-pagina [role="radiogroup"] {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .rh-kpi-grid {{ grid-template-columns: 1fr; }}
        .rh-kpi-value {{ font-size: 1.35rem; }}
        .st-key-pagina button {{
          font-size: 0.82rem !important;
          padding-inline: 0.55rem !important;
        }}
      }}
    </style>
    """


# A paleta da execução atual é lida antes de desenhar a central. Quando o tema
# muda, o Streamlit executa novamente e aplica o novo conjunto de cores.
paleta_atual = PALETAS[st.session_state["tema"]]
st.html(css_aplicacao(paleta_atual))


# ---------------------------------------------------------------------------
# Central fixa de navegação
# ---------------------------------------------------------------------------

opcoes_filial = ["Todas"] + sorted(bases.mensal["filial"].dropna().unique().tolist())
opcoes_departamento = ["Todos"] + sorted(
    bases.mensal["departamento"].dropna().unique().tolist()
)
opcoes_mes = ["Total"] + list(MESES.values())

# O container com ``key`` recebe a classe usada no CSS ``position: sticky``.
with st.container(key="fixed_menu"):
    coluna_marca, coluna_ano, coluna_exportar = st.columns(
        [1.75, 0.78, 0.47],
        gap="medium",
        vertical_alignment="bottom",
        wrap=True,
    )

    with coluna_marca:
        st.html("<div class='rh-brand'>People Analytics 360</div>")

    with coluna_ano:
        # As opções são strings para sincronizar corretamente com a URL.
        ano_selecionado = st.segmented_control(
            "Ano",
            options=ANOS_NAVEGACAO,
            required=True,
            key="ano",
            bind="query-params",
            width="content",
            wrap=False,
        )

    with coluna_exportar:
        # O espaço é criado agora e preenchido depois que os filtros existirem.
        # O CSS alinha o botão com o ano no desktop e o centraliza no celular.
        slot_exportar = st.empty()

    # Em telas estreitas, os sete botões quebram em linhas para evitar rolagem.
    pagina_selecionada = st.segmented_control(
        "Página do dashboard",
        options=PAGINAS,
        required=True,
        key="pagina",
        bind="query-params",
        label_visibility="collapsed",
        width="stretch",
        wrap=True,
    )

    # O container horizontal mantém os filtros à esquerda. Cada widget recebe
    # uma largura proporcional ao texto que precisa exibir e pode quebrar para
    # outra linha em telas estreitas, sem comprimir os rótulos.
    with st.container(
        key="barra_filtros",
        horizontal=True,
        horizontal_alignment="left",
        vertical_alignment="bottom",
        gap="small",
        wrap=True,
    ):
        mes_selecionado = st.selectbox(
            "Mês", opcoes_mes, key="mes", width="stretch"
        )
        filial_selecionada = st.selectbox(
            "Filial", opcoes_filial, key="filial", width="stretch"
        )
        departamento_selecionado = st.selectbox(
            "Departamento",
            opcoes_departamento,
            key="departamento",
            width="stretch",
        )
        tema_selecionado = st.segmented_control(
            "Cores do painel",
            options=list(PALETAS),
            required=True,
            key="tema",
            format_func=lambda nome_tema: CIRCULOS_TEMAS[nome_tema],
            help=(
                "Azul, claro, verde e roxo. O círculo selecionado define "
                "as cores dos cartões e gráficos."
            ),
            width="content",
            wrap=True,
        )


# ---------------------------------------------------------------------------
# Conversão dos controles e preparação das bases filtradas
# ---------------------------------------------------------------------------

# O dicionário inverso transforma "JAN" em 1, "FEV" em 2 etc.
numero_por_mes = {nome: numero for numero, nome in MESES.items()}
mes_numero = None if mes_selecionado == "Total" else numero_por_mes[mes_selecionado]

filtros = FiltrosDashboard(
    ano=ano_selecionado,
    mes=mes_numero,
    filial=filial_selecionada,
    departamento=departamento_selecionado,
)
contexto = preparar_contexto(bases, filtros)
pagina = construir_pagina(
    pagina_selecionada,
    contexto,
    bases,
    filtros,
    tema_selecionado,
)


# ---------------------------------------------------------------------------
# Exportação Excel no canto superior direito
# ---------------------------------------------------------------------------

nome_periodo = ano_selecionado.lower()
if mes_selecionado != "Total":
    nome_periodo += f"_{mes_selecionado.lower()}"

# A função lambda adia a criação do Excel até o clique. Isso deixa a primeira
# abertura mais rápida e exporta exatamente o contexto filtrado desta execução.
slot_exportar.download_button(
    "Baixar relatório",
    data=lambda: criar_relatorio_excel(contexto, filtros, diagnostico),
    file_name=f"Relatorio_RH_{nome_periodo}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    icon=":material/download:",
    type="primary",
    on_click="ignore",
    width="stretch",
    key="export_report",
    help="Baixar somente indicadores agregados conforme os filtros atuais.",
)


# ---------------------------------------------------------------------------
# Componentes de apresentação
# ---------------------------------------------------------------------------

def html_kpis(itens: list[dict[str, str]]) -> str:
    """Transforma a lista de KPIs em cartões responsivos e temáticos."""

    cartoes = []
    for item in itens:
        cartoes.append(
            "<div class='rh-kpi'>"
            f"<span class='rh-kpi-icon'>{escape(item['icone'])}</span>"
            f"<div class='rh-kpi-label'>{escape(item['rotulo'])}</div>"
            f"<div class='rh-kpi-value'>{escape(item['valor'])}</div>"
            f"<div class='rh-kpi-note'>{escape(item['nota'])}</div>"
            "</div>"
        )
    return "<div class='rh-kpi-grid'>" + "".join(cartoes) + "</div>"


def mostrar_graficos(graficos: list[dict[str, object]]) -> None:
    """Exibe dois gráficos por linha, mantendo responsividade e acessibilidade."""

    configuracao_plotly = {
        "displaylogo": False,
        "scrollZoom": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "scale": 2},
    }
    for inicio in range(0, len(graficos), 2):
        # No computador são dois gráficos por linha; no celular, as colunas
        # empilham automaticamente para preservar rótulos e áreas clicáveis.
        colunas = st.columns(2, wrap=True)
        for deslocamento, item in enumerate(graficos[inicio : inicio + 2]):
            with colunas[deslocamento]:
                with st.container(border=True, height="stretch"):
                    st.plotly_chart(
                        item["figura"],
                        width="stretch",
                        theme=None,
                        config=configuracao_plotly,
                        alt=str(item["alt"]),
                        key=f"grafico_{pagina_selecionada}_{inicio + deslocamento}",
                    )


# ---------------------------------------------------------------------------
# Área rolável do dashboard
# ---------------------------------------------------------------------------

with st.container(key="dashboard_body"):
    st.html(
        f"<h1 class='rh-page-title'>{escape(pagina.titulo)}</h1>"
        f"<p class='rh-page-subtitle'>{escape(pagina.subtitulo)}</p>"
    )

    if not pagina.graficos:
        st.warning(
            "A combinação de filtros não possui dados. A ausência foi preservada; "
            "o painel não substituiu o período por zero.",
            title="Sem dados para exibir",
            icon=":material/info:",
        )
    else:
        st.html(html_kpis(pagina.kpis))
        mostrar_graficos(pagina.graficos)

        if pagina.tabela is not None:
            st.subheader(
                pagina.titulo_tabela or "Detalhamento",
                icon=":material/table_chart:",
                text_alignment="center",
            )
            st.dataframe(
                pagina.tabela,
                hide_index=True,
                height=430,
                width="stretch",
                alt=pagina.titulo_tabela or "Tabela de detalhamento do painel",
                key=f"tabela_{pagina_selecionada}",
            )

    st.caption(
        "Dados integralmente fictícios para demonstração e portfólio. "
        "Nenhum atributo pertence a pessoas reais. 2024 e 2025 completos; "
        "2026 disponível de janeiro a setembro. Dados sensíveis somente agregados."
    )

