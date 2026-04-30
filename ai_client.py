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


async def _tts_one(text: str, voice: str) -> bytes:
    """Bitta segmentni edge-tts orqali ovozga aylantiradi."""
    communicate = edge_tts.Communicate(text, voice)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


async def text_to_speech(text: str) -> bytes:
    """Bitta ovoz bilan (asosiy ruscha) — eski API uchun."""
    return await _tts_one(text, settings.tts_voice)


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
_LATIN_RE = re.compile(r"[A-Za-z]")
_MARKDOWN_RE = re.compile(r"[*_`~#>]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_PARENS_RE = re.compile(r"\(([^()]*)\)")
_BRACKETS_RE = re.compile(r"\[([^\[\]]*)\]")
_MULTISPACE_RE = re.compile(r"\s+")
_CYR_WORD_RE = re.compile(r"[А-Яа-яЁё][А-Яа-яЁё\-’']*")
_LAT_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-’']*")


def has_russian(text: str) -> bool:
    return bool(_RUSSIAN_RE.search(text))


def _unwrap_or_drop(s: str, pattern: re.Pattern[str]) -> str:
    """Qavs ichi ruscha bo'lsa — saqlaydi, faqat lotin bo'lsa va oldidagi
    haqiqiy so'z ruscha bo'lsa — transliteratsiya deb hisoblab o'chiradi.
    Aks holda (oldida lotincha so'z bor) — qavs ichini saqlaydi (o'zbek izohi)."""
    def repl(m: re.Match[str]) -> str:
        content = m.group(1)
        if _RUSSIAN_RE.search(content):
            return " " + content + " "
        # Tinish belgilari va bo'shliqdan keyin oxirgi haqiqiy harfni topamiz.
        prev = s[: m.start()]
        i = len(prev) - 1
        while i >= 0 and not (prev[i].isalpha() or prev[i].isdigit()):
            i -= 1
        if i >= 0 and _RUSSIAN_RE.match(prev[i]):
            return " "
        return " " + content + " "
    return pattern.sub(repl, s)


def _clean_for_tts(text: str) -> str:
    """Markdown, HTML, transliteratsiya qavslari va keraksiz belgilarni olib tashlaydi."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = _unwrap_or_drop(text, _PARENS_RE)
    text = _unwrap_or_drop(text, _BRACKETS_RE)
    text = _MARKDOWN_RE.sub("", text)
    # Toq qolgan qavslar bo'lsa — ovoz pauza qilmasin uchun olib tashlaymiz.
    text = re.sub(r"[()\[\]<>]", " ", text)
    text = _MULTISPACE_RE.sub(" ", text)
    return text


def _split_by_script(text: str) -> list[tuple[str, str]]:
    """Tozalangan matnni [(voice_tag, segment), ...] ko'rinishida qaytaradi.
    voice_tag: 'ru' (kirillcha) yoki 'uz' (lotincha).
    Yonma-yon bir xil til segmentlari (orasidagi tinish belgilari bilan) birlashtiriladi.
    """
    segments: list[tuple[str, str]] = []
    current_voice: str | None = None
    buffer: list[str] = []

    pos = 0
    n = len(text)
    while pos < n:
        m = _CYR_WORD_RE.match(text, pos)
        if m:
            atom_voice: str | None = "ru"
            atom = m.group(0)
            pos = m.end()
        else:
            m = _LAT_WORD_RE.match(text, pos)
            if m:
                atom_voice = "uz"
                atom = m.group(0)
                pos = m.end()
            else:
                atom_voice = None
                atom = text[pos]
                pos += 1

        if atom_voice is None:
            buffer.append(atom)
        elif current_voice is None or atom_voice == current_voice:
            current_voice = atom_voice
            buffer.append(atom)
        else:
            seg = "".join(buffer).strip()
            if seg and current_voice:
                segments.append((current_voice, seg))
            buffer = [atom]
            current_voice = atom_voice

    seg = "".join(buffer).strip()
    if seg and current_voice:
        segments.append((current_voice, seg))

    # Juda qisqa o'zbek bo'laklarini (1-2 harf — odatda noto'g'ri tan olingan
    # transliteratsiya yoki abbreviatura) tashlab yuboramiz.
    result: list[tuple[str, str]] = []
    for v, s in segments:
        if v == "ru" and _RUSSIAN_RE.search(s):
            result.append((v, s))
        elif v == "uz" and len(_LATIN_RE.findall(s)) >= 3:
            result.append((v, s))
    return result


async def text_to_speech_mixed(text: str) -> tuple[bytes, str]:
    """Aralash matnni har til o'z ovozi bilan o'qiydi va MP3'ni birlashtiradi.

    Ruscha qismlar — `settings.tts_voice` (Dmitry, erkak),
    o'zbekcha qismlar — `settings.tts_voice_uz` (Madina, ayol).
    Qaytaradi: (audio_bytes, caption_text).
    """
    cleaned = _clean_for_tts(text)
    segments = _split_by_script(cleaned)
    if not segments:
        return b"", ""

    voice_for = {"ru": settings.tts_voice, "uz": settings.tts_voice_uz}

    results = await asyncio.gather(
        *(_tts_one(seg, voice_for[v]) for v, seg in segments),
        return_exceptions=True,
    )
    audio_chunks: list[bytes] = []
    for r in results:
        if isinstance(r, bytes):
            audio_chunks.append(r)
        else:
            logger.warning("TTS segment xatosi: %s", r)
    audio = b"".join(audio_chunks)
    caption = " ".join(s for _, s in segments)
    return audio, caption
