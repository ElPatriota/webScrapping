#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os
import sys
import json
import hashlib
from supabase import create_client

# ---------------- CONFIG ----------------
LOGIN_URL = "http://www.algieba.cl/blogCiin/validarLogin.php"
BLOG_URL = "http://www.algieba.cl/blogCiin/"

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ---------------- UTILS ----------------
def log(msg):
    print(msg, flush=True)

def get_users():
    raw = os.getenv("BLOG_USERS_JSON")
    if not raw:
        raise Exception("Falta variable BLOG_USERS_JSON")
    return json.loads(raw)

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise Exception("Faltan variables de Supabase")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def normalize_text(text):
    return " ".join(text.strip().lower().split())

def generate_hash(post, user):
    fecha = normalize_text(post["fecha_autor"])
    contenido = normalize_text(post["contenido"])

    raw = f"{user}-{fecha}-{contenido}"
    return hashlib.sha256(raw.encode()).hexdigest()

# ---------------- LOGIN ----------------
def get_session(user, password):
    s = requests.Session()
    s.headers.update(HEADERS)

    payload = {
        "loginUsuario": user,
        "claveUsuario": password,
        "ingresarUsuario": "Ingresar"
    }

    try:
        s.post(LOGIN_URL, data=payload, timeout=15)
    except Exception as e:
        raise Exception(f"Error login {user}: {e}")

    return s

# ---------------- SCRAP ----------------
def get_latest_post(session):
    try:
        res = session.get(BLOG_URL, timeout=15)
    except Exception as e:
        raise Exception(f"Error al cargar blog: {e}")

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
def save_post(supabase, post, user, name):
    hash_value = generate_hash(post, user)

    post_data = {
        "fecha_autor": post["fecha_autor"],
        "contenido": post["contenido"],
        "link": post["link"],
        "blog_user": user,
        "blog_name": name,
        "hash": hash_value
    }

    try:
        supabase.table("blog_monitor").insert(post_data).execute()

        log(f"💾 Insertado nuevo post ({name})")
        return True  # 👉 SOLO aquí envías mail

    except Exception as e:
        error_str = str(e).lower()

        if "duplicate key" in error_str or "unique constraint" in error_str:
            log(f"🔁 Ya existía (hash duplicado) ({name})")
            return False

        log(f"🔴 Error DB ({name}): {e}")
        return False
    
# ---------------- EMAIL ----------------
def send_email(post, user, name):
    cuerpo = f"""
📰 Nuevo post - {name}

👤 Usuario: {user}
📅 {post['fecha_autor']}

{post['contenido']}

🔗 {post['link']}
"""

    msg = MIMEText(cuerpo)
    msg["Subject"] = f"📰 Nuevo post - {name}"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)

        log(f"📩 Email enviado ({name})")

    except Exception as e:
        log(f"🔴 Error enviando email ({name}): {e}")

# ---------------- MAIN ----------------
def main():
    log("🚀 Iniciando chequeo multi-usuario")

    supabase = get_supabase()
    users = get_users()

    for u in users:
        user = u["user"]
        password = u["pass"]
        name = u.get("name", user)

        log(f"\n👤 Procesando: {name}")

        try:
            session = get_session(user, password)
            latest = get_latest_post(session)

            log(f"🆕 Detectado: {latest['fecha_autor']}")

            inserted = save_post(supabase, latest, user, name)

            if inserted:
                send_email(latest, user, name)
            else:
                log(f"✅ Sin cambios ({name})")

        except Exception as e:
            log(f"🔴 Error en {name}: {e}")
            continue

    log("\n🏁 Proceso finalizado")

# ---------------- RUN ----------------
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("🔥 ERROR CRÍTICO:", e)
        sys.exit(1)