"""Execute: uv run streamlit run main.py."""

from collections import Counter
from difflib import SequenceMatcher
from html import escape
from time import perf_counter

import pandas as pd
import streamlit as st

from analysis import compare, load_data
from normalizer import METHODS, ROOT, TOKEN, Normalizer, baseline, fold

st.set_page_config(page_title="Relatos em foco", page_icon="🔎", layout="wide")


@st.cache_resource
def get_normalizer(resource_version):
    return Normalizer()


@st.cache_data
def read_data(version):
    return load_data()


@st.cache_data(show_spinner="Comparando os cinco métodos e medindo os tempos…")
def analyze(frame, distance, threshold, resource_version):
    return compare(frame, get_normalizer(resource_version), distance, threshold)


def highlighted(before, after):
    """HTML escapado: entrada do usuário nunca é interpretada como marcação."""
    fragments = []
    for op, _, _, start, end in SequenceMatcher(None, before.split(), after.split()).get_opcodes():
        value = escape(" ".join(after.split()[start:end]))
        if op in ("replace", "insert"):
            value = f'<mark style="background:#d6f5df;color:#123c24">{value}</mark>'
        fragments.append(value)
    return " ".join(fragments)


resource_version = tuple(p.stat().st_mtime_ns for p in sorted((ROOT / "resources").iterdir()))
try:
    normalizer = get_normalizer(resource_version)
    data = read_data((ROOT / "data/relatos_de_campo.csv").stat().st_mtime_ns)
except (OSError, ValueError, pd.errors.ParserError) as exc:
    st.error(f"Não foi possível carregar os dados: {exc}")
    st.stop()

st.title("🔎 Relatos em foco")
st.write("Um laboratório de grafia para relatos de campo: explore, compare e revise as sugestões.")
st.caption("Processamento local • cinco métodos determinísticos • dados originais preservados")

with st.sidebar:
    st.header("Recorte dos dados")
    classes = st.multiselect("Classes", sorted(data.classe.unique()))
    dates = st.date_input(
        "Período",
        value=(data.data.min().date(), data.data.max().date()),
        min_value=data.data.min().date(),
        max_value=data.data.max().date(),
    )
    st.header("Correção aproximada")
    distance = st.select_slider("Distância máxima de edição", options=[1, 2], value=2)
    threshold = st.slider("Similaridade mínima Jaro-Winkler", 0.80, 1.0, 0.92, 0.01)
    st.caption(
        "Palavras de 4 a 5 letras aceitam no máximo uma edição. "
        "Jaro usa o limiar de similaridade e a mesma janela de comprimento."
    )
    st.caption(
        f"Dicionário português: {normalizer.portuguese_size:,} chaves sem acento. "
        f"Complemento industrial: {len(normalizer.domain)} termos."
    )

filtered = data.copy()
if classes:
    filtered = filtered[filtered.classe.isin(classes)]
if len(dates) == 2:
    filtered = filtered[filtered.data.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]
else:
    st.info("Selecione a data final para aplicar o filtro de período.")

overview, methods, comparison, lab, evaluation = st.tabs(
    ["Dataset", "Como funciona", "Comparação", "Seu texto", "Avaliação e vocabulário"]
)

with overview:
    st.subheader("O que os coletores registraram")
    a, b, c, d = st.columns(4)
    a.metric("Relatos no recorte", len(filtered))
    b.metric("Equipamentos", filtered.equipamento.nunique())
    c.metric("Textos repetidos", filtered.texto.duplicated().sum())
    d.metric("Caracteres / relato", round(filtered.texto.str.len().mean()) if len(filtered) else 0)
    left, right = st.columns(2)
    with left:
        st.caption("Distribuição por classe")
        st.bar_chart(filtered.classe.value_counts().rename("Relatos"), horizontal=True)
    with right:
        st.caption("Distribuição por equipamento")
        st.bar_chart(filtered.equipamento.value_counts().rename("Relatos"), horizontal=True)
    if len(filtered):
        st.caption("Relatos por dia")
        st.line_chart(filtered.groupby("data").size().rename("Relatos"))
        tokens = Counter(fold(m.group()) for text in filtered.texto for m in TOKEN.finditer(text))
        unknown = [
            (word, count)
            for word, count in tokens.most_common()
            if word not in normalizer.lexicon and len(word) >= 4
        ]
        with st.expander("Palavras fora do vocabulário: pistas para revisão"):
            st.caption("Não são necessariamente erros: podem ser termos técnicos ou nomes válidos.")
            st.dataframe(
                pd.DataFrame(unknown, columns=["Palavra", "Ocorrências"]),
                hide_index=True,
                width="stretch",
            )
    st.dataframe(filtered, hide_index=True, width="stretch")

with methods:
    st.subheader("Cinco formas leves de normalizar")
    st.write(
        "Todos os métodos convertem para minúsculas, normalizam espaços e expandem "
        "abreviações com regex. Os demais acrescentam uma etapa de correção lexical."
    )
    with st.container(border=True):
        techniques = list(METHODS.items())
        for start in range(0, len(techniques), 3):
            for column, (name, description) in zip(
                st.columns(3), techniques[start : start + 3], strict=False
            ):
                with column.container(border=True):
                    st.markdown(f"### {name}")
                    st.write(description)
    st.info(
        "Levenshtein, Damerau e Jaro consultam o dicionário português do pyspellchecker "
        "mais o vocabulário industrial. O método Dicionário usa esses mesmos termos "
        "para acentuação e uma tabela explícita para erros conhecidos."
    )
    st.write(
        "A comparação usa chaves sem acento e devolve a forma acentuada do vocabulário. "
        "A busca aproximada prioriza termos industriais e só procura no vocabulário geral "
        "quando nenhum termo industrial passa pelo limite. Empates são preservados. "
        "Palavras conhecidas e desconhecidas com menos "
        "de quatro letras não sofrem correção aproximada. Números e códigos mistos "
        "são preservados, além da conversão para minúsculas."
    )
    st.warning(
        "Sem contexto, não há correção gramatical nem garantia de sentido. "
        "'cadeira' é uma palavra válida e será preservada, mesmo se o coletor quis "
        "escrever 'caldeira'. A regra 'n → não' é uma convenção deste dataset."
    )
    st.markdown(
        "Referências: [pyspellchecker / português](https://pyspellchecker.readthedocs.io/en/latest/), "
        "[distâncias RapidFuzz](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/index.html)."
    )

