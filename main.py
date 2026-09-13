import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction
import sqlite3
import datetime

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Configurazione server
    c.execute('''CREATE TABLE IF NOT EXISTS config (
                    guild_id INTEGER PRIMARY KEY,
                    chan_auth INTEGER,
                    role_banchiere INTEGER,
                    role_milionario INTEGER,
                    role_multa INTEGER,
                    role_staff INTEGER
                )''')

    # Conti personali
    c.execute('''CREATE TABLE IF NOT EXISTS conti (
                    user_id INTEGER PRIMARY KEY,
                    nome_rp TEXT,
                    data_nascita TEXT,
                    saldo REAL DEFAULT 0,
                    bloccato INTEGER DEFAULT 0,
                    debito_tasse REAL DEFAULT 0,
                    lavoro TEXT DEFAULT NULL
                )''')

    # Fondi di risparmio
    c.execute('''CREATE TABLE IF NOT EXISTS fondi (
                    user_id INTEGER,
                    nome_fondo TEXT,
                    importo REAL,
                    PRIMARY KEY (user_id, nome_fondo)
                )''')

    # Conti condivisi
    c.execute('''CREATE TABLE IF NOT EXISTS conti_condivisi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT UNIQUE,
                    proprietario_id INTEGER,
                    saldo REAL DEFAULT 0
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS membri_condivisi (
                    conto_id INTEGER,
                    user_id INTEGER,
                    PRIMARY KEY (conto_id, user_id)
                )''')

    # Transazioni
    c.execute('''CREATE TABLE IF NOT EXISTS transazioni (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    tipo TEXT,
                    importo REAL,
                    data TEXT
                )''')

    conn.commit()
    conn.close()

init_db()

# --- BOT BOT CONSTANTS AND INIT ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class BankingBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        stipendi_e_tasse_loop.start()

bot = BankingBot()

STIPENDI = {
    "FDO": 3200,
    "Vigile Del Fuoco": 3500,
    "SUEM": 3800,
    "ACI": 2200,
    "Tassista": 2000,
    "Camionista": 3000,
    "Autista BUS": 2300
}

# --- HELPERS ---
def get_db():
    return sqlite3.connect('database.db')

def log_transazione(user_id, tipo, importo):
    conn = get_db()
    c = conn.cursor()
    data = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute("INSERT INTO transazioni (user_id, tipo, importo, data) VALUES (?, ?, ?, ?)", (user_id, tipo, importo, data))
    conn.commit()
    conn.close()

def check_conto_attivo(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT bloccato FROM conti WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    if not res:
        return False, "❌ Non possiedi un conto attivo."
    if res[0] == 1:
        return False, "🔒 Il tuo conto bancario è attualmente bloccato dallo staff."
    return True, ""

# --- AUTOMAZIONE SETTIMANALE ---
@tasks.loop(hours=168) # 1 settimana
async def stipendi_e_tasse_loop():
    conn = get_db()
    c = conn.cursor()
    
    # Processa stipendi
    c.execute("SELECT user_id, lavoro FROM conti WHERE lavoro IS NOT NULL AND bloccato = 0")
    lavoratori = c.fetchall()
    for uid, lavoro in lavoratori:
        if lavoro in STIPENDI:
            paga = STIPENDI[lavoro]
            c.execute("UPDATE conti SET saldo = saldo + ? WHERE user_id = ?", (paga, uid))
            log_transazione(uid, f"Stipendio ({lavoro})", paga)
            user = bot.get_user(uid)
            if user:
                try:
                    embed = discord.Embed(title="🏦 Accredito Stipendio", description=f"Hai ricevuto lo stipendio di **€ {paga:,}** per la professione: **{lavoro}**.", color=discord.Color.green())
                    await user.send(embed=embed)
                except: pass

    # Processa Tassa Settimanale (€400)
    c.execute("UPDATE conti SET debito_tasse = debito_tasse + 400 WHERE bloccato = 0")
    c.execute("SELECT user_id FROM conti WHERE bloccato = 0")
    tassati = c.fetchall()
    for uid in tassati:
        user = bot.get_user(uid[0])
        if user:
            try:
                embed = discord.Embed(title="🧾 Tassa Settimanale", description="È stata emessa la tassa settimanale di **€ 400**. Usa `/paga-tasse` per saldarla.", color=discord.Color.orange())
                await user.send(embed=embed)
            except: pass
            
    conn.commit()
    conn.close()

# --- 1️⃣ SETUP E CONFIGURAZIONE ---
setup_group = app_commands.Group(name="setup", description="Configura il sistema del Bot Bancario")

@setup_group.command(name="canale", description="Imposta il canale delle autorizzazioni")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_canale(interaction: Interaction, canale: discord.TextChannel):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO config (guild_id, chan_auth) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET chan_auth=excluded.chan_auth", (interaction.guild_id, canale.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Canale autorizzazioni impostato su {canale.mention}", ephemeral=True)

