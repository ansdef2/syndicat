"""Минимальная линейная алгебра на стандартной библиотеке.

Матрицы - списки списков. Размерность периметра (11 классов ОКВЭД)
такова, что метод Гаусса-Жордана точнее и дешевле любой зависимости.
"""

Matrix = list


def identity(n: int) -> Matrix:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def sub(a: Matrix, b: Matrix) -> Matrix:
    return [[a[i][j] - b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def inverse(m: Matrix) -> Matrix:
    """Обращение методом Гаусса-Жордана с выбором ведущего элемента."""
    n = len(m)
    aug = [list(row) + identity(n)[i] for i, row in enumerate(m)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("матрица вырождена: (I - A) необратима")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        p = aug[col][col]
        aug[col] = [v / p for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor:
                aug[r] = [v - factor * w for v, w in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


def vec_mat(v, m: Matrix):
    """v @ M - строка на матрицу."""
    n_cols = len(m[0])
    return [sum(v[i] * m[i][j] for i in range(len(v))) for j in range(n_cols)]


def column(m: Matrix, j: int):
    return [row[j] for row in m]


def leontief_inverse(a: Matrix) -> Matrix:
    """(I - A)^-1 - матрица полных затрат."""
    return inverse(sub(identity(len(a)), a))
