"""Compatibility wrapper for the installed deterministic fixture generator."""


def generate():
    from normalization.__main__ import main
    import sys
    return main(["generate-fixtures", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(generate())
