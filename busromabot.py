import telegram
from telegram.ext import Updater
import logging
from telegram.ext import CommandHandler, MessageHandler, BaseFilter, CallbackQueryHandler
from xmlrpc.client import Server
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
#from RequestsTransport import HTTPProxyTransport
import xmlrpc.client
from pprint import pprint
import pickle
import os


script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)


# put the token in the same path inside a text file
with open("token.txt", "r") as f:
    TOKEN = f.read()

DEV_KEY = ''  # dev key qui

#transport = HTTPProxyTransport({'http': 'proxy.server:3128'})

s1 = Server('http://muovi.roma.it/ws/xml/autenticazione/1')
s2 = Server('http://muovi.roma.it/ws/xml/paline/7')

token = s1.autenticazione.Accedi(DEV_KEY, '')
updater = Updater(token=TOKEN)
dispatcher = updater.dispatcher
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


def build_menu(buttons,
               n_cols,
               header_buttons=None,
               footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu


def start(bot, update, chat_data):
    button_list = [
        InlineKeyboardButton("ℹ️ Info & Guida", callback_data="3"),
        InlineKeyboardButton("⭐️ I miei preferiti", callback_data="4"),
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))
    chat_data["chat_id"] = update.message.chat_id
    bot.send_message(chat_id=update.message.chat_id, text=("Sei nel menù principale del bot. *Cosa vuoi fare?*"), reply_markup=reply_markup,
                     parse_mode=telegram.ParseMode.MARKDOWN, pass_chat_data=True)



def cerca(bot, update, chat_data):
    global token
    messaggio = update.message.text
    if len(messaggio[7:]) == 5:
        chat_data["daCerca"] = True
        chat_data["FermataDaCerca"] = messaggio[7:]
        chat_data["daPulsante"] = False
        chat_data["chat_id"] = update.message.chat_id
        fermata(bot, update, chat_data)
    else:
        dizionarioCapolinea = {}
        try:
            rispostaLinea = s2.paline.Percorsi(token, messaggio[7:], "it")
        except xmlrpc.client.Fault:
            token = s1.autenticazione.Accedi(DEV_KEY, '')
            rispostaLinea = s2.paline.Percorsi(token, messaggio[7:], "it")
        lista_capolinea = rispostaLinea["risposta"]["percorsi"]
        stringa_finale_1 = "*Seleziona una direzione*"
        for i in lista_capolinea:
            descrizione = i["descrizione"]
            if descrizione != "":
                descrizione += " "
            capolinea = i["capolinea"]
            id_percorso = i["id_percorso"]
            dizionarioCapolinea[capolinea] = id_percorso
        chat_data["dizionarioCapolinea"] = dizionarioCapolinea
        custom_keyboard = [[key] for key in dizionarioCapolinea.keys()]
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.send_message(chat_id=update.message.chat_id, text=(stringa_finale_1), reply_markup=reply_markup,
                         parse_mode=telegram.ParseMode.MARKDOWN, pass_chat_data=True)
        chat_data["daPulsante"] = False


def direzione(bot, update, chat_data):
    chat_data["daCerca"] = False
    global token
    messaggio = update.message.text
    capolinea_input = chat_data["dizionarioCapolinea"][messaggio]
    try:
        rispostaPercorso = s2.paline.Percorso(token, capolinea_input, "", "", "it")
    except xmlrpc.client.Fault:
        token = s1.autenticazione.Accedi(DEV_KEY, '')
        rispostaPercorso = s2.paline.Percorso(token, capolinea_input, "", "", "it")
    lista_fermate = rispostaPercorso["risposta"]["fermate"]
    dizionarioFermate = {}
    for i in lista_fermate:
        nome_fermata = i["nome_ricapitalizzato"]
        id_palina = i["id_palina"]
        dizionarioFermate[id_palina + " - " + nome_fermata] = id_palina
    custom_keyboard = [[key] for key in dizionarioFermate.keys()]
    stringa_finale_2 = "*Seleziona fermata*"

    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    bot.send_message(chat_id=update.message.chat_id, text=(stringa_finale_2), reply_markup=reply_markup,
                     parse_mode=telegram.ParseMode.MARKDOWN, pass_chat_data=True)


