import itertools

import numpy as np


def get_keyword_combinations(keywords: list[str]) -> list[str]:
    if not keywords:
        return []

    all_combinations = []
    for i in range(1, len(keywords) + 1):
        all_combinations.extend(itertools.combinations(keywords, i))

    output_queries = [" AND ".join(f'"{k}"' for k in combo) for combo in all_combinations]
    output_queries.sort(key=len, reverse=True)

    return output_queries


def calculate_sentence_difference(s1: str | list[str], s2: str | list[str]) -> float:
    words1 = s1.split() if isinstance(s1, str) else s1
    words2 = s2.split() if isinstance(s2, str) else s2

    if len(words1) > len(words2):
        words1, words2 = words2, words1

    if not words1:
        return sum(len(w) for w in words2) + len(words2)

    len1, len2 = len(words1), len(words2)
    len_diff_matrix = np.zeros((len1, len2), float)
    char_diff_matrix = np.zeros((len1, len2), float)

    for i in range(len1):
        for j in range(len2):
            len_diff_matrix[i, j] = abs(len(words1[i]) - len(words2[j]))
            w1, w2 = words1[i], words2[j]

            if len(w1) > len(w2):
                w1, w2 = w2, w1

            diff = sum(1 for k in range(len(w1)) if w1[k] != w2[k])
            char_diff_matrix[i, j] = diff

    total_cost_matrix = np.add(len_diff_matrix, char_diff_matrix)
    total_result = 0
    matched_j_indices = set()

    for i in range(len1):
        min_cost = np.inf
        best_j = -1

        for j in range(len2):
            if j not in matched_j_indices and total_cost_matrix[i, j] < min_cost:
                min_cost = total_cost_matrix[i, j]
                best_j = j

        if best_j != -1:
            total_result += min_cost
            matched_j_indices.add(best_j)

    return total_result + abs(len(s1) - len(s2))
