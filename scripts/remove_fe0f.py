"""Remove U+FE0F emoji variant selector remnants from Python source files."""
import argparse
import os

FE0F = "\ufe0f"


def process_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    if FE0F not in source:
        return False

    cleaned = source.replace(FE0F, "")
    with open(path, "w", encoding="utf-8") as f:
        f.write(cleaned)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    for path in args.files:
        if process_file(path):
            print(f"Updated: {path}")


if __name__ == "__main__":
    main()
