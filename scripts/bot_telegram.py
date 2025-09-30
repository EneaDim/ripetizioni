# Importa il modulo sqlite3 per gestire il database locale
import sqlite3

# Importa il modulo os per accedere a variabili d'ambiente e operazioni sul filesystem
import os

# Importa datetime per gestire date e orari
from datetime import datetime, timedelta, timezone

# Importa classi e funzioni da python-telegram-bot per creare bot Telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,                 # Istanza principale del bot
    CommandHandler,             # Gestore di comandi (/start, /adminslots, ecc.)
    CallbackQueryHandler,       # Gestore per pulsanti inline
    ConversationHandler,        # Gestore per flussi conversazionali
    ContextTypes,               # Tipi per il contesto
    filters,                    # Filtri per messaggi
)

# Funzione per fare escaping del Markdown v2
from telegram.helpers import escape_markdown

# Recupera il TOKEN del bot da variabile d'ambiente o usa un valore di default
TOKEN = os.getenv("TOKEN", "INSERISCI_IL_TUO_TOKEN")

# Recupera l'ID dell’amministratore da variabile d'ambiente o usa 0
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Percorso del file del database SQLite
DB_FILE = "data/bot_users.db"

# Stati della conversazione (per ConversationHandler)
CHOOSING_DATE, CHOOSING_TIME = range(2)

# Crea la cartella 'data' se non esiste
os.makedirs("data", exist_ok=True)

# ------------------------- DATABASE ---------------------------------

def init_db_and_populate_if_needed():
    """Inizializza il database e crea slot di prenotazione per i prossimi 5 anni."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Crea la tabella utenti, se non esiste
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id TEXT,
        first_name TEXT,
        last_name TEXT,
        username TEXT,
        created_at TEXT
    )
    """)

    # Crea la tabella prenotazioni, se non esiste
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        time TEXT,
        is_booked INTEGER DEFAULT 0,
        booked_by TEXT
    )
    """)

    conn.commit()

    # Verifica se ci sono già slot prenotabili
    cur.execute("SELECT COUNT(*) FROM bookings")
    count = cur.fetchone()[0]

    # Se nessuno slot esiste, popola il database con slot per 5 anni
    if count == 0:
        start_date = datetime.now()
        end_date = start_date + timedelta(days=365 * 5)
        orari = ["16:00", "17:00", "18:00", "19:00"]
        giorno = start_date
        while giorno <= end_date:
            if giorno.weekday() < 5:  # Solo giorni feriali
                for ora in orari:
                    cur.execute("""
                        INSERT INTO bookings (date, time, is_booked)
                        VALUES (?, ?, 0)
                    """, (giorno.strftime("%Y-%m-%d"), ora))
            giorno += timedelta(days=1)
        conn.commit()
    conn.close()

async def log_user(user):
    """Registra un nuovo utente nel database."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (telegram_id, first_name, last_name, username, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        str(user.id),
        user.first_name or "",
        user.last_name or "",
        user.username or "",
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()
    conn.close()

# --------------------- TASTIERE -------------------------------------

def main_menu_keyboard():
    """Tastiera inline con il solo menu principale."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Menu principale", callback_data="start")]
    ])

def full_menu_keyboard():
    """Tastiera completa con tutte le opzioni."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Materie disponibili", callback_data="materie")],
        [InlineKeyboardButton("ℹ️ Info e tariffe", callback_data="info")],
        [InlineKeyboardButton("🗓 Prenota lezione", callback_data="prenota")],
        [InlineKeyboardButton("❌ Cancella prenotazione", callback_data="cancella")],
        [InlineKeyboardButton("📜 Menu principale", callback_data="start")]
    ])

def info_prenota_keyboard():
    """Tastiera con info e prenota."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ℹ️ Info e tariffe", callback_data="info")],
        [InlineKeyboardButton("🗓 Prenota lezione", callback_data="prenota")],
        [InlineKeyboardButton("📜 Menu principale", callback_data="start")]
    ])

def prenota_only_keyboard():
    """Tastiera con solo prenotazione."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓 Prenota lezione", callback_data="prenota")],
        [InlineKeyboardButton("📜 Menu principale", callback_data="start")]
    ])

