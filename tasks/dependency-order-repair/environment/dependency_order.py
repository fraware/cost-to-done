"""Starter dependency ordering implementation."""


def build_order(dependencies):
    ordered = []
    visited = set()

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        for dependency in dependencies.get(name, []):
            visit(dependency)
        ordered.append(name)

    for name in dependencies:
        visit(name)
    return ordered