def fermata(bot, update, chat_data):
    global token
    if chat_data["daPulsante"]:
        numFermata = chat_data[chat_data["message_id"]][0]
    elif chat_data["daCerca"]:
        numFermata = chat_data["FermataDaCerca"]
    else:
        numFermata = update.message.text[:5]
        chat_data["chat_id"] = update.message.chat_id
    try:
        rispostaPalina = s2.paline.Previsioni(token, numFermata, "it")
    except xmlrpc.client.Fault:
        token = s1.autenticazione.Accedi(DEV_KEY, '')
        rispostaPalina = s2.paline.Previsioni(token, numFermata, "it")
    lista_arrivi = rispostaPalina["risposta"]["primi_per_palina"][0]["arrivi"]
    nome_palina = rispostaPalina["risposta"]["primi_per_palina"][0]["nome_palina"]
    stringa_finale = "Prossimi arrivi a *" + nome_palina + "*:\n\n"
    for i in lista_arrivi:
        try:
            direzione = i["capolinea"]
            annuncio = i["annuncio"]
            linea_palina = i["linea"]
            stringa_finale += "Linea *" + linea_palina + "* direzione *" + direzione + "*: " + "_" + annuncio + "_" + "\n------------------\n"
        except KeyError:
            pass
    button_list = [
        InlineKeyboardButton("Aggiorna 🔄", callback_data="1"),
        InlineKeyboardButton("Aggiungi ai preferiti ⭐️", callback_data="2"),
    ]
    reply_markup = InlineKeyboardMarkup(build_menu(button_list, n_cols=1))
    chat_data["fermata"] = numFermata
    if chat_data["daPulsante"]:
        try:
            bot.edit_message_text(chat_id=chat_data["chat_id"], text=stringa_finale, message_id=chat_data["message_id"],
                                  parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=reply_markup,
                                  pass_chat_data=True)
        except telegram.error.BadRequest:
            bot.answer_callback_query(callback_query_id=chat_data["query_id"], text="Nessun aggiornamento disponibile")
    else:
        message_sent = bot.send_message(chat_id=chat_data["chat_id"], text=stringa_finale,
                                        parse_mode=telegram.ParseMode.MARKDOWN,
                                        reply_markup=reply_markup, pass_chat_data=True)
        chat_data[message_sent.message_id] = [numFermata, nome_palina]

def RimuoviPreferito(bot, update, chat_data):
    dizionarioPreferiti = pickle.load(open("preferiti.pickle", "rb"))
    lista_preferiti = dizionarioPreferiti[update.message.chat_id]
    preferitoDaEliminare = update.message.text[9:]
    for i in lista_preferiti:
        if preferitoDaEliminare == i[:5]:
            lista_preferiti.remove(i)
    dizionarioPreferiti[update.message.chat_id] = lista_preferiti
    pickle.dump(dizionarioPreferiti, open("preferiti.pickle", "wb"))
    bot.send_message(chat_id=chat_data["chat_id"], text="Eliminato con successo. Usa /start per ritornare al menù", pass_chat_data=True)




