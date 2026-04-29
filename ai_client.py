"""AI client: Google Gemini (chat / JSON / STT) + edge-tts (TTS).

Hammasi BEPUL — Gemini'ning bepul tarifi, edge-tts esa kalit ham talab qilmaydi.
Vaqtinchalik xatolarda avtomatik qayta urinish va zaxira modelga o'tish bor.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

import edge_tts
from google import genai
from google.genai import errors, types

from config import settings
from prompts import EXTRACT_RU_SYSTEM

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)

# Vaqtinchalik xato kodlari (server band, rate limit va h.k.)
_RETRY_CODES = {429, 500, 502, 503, 504}

# Asosiy model band bo'lsa, ushbu modellarga ketma-ket o'tib ko'riladi
_FALLBACK_MODELS = ("gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite")


async def _generate(contents, config) -> types.GenerateContentResponse:
    """Asosiy modelda urin, vaqtinchalik xatoda qayta urin, keyin fallback'ga o't."""
    primary = settings.gemini_model
    candidates = [primary] + [m for m in _FALLBACK_MODELS if m != primary]
    last_err: Exception | None = None

    for model in candidates:
        for attempt in range(2):
            try:
                return await _client.aio.models.generate_content(
                    model=model, contents=contents, config=config,
                )
            except errors.APIError as e:
                last_err = e
                code = getattr(e, "code", None)
                if code in _RETRY_CODES:
                    delay = 1.0 * (attempt + 1)
                    logger.warning(
                        "Gemini %s -> %s, %.1fs kutib qayta urinaman",
                        model, code, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
        logger.warning("Gemini %s ishlamadi — fallback modelga o'tyapman", model)

    if last_err:
        raise last_err
    raise RuntimeError("Gemini'ning hech qaysi modeli javob bermadi")


def _to_gemini_contents(history: list[dict], user_message: str) -> list:
    """OpenAI-style history'ni Gemini formatiga o'tkazadi."""
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )
    contents.append(
        types.Content(role="user", parts=[types.Part(text=user_message)])
    )
    return contents


async def chat(system_prompt: str, history: list[dict], user_message: str) -> str:
    contents = _to_gemini_contents(history, user_message)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.6,
        max_output_tokens=900,
    )
    response = await _generate(contents, config)
    return (response.text or "").strip()


async def chat_json(system_prompt: str, user_message: str) -> dict:
    """JSON formatdagi javob (quiz, daily word)."""
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
        max_output_tokens=1500,
        response_mime_type="application/json",
    )
    response = await _generate(user_message, config)
    raw = (response.text or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("AI JSON noto'g'ri: %s", raw[:200])
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(cleaned)


async def text_to_speech(text: str) -> bytes:
    """edge-tts (Microsoft) — bepul TTS, MP3 oqimini qaytaradi."""
    communicate = edge_tts.Communicate(text, settings.tts_voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


async def speech_to_text(audio_bytes: bytes, mime: str = "audio/ogg") -> str:
    """Gemini multimodal — ovozli xabarni matnga o'tkazadi (rus tili ustuvor)."""
    contents = [
        types.Part(text=(
            "Transkripsiya qiling. Faqat ovozda eshitilgan matnni qaytaring "
            "(asosan ruscha, kirill yozuvida). Hech qanday izoh, qo'shtirnoq "
            "yoki sarlavha qo'shmang."
        )),
        types.Part(inline_data=types.Blob(data=audio_bytes, mime_type=mime)),
    ]
    config = types.GenerateContentConfig(temperature=0, max_output_tokens=500)
    response = await _generate(contents, config)
    return (response.text or "").strip()


_RUSSIAN_RE = re.compile(r"[А-Яа-яЁё]")
_MARKDOWN_RE = re.compile(r"[*_`~#>]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_PARENS_RE = re.compile(r"\(([^()]*)\)")
_BRACKETS_RE = re.compile(r"\[([^\[\]]*)\]")
_MULTISPACE_RE = re.compile(r"\s+")


def has_russian(text: str) -> bool:
    return bool(_RUSSIAN_RE.search(text))


def _unwrap_or_drop(s: str, pattern: re.Pattern[str]) -> str:
    """Qavs ichida ruscha bo'lsa — ichini saqlaydi, qavslarni olib tashlaydi.
    Ruscha bo'lmasa — butun qavsni o'chiradi (transliteratsiya/izoh)."""
    def repl(m: re.Match[str]) -> str:
        content = m.group(1)
        return content if _RUSSIAN_RE.search(content) else " "
    return pattern.sub(repl, s)


def _clean_for_tts(text: str) -> str:
    """Markdown, HTML, transliteratsiya qavslari va keraksiz belgilarni olib tashlaydi."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = _unwrap_or_drop(text, _PARENS_RE)
    text = _unwrap_or_drop(text, _BRACKETS_RE)
    text = _MARKDOWN_RE.sub("", text)
    # Toq qolgan qavslar bo'lsa — ovoz pauza qilmasin uchun olib tashlaymiz.
    text = re.sub(r"[()\[\]<>]", " ", text)
    return text


async def extract_russian(text: str) -> str:
    """Aralash matndan faqat ruscha qismni ajratadi (TTS uchun)."""
    if not has_russian(text):
        return ""

    text = _clean_for_tts(text)

    direct_lines = []
    for line in text.splitlines():
        ru_chars = _RUSSIAN_RE.findall(line)
        if len(ru_chars) >= 3:
            cleaned = re.sub(r"^[^А-Яа-яЁё]+", "", line)
            cleaned = re.sub(r"[^А-Яа-яЁё.,!?\-\s'’\":]+$", "", cleaned)
            cleaned = _MULTISPACE_RE.sub(" ", cleaned).strip()
            if cleaned:
                direct_lines.append(cleaned)

    if direct_lines:
        return " ".join(direct_lines)[:1000]

    config = types.GenerateContentConfig(
        system_instruction=EXTRACT_RU_SYSTEM,
        temperature=0,
        max_output_tokens=400,
    )
    response = await _generate(text, config)
    return _MULTISPACE_RE.sub(" ", (response.text or "")).strip()[:1000]
