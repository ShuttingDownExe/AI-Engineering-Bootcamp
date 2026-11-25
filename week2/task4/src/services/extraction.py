import re
from pathlib import Path
from pypdf import PdfReader

def extract_pages(file_path: Path) -> list[dict]:
    reader = PdfReader(file_path)

    return [
        {
            "page": page_number,
            "text": page.extract_text() or ""
        }
        for page_number, page in enumerate(reader.pages, start=1)
    ]


def split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+",text)
        if sentence.strip()
    ]

def chunk_pages(
        pages: list[dict],
        target_size: int = 1_500,
        overlap_sentences: int = 2
) -> list[dict]:
    chunks = []
    chunk_index= 0

    for page in pages:
        current_sentences = []
        current_size = 0

        for sentence in split_sentences(page["text"]):
            sentence_size = len(sentence)+1
            if(current_sentences and current_size +sentence_size > target_size):
                chunks.append({
                    "chunk_index": chunk_index,
                    "page": page["page"],
                    "content": " ".join(current_sentences)
                })
                chunk_index+=1

                current_sentences = current_sentences[-overlap_sentences:]
                current_size = sum(
                    len(item) +1 for item in current_sentences
                )

            current_sentences.append(sentence)
            current_size+=sentence_size

        if current_sentences:
            chunks.append({
                "chunk_index": chunk_index,
                "page": page["page"],
                "content": " ".join(current_sentences)
            })
            chunk_index +=1
    return chunks
