# 🇷🇺 Rus tilini o'rgatuvchi Telegram bot

O'zbek tilida so'zlashuvchi foydalanuvchilarga rus tilini o'rgatadigan to'liq
funksional Telegram bot. **aiogram 3** + **Google Gemini** (chat / JSON / STT) +
**edge-tts** (Microsoft, bepul TTS) + **SQLite** (aiosqlite) + **APScheduler**
asosida qurilgan. **Hech qanday to'lovsiz ishlaydi.**

---

## ✨ Imkoniyatlar

### O'rganish rejimlari
| Rejim | Tavsif |
|-------|--------|
| 📚 Grammatika | Rus tili grammatik qoidalarini misollar bilan o'rgatadi |
| 💬 So'z boyligi | Tanlangan mavzu bo'yicha yangi so'zlarni o'rgatadi |
| ❓ Savol-javob | Kundalik vaziyatlardagi suhbat shablonlari |
| 🔄 Tarjima | O'zbekcha ↔ ruscha avtomatik tarjima |
| 🗣 Dialog | Bot bilan ruscha sodda suhbat — xatolar muloyim tuzatiladi |
| 📝 Matn tahlili | Yuborilgan ruscha matnni tarjima qilib, grammatik tahlil beradi |

### Qo'shimcha funksiyalar
- 🎯 **Test (Quiz) rejimi** — 8 ta mavzudan birini tanlab, 5 savolli test ishlash
- 🌟 **Ball tizimi** — har bir to'g'ri javob, har bir suhbat uchun ball
- 🔥 **Streak** — ketma-ket faol kunlar hisoblanadi
- 🏆 **Reyting** — top 10 foydalanuvchilar ro'yxati
- 📈 **Daraja tizimi** — A1/A2/B1/B2 tanlash, javoblar darajaga moslashadi
- 🎤 **Ovozli xabarlar** — Whisper orqali transkripsiya, ruscha gapirib mashq qilish
- 🔊 **TTS (talaffuz)** — har bir bot javobini "🔊 Eshitish" tugmasi bilan eshitish
- 🌅 **Kunlik so'z** — har kuni belgilangan vaqtda yangi ruscha so'z yuboriladi
- ⚙️ **Sozlamalar** — daraja, kunlik xabar holati, tarixni tozalash
- 🛡 **Throttling** — spamga qarshi himoya
- 📊 **Statistika** — `/stats` orqali shaxsiy progress

---

## 🛠 O'rnatish

### 1) Repository

```bash
git clone https://github.com/<sizning-username>/tg_bot_rus_tili.git
cd tg_bot_rus_tili
```

### 2) Virtual muhit

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3) `.env` faylini sozlash

`.env.example` ni nusxalang:

```bash
cp .env.example .env       # Linux/macOS
copy .env.example .env     # Windows
```

Va to'ldiring:

```env
BOT_TOKEN=12345:AAA...                  # @BotFather'dan

# Google Gemini — BEPUL: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=AIza...                  # 1500 so'rov/kun bepul
GEMINI_MODEL=gemini-2.5-flash           # boshqa: gemini-2.5-flash-lite, gemini-2.0-flash

# edge-tts (Microsoft) — kalit kerak emas, butunlay bepul
TTS_VOICE=ru-RU-DmitryNeural            # erkak. Ayol uchun: ru-RU-SvetlanaNeural

DB_PATH=data/bot.sqlite3
THROTTLE_RATE=1.0                       # foydalanuvchi sekundiga 1 ta xabar
DAILY_WORD_HOUR=9                       # kunlik so'z soati
DAILY_WORD_MINUTE=0
TIMEZONE=Asia/Tashkent

ADMIN_IDS=123456789                     # admin Telegram ID(lar), vergul bilan
```

> 💰 **Hech qanday to'lov kerak emas:**
> - **Gemini API** — Google AI Studio'da bepul kalit oling (kuniga 1500 so'rov)
> - **edge-tts** — Microsoft Edge brauzerining ovozlaridan foydalanadi, kalit yo'q
> - Faqat OpenAI emas — boshqa har qanday API'da pulli akkaunt ham ochish shart emas

> ⚠️ `.env` faylini hech qachon GitHub'ga yuklamang — `.gitignore` allaqachon
> uni e'tiborsiz qoldiradi.