def inside_prenota_only_keyboard():
    """Tastiera per annullare prenotazioni."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancella prenotazione", callback_data="cancella")],
        [InlineKeyboardButton("📜 Menu principale", callback_data="start")]
    ])

# ------------------------- UTILS ------------------------------------

async def notify_admin(text, app: Application):
    """Invia un messaggio all’amministratore."""
    await app.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="MarkdownV2")

def escape_md(text: str) -> str:
    """Effettua escaping dei caratteri Markdown."""
    import re
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def build_welcome_message():
    welcome = (
        "👋 *Benvenuto\\!*\n"
        "\n"
        "🎵 Sono *Matteo Corazza*, *insegnante di musica* con esperienza nell'insegnamento di *chitarra* e *pianoforte*, "
        "appassionato di didattica su misura\\.\n"
        "\n"
        "💡 Offro *lezioni e coaching musicali personalizzati* in:\n"
        "• Chitarra \\(acustica ed elettrica\\)\n"
        "• Pianoforte \\(classico e moderno\\)\n"
        "• Teoria musicale, armonia, ear training\n"
        "\n"
        "🎉 *Prima lezione di prova gratuita* per conoscerci, e *sconti speciali* se porti un amico\\.\n"
        "\n"
        "📲 *Scegli qui sotto come iniziare:*"
    )
    keyboard = [
        [InlineKeyboardButton("📚 Materie disponibili", callback_data="materie")],
        [InlineKeyboardButton("ℹ️ Info e tariffe", callback_data="info")],
        [InlineKeyboardButton("🗓 Prenota lezione", callback_data="prenota")],
    ]
    return welcome, InlineKeyboardMarkup(keyboard)

#def build_welcome_message():
#    """Crea il messaggio di benvenuto e la tastiera iniziale."""
#    welcome = (
#        "👋 *Benvenuto\\!*\n"
#        "\n"
#        "🎓 Sono un *Ingegnere Elettronico Magistrale* con oltre *5 anni di esperienza industriale* e appassionato di didattica\\.\n"
#        "\n"
#        "💡 Offro *ripetizioni personalizzate* in:\n"
#        "• Matematica\n"
#        "• Informatica\n"
#        "• Elettronica\n"
#        "\n"
#        "🎉 *Prima ora gratuita* e *sconti per amici\\!*\n"
#        "\n"
#        "📲 *Scegli qui sotto come iniziare:*"
#    )
#    keyboard = [
#        [InlineKeyboardButton("📚 Materie disponibili", callback_data="materie")],
#        [InlineKeyboardButton("ℹ️ Info e tariffe", callback_data="info")],
#        [InlineKeyboardButton("🗓 Prenota lezione", callback_data="prenota")],
#    ]
#    return welcome, InlineKeyboardMarkup(keyboard)

# --------------------- HANDLER COMANDI ------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestore del comando /start o pulsante 'start'."""
    user = update.effective_user
    if update.message:
        await log_user(user)
        username = user.username or "-"
        escaped_username = escape_markdown(username, version=2)
        text = f"📥 Nuovo utente: `{user.id}` @{escaped_username}"
        await notify_admin(text, context.application)

    welcome, keyboard = build_welcome_message()
    await (update.message or update.callback_query.message).reply_text(
        welcome, parse_mode="MarkdownV2", reply_markup=keyboard
    )