@setup_group.command(name="banchiere", description="Imposta il ruolo Banchiere")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_banchiere(interaction: Interaction, ruolo: discord.Role):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO config (guild_id, role_banchiere) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET role_banchiere=excluded.role_banchiere", (interaction.guild_id, ruolo.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Ruolo Banchiere impostato su {ruolo.mention}", ephemeral=True)

@setup_group.command(name="milionario", description="Imposta il ruolo Milionario")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_milionario(interaction: Interaction, ruolo: discord.Role):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO config (guild_id, role_milionario) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET role_milionario=excluded.role_milionario", (interaction.guild_id, ruolo.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Ruolo Milionario impostato su {ruolo.mention}", ephemeral=True)

@setup_group.command(name="multa", description="Imposta il ruolo per le multe")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_multa(interaction: Interaction, ruolo: discord.Role):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO config (guild_id, role_multa) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET role_multa=excluded.role_multa", (interaction.guild_id, ruolo.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Ruolo Multa impostato su {ruolo.mention}", ephemeral=True)

@setup_group.command(name="staff", description="Imposta il ruolo Staff")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_staff(interaction: Interaction, ruolo: discord.Role):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO config (guild_id, role_staff) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET role_staff=excluded.role_staff", (interaction.guild_id, ruolo.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Ruolo Staff impostato su {ruolo.mention}", ephemeral=True)

@setup_group.command(name="mostra", description="Mostra la configurazione del server")
async def setup_mostra(interaction: Interaction):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM config WHERE guild_id = ?", (interaction.guild_id,))
    cfg = c.fetchone()
    conn.close()
    if not cfg:
        return await interaction.response.send_message("❌ Nessuna configurazione trovata.", ephemeral=True)
    
    embed = discord.Embed(title="⚙️ Configurazione Server", color=discord.Color.blue())
    embed.add_field(name="Canale Autorizzazioni", value=f"<#{cfg[1]}>" if cfg[1] else "Non impostato")
    embed.add_field(name="Ruolo Banchiere", value=f"<@&{cfg[2]}>" if cfg[2] else "Non impostato")
    embed.add_field(name="Ruolo Milionario", value=f"<@&{cfg[3]}>" if cfg[3] else "Non impostato")
    embed.add_field(name="Ruolo Multa", value=f"<@&{cfg[4]}>" if cfg[4] else "Non impostato")
    embed.add_field(name="Ruolo Staff", value=f"<@&{cfg[5]}>" if cfg[5] else "Non impostato")
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.tree.add_command(setup_group)

# --- 2️⃣ FLUSSO APERTURA CONTO ---
class ModalAperturaConto(discord.ui.Modal, title="Richiesta Apertura Conto"):
    nome_rp = discord.ui.TextInput(label="Nome e Cognome RP", placeholder="Es. Mario Rossi")
    data_nascita = discord.ui.TextInput(label="Data di Nascita", placeholder="GG/MM/AAAA")
    motivo = discord.ui.TextInput(label="Motivo dell'apertura", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: Interaction):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT chan_auth FROM config WHERE guild_id = ?", (interaction.guild_id,))
        res = c.fetchone()
        conn.close()

        if not res or not res[0]:
            return await interaction.response.send_message("❌ Il canale autorizzazioni non è configurato nello /setup.", ephemeral=True)

        chan = interaction.guild.get_channel(res[0])
        embed = discord.Embed(title="💳 Richiesta Apertura Conto", color=discord.Color.gold())
        embed.add_field(name="Utente", value=interaction.user.mention)
        embed.add_field(name="Nome RP", value=self.nome_rp.value)
        embed.add_field(name="Data di Nascita", value=self.data_nascita.value)
        embed.add_field(name="Motivo", value=self.motivo.value, inline=False)
        
        view = ViewApprovazione(interaction.user.id, self.nome_rp.value, self.data_nascita.value)
        await chan.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Richiesta inviata allo staff!", ephemeral=True)

