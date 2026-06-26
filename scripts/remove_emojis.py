"""Remove emojis from Python string literals and comments only."""
import argparse
import io
import tokenize
import emoji

EMOJIS = set(emoji.EMOJI_DATA.keys())


def remove_emojis(text: str) -> str:
    return "".join(ch for ch in text if ch not in EMOJIS)


def process_file(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    if not any(ch in EMOJIS for ch in source):
        return False

    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    changed = False
    new_tokens = []
    for tok in tokens:
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            new_text = remove_emojis(tok.string)
            if new_text != tok.string:
                changed = True
                tok = tokenize.TokenInfo(
                    type=tok.type,
                    string=new_text,
                    start=tok.start,
                    end=tok.end,
                    line=tok.line,
                )
        new_tokens.append(tok)

    if not changed:
        return False

    new_source = tokenize.untokenize(new_tokens)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_source)
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