def Pulsanti(bot, update, chat_data):
    query = update.callback_query
    if "{}".format(query.data) == "1":
        chat_data["daPulsante"] = True
        chat_data["message_id"] = query.message.message_id
        chat_data["query_id"] = query["id"]
        fermata(bot, update, chat_data)
    elif "{}".format(query.data) == "2":
        #bot.answer_callback_query(callback_query_id=query["id"], text="Work in progress")
        preferito = chat_data[query.message.message_id]
        splitter = " - "
        elemento_lista = splitter.join(preferito)
        chat_data["preferito"] = elemento_lista
        try:
            dizionarioPreferiti = pickle.load(open("preferiti.pickle", "rb"))
        except FileNotFoundError:
            dizionarioPreferiti = {}
            pickle.dump(dizionarioPreferiti, open("preferiti.pickle", "wb"))
        if chat_data["chat_id"] not in dizionarioPreferiti:
            dizionarioPreferiti[chat_data["chat_id"]] = []
        if elemento_lista not in dizionarioPreferiti[chat_data["chat_id"]]:
            dizionarioPreferiti[chat_data["chat_id"]].append(elemento_lista)
            pickle.dump(dizionarioPreferiti, open("preferiti.pickle", "wb"))
            bot.answer_callback_query(callback_query_id=query["id"], text="Aggiunto correttamente")
        else:
            bot.answer_callback_query(callback_query_id=query["id"], text="Già presente nei preferiti")
    elif "{}".format(query.data) == "3":
    	bot.send_message(chat_id=chat_data["chat_id"], text='[Clicca qui per aprire la guida](http://telegra.ph/Guida-a-Bus-Roma-Bot-08-06)\n\n📰 Segui @CigoBotNews per eventuali aggiornamenti \n\n📝 Segnala un bug a @parlaconcigobot, comprendendo screenshot ed una descrizione accurata del problema.\n\n⚠️ Nota che gli orari degli arrivi e delle partenze non sono sempre esatti. I dati che questo bot trasmette sono offerti da muovi.roma.it, perciò per eventuali ritardi od autobus inesistenti, non è da considerarsi responsabile.', parse_mode=telegram.ParseMode.MARKDOWN)
        
    elif "{}".format(query.data) == "4":
        global token
        dizionarioPreferiti = pickle.load(open("preferiti.pickle", "rb"))
        try:
            custom_keyboard = [[i] for i in dizionarioPreferiti[chat_data["chat_id"]]]
            if not custom_keyboard:
                bot.answer_callback_query(callback_query_id=query["id"], text="Non hai preferiti")
            reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
            stringa_finale = "*Ecco la lista dei tuoi preferiti*. Per rimuoverne uno, semplicemente *clicca uno dei seguenti comandi*, li copierai in automatico e poi inviali al bot:\n"
            for i in dizionarioPreferiti[chat_data["chat_id"]]:
                stringa_finale += "```" + ". " + "/rimuovi " + i[:5] + "```" + "\n"
            bot.send_message(chat_id=chat_data["chat_id"],
                             text=stringa_finale,
                             parse_mode=telegram.ParseMode.MARKDOWN,
                             reply_markup=reply_markup, pass_chat_data=True)
        except KeyError:
            bot.answer_callback_query(callback_query_id=query["id"], text="Non hai alcun preferito")
        chat_data["daPulsante"] = False
        chat_data["daCerca"] = False



class FiltroDirezioni(BaseFilter):
    def filter(self, message):
        return message.text[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class FiltroFermate(BaseFilter):
    def filter(self, message):
        return message.text[0] in '0123456789'


filtro_direzioni = FiltroDirezioni()
filtro_fermate = FiltroFermate()

start_handler = CommandHandler('start', start, pass_chat_data=True)
cerca_handler = CommandHandler('cerca', cerca, pass_chat_data=True)
direzione_handler = MessageHandler(filtro_direzioni, direzione, pass_chat_data=True)
fermata_handler = MessageHandler(filtro_fermate, fermata, pass_chat_data=True)
RimuoviPreferito_handler = CommandHandler('rimuovi', RimuoviPreferito, pass_chat_data=True)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(cerca_handler)
dispatcher.add_handler(direzione_handler)
dispatcher.add_handler(fermata_handler)
dispatcher.add_handler(RimuoviPreferito_handler)
dispatcher.add_handler(CallbackQueryHandler(Pulsanti, pass_chat_data=True))
# dispatcher.add_handler(CallbackQueryHandler(PulsantePreferiti))

updater.start_polling()