class ViewApprovazione(discord.ui.View):
    def __init__(self, target_id, nome_rp, data_nascita):
        super().__init__(timeout=None)
        self.target_id = target_id
        self.nome_rp = nome_rp
        self.data_nascita = data_nascita

    @discord.ui.button(label="Approvato", style=discord.ButtonStyle.success)
    async def approva(self, interaction: Interaction, button: discord.ui.Button):
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO conti (user_id, nome_rp, data_nascita) VALUES (?, ?, ?)", (self.target_id, self.nome_rp, self.data_nascita))
        c.execute("SELECT role_milionario FROM config WHERE guild_id = ?", (interaction.guild_id,))
        role_id = c.fetchone()
        conn.commit()
        conn.close()

        member = interaction.guild.get_member(self.target_id)
        if member and role_id and role_id[0]:
            role = interaction.guild.get_role(role_id[0])
            if role: await member.add_roles(role)

        if member:
            try: await member.send("🎉 La tua richiesta di apertura conto è stata **APPROVATA**!")
            except: pass

        await interaction.response.send_message(f"✅ Conto di <@{self.target_id}> approvato.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Rifiutato", style=discord.ButtonStyle.danger)
    async def rifiuta(self, interaction: Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.target_id)
        if member:
            try: await member.send("❌ La tua richiesta di apertura conto è stata **RIFIUTATA** dallo Staff.")
            except: pass
        await interaction.response.send_message(f"❌ Conto di <@{self.target_id}> rifiutato.", ephemeral=True)
        self.stop()

class ViewBottoneConto(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="💳 Crea Conto", style=discord.ButtonStyle.primary, custom_id="btn_crea_conto")
    async def crea(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalAperturaConto())

