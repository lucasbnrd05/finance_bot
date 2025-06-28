# bot.py
import telebot
from telebot import apihelper, types # types pour les boutons potentiels futurs
import os
import time
import schedule
import threading
from dotenv import load_dotenv
import google.generativeai as genai
import sys # Pour sys.exit()
import json # Pour la persistance

from financial_data import (
    get_selected_items_formatted,
    get_detailed_stock_data,
    get_company_officers
)

# --- Configuration & Chargement Clés ---
load_dotenv()
TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 0))

if not TELEGRAM_API_KEY:
    print("Erreur: TELEGRAM_API_KEY non trouvé.")
    sys.exit(1)

bot = telebot.TeleBot(TELEGRAM_API_KEY, parse_mode="Markdown")

# --- Configuration Gemini ---
gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Utiliser un modèle rapide pour les réponses interactives
        gemini_model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
        print("Modèle Gemini configuré (gemini-1.5-flash-latest).")
    except Exception as e:
        print(f"Erreur config Gemini: {e}")
else:
    print("Avertissement: GEMINI_API_KEY non configuré. IA désactivée.")

# --- Persistance des Abonnements ---
subscribed_chats = set()
PERSISTENCE_FILE = "subscribed_chats.json"

def load_subscriptions():
    global subscribed_chats
    if os.path.exists(PERSISTENCE_FILE):
        try:
            with open(PERSISTENCE_FILE, 'r') as f:
                subscribed_chats = set(json.load(f))
            print(f"Abonnements chargés: {len(subscribed_chats)}.")
        except json.JSONDecodeError:
            print(f"Erreur décodage JSON dans {PERSISTENCE_FILE}. Fichier ignoré/sera écrasé.")
            subscribed_chats = set()
        except Exception as e:
            print(f"Erreur chargement abonnements: {e}")
    else:
        print("Aucun fichier d'abonnements trouvé. Démarrage avec une liste vide.")

def save_subscriptions():
    try:
        with open(PERSISTENCE_FILE, 'w') as f:
            json.dump(list(subscribed_chats), f)
    except Exception as e:
        print(f"Erreur sauvegarde abonnements: {e}")

# --- Contrôle d'Arrêt du Bot ---
stop_event = threading.Event() # Pour signaler l'arrêt propre

# --- Décorateur pour restreindre aux propriétaires ---
def owner_only(func):
    def wrapper(message):
        if BOT_OWNER_ID == 0: # Si non configuré, ne pas restreindre pour dev facile
             print("BOT_OWNER_ID non configuré. Commande non restreinte.")
        elif message.from_user.id != BOT_OWNER_ID:
            bot.reply_to(message, "🚫 Commande réservée au propriétaire du bot.")
            return
        return func(message)
    return wrapper

# --- Helper Function for simulated clear ---
def simulate_clear_chat_and_welcome(message):
    """
    Simule un nettoyage du chat en envoyant des lignes vides,
    puis renvoie le message de bienvenue.
    """
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing') # Indiquer une action

    # Envoyer un message de "nettoyage"
    # Vous pouvez ajuster le nombre de lignes vides.
    # Telegram a des limites sur la fréquence d'envoi, donc trop de messages rapides peuvent être un problème.
    # Une alternative est un seul long message avec beaucoup de sauts de ligne.
    clear_message_text = "Nettoyage de l'affichage en cours...\n" + ("\n" * 50) # 50 sauts de ligne
    
    # Pour éviter de potentiellement dépasser la limite de caractères d'un seul message
    # avec trop de sauts de ligne, on envoie un message puis le message de bienvenue.
    # Une autre approche serait d'envoyer plusieurs petits messages de sauts de ligne,
    # mais cela peut être plus lent et plus sujet au rate limiting.

    # Option 1: Envoyer un message qui pousse le contenu vers le haut
    try:
        # Tenter de supprimer le message de commande /clear de l'utilisateur
        # Cela ne fonctionne que si le bot a les droits d'admin dans un groupe
        # et que le message n'est pas trop vieux. Dans un chat privé, ça ne marche pas.
        # bot.delete_message(chat_id, message.message_id)
        
        # Envoyer le message de "nettoyage"
        # msg_to_delete = bot.send_message(chat_id, "🧹 Nettoyage de l'affichage...")
        # time.sleep(0.5) # Petit délai
        # bot.delete_message(chat_id, msg_to_delete.message_id) # Supprimer notre propre message de nettoyage
                                                            # pour que ce soit plus propre.
                                                            # Fonctionne car c'est notre message récent.
        
        # Alternative plus simple: juste envoyer les sauts de ligne
        bot.send_message(chat_id, "🧹") # Un emoji pour marquer le "clear"
        bot.send_message(chat_id, "\n" * 30,disable_notification=True) # Beaucoup de sauts de ligne
                                                                  # disable_notification pour être discret

    except Exception as e:
        print(f"Erreur mineure lors de la tentative de nettoyage simulé: {e}")
        # Continuer même si la suppression ou l'envoi du message de nettoyage échoue

    # Renvoyer le message de bienvenue
    send_welcome(message, is_clear_command=True) # Passer un flag pour ajuster la réponse si besoin


