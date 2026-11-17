"""Cinco métodos determinísticos; o CSV original nunca é alterado."""

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from rapidfuzz import process
from rapidfuzz.distance import DamerauLevenshtein, JaroWinkler, Levenshtein
from spellchecker import SpellChecker

ROOT = Path(__file__).resolve().parent
TOKEN = re.compile(r"(?<!\w)[^\W\d_]+(?!\w)")
METHODS = {
    "Regex": "Aplica padrões de texto para organizar espaços e expandir abreviações, "
    "como 'c/' para 'com'. Só altera o que tem uma regra definida.",
    "Dicionário": "Consulta palavras e substituições cadastradas para corrigir erros "
    "conhecidos e recuperar acentos, como 'flga' para 'folga'.",
    "Levenshtein": "Procura no vocabulário a palavra que exige menos letras inseridas, "
    "removidas ou substituídas, como 'mancl' para 'mancal'.",
    "Damerau-Levenshtein": "Funciona como Levenshtein e também reconhece duas letras "
    "vizinhas invertidas, como 'macnal' para 'mancal', contando uma única edição.",
    "Jaro-Winkler": "Compara letras em comum e sua ordem, dando mais peso ao começo "
    "da palavra. Sugere grafias parecidas, mas pode confundir palavras com o mesmo prefixo.",
}
ABBREVIATIONS = [
    (r"(?<!\w)c\s*/", "com "),
    (r"(?<!\w)s\s*/", "sem "),
    (r"\bn\b", "não"),
    (r"\bbba\b\.?", "bomba"),
    (r"\bequip\b\.?", "equipamento"),
    (r"\bmot\b\.?", "motor"),
    (r"\bcompr\b\.?", "compressor"),
    (r"\btemp\b\.?", "temperatura"),
    (r"\bpress\b\.?", "pressão"),
    (r"\bvaz\b\.?", "vazamento"),
    (r"\balmox\b\.?", "almoxarifado"),
]
RULES = [(re.compile(pattern), replacement) for pattern, replacement in ABBREVIATIONS]


def fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.casefold()) if not unicodedata.combining(c)
    )


def baseline(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def regex_normalize(text: str) -> str:
    result = baseline(text)
    for pattern, replacement in RULES:
        result = pattern.sub(replacement, result)
    return " ".join(result.split())


class Normalizer:
    def __init__(self):
        portuguese = SpellChecker(language="pt").word_frequency.dictionary
        self.portuguese_words = {word for word in portuguese if word.isalpha()}
        self.lexicon = {}
        # A forma mais frequente resolve colisões de acentos no dicionário geral.
        for word in sorted(portuguese, key=lambda w: (portuguese[w], w)):
            if word.isalpha():
                self.lexicon[fold(word)] = word
        self.portuguese_size = len(self.lexicon)
        words = (ROOT / "resources/vocabulario.txt").read_text().splitlines()
        self.domain = {fold(w): w for w in words if w}
        self.lexicon.update(self.domain)
        self.by_length = defaultdict(list)
        for word in sorted(self.lexicon):
            self.by_length[len(word)].append(word)
        self.variants = json.loads((ROOT / "resources/substituicoes.json").read_text())
        self.candidate_cache = {}

    def candidates(self, length: int, limit: int) -> tuple[str, ...]:
        key = (length, limit)
        if key not in self.candidate_cache:
            self.candidate_cache[key] = tuple(
                word
                for size in range(length - limit, length + limit + 1)
                for word in self.by_length.get(size, ())
            )
        return self.candidate_cache[key]

    def correct_token(self, token: str, method: str, max_distance: int, threshold: float) -> str:
        key = fold(token)
        if method == "Dicionário" and key in self.variants:
            return self.variants[key]
        if token in self.portuguese_words and key not in self.domain:
            return token
        if key in self.lexicon:
            return self.lexicon[key]
        if method == "Dicionário":
            return token
        # shortcut: sem contexto, palavras curtas e empates são preservados;
        # ampliar apenas com exemplos rotulados e regras de domínio revisadas.
        if len(key) < 4:
            return token
        limit = min(max_distance, 1 if len(key) < 6 else 2)
        candidates = [w for w in self.domain if abs(len(w) - len(key)) <= limit]
        scorer = {
            "Levenshtein": Levenshtein.distance,
            "Damerau-Levenshtein": DamerauLevenshtein.distance,
            "Jaro-Winkler": JaroWinkler.normalized_distance,
        }[method]
        cutoff = 1 - threshold if method == "Jaro-Winkler" else limit
        scored = process.extract(key, candidates, scorer=scorer, limit=2, score_cutoff=cutoff)
        if not scored:
            scored = process.extract(
                key, self.candidates(len(key), limit), scorer=scorer, limit=2, score_cutoff=cutoff
            )
        if not scored:
            return token
        best, score, _ = scored[0]
        if len(scored) > 1 and abs(scored[1][1] - score) < 1e-12:
            return token
        return self.lexicon[best]

    def normalize_many(self, texts, method: str, max_distance=2, threshold=0.92) -> list[str]:
        if method not in METHODS:
            raise ValueError(f"Método desconhecido: {method}")
        if max_distance not in (1, 2) or not 0.8 <= threshold <= 1:
            raise ValueError("Use distância 1 ou 2 e limiar entre 0,8 e 1.")
        prepared = []
        for text in texts:
            if not isinstance(text, str):
                raise TypeError("Cada relato deve ser um texto.")
            prepared.append(regex_normalize(text))
        if method == "Regex":
            return prepared
        # Cada palavra distinta é comparada uma vez por lote, em todos os métodos.
        corrections = {
            token: self.correct_token(token, method, max_distance, threshold)
            for token in sorted({m.group() for text in prepared for m in TOKEN.finditer(text)})
        }
        return [TOKEN.sub(lambda m: corrections[m.group()], text) for text in prepared]
