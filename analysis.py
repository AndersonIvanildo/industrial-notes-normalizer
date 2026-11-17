"""Leitura validada e comparação reproduzível, independentes da interface."""

from statistics import median
from time import perf_counter

import pandas as pd

from normalizer import METHODS, ROOT, Normalizer, baseline


def load_data() -> pd.DataFrame:
    frame = pd.read_csv(ROOT / "data/relatos_de_campo.csv", dtype=str)
    required = {"id", "data", "equipamento", "texto", "classe"}
    if not required <= set(frame.columns):
        raise ValueError(f"O CSV deve conter as colunas: {', '.join(sorted(required))}.")
    if frame.empty or frame[list(required)].isna().any().any():
        raise ValueError("O CSV está vazio ou contém campos obrigatórios ausentes.")
    if frame[list(required)].apply(lambda col: col.str.strip().eq("")).any().any():
        raise ValueError("O CSV contém campos obrigatórios em branco.")
    frame["data"] = pd.to_datetime(frame["data"], format="%Y-%m-%d", errors="raise")
    return frame


def compare(frame: pd.DataFrame, normalizer: Normalizer, distance=2, threshold=0.92):
    texts = frame["texto"].tolist()
    result = frame.copy()
    base = [baseline(text) for text in texts]
    metrics = []
    for method in METHODS:
        output = normalizer.normalize_many(texts, method, distance, threshold)
        elapsed = []
        # Aquecimento acima; mede o lote inteiro, sem cache de palavras entre execuções.
        for _ in range(3):
            start = perf_counter()
            normalizer.normalize_many(texts, method, distance, threshold)
            elapsed.append(perf_counter() - start)
        seconds = median(elapsed)
        result[method] = output
        changed = sum(before != after for before, after in zip(base, output, strict=True))
        metrics.append(
            {
                "Método": method,
                "Relatos alterados": changed,
                "Alterados (%)": round(changed / len(texts) * 100, 2),
                "Tempo do lote (ms)": round(seconds * 1000, 2),
                "ms/relato": round(seconds * 1000 / len(texts), 4),
                "Relatos/s": round(len(texts) / seconds),
            }
        )
    return result, pd.DataFrame(metrics)