# --- Commandes du Bot ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome_handler(message): # Renommer pour éviter conflit de nom si appelé directement
    send_welcome(message, is_clear_command=False)

# Cette fonction sera maintenant appelée par /start, /help ET /clear (via simulate_clear_chat_and_welcome)
def send_welcome(message, is_clear_command=False): # Ajout du paramètre is_clear_command
    global BOT_OWNER_ID # Si vous définissez un owner_id
    if BOT_OWNER_ID == 0 and message.from_user.id and not is_clear_command: # Enregistrer l'ID du premier utilisateur comme propriétaire potentiel
        print(f"Conseil: Pour la commande /stop, définissez BOT_OWNER_ID={message.from_user.id} dans votre .env")

    disclaimer_lt_score = "⚠️ _Le 'Score Potentiel LT' est une HEURISTIQUE hautement simplifiée et expérimentale. Il ne constitue PAS un conseil financier. Faites TOUJOURS vos propres recherches approfondies._"
    
    # Message initial différent si c'est après un /clear
    if is_clear_command:
        intro_message = "Affichage réinitialisé. Commandes disponibles :\n"
    else:
        intro_message = "🤖 Assistant d'Information Financière Personnel (Usage Privé)\n\n**Commandes Disponibles :**\n"

    welcome_text_core = (
        "/longterm : ETFs & Actions triés par Score Potentiel LT.\n"
        "/longtermetf : ETFs triés par Score Potentiel LT.\n"
        "/longtermact : Actions triées par Score Potentiel LT.\n"
        "\n/list : Listes sélectionnées (non triées par score).\n"
        "/detail `<TICKER>` : Infos détaillées (ex: `/detail AAPL`).\n"
        "/officers `<TICKER>` : Dirigeants (ex: `/officers MSFT`).\n"
        "\n/info : S'abonner/Se désabonner aux màj (12h).\n"
        "/status : Statut de l'abonnement.\n"
        "/ask `<question>` : Question à l'IA (Gemini).\n"
        "/clear : Réinitialise l'affichage et montre ce message.\n" # Ajout de /clear ici
        f"\n{disclaimer_lt_score}"
    )
    if BOT_OWNER_ID != 0:
        welcome_text_core += "\n/stop : Arrête le bot (propriétaire uniquement)."

    full_welcome_text = intro_message + welcome_text_core

    # Utiliser bot.send_message au lieu de bot.reply_to pour /clear,
    # car le message original /clear pourrait être "loin" en haut.
    if is_clear_command:
        bot.send_message(message.chat.id, full_welcome_text)
    else:
        bot.reply_to(message, full_welcome_text)

@bot.message_handler(commands=['clear'])
def handle_clear_command(message):
    bot.send_chat_action(message.chat.id, 'typing')
    simulate_clear_chat_and_welcome(message)

