from __future__ import annotations


def decode_qr_bytes(raw: bytes, encodings: tuple[str, ...]) -> str:
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    fallback = encodings[0] if encodings else "utf-8"
    return raw.decode(fallback, errors="replace")
