# Relatos em foco

Mini projeto Streamlit para explorar cinco métodos rápidos de pré-processamento e
correção lexical de relatos industriais, sem sobrescrever os dados originais.
A interface e os exemplos estão em português.

## Executar

Requisitos: Python 3.12–3.14 e [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked
uv run streamlit run main.py
```

Abra o endereço informado pelo Streamlit, normalmente http://localhost:8501.
O ponto de entrada é **`main.py`**, inclusive no Streamlit Community Cloud.
Não precisa de chave de API nem de baixar modelos. Após a instalação, o
processamento dos textos é local.

Alternativa com pip:

```bash
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

`requirements.txt` foi exportado do `uv.lock`, com versões fixadas e apenas as
dependências de execução. Para regenerar depois de atualizar dependências:

```bash
uv export --frozen --no-dev --no-hashes --format requirements-txt --no-emit-project --output-file requirements.txt --quiet
```

## O que explorar no app

- **Dataset:** filtros por período, classe e equipamento; gráficos, textos
  repetidos e palavras fora do vocabulário para revisão.
- **Como funciona:** os cinco métodos, suas regras e limitações.
- **Comparação:** original e resultado, destaque de alterações, tempos medidos,
  parâmetros de distância/similaridade e download CSV com os cinco resultados.
- **Seu texto:** entrada de até 10 mil caracteres, resultado de cada método e download.
- **Avaliação e vocabulário:** referências manuais ilustrativas, acerto exato
  por método, termos industriais e tabela de substituições.

## Dataset e achados iniciais

`data/relatos_de_campo.csv` contém **3.000 relatos**, de 1 a 30 de junho de 2026,
com as colunas `id`, `data`, `equipamento`, `texto` e `classe`. Não há campos
obrigatórios ausentes; existem oito repetições de texto (além da primeira ocorrência),
que são mantidas porque podem representar eventos diferentes.

| Classe | Relatos |
|---|---:|
| eletrica | 902 |
| mecanica | 842 |
| hidraulica | 499 |
| instrumentacao | 439 |
| seguranca | 318 |

Há sete equipamentos: ponte, bomba, esteira, compressor, prensa, caldeira e motor.
Os principais problemas observados são:

| Problema | Exemplo | Resultado desejado |
|---|---|---|
| Abreviação | `mot. c/ temp. alta` | `motor com temperatura alta` |
| Omissão | `flga no mancl` | `folga no mancal` |
| Transposição | `acoplamneto` | `acoplamento` |
| Inserção | `rolammento` | `rolamento` |
| Acentuação | `valvula com vibracao` | `válvula com vibração` |
| Erro que forma palavra válida | `cadeira` por `caldeira` | exige contexto/revisão |

## Os cinco métodos

Todos partem da mesma preparação: Unicode NFC, minúsculas, espaços uniformes e
expansão de abreviações por regex, com limites de palavra para evitar substituições
dentro de outros termos. Não removemos negações, números, unidades ou pontuação
livre: são informações úteis para interpretar as ocorrências.

| Método | Etapa adicional | Custo e limite prático |
|---|---|---|
| Regex | Nenhuma: regras de abreviações e espaços | Varreduras lineares; só cobre padrões conhecidos |
| Dicionário | Substituições exatas revisadas e acentuação conhecida | Consulta em tabela; não generaliza erros novos |
| Levenshtein | Menor distância por inserção, remoção e substituição | Busca compilada; uma inversão costuma custar duas edições |
| Damerau–Levenshtein | Inclui transposição adjacente como uma edição | Bom para letras invertidas; ainda pode confundir palavras próximas |
| Jaro–Winkler | Similaridade com preferência por prefixos comuns | Corte por similaridade; pode favorecer prefixos incorretamente |

### Dicionário português

**Sim, Levenshtein precisa de palavras candidatas.** A distância sozinha não diz
qual é a grafia correta. O projeto carrega `SpellChecker(language="pt")` do
**pyspellchecker**: cerca de 385 mil chaves alfabéticas distintas após retirar
acentos para comparação. Usamos o dicionário da biblioteca; os algoritmos de
distância são os do RapidFuzz, não a função de correção do pyspellchecker.

A lista portuguesa é baseada em frequências de legendas, não é um dicionário
normativo exclusivo de português brasileiro. Há duas extensões locais:

- `resources/vocabulario.txt`: formas canônicas industriais, com acentos.
- `resources/substituicoes.json`: variantes que o método Dicionário corrige
  explicitamente; os métodos aproximados não usam essa tabela.

Nenhum erro frequente do CSV é aprendido automaticamente como palavra correta.
As chaves da busca ignoram acentos; a saída usa a forma canônica. As formas
industriais prevalecem no vocabulário. Para palavras gerais, uma grafia já
reconhecida é preservada; na restauração de acentos, a forma mais frequente resolve
colisões, o que pode errar em casos ambíguos.

Para manter a busca rápida e adequada ao domínio, os três métodos aproximados
**procuram primeiro nos termos industriais**. Se nenhum candidato passa no limite,
consultam o dicionário português geral. Portanto, o resultado é uma preferência
de domínio, não necessariamente o mínimo global de distância no português.
Empates entre os melhores candidatos da etapa escolhida mantêm o original.

Palavras desconhecidas com menos de quatro letras são preservadas na busca
aproximada. A distância é limitada a uma edição para 4–5 letras e até duas para
palavras maiores. Jaro–Winkler usa limiar padrão de 0,92 e a mesma janela de
comprimento para restringir candidatos; ele não usa distância de edição para
decidir a similaridade. Códigos alfanuméricos como `RO001`, `220V` e `50cv` não
sofrem correção lexical, mas são convertidos para minúsculas.

### Velocidade e avaliação

Cada palavra distinta é corrigida uma vez por lote. O vocabulário e os índices
por comprimento são reutilizados; o Streamlit guarda resultados de recortes já
calculados. Os tempos exibidos são a **mediana de três execuções após aquecimento**,
refazendo o mapa de palavras por lote e excluindo carga do dicionário, leitura de
arquivo e interface. Compare os métodos no mesmo recorte e computador; o tempo
de um texto individual no laboratório é apenas uma observação interativa.

O dataset não oferece uma versão correta de referência. A porcentagem de relatos
alterados **não mede qualidade**. O app usa os 22 exemplos manuais de
`resources/avaliacao.csv` para demonstrar acerto exato, inclusive preservação de
textos válidos. Esses exemplos foram escolhidos depois de explorar o dataset:
não são um conjunto independente nem comprovam acurácia em produção.

Medição local de referência em 17/11/2026, com os 3.000 relatos, distância máxima
2 e limiar Jaro–Winkler 0,92 (tempos arredondados, dependentes da máquina e carga):

| Método | Tempo do lote | Relatos alterados | Acertos nos 22 exemplos |
|---|---:|---:|---:|
| Regex | 127 ms | 1.471 | 7 |
| Dicionário | 190 ms | 2.753 | 21 |
| Levenshtein | 450 ms | 2.804 | 20 |
| Damerau–Levenshtein | 357 ms | 2.811 | 22 |
| Jaro–Winkler | 670 ms | 2.811 | 22 |

As alterações incluem expansão de abreviações e restauração de acentos. O método
Dicionário não corrigiu a inserção `rolammento`; Levenshtein preservou `ruiod` e
`truno` nos exemplos por limite/ambiguidade. Damerau e Jaro acertaram todos esses
exemplos escolhidos, mas isso não comprova superioridade geral. O app recalcula
as medidas para os filtros e parâmetros selecionados.

Para o primeiro uso, regras e substituições revisadas oferecem previsibilidade.
Damerau–Levenshtein é uma boa hipótese para investigar transposições. A escolha
final deve usar uma amostra separada, rotulada por alguém do domínio, medindo
acertos, erros restantes e correções indevidas. Os métodos não entendem contexto,
concordância ou significado: `cadeira` continuará válida, e a regra `n → não`
pressupõe a convenção dos coletores deste dataset.

## Estrutura e validação

```text
main.py                  # interface Streamlit
normalizer.py            # cinco métodos e vocabulários
analysis.py              # leitura validada e benchmark
data/relatos_de_campo.csv # dados originais
resources/               # termos, variantes e referências manuais
tests/                   # lógica, português, preservação e interação do app
pyproject.toml           # projeto e dependências uv
uv.lock                  # resolução reproduzível
requirements.txt         # exportação para pip / hospedagem
```

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Os testes verificam regras, limites de palavra, acentos, uso do português fora do
vocabulário industrial, distâncias, códigos, entradas inválidas, preservação do
CSV e o fluxo Streamlit com filtro e entrada de texto.

Referências: [dicionários pyspellchecker](https://pyspellchecker.readthedocs.io/en/latest/),
[Levenshtein](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html),
[Damerau–Levenshtein](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/DamerauLevenshtein.html),
[Jaro–Winkler](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/JaroWinkler.html),
[cache Streamlit](https://docs.streamlit.io/develop/concepts/architecture/caching).