@bot.message_handler(commands=['stop'])
@owner_only # Restreint cette commande
def stop_bot_command(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, "⏳ Arrêt du bot en cours...")
    print(f"Arrêt du bot initié par le propriétaire (ID: {message.from_user.id}).")
    stop_event.set() # Signale aux threads (scheduler) de s'arrêter
    
    # Arrêter le polling de Telebot
    # Cela peut prendre quelques secondes pour que le thread de polling se termine
    bot.stop_polling()
    print("Polling de Telebot arrêté.")

    # Il n'est généralement pas nécessaire de faire os._exit(0) si les threads sont bien gérés (daemon=True)
    # et que le thread principal (celui de infinity_polling) se termine.
    # La boucle principale du script se terminera après que bot.stop_polling() ait fait effet.

def send_financial_list(message, item_type=None, sort_by_score=True, score_type="long_term", limit=7):
    """Fonction helper pour envoyer les listes financières."""
    bot.send_chat_action(message.chat.id, 'typing')
    
    text_parts = []
    if item_type is None or item_type.upper() == "ETF":
        text_parts.append(get_selected_items_formatted(item_type="ETF", limit=limit, sort_by_score=sort_by_score, score_type=score_type))
    
    if item_type is None or item_type.upper() == "ACTION":
        text_parts.append(get_selected_items_formatted(item_type="ACTION", limit=limit, sort_by_score=sort_by_score, score_type=score_type))
    
    full_text = "\n\n".join(text_parts)
    
    disclaimer_lt_score = "\n\n⚠️ _Score Potentiel LT expérimental. Non un conseil._"
    if sort_by_score and score_type == "long_term":
        full_text += disclaimer_lt_score

    try:
        # Gérer les messages trop longs en les divisant
        if len(full_text) > 4096:
            bot.reply_to(message, "Les informations combinées sont très longues.")
            if item_type is None: # Si on demandait les deux
                bot.send_message(message.chat.id, text_parts[0] + (disclaimer_lt_score if sort_by_score and score_type == "long_term" else ""))
                time.sleep(0.5) # Petit délai
                bot.send_message(message.chat.id, text_parts[1] + (disclaimer_lt_score if sort_by_score and score_type == "long_term" else ""))
            else: # Si on demandait un seul type mais qu'il est trop long (peu probable avec limit=7)
                 bot.send_message(message.chat.id, "Informations trop longues, affichage partiel.")
        else:
            bot.reply_to(message, full_text)
    except apihelper.ApiTelegramException as e:
        print(f"Erreur API Telegram (send_financial_list): {e}")
        bot.reply_to(message, "Une erreur est survenue lors de l'affichage des listes.")

@bot.message_handler(commands=['longterm'])
def send_longterm_all(message):
    send_financial_list(message, item_type=None, sort_by_score=True, score_type="long_term", limit=7)

@bot.message_handler(commands=['longtermetf'])
def send_longterm_etf(message):
    send_financial_list(message, item_type="ETF", sort_by_score=True, score_type="long_term", limit=10)

@bot.message_handler(commands=['longtermact'])
def send_longterm_action(message):
    send_financial_list(message, item_type="ACTION", sort_by_score=True, score_type="long_term", limit=10)

@bot.message_handler(commands=['list']) # Listes non triées par score
def send_list_all_no_sort(message):
    send_financial_list(message, item_type=None, sort_by_score=False, limit=10)

