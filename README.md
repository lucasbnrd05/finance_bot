# Bot d'Investissement Telegram

Ce projet est un bot Telegram personnel conçu pour fournir des informations financières sur les actions et les ETFs. Il intègre l'API de `yfinance` pour les données de marché et l'API Google Gemini pour répondre à des questions ouvertes.

Le bot est capable de :
- Afficher des listes d'actions et d'ETFs.
- Calculer et trier les actifs selon un **score de potentiel à long terme heuristique et expérimental**.
- Fournir des détails complets sur un ticker spécifique.
- Lister les dirigeants d'une entreprise.
- Gérer un système d'abonnement pour des mises à jour périodiques.
- Répondre à des questions financières générales grâce à l'IA de Google Gemini.

---

## Exemple d'Interaction

  <!-- Vous pouvez remplacer ce lien par une capture d'écran réelle -->

```
Vous: /longterm

Bot: 🤖 Assistant d'Information Financière Personnel (Usage Privé)

📊 **Actions par Potentiel LT (Score Desc.):**
Apple Inc (AAPL): 175.53 USD (+1.50 USD, +0.86%) (Score LT: 8.7)
Microsoft Corp (MSFT): 427.00 USD (-2.80 USD, -0.65%) (Score LT: 8.5)
...

📈 **ETFs par Potentiel LT (Score Desc.):**
SPDR S&P 500 ETF (SPY): 520.45 USD (+3.20 USD, +0.62%) (Score LT: 7.9)
Invesco QQQ Trust (QQQ): 440.15 USD (+2.10 USD, +0.48%) (Score LT: 7.8)
...

⚠️ _Score Potentiel LT expérimental. Non un conseil._

Vous: /detail LVMH.PA

Bot: 🔍 **Détails pour LVMH Moet Hennessy Louis Vuitton SE (LVMH.PA)**
_Nom_: LVMH Moet Hennessy Louis Vuitton SE
_Prix_: 730.50 EUR
_Clôture Préc._: 725.10 EUR
_Changement_: +5.40 EUR (+0.74%)
...

Vous: /ask Quelles sont les perspectives pour l'intelligence artificielle en 2024 ?

Bot: 🧠 _Réponse IA (Gemini). Info générale, pas un conseil financier. Vérifiez toujours._
En 2024, le secteur de l'intelligence artificielle continue de montrer une croissance explosive, principalement tirée par les avancées dans les modèles de langage (LLMs) et l'IA générative...
```

---

## Fonctionnalités (Commandes)

*   `/start`, `/help` : Affiche le message de bienvenue et la liste des commandes.
*   `/clear` : "Nettoie" l'affichage en envoyant des sauts de ligne et ré-affiche le message d'aide.
*   `/longterm` : Affiche les listes d'actions et d'ETFs les mieux classés par le score de potentiel à long terme.
*   `/longtermetf` : Affiche uniquement les ETFs, classés par score.
*   `/longtermact` : Affiche uniquement les actions, classées par score.
*   `/list` : Affiche les listes de suivi par défaut, sans classement par score.
*   `/detail <TICKER>` : Fournit des informations détaillées pour un symbole boursier (ex: `/detail AAPL`).
*   `/officers <TICKER>` : Affiche la liste des dirigeants de l'entreprise (ex: `/officers MSFT`).
*   `/ask <question>` : Pose une question à l'IA (Google Gemini).
*   `/info` : S'abonne ou se désabonne des rapports périodiques (envoyés toutes les 12 heures).
*   `/status` : Vérifie le statut de votre abonnement.
*   `/stop` : Arrête le bot (commande réservée au propriétaire).

---

## Installation et Configuration

### 1. Prérequis
- Python 3.8 ou plus récent.
- Un compte Telegram et un bot créé via [BotFather](https://core.telegram.org/bots#botfather).
- Une clé d'API pour [Google AI Studio (Gemini)](https://makersuite.google.com/app/apikey).

### 2. Cloner le projet
```bash
git clone https://github.com/lucasbnrd05/finance_bot.git
cd finance_bot
```

### 3. Créer un environnement virtuel et installer les dépendances
Il est fortement recommandé d'utiliser un environnement virtuel.

```bash
# Créer l'environnement
python -m venv venv

# Activer l'environnement
# Sur Windows:
venv\Scripts\activate
# Sur macOS/Linux:
source venv/bin/activate

# Installer les paquets nécessaires
pip install py-telegram-bot-api python-dotenv google-generativeai schedule yfinance pandas numpy
```

### 4. Configurer les variables d'environnement
Créez un fichier nommé `.env` à la racine du projet en copiant le modèle ci-dessous. **Ce fichier est ignoré par Git pour protéger vos clés.**

```dotenv
# .env

# Clé API de votre bot Telegram obtenue depuis BotFather
TELEGRAM_API_KEY="VOTRE_CLE_TELEGRAM_ICI"

# Clé API pour Google Gemini (obtenue depuis Google AI Studio)
# Optionnelle : si vide, la commande /ask sera désactivée.
GEMINI_API_KEY="VOTRE_CLE_GEMINI_ICI"

# Votre ID utilisateur Telegram. Le bot peut le deviner au premier /start
# Essentiel pour que la commande /stop fonctionne.
# Pour trouver votre ID, vous pouvez envoyer /start au bot @userinfobot
BOT_OWNER_ID="VOTRE_ID_TELEGRAM_ICI"
```

---

## Lancement du Bot

Une fois les dépendances installées et le fichier `.env` configuré, lancez le bot avec la commande :

```bash
python bot.py
```

Le bot démarrera et commencera à écouter les messages. Vous pouvez l'arrêter proprement dans la console avec `Ctrl+C` ou en envoyant la commande `/stop` depuis votre compte Telegram (si `BOT_OWNER_ID` est correctement configuré).

---

## Architecture du Projet

*   `bot.py`: Fichier principal. Gère la logique du bot Telegram, les commandes, les threads pour les tâches planifiées et l'arrêt propre.
*   `financial_data.py`: Module dédié à la récupération et au traitement des données financières. Il interroge `yfinance` et contient la logique pour le calcul des scores.
*   `.env`: Fichier de configuration pour les clés d'API et les informations sensibles.
*   `subscribed_chats.json`: Fichier de persistance qui sauvegarde les ID des utilisateurs abonnés aux notifications, permettant au bot de se souvenir des abonnements même après un redémarrage.

### Personnalisation

Vous pouvez facilement modifier les listes d'actions et d'ETFs suivis par défaut en éditant les listes `DEFAULT_ETF_TICKERS` et `DEFAULT_ACTION_TICKERS` au début du fichier `financial_data.py`.

---

## ⚠️ Avertissement Important

Ce bot est un projet personnel à but éducatif et informatif. Les données sont fournies "en l'état". Le **"Score Potentiel LT" est une heuristique hautement simplifiée et expérimentale**. Il ne constitue en aucun cas un conseil financier, une recommandation d'achat ou de vente. Faites **toujours** vos propres recherches approfondies (DYOR - Do Your Own Research) avant de prendre toute décision d'investissement.