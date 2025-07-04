# --- COLORI ---
ORANGE=\033[38;5;208m
NC=\033[0m

# --- VARIABILI ---
# Carica le variabili da .env se esiste
ifneq (,$(wildcard .env))
	include .env
	export
endif
VENV_DIR=.venv
DB_FILE=data/bot_users.db
SCRIPT=scripts/bot_telegram.py

# --- TARGETS ---

help:
	@echo ""
	@echo "$(ORANGE)Usage: make [target]$(NC)"
	@echo ""
	@echo "$(ORANGE)Targets:$(NC)"
	@echo "  help           Mostra questo messaggio"
	@echo "  init           Crea .venv, installa pacchetti, prepara cartella data/"
	@echo "  venv           Attiva l'ambiente virtuale"
	@echo "  freeze         Aggiorna requirements.txt"
	@echo "  bot            Avvia bot Telegram con TOKEN e ADMIN_CHAT_ID"
	@echo "  clean          Pulisce tutto: __pycache__, *.pyc, DB"
	@echo "  clean-pyc      Rimuove solo file Python compilati"
	@echo "  clean-db       Rimuove il database utenti"
	@echo ""

init:
	@echo "$(ORANGE)🔧 Inizializzazione progetto...$(NC)"
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(ORANGE)📦 Creo ambiente virtuale $(VENV_DIR)$(NC)"; \
		python3 -m venv $(VENV_DIR); \
	fi
	@echo "$(ORANGE)📥 Attivo $(VENV_DIR) e installo dipendenze$(NC)"
	@. $(VENV_DIR)/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@mkdir -p data scripts && touch scripts/__init__.py
	@echo "$(ORANGE)✅ Setup completato$(NC)"

venv:
	@echo "$(ORANGE)✨ Attiva ambiente virtuale con:$(NC)"
	@echo "source $(VENV_DIR)/bin/activate"

freeze:
	@echo "$(ORANGE)📦 Aggiorno requirements.txt$(NC)"
	@. $(VENV_DIR)/bin/activate && pip freeze > requirements.txt

bot:
	@echo "$(ORANGE)🤖 Avvio bot Telegram$(NC)"
	TOKEN=$(TOKEN) ADMIN_CHAT_ID=$(ADMIN_CHAT_ID) $(VENV_DIR)/bin/python3 $(SCRIPT)

clean:
	@echo "$(ORANGE)🧹 Pulizia completa$(NC)"
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type f -name '*.pyc' -delete
	rm -rf $(DB_FILE)
	@echo "$(ORANGE)✅ Clean completato$(NC)"

clean-pyc:
	@echo "$(ORANGE)🧹 Rimuovo __pycache__ e *.pyc$(NC)"
	find . -type d -name '__pycache__' -exec rm -r {} +
	find . -type f -name '*.pyc' -delete

clean-db:
	@echo "$(ORANGE)🗑️ Rimuovo file database ($(DB_FILE))$(NC)"
	rm -f $(DB_FILE)

