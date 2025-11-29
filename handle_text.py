# handle_text.py

import re
import emoji


def prepare_tts_input_with_context(text: str) -> str:
    """
    Prepares text for a TTS API by cleaning Markdown and adding minimal contextual hints
    for certain Markdown elements like headers. Preserves paragraph separation.

    Args:
        text (str): The raw text containing Markdown or other formatting.

    Returns:
        str: Cleaned text with contextual hints suitable for TTS input.
    """

    # Remove emojis
    text = emoji.replace_emoji(text, replace="")

    # Add context for headers
    def header_replacer(match):
        level = len(match.group(1))  # Number of '#' symbols
        header_text = match.group(2).strip()
        if level == 1:
            return f"Title — {header_text}\n"
        elif level == 2:
            return f"Section — {header_text}\n"
        else:
            return f"Subsection — {header_text}\n"

    text = re.sub(r"^(#{1,6})\s+(.*)", header_replacer, text, flags=re.MULTILINE)

    # Remove links while keeping the link text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Describe inline code
    text = re.sub(r"`([^`]+)`", r"code snippet: \1", text)

    # Remove bold/italic symbols but keep the content
    text = re.sub(r"(\*\*|__|\*|_)", "", text)

    # Remove code blocks (multi-line) with a description
    text = re.sub(r"```([\s\S]+?)```", r"(code block omitted)", text)

    # Remove image syntax but add alt text if available
    text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"Image: \1", text)

    # Remove HTML tags
    text = re.sub(r"</?[^>]+(>|$)", "", text)

    # Normalize line breaks
    text = re.sub(r"\n{2,}", "\n\n", text)  # Ensure consistent paragraph separation

    # Replace multiple spaces within lines
    text = re.sub(r" {2,}", " ", text)

    # Trim leading and trailing whitespace from the whole text
    text = text.strip()

    return text


def chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """
    Splits text into chunks of approximately max_chars length,
    attempting to break at paragraph boundaries first, then sentences.
    """
    if not text:
        return []

    chunks = []
    current_chunk = []
    current_length = 0

    # Split by double newlines to preserve paragraphs
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        # If adding this paragraph exceeds limit
        if current_length + len(para) > max_chars:
            # If current chunk is not empty, push it
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0

            # If paragraph itself is huge, we might need to just add it
            # (or split by sentences, but let's keep it simple for now as edge-tts is robust)
            if len(para) > max_chars:
                chunks.append(para)
            else:
                current_chunk.append(para)
                current_length += len(para)
        else:
            current_chunk.append(para)
            current_length += len(para)

    # Append remaining
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks
