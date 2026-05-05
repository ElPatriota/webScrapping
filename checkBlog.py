#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import sys
from supabase import create_client, Client

# ---------------- CONFIG (desde ENV) ----------------
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

# ---------------- HEADERS ----------------
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ---------------- SUPABASE ----------------
def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("Faltan variables de entorno de Supabase")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- LOGIN ----------------
def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)

    if not USE_LOGIN:
        return s

    payload = {
        "loginUsuario": USER,
        "claveUsuario": PASSWORD,
        "ingresarUsuario": "Ingresar"
    }

    r = s.post(LOGIN_URL, data=payload, timeout=15)
    return s

# ---------------- SCRAP ----------------
def get_latest_post(session):
    res = session.get(BLOG_URL, timeout=15)
    res.encoding = res.apparent_encoding or "utf-8"

    soup = BeautifulSoup(res.text, "html.parser")

    cont = soup.find(id="ajaxDivNoticias")
    noticias = cont.find_all(id="divNoticia") if cont else soup.find_all("div", id="divNoticia")

    if not noticias:
        raise Exception("No se encontraron noticias")

    latest = noticias[0]

    fecha = latest.find("b").get_text(strip=True) if latest.find("b") else ""
    contenido = latest.find("p").get_text(strip=True) if latest.find("p") else latest.get_text(" ", strip=True)

    a_tag = latest.find("a", href=True)
    link = a_tag["href"] if a_tag else BLOG_URL

    return {
        "fecha_autor": fecha,
        "contenido": contenido,
        "link": link
    }

# ---------------- DB ----------------
def get_last_post(supabase):
    res = supabase.table("blog_monitor") \
        .select("*") \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    return res.data[0] if res.data else None

def save_post(supabase, post):
    supabase.table("blog_monitor").insert(post).execute()

# ---------------- EMAIL ----------------
def send_email(post):
    cuerpo = f"""
📰 Nuevo post detectado

📅 {post['fecha_autor']}

{post['contenido']}

🔗 {post['link']}
"""

    msg = MIMEText(cuerpo)
    msg["Subject"] = "Nuevo post Blog CIIN"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("📩 Email enviado")

# ---------------- MAIN ----------------
def main():
    print("🚀 Iniciando chequeo...")

    session = get_session()
    supabase = get_supabase()

    latest = get_latest_post(session)
    last_saved = get_last_post(supabase)

    print("🆕 Último detectado:", latest["fecha_autor"])

    if not last_saved:
        print("⚠️ No hay registros previos → guardando primero")
        save_post(supabase, latest)
        send_email(latest)
        return

    if latest["fecha_autor"] != last_saved["fecha_autor"]:
        print("🔥 Nuevo post encontrado!")
        save_post(supabase, latest)
        send_email(latest)
    else:
        print("✅ Sin cambios")

# ---------------- RUN ----------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("🔴 ERROR:", e)
        sys.exit(1)