### 4) Ishga tushirish

```bash
python bot.py
```

Telegram'da botingizga `/start` yuboring.

---

## 🐳 Docker bilan ishga tushirish

```bash
docker compose up -d --build
docker compose logs -f bot
```

Ma'lumotlar bazasi `./data/` papkasiga `volume` orqali saqlanadi.

---

## 🌐 Webhook rejimi (production)

`.env` ga qo'shing:

```env
WEBHOOK_URL=https://yourdomain.com
WEBHOOK_PATH=/webhook
WEBHOOK_PORT=8080
WEBHOOK_SECRET=istalgan_maxfiy_string
```

`docker-compose.yml` da portni oching:

```yaml
ports:
  - "8080:8080"
```

va reverse-proxy (nginx / caddy) bilan HTTPS uloving.

---

## 📋 Buyruqlar

| Buyruq | Vazifa |
|--------|--------|
| `/start` | Botni ishga tushirish + asosiy menyu |
| `/menu` | Asosiy menyu |
| `/stats` | Shaxsiy statistika |
| `/leaderboard` | Top 10 reyting |
| `/reset` | Suhbat tarixini tozalash |
| `/cancel` | Joriy amalni bekor qilish |
| `/help` | Yordam |

---

## 🗂 Loyiha tuzilmasi

```
tg_bot_rus_tili/
├── bot.py                  # Kirish nuqtasi (polling/webhook)
├── config.py               # .env'dan settings dataclass
├── db.py                   # SQLite layer (aiosqlite)
├── states.py               # FSM bosqichlari
├── middlewares.py          # DI + throttling
├── prompts.py              # Barcha system promptlar (daraja-aware)
├── keyboards.py            # Inline klaviaturalar
├── ai_client.py            # OpenAI: chat / JSON / TTS / STT
├── scheduler.py            # Kunlik so'z planlovchisi
├── handlers/
│   ├── __init__.py         # Routerlarni yig'adi
│   ├── common.py           # /start, /menu, /help, /reset
│   ├── modes.py            # 6 ta o'rganish rejimi + TTS
│   ├── quiz.py             # Test rejimi
│   ├── voice.py            # Ovozli xabarlar (Whisper)
│   ├── settings_h.py       # Sozlamalar menyusi
│   └── stats.py            # /stats, /leaderboard
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 💡 Ishlash printsipi

1. **Foydalanuvchi qabul qilinadi:** har xabar oldidan `DBMiddleware` foydalanuvchini
   bazaga upsert qiladi va handler'ga `User` obyektini uzatadi.
2. **Throttling:** `ThrottlingMiddleware` har bir user uchun sekundiga 1 ta xabarni o'tkazadi.
3. **Rejim tanlanganda** FSM `ModeState.chatting` ga o'tadi va `mode` saqlanadi.
4. **Chat handler** SQLite'dagi oxirgi 12 ta xabarni kontekst sifatida oladi va
   tanlangan rejim + foydalanuvchi darajasiga mos system prompt bilan OpenAI'ga yuboradi.
5. **Quiz** OpenAI'dan JSON formatida 5 ta savol oladi (`response_format=json_object`),
   inline tugmalar bilan ko'rsatadi, ballarni saqlaydi.
6. **Voice** xabar — Whisper bilan transkripsiya qilinadi va xuddi matn kabi qayta ishlanadi.
7. **TTS tugmasi** — bot javobining ruscha qismini ajratib, OpenAI TTS orqali
   ovozli xabar sifatida qaytaradi.
8. **Kunlik so'z** — APScheduler har kuni belgilangan soatda obunachilarga JSON
   formatda generatsiya qilingan yangi so'z yuboradi.

---

## 🚀 Keyingi yaxshilanishlar (g'oyalar)

- Foydalanuvchining yangi o'rgangan so'zlarini bazada saqlash + Anki-stil takrorlash
- O'qigan so'zlarini eslatib turuvchi spaced repetition
- Webhook'da nginx + Let's Encrypt auto-config
- `pytest` testlari (db, prompts, keyboards uchun)
- PostgreSQL'ga migratsiya
- Multi-til UI (rus, qozoq, qirg'iz tillarini ham qo'shish)

---

## 📄 Litsenziya

MIT
