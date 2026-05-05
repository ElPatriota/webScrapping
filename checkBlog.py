#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
from datetime import datetime
import pytz
from supabase import create_client

# ---------------- CONFIG ----------------
USE_LOGIN = True

LOGIN_URL = "http://www.algieba.cl/blogCiin/validarLogin.php"
BLOG_URL = "http://www.algieba.cl/blogCiin/"

USER = os.getenv("BLOG_USER")
PASSWORD = os.getenv("BLOG_PASS")

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ---------------- INIT ----------------
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- HORARIO ----------------
def is_valid_time():
    tz = pytz.timezone("America/Santiago")
    hora = datetime.now(tz).hour
    return 7 <= hora < 22

# ---------------- LOGIN ----------------
def get_logged_session():
    s = requests.Session()
    s.headers.update(HEADERS)

    if not USE_LOGIN:
        return s

    payload = {
        "loginUsuario": USER,
        "claveUsuario": PASSWORD,
        "ingresarUsuario": "Ingresar"
    }

    print("🔐 Haciendo login...")
    s.post(LOGIN_URL, data=payload, timeout=15)

    return s

# ---------------- SCRAP ----------------
def get_latest_post(session):
    print("🌐 Consultando blog...")

    res = session.get(BLOG_URL, timeout=15)
    res.encoding = res.apparent_encoding or "utf-8"

    soup = BeautifulSoup(res.text, "html.parser")

    noticias = soup.find_all("div", id="divNoticia")

    if not noticias:
        raise Exception("❌ No se encontraron noticias")

    latest = noticias[0]

    fecha_tag = latest.find("b")
    contenido_tag = latest.find("p")

    fecha_autor = fecha_tag.get_text(strip=True) if fecha_tag else "Sin fecha"
    contenido = contenido_tag.get_text(strip=True) if contenido_tag else latest.get_text(strip=True)

    return {
        "fecha_autor": fecha_autor,
        "contenido": contenido
    }

# ---------------- SUPABASE ----------------
def get_last_post():
    print("📦 Consultando último registro en Supabase...")

    res = supabase.table("blog_monitor") \
        .select("*") \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if res.data:
        return res.data[0]

    return None


def save_post(post):
    print("💾 Guardando nuevo post en Supabase...")

    supabase.table("blog_monitor").insert({
        "fecha_autor": post["fecha_autor"],
        "contenido": post["contenido"]
    }).execute()

# ---------------- EMAIL ----------------
def send_email(post):
    print("📧 Enviando correo...")

    cuerpo = f"""
📰 Nueva publicación en el Blog CIIN

📅 {post['fecha_autor']}

🗞️ {post['contenido']}
"""

    msg = MIMEText(cuerpo)
    msg["Subject"] = "Nuevo post en el Blog CIIN"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

# ---------------- MAIN ----------------
def main():
    print("🚀 Iniciando ejecución...")

    # ⏰ Validar horario
    if not is_valid_time():
        print("⏰ Fuera de horario (07:00 - 22:00 Chile)")
        return

    # 🔐 Login
    session = get_logged_session()

    # 📰 Obtener último post
    latest = get_latest_post(session)

    print(f"📌 Último encontrado: {latest['fecha_autor']}")

    # 📦 Obtener último guardado
    last = get_last_post()

    if not last:
        print("🆕 Primera ejecución → se envía correo")
        send_email(latest)
        save_post(latest)
        return

    if latest["fecha_autor"] != last["fecha_autor"]:
        print("🔥 Nuevo post detectado!")
        send_email(latest)
        save_post(latest)
    else:
        print("✅ Sin cambios")

# ---------------- RUN ----------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n🔴 ERROR:", e)
        exit(1)