async def admin_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra all’amministratore gli slot disponibili nei prossimi 10 giorni (escludendo sab e dom)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ Solo l’amministratore può usare questo comando.",
            reply_markup=main_menu_keyboard()
        )
        return

    oggi = datetime.today()
    limite = oggi + timedelta(days=10)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT date, time, is_booked FROM bookings
        WHERE date >= ? AND date <= ?
        AND strftime('%w', date) NOT IN ('0', '6')
        ORDER BY date ASC, time ASC
    """, (oggi.strftime("%Y-%m-%d"), limite.strftime("%Y-%m-%d")))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "ℹ️ Nessuno slot trovato.",
            reply_markup=main_menu_keyboard()
        )
        return

    output = ""
    current_date = ""
    for date, time, is_booked in rows:
        if date != current_date:
            output += f"\n📅 *{escape_md(date)}*\n"
            current_date = date
        status = "✅" if is_booked == 0 else "❌"
        output += f"{status} {escape_md(time)}\n"

    await update.message.reply_text(
        output,
        parse_mode="MarkdownV2",
        reply_markup=main_menu_keyboard()
    )

# ----------------- Conversazione prenotazioni -----------------------

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce i pulsanti inline del menu."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "materie":
        await query.message.reply_text(
            (
                "📚 *Corsi e competenze offerte\\:*\n\n"
                "✅ *Chitarra*\n"
                "  \\- Tecnica di base e avanzata \\(plettro, fingerstyle\\)\n"
                "  \\- Ritmica, accompagnamento e arpeggi\n"
                "  \\- Improvvisazione e linguaggio \\(rock, pop, blues, jazz\\)\n"
                "  \\- Lettura, tablature e studio del repertorio\n\n"
                "✅ *Pianoforte*\n"
                "  \\- Impostazione, tecnica e indipendenza delle mani\n"
                "  \\- Accompagnamento moderno e voicings\n"
                "  \\- Lettura, ear training e interpretazione\n"
                "  \\- Repertorio classico e contemporaneo\n\n"
                "✅ *Teoria & Musicianship*\n"
                "  \\- Teoria musicale di base e avanzata\n"
                "  \\- Armonia funzionale e moderna\n"
                "  \\- Ear training e solfeggio ritmico/melodico\n"
                "  \\- Scrittura, arrangiamento e basi di home recording\n\n"
                "📈 *Metodo personalizzato*: percorso su misura per principianti, intermedi e avanzati\n"
            ),
            parse_mode="MarkdownV2",
            reply_markup=info_prenota_keyboard()
        )
    elif data == "info":
        await query.message.reply_text(
            (
                "ℹ️ *Info & Tariffe\\:*\n\n"
                "💼 *Tariffa standard*: *50 CHF\\/ora*\n\n"
                "🎁 *Pacchetti risparmio*: \n"
                "  \\- 5 ore: 225 CHF \\(45 CHF\\/ora\\)\n"
                "  \\- 10 ore: 400 CHF \\(40 CHF\\/ora\\)\n\n"
                "📅 Lezioni in presenza a Mendrisio oppure online via Zoom\\/Teams\\.\n\n"
                "🔄 Possibilità di riprogrammare la lezione con almeno 24h di preavviso\\.\n\n"
                "💳 *Modalità di pagamento*: \n"
                "  \\- Contanti\n"
                "  \\- TWINT\n"
                "  \\- Bonifico bancario\n\n"
                "🎉 *Offerte speciali*: \n"
                "  \\- La *prima lezione di prova è gratuita*, senza impegno\\.\n"
                "  \\- Porta un amico e ottieni *\\-20% di sconto* sulla prossima lezione\\.\n\n"
                "📞 Per qualsiasi dubbio o esigenza particolare, scrivimi su Telegram\\.\n"
                "Sono a tua completa disposizione per costruire un percorso musicale efficace per te\\. 🎶"
            ),
            parse_mode="MarkdownV2",
            reply_markup=prenota_only_keyboard()
        )
    
    #if data == "materie":
    #    await query.message.reply_text(
    #        (
    #            "📚 *Materie e competenze offerte\\:*\n\n"
    #            "✅ *Matematica*\n"
    #            "  \\- Analisi matematica\n"
    #            "  \\- Algebra lineare e matrici\n"
    #            "  \\- Statistica e probabilità\n"
    #            "  \\- Matematica per l’ingegneria\n\n"
    #            "✅ *Informatica*\n"
    #            "  \\- Fondamenti di programmazione \\(C, Python\\)\n"
    #            "  \\- Strutture dati e algoritmi\n"
    #            "  \\- Sistemi operativi, basi di Linux\n"
    #            "  \\- Introduzione a microcontrollori, script e automazione\n\n"
    #            "✅ *Elettronica Digitale*\n"
    #            "  \\- Logiche combinatorie e sequenziali\n"
    #            "  \\- Flusso di progetto \\(ASIC\\-FPGA\\)\n"
    #            "  \\- Progetti su FPGA e microcontrollori\n"
    #            "  \\- Architetture di sistemi digitali e SoC\n"
    #            "  \\- Linguaggi HDL\\: VHDL, SystemVerilog\n\n"
    #            "✅ *Elettronica Analogica*\n"
    #            "  \\- Elettrotecnica\n"
    #            "  \\- Amplificatori operazionali e filtri\n"
    #            "  \\- Circuiti alimentatori e regolatori\n"
    #            "  \\- Simulazioni SPICE e analisi dei circuiti\n\n"
    #            "📈 *Metodo personalizzato*: lezioni su misura per le tue esigenze accademiche o professionali\n"
    #        ),
    #        parse_mode="MarkdownV2",
    #        reply_markup=info_prenota_keyboard()
    #    )
    #elif data == "info":
    #    await query.message.reply_text(
    #        (
    #            "ℹ️ *Info & Tariffe\\:*\n\n"
    #            "💼 *Tariffa standard*: *50 CHF\\/ora*\n\n"
    #            "🎁 *Pacchetti risparmio*: \n"
    #            "  \\- 5 ore: 225 CHF \\(45 CHF\\/ora\\)\n"
    #            "  \\- 10 ore: 400 CHF \\(40 CHF\\/ora\\)\n\n"
    #            "📅 Lezioni in presenza a Mendrisio oppure online via Zoom\\/Teams\\.\n\n"
    #            "🔄 Possibilità di riprogrammare la lezione con almeno 24h di preavviso\\.\n\n"
    #            "💳 *Modalità di pagamento*: \n"
    #            "  \\- Contanti\n"
    #            "  \\- TWINT\n"
    #            "  \\- Bonifico bancario\n\n"
    #            "🎉 *Offerte speciali*: \n"
    #            "  \\- La *prima ora è gratuita*, senza impegno\\.\n"
    #            "  \\- Porta un amico e ottieni *\\-20% di sconto* sulla prossima lezione\\.\n\n"
    #            "📞 Per qualsiasi dubbio o esigenza particolare, [scrivimi direttamente qui](https://t.me/eneadim)\\!\n"
    #            "Sono a tua completa disposizione per costruire un piano che funzioni per te\\. 🚀"
    #        ),
    #        parse_mode="MarkdownV2",
    #        reply_markup=prenota_only_keyboard()
    #    )
    elif data == "prenota":
        await start_booking(update, context)
    elif data == "start":
        await start(update, context)

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Avvia la conversazione per prenotare una lezione (escludendo sab e dom)."""
    query = update.callback_query
    await query.answer()

    today = datetime.today()
    keyboard, row = [], []

    # Genera i prossimi 7 giorni, ma solo giorni feriali
    days_added = 0
    day_offset = 0
    while days_added < 7:
        day = today + timedelta(days=day_offset)
        day_offset += 1

        if day.weekday() >= 5:  # 5 = sabato, 6 = domenica → salta
            continue

        label = day.strftime("%a %d/%m")
        callback = f"date_{day.strftime('%Y-%m-%d')}"
        row.append(InlineKeyboardButton(label, callback_data=callback))

        if len(row) == 3:
            keyboard.append(row)
            row = []
        days_added += 1

    if row:
        keyboard.append(row)

    # Aggiungi i pulsanti extra sotto
    keyboard += [
        [InlineKeyboardButton("❌ Cancella prenotazione", callback_data="cancella")],
        [InlineKeyboardButton("📜 Menu principale", callback_data="start")]
    ]

    await query.message.reply_text(
        escape_md("🗓 Scegli una data disponibile:"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="MarkdownV2"
    )
    return CHOOSING_DATE

async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra gli orari disponibili per la data scelta."""
    query = update.callback_query
    await query.answer()
    chosen_date = query.data.replace("date_", "")
    context.user_data["chosen_date"] = chosen_date

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT time FROM bookings WHERE date = ? AND is_booked = 0", (chosen_date,))
    slots = [row[0] for row in cur.fetchall()]
    conn.close()

    if not slots:
        await query.edit_message_text(f"⛔ Nessuno slot disponibile per il {chosen_date}.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(time, callback_data=f"time_{time}")] for time in slots]
    await query.edit_message_text(
        escape_md(f"🕒 Scegli un orario per il {chosen_date}:"),
        reply_markup=InlineKeyboardMarkup(keyboard +
                                          [[InlineKeyboardButton("❌ Cancella prenotazione", callback_data="cancella")],
                                          [InlineKeyboardButton("📜 Menu principale", callback_data="start")]]),
        parse_mode="MarkdownV2"
    )
    return CHOOSING_TIME


async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra le prenotazioni attive da cancellare."""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    # Recupera le prenotazioni dell'utente
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        SELECT date, time FROM bookings 
        WHERE is_booked = 1 AND booked_by = ?
        ORDER BY date ASC, time ASC
    """, (str(user_id),))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await query.message.reply_text(
            "ℹ️ Non risultano prenotazioni attive.",
            reply_markup=main_menu_keyboard()
        )
        return

    keyboard = []
    for date, time in rows:
        label = f"{date} {time}"
        callback = f"cancel_{date}_{time.replace(':', '-')}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    keyboard.append([InlineKeyboardButton("📜 Menu principale", callback_data="start")])

    await query.message.reply_text(
        escape_md("❌ Seleziona la prenotazione da cancellare:"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="MarkdownV2"
    )

async def confirm_cancellation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chiede conferma per la cancellazione della prenotazione."""
    query = update.callback_query
    await query.answer()

    data = query.data.replace("cancel_", "")
    date_str, time_str = data.rsplit("_", 1)
    time_str = time_str.replace("-", ":")

    text = escape_md(
        f"⚠️ Sei sicuro di voler cancellare la prenotazione per il {date_str} alle {time_str}?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Conferma", callback_data=f"confirm_{data}")],
        [InlineKeyboardButton("🔙 Annulla", callback_data="cancella")]
    ])

    await query.edit_message_text(
        text, parse_mode="MarkdownV2", reply_markup=keyboard
    )