# --- Handlers /detail, /officers, /info, /status, /ask (globalement inchangés) ---
@bot.message_handler(commands=['detail'])
def send_detailed_financial_info_handler(message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "Usage: `/detail <TICKER>`")
            return
        ticker_symbol = parts[1].strip().upper()
    except IndexError:
        bot.reply_to(message, "Format incorrect. Usage: `/detail <TICKER>`")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    data = get_detailed_stock_data(ticker_symbol)

    if data.get("error"):
        bot.reply_to(message, data["error"])
        return

    response_parts = [f"🔍 **Détails pour {data.get('shortName', ticker_symbol)} ({ticker_symbol})**\n"]
    def add_info(label, value, is_price=False, is_percent=False, is_large_number=False):
        if value is not None and str(value).strip() != "":
            val_str = str(value)
            if isinstance(value, str): response_parts.append(f"_{label}_: {val_str}\n")
            elif is_price: response_parts.append(f"_{label}_: {float(val_str):.2f} {data.get('currency', '')}\n")
            elif is_percent: response_parts.append(f"_{label}_: {float(val_str)*100:.2f}%\n")
            elif is_large_number: response_parts.append(f"_{label}_: {int(float(val_str)):,}\n") # int() pour enlever .0 potentiel
            else: response_parts.append(f"_{label}_: {val_str}\n")
    
    add_info("Nom", data.get('longName'))
    add_info("Prix", data.get('currentPrice'), is_price=True)
    add_info("Clôture Préc.", data.get('previousClose'), is_price=True)
    if data.get('regularMarketChange') is not None and data.get('regularMarketChangePercent') is not None:
        change, change_pct = data.get('regularMarketChange'), data.get('regularMarketChangePercent') * 100
        response_parts.append(f"_Changement_: {change:+.2f} {data.get('currency', '')} ({change_pct:+.2f}%)\n")
    add_info("Capitalisation", data.get('marketCap'), is_large_number=True)
    add_info("Secteur", data.get('sector')); add_info("Industrie", data.get('industry'))
    add_info("P/E (TTM)", data.get('trailingPE')); add_info("P/E (Fwd)", data.get('forwardPE'))
    add_info("Rdt Div.", data.get('dividendYield'), is_percent=True)
    add_info("Site Web", data.get('website'))
    
    response_text = "".join(response_parts)
    if data.get('longBusinessSummary'):
        summary = data['longBusinessSummary']
        response_text += f"\n**Résumé Activité:**\n{summary[:1000]}"
        if len(summary) > 1000: response_text += "..."

    if len(response_text) > 4096:
        bot.reply_to(message, "Infos trop longues. Affichage des principaux éléments:\n" + "".join(response_parts[:8]))
    else:
        bot.reply_to(message, response_text)

@bot.message_handler(commands=['officers'])
def send_officers_info_handler(message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "Usage: `/officers <TICKER>`")
            return
        ticker_symbol = parts[1].strip().upper()
    except IndexError:
        bot.reply_to(message, "Format incorrect. Usage: `/officers <TICKER>`")
        return
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, get_company_officers(ticker_symbol))

@bot.message_handler(commands=['info'])
def toggle_info_subscription_handler(message):
    chat_id = message.chat.id
    if chat_id in subscribed_chats:
        subscribed_chats.remove(chat_id)
        bot.reply_to(message, "✅ Désabonné des infos périodiques.")
    else:
        subscribed_chats.add(chat_id)
        bot.reply_to(message, "✅ Abonné aux infos périodiques (toutes les 12h)!")
    save_subscriptions()

@bot.message_handler(commands=['status'])
def send_status_handler(message):
    status_msg = "✅ Abonné aux infos périodiques." if message.chat.id in subscribed_chats else "❌ Non abonné. Utilisez /info."
    bot.reply_to(message, status_msg)

@bot.message_handler(commands=['ask'])
def ask_gemini_handler(message):
    if not gemini_model:
        bot.reply_to(message, "🤖 IA (Gemini) non disponible actuellement.")
        return
    
    prompt = message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1)) > 1 else ""
    if not prompt.strip():
        bot.reply_to(message, "Veuillez poser une question après /ask.\nEx: `/ask Perspectives du secteur des semi-conducteurs ?`")
        return

    disclaimer_ia = "\n\n🧠 _Réponse IA (Gemini). Info générale, pas un conseil financier. Vérifiez toujours._"
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        # Pour une question financière, il est bon de guider Gemini
        contextual_prompt = (f"En tant qu'assistant d'information financière pour un usage personnel, "
                             f"fournis une analyse concise et informative sur la question suivante, "
                             f"en te basant sur des connaissances générales publiques. "
                             f"Évite les conseils d'investissement directs ou les prédictions spéculatives. "
                             f"Question: {prompt}")
        response = gemini_model.generate_content(contextual_prompt)
        response_text = response.text + disclaimer_ia
        
        # Gestion des messages longs
        if len(response_text) > 4096:
            for i in range(0, len(response_text), 4090): # Laisse une petite marge
                bot.send_message(message.chat.id, response_text[i:i+4090])
        else:
            bot.reply_to(message, response_text)
    except Exception as e:
        print(f"Erreur Gemini: {e}")
        bot.reply_to(message, f"🤖 Oups! Erreur en contactant l'IA. {disclaimer_ia}")