with comparison:
    st.subheader("Antes, depois e custo de processamento")
    if filtered.empty:
        st.info("Nenhum relato no recorte. Ajuste os filtros; o laboratório continua disponível.")
    else:
        result, metrics = analyze(filtered, distance, threshold, resource_version)
        st.dataframe(metrics, hide_index=True, width="stretch")
        st.caption(
            "Tempo: mediana de 3 execuções do lote após aquecimento, sem leitura do CSV, "
            "carga do dicionário ou renderização. O mapa de correções é refeito por lote. "
            "Resultados são guardados pelo Streamlit entre interações. "
            "'Alterado' compara com o original já em minúsculas e com espaços normalizados; "
            "inclui abreviações e acentos. Alteração não significa acerto."
        )
        st.bar_chart(metrics.set_index("Método")[["Tempo do lote (ms)"]], horizontal=True)
        chosen = st.selectbox("Método para inspecionar", list(METHODS))
        only_changes = st.checkbox("Exibir apenas relatos alterados", value=True)
        view = result.copy()
        if only_changes:
            view = view[view[chosen] != view.texto.map(baseline)]
        st.dataframe(
            view[["id", "equipamento", "classe", "texto", chosen]], hide_index=True, width="stretch"
        )
        if len(view):
            selected_id = st.selectbox("Inspecionar relato", view.id.tolist())
            row = view[view.id == selected_id].iloc[0]
            st.text(row.texto)
            st.markdown(highlighted(baseline(row.texto), row[chosen]), unsafe_allow_html=True)
            st.caption(
                "Verde: palavras inseridas ou substituídas em relação ao original normalizado."
            )
        st.download_button(
            "Baixar comparação dos cinco métodos (CSV)",
            result.to_csv(index=False).encode("utf-8-sig"),
            "relatos_comparados.csv",
            "text/csv",
        )

with lab:
    st.subheader("Experimente um relato")
    with st.form("lab"):
        text = st.text_area(
            "Texto do coletor",
            value="Mot. c/ ruiod no mancl e temp. alta. CLP 220V n parte.",
            max_chars=10000,
            height=130,
        )
        submitted = st.form_submit_button("Comparar meu texto", type="primary")
    if submitted:
        if not text.strip():
            st.warning("Digite um relato para comparar.")
        else:
            outputs = []
            for name in METHODS:
                start = perf_counter()
                corrected = normalizer.normalize_many([text], name, distance, threshold)[0]
                elapsed = (perf_counter() - start) * 1000
                st.markdown(f"**{name}** · {elapsed:.3f} ms")
                st.markdown(highlighted(baseline(text), corrected), unsafe_allow_html=True)
                outputs.append({"Método": name, "Original": text, "Resultado": corrected})
            st.caption("Tempo de uma execução interativa; não equivale ao benchmark do lote.")
            st.download_button(
                "Baixar resultados do meu texto",
                pd.DataFrame(outputs).to_csv(index=False),
                "meu_relato.csv",
                "text/csv",
            )

with evaluation:
    st.subheader("Avaliação ilustrativa com referência manual")
    st.write(
        "O dataset não contém texto corrigido de referência. Os exemplos abaixo foram "
        "selecionados após explorar os dados e incluem acentos, abreviações, erros e "
        "preservação. São uma demonstração, não uma estimativa de acurácia em produção."
    )
    examples = pd.read_csv(ROOT / "resources/avaliacao.csv")
    scores = []
    for name in METHODS:
        examples[name] = normalizer.normalize_many(
            examples.entrada.tolist(), name, distance, threshold
        )
        exact = (examples[name] == examples.esperado).sum()
        scores.append(
            {
                "Método": name,
                "Acertos exatos": exact,
                "Total": len(examples),
                "Acerto ilustrativo (%)": round(exact / len(examples) * 100, 1),
            }
        )
    st.dataframe(pd.DataFrame(scores), hide_index=True, width="stretch")
    st.dataframe(examples, hide_index=True, width="stretch")
    st.caption(
        "Acerto exato exige a frase inteira igual à referência. Para uma avaliação real, "
        "rotule uma amostra separada e meça também correções indevidas e erros restantes."
    )
    with st.expander("Vocabulários e substituições revisáveis"):
        st.write(
            "Português: lista de frequências distribuída com pyspellchecker (language='pt'), "
            "derivada de legendas. Não é um dicionário normativo exclusivo de pt-BR. "
            "A forma mais frequente resolve colisões de acentos; termos industriais prevalecem. "
            "Nenhuma palavra do CSV entra automaticamente como grafia correta."
        )
        st.dataframe(
            pd.DataFrame(sorted(normalizer.domain.values()), columns=["Termo industrial"]),
            hide_index=True,
        )
        st.dataframe(
            pd.DataFrame(normalizer.variants.items(), columns=["Variante", "Correção"]),
            hide_index=True,
        )