async def do_cancellation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Esegue la cancellazione della prenotazione nel database."""
    query = update.callback_query
    await query.answer()

    data = query.data.replace("confirm_", "")
    date_str, time_str = data.rsplit("_", 1)
    time_str = time_str.replace("-", ":")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        UPDATE bookings SET is_booked = 0, booked_by = NULL
        WHERE date = ? AND time = ? AND booked_by = ?
    """, (date_str, time_str, str(query.from_user.id)))
    conn.commit()
    conn.close()

    await query.edit_message_text(
        escape_md(f"✅ Prenotazione cancellata per il {date_str} alle {time_str}."),
        parse_mode="MarkdownV2",
        reply_markup=main_menu_keyboard()
    )

    await notify_admin(
        escape_md(f"❌ Prenotazione cancellata:\nData: {date_str}\nOra: {time_str}\nUtente: {query.from_user.id} @{query.from_user.username or '-'}"),
        context.application
    )

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Conferma la prenotazione e salva nel database."""
    query = update.callback_query
    await query.answer()
    chosen_time = query.data.replace("time_", "")
    chosen_date = context.user_data.get("chosen_date")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        UPDATE bookings SET is_booked = 1, booked_by = ?
        WHERE date = ? AND time = ? AND is_booked = 0
    """, (str(query.from_user.id), chosen_date, chosen_time))
    conn.commit()
    conn.close()

    await query.edit_message_text(
        escape_md(f"✅ Prenotato per {chosen_date} alle {chosen_time}. Ti confermerò appena possibile!"),
        parse_mode="MarkdownV2",
        reply_markup=main_menu_keyboard()
    )
    await notify_admin(
        escape_md(f"🗓 Nuova prenotazione:\nData: {chosen_date}\nOra: {chosen_time}\nUtente: {query.from_user.id} @{query.from_user.username or '-'}"),
        context.application
    )
    return ConversationHandler.END

# ------------------------- MAIN -------------------------------------

def main():
    """Avvia il bot."""
    app = Application.builder().token(TOKEN).build()

    # Definisce il ConversationHandler per le prenotazioni
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_booking, pattern="prenota")],
        states={
            CHOOSING_DATE: [CallbackQueryHandler(choose_time, pattern=r"date_.*")],
            CHOOSING_TIME: [CallbackQueryHandler(confirm_booking, pattern=r"time_.*")],
        },
        fallbacks=[],
        per_message=False
    )

    # Aggiunge gli handler
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("adminslots", admin_slots))
    app.add_handler(CallbackQueryHandler(cancel_booking, pattern="cancella"))
    app.add_handler(CallbackQueryHandler(confirm_cancellation, pattern=r"cancel_.*"))
    app.add_handler(CallbackQueryHandler(do_cancellation, pattern=r"confirm_.*"))
    app.add_handler(CallbackQueryHandler(button))

    # Inizializza il database
    init_db_and_populate_if_needed()

    print("🤖 Bot in esecuzione…")
    if os.getenv("RAILWAY") == "1":
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8080)),
            url_path=TOKEN,
            webhook_url=f"ripetizioni-production.up.railway.app/{TOKEN}"
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