# --- Tâches Planifiées ---
def send_scheduled_info_to_chat(chat_id):
    if stop_event.is_set(): return # Ne rien faire si arrêt demandé
    try:
        print(f"Envoi infos planifiées à {chat_id}")
        # Pour les updates, on peut utiliser le score LT ou des listes non triées plus courtes
        etfs_text = get_selected_items_formatted(item_type="ETF", limit=5, sort_by_score=True, score_type="long_term")
        actions_text = get_selected_items_formatted(item_type="ACTION", limit=5, sort_by_score=True, score_type="long_term")
        update_text = (
            f"🔔 **Votre Point Financier Périodique** 🔔\n\n"
            f"{etfs_text}\n\n{actions_text}\n\n"
            f"_Prochaine mise à jour dans ~12h. Score LT expérimental._"
        )
        bot.send_message(chat_id, update_text)
    except apihelper.ApiTelegramException as e:
        print(f"Erreur API Telegram (envoi planifié) pour {chat_id}: {e}")
        if e.error_code == 403: # Forbidden: bot blocked
           if chat_id in subscribed_chats:
               subscribed_chats.remove(chat_id)
               save_subscriptions()
               print(f"Chat {chat_id} désabonné (bot bloqué).")
    except Exception as e:
        print(f"Erreur générique (envoi planifié) pour {chat_id}: {e}")

def job_send_periodic_info():
    if stop_event.is_set(): return
    if not subscribed_chats: return
    print(f"Tâche planifiée: Envoi infos à {len(subscribed_chats)} abonné(s).")
    for chat_id in list(subscribed_chats):
        if stop_event.is_set(): break # Vérifier avant chaque envoi
        send_scheduled_info_to_chat(chat_id)
        time.sleep(2) # Éviter rate limiting (augmenté un peu)

def run_scheduler():
    # schedule.every(1).minutes.do(job_send_periodic_info) # Pour test rapide
    schedule.every(12).hours.do(job_send_periodic_info)
    # schedule.every().day.at("08:00").do(job_send_periodic_info) # Ex: tous les jours à 8h

    while not stop_event.is_set():
        schedule.run_pending()
        time.sleep(20) # Vérifier toutes les 20 secondes si arrêt demandé
    print("Thread du planificateur arrêté.")

# --- Démarrage & Arrêt du Bot ---
if __name__ == '__main__':
    load_subscriptions()
    print(f"Démarrage du bot... Propriétaire ID configuré: {BOT_OWNER_ID if BOT_OWNER_ID else 'Non (commandes admin désactivées)'}")

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True) # daemon=True permet au thread de se fermer avec le principal
    scheduler_thread.start()
    print("Planificateur de tâches démarré.")

    print("Bot en écoute des messages (Ctrl+C pour arrêter)...")
    try:
        # infinity_polling va bloquer ici jusqu'à ce que stop_polling soit appelé ou une erreur survienne
        bot.infinity_polling(skip_pending=True,none_stop=False, timeout=30, long_polling_timeout = 20) # none_stop pour Ctrl+C
    except KeyboardInterrupt:
        print("Arrêt demandé par Ctrl+C.")
        stop_event.set() # Signaler aux autres threads
        bot.stop_polling()
    except Exception as e:
        print(f"Erreur critique du bot: {e}")
        stop_event.set()
        bot.stop_polling()
    finally:
        print("Nettoyage avant l'arrêt...")
        # Attendre que le scheduler thread se termine s'il n'est pas daemon ou si on veut être sûr
        if scheduler_thread.is_alive():
             print("Attente de l'arrêt du planificateur...")
             scheduler_thread.join(timeout=5) # Attendre max 5 sec
        
        save_subscriptions() # Sauvegarder une dernière fois
        print("Bot arrêté.")
        # sys.exit(0) # Assure que le script se termine complètement