@bot.tree.command(name="conto-embed", description="Invia l'embed per la creazione del conto (Solo Staff)")
async def conto_embed(interaction: Interaction):
    embed = discord.Embed(title="🏦 Banca Stato", description="Clicca sul pulsante sottostante per inviare la richiesta di apertura conto.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=ViewBottoneConto())
    await interaction.response.send_message("Pannello inviato!", ephemeral=True)

# --- 3️⃣ SISTEMA STIPENDI E TASSE ---
@bot.tree.command(name="embed-stipendi", description="Mostra la tabella degli stipendi pubblicamente")
async def embed_stipendi(interaction: Interaction):
    embed = discord.Embed(title="💼 Tabella Stipendi Statali", color=discord.Color.green())
    for job, paga in STIPENDI.items():
        embed.add_field(name=job, value=f"€ {paga:,}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="aggiungi-membro-stipendio", description="Registra un utente agli stipendi automatici (Solo Staff)")
async def aggiungi_membro_stipendio(interaction: Interaction, utente: discord.User, lavoro: str):
    if lavoro not in STIPENDI:
        return await interaction.response.send_message(f"❌ Lavoro non valido. Scegli tra: {', '.join(STIPENDI.keys())}", ephemeral=True)
    
    ok, err = check_conto_attivo(utente.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE conti SET lavoro = ? WHERE user_id = ?", (lavoro, utente.id))
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"✅ Utente {utente.mention} registrato con successo come **{lavoro}**.")

@bot.tree.command(name="paga-tasse", description="Paga le tasse accumulate sul tuo conto")
async def paga_tasse(interaction: Interaction):
    ok, err = check_conto_attivo(interaction.user.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT saldo, debito_tasse FROM conti WHERE user_id = ?", (interaction.user.id,))
    saldo, debito = c.fetchone()

    if debito <= 0:
        conn.close()
        return await interaction.response.send_message("ℹ️ Non hai alcun debito di tasse da pagare.", ephemeral=True)

    if saldo < debito:
        conn.close()
        return await interaction.response.send_message(f"❌ Saldo insufficiente. Hai bisogno di € {debito:,} ma possiedi € {saldo:,}.", ephemeral=True)

    c.execute("UPDATE conti SET saldo = saldo - ?, debito_tasse = 0 WHERE user_id = ?", (debito, interaction.user.id))
    conn.commit()
    conn.close()

    log_transazione(interaction.user.id, "Pagamento Tasse", -debito)
    await interaction.response.send_message(f"✅ Tasse pagate con successo per un importo pari a **€ {debito:,}**.")

# --- 4️⃣ COMANDI OPERATIVI (CONTO PERSONALE) ---
@bot.tree.command(name="saldo", description="Visualizza il tuo saldo e dettagli")
async def saldo(interaction: Interaction):
    ok, err = check_conto_attivo(interaction.user.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT saldo, debito_tasse, bloccato FROM conti WHERE user_id = ?", (interaction.user.id,))
    sal, deb, bloc = c.fetchone()

    c.execute("SELECT SUM(importo) FROM fondi WHERE user_id = ?", (interaction.user.id,))
    fondi = c.fetchone()[0] or 0
    conn.close()

    embed = discord.Embed(title="💳 Dettaglio Saldo", color=discord.Color.blue())
    embed.add_field(name="Saldo Disponibile", value=f"€ {sal:,}", inline=False)
    embed.add_field(name="Totale Fondi", value=f"€ {fondi:,}", inline=False)
    embed.add_field(name="Debito Tasse", value=f"€ {deb:,}", inline=False)
    embed.add_field(name="Stato Conto", value="🔴 Bloccato" if bloc else "🟢 Attivo", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="bonifico", description="Esegui un bonifico verso un altro conto RP")
async def bonifico(interaction: Interaction, importo: float, mittente: str, destinatario: str, nota: str = "Nessuna"):
    ok, err = check_conto_attivo(interaction.user.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)

    if importo <= 0: return await interaction.response.send_message("❌ Importo non valido.", ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT saldo, nome_rp FROM conti WHERE user_id = ?", (interaction.user.id,))
    saldo, nome_rp = c.fetchone()

    if mittente.lower() != nome_rp.lower():
        conn.close()
        return await interaction.response.send_message("❌ Il nome mittente inserito non corrisponde al tuo Nome RP registrato.", ephemeral=True)

    if saldo < importo:
        conn.close()
        return await interaction.response.send_message("❌ Saldo insufficiente.", ephemeral=True)

    c.execute("SELECT user_id FROM conti WHERE LOWER(nome_rp) = LOWER(?)", (destinatario,))
    dest = c.fetchone()
    if not dest:
        conn.close()
        return await interaction.response.send_message("❌ Destinatario non trovato nel database.", ephemeral=True)

    dest_id = dest[0]
    c.execute("UPDATE conti SET saldo = saldo - ? WHERE user_id = ?", (importo, interaction.user.id))
    c.execute("UPDATE conti SET saldo = saldo + ? WHERE user_id = ?", (importo, dest_id))
    conn.commit()
    conn.close()

    log_transazione(interaction.user.id, f"Bonifico a {destinatario}", -importo)
    log_transazione(dest_id, f"Bonifico da {mittente}", importo)

    dest_user = bot.get_user(dest_id)
    if dest_user:
        try: await dest_user.send(f"📩 Hai ricevuto un bonifico di **€ {importo:,}** da **{mittente}**. Nota: {nota}")
        except: pass

    await interaction.response.send_message(f"✅ Bonifico di **€ {importo:,}** inviato a **{destinatario}**.")

@bot.tree.command(name="transazioni", description="Mostra la cronologia transazioni")
async def transazioni(interaction: Interaction):
    ok, err = check_conto_attivo(interaction.user.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT tipo, importo, data FROM transazioni WHERE user_id = ? ORDER BY id DESC LIMIT 10", (interaction.user.id,))
    rows = c.fetchall()
    conn.close()

    embed = discord.Embed(title="📜 Ultime 10 Transazioni", color=discord.Color.blue())
    for tipo, imp, dt in rows:
        segno = "+" if imp > 0 else ""
        embed.add_field(name=f"{dt} - {tipo}", value=f"**{segno}€ {imp:,}**", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stato", description="Verifica lo stato generale del tuo conto")
async def stato(interaction: Interaction):
    ok, err = check_conto_attivo(interaction.user.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT nome_rp, data_nascita, saldo, lavoro, bloccato, debito_tasse FROM conti WHERE user_id = ?", (interaction.user.id,))
    r = c.fetchone()
    conn.close()

    embed = discord.Embed(title="👤 Stato Conto", color=discord.Color.blue())
    embed.add_field(name="Titolare RP", value=r[0])
    embed.add_field(name="Data di Nascita", value=r[1])
    embed.add_field(name="Saldo", value=f"€ {r[2]:,}")
    embed.add_field(name="Occupazione", value=r[3] or "Disoccupato")
    embed.add_field(name="Stato Operativo", value="🔴 Bloccato" if r[4] else "🟢 Attivo")
    embed.add_field(name="Debito Tasse", value=f"€ {r[5]:,}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="multa", description="Emette una sanzione verso un conto")
async def multa(interaction: Interaction, utente: discord.User, importo: float, motivo: str):
    if importo <= 0: return await interaction.response.send_message("❌ Importo non valido.", ephemeral=True)

    ok, err = check_conto_attivo(utente.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT saldo FROM conti WHERE user_id = ?", (utente.id,))
    saldo = c.fetchone()[0]

    prelievo = min(saldo, importo)
    c.execute("UPDATE conti SET saldo = saldo - ? WHERE user_id = ?", (prelievo, utente.id))
    conn.commit()
    conn.close()

    log_transazione(utente.id, f"Multa ({motivo})", -prelievo)

    try: await utente.send(f"⚠️ Hai ricevuto una multa di **€ {importo:,}** per la seguente motivazione: **{motivo}**.")
    except: pass

    await interaction.response.send_message(f"✅ Multa di € {importo:,} applicata all'utente {utente.mention} (Addebitati € {prelievo:,}).")

@bot.tree.command(name="aggiungi-fondo", description="Versa denaro in un fondo di risparmio")
async def aggiungi_fondo(interaction: Interaction, fondo: str, importo: float):
    ok, err = check_conto_attivo(interaction.user.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)
    if importo <= 0: return await interaction.response.send_message("❌ Importo non valido.", ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT saldo FROM conti WHERE user_id = ?", (interaction.user.id,))
    saldo = c.fetchone()[0]

    if saldo < importo:
        conn.close()
        return await interaction.response.send_message("❌ Saldo non sufficiente.", ephemeral=True)

    c.execute("UPDATE conti SET saldo = saldo - ? WHERE user_id = ?", (importo, interaction.user.id))
    c.execute("INSERT INTO fondi (user_id, nome_fondo, importo) VALUES (?, ?, ?) ON CONFLICT(user_id, nome_fondo) DO UPDATE SET importo = importo + excluded.importo", (interaction.user.id, fondo, importo))
    conn.commit()
    conn.close()

    log_transazione(interaction.user.id, f"Versamento fondo: {fondo}", -importo)
    await interaction.response.send_message(f"✅ Versati **€ {importo:,}** nel fondo **{fondo}**.")

@bot.tree.command(name="preleva-fondo", description="Preleva denaro da un fondo di risparmio")
async def preleva_fondo(interaction: Interaction, fondo: str, importo: float):
    ok, err = check_conto_attivo(interaction.user.id)
    if not ok: return await interaction.response.send_message(err, ephemeral=True)
    if importo <= 0: return await interaction.response.send_message("❌ Importo non valido.", ephemeral=True)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT importo FROM fondi WHERE user_id = ? AND nome_fondo = ?", (interaction.user.id, fondo))
    res = c.fetchone()

    if not res or res[0] < importo:
        conn.close()
        return await interaction.response.send_message("❌ Fondi non sufficienti nel fondo specificato.", ephemeral=True)

    c.execute("UPDATE fondi SET importo = importo - ? WHERE user_id = ? AND nome_fondo = ?", (importo, interaction.user.id, fondo))
    c.execute("UPDATE conti SET saldo = saldo + ? WHERE user_id = ?", (importo, interaction.user.id))
    conn.commit()
    conn.close()

    log_transazione(interaction.user.id, f"Prelievo fondo: {fondo}", importo)
    await interaction.response.send_message(f"✅ Prelevati **€ {importo:,}** dal fondo **{fondo}**.")

# --- 5️⃣ GESTIONE CONTI CONDIVISI ---
@bot.tree.command(name="miei-conti-condivisi", description="Mostra i conti condivisi di cui fai parte")
async def miei_conti_condivisi(interaction: Interaction):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT cc.nome, cc.saldo, cc.proprietario_id 
                 FROM conti_condivisi cc 
                 LEFT JOIN membri_condivisi mc ON cc.id = mc.conto_id 
                 WHERE cc.proprietario_id = ? OR mc.user_id = ?""", (interaction.user.id, interaction.user.id))
    rows = list(set(c.fetchall()))
    conn.close()

    if not rows:
        return await interaction.response.send_message("❌ Non sei membro di alcun conto condiviso.", ephemeral=True)

    embed = discord.Embed(title="👥 Conti Condivisi", color=discord.Color.blue())
    for nome, saldo, prop_id in rows:
        ruolo = "👑 Proprietario" if prop_id == interaction.user.id else "👤 Membro"
        embed.add_field(name=f"Conto: {nome}", value=f"Saldo: € {saldo:,}\nRuolo: {ruolo}", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# Run bot
bot.run("TOKEN")
