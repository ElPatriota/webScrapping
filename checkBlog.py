#!/usr/bin/env python3
# checkBlog.py - Versión con debug y selectores robustos

import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import json
import os
import sys

# ---------------- CONFIG ----------------
USE_LOGIN = True            # True si debes hacer login; False si no
LOGIN_URL = "http://www.algieba.cl/blogCiin/validarLogin.php"
BLOG_URL = "http://www.algieba.cl/blogCiin/"
USER = "primerobas"
PASSWORD = "Q5oAhjgt"

LAST_FILE = "last_post.json"

EMAIL_USER = "a.castro.m@gmail.com"
EMAIL_PASS = "inka bjly mwai ebkv"
EMAIL_TO = "a.castro.m@gmail.com, reyestorres.lady@gmail.com"

# ---------------- HELPERS ----------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

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
    try:
        r = s.post(LOGIN_URL, data=payload, allow_redirects=True, timeout=15)
    except Exception as e:
        raise Exception(f"Error al conectar al login: {e}")

    return s

# ---------------- SCRAP ----------------
def get_latest_post(session):
    try:
        res = session.get(BLOG_URL, timeout=15)
    except Exception as e:
        raise Exception(f"Error al obtener la página del blog: {e}")

    # parsear
    res.encoding = res.apparent_encoding or "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    # 1) Intentar encontrar el contenedor principal por id "ajaxDivNoticias"
    cont = soup.find(id="ajaxDivNoticias")
    if cont:
        noticias = cont.find_all(id="divNoticia")
    else:
        # fallback: buscar directamente todos los div con id=divNoticia en todo el documento
        noticias = soup.find_all("div", id="divNoticia")

    if not noticias:
        # Intentar otro fallback: quizá los divs tienen clase en lugar de id por cambios futuros
        noticias = soup.select(".divNoticias #divNoticia, div[id^='divNoticia'], .divNoticias div")
    
    if not noticias:
        # Si aún no hay nada, lanzar excepción con información para debug
        raise Exception("No se encontraron noticias con los selectores esperados. Revisa el HTML (ver snippets arriba).")

    # tomar la primera noticia (la más reciente según el HTML)
    latest = noticias[0]

    # extraer fecha/autor y contenido con robustez
    fecha_autor_tag = latest.find("b")
    contenido_tag = latest.find("p")

    fecha_autor = fecha_autor_tag.get_text(strip=True) if fecha_autor_tag else ""
    contenido = contenido_tag.get_text(strip=True) if contenido_tag else latest.get_text(" ", strip=True)

    # algunos posts contienen enlaces relativos: si necesitas link, buscar <a> dentro
    a_tag = latest.find("a", href=True)
    link = a_tag["href"] if a_tag else BLOG_URL

    return {"fecha_autor": fecha_autor, "contenido": contenido, "link": link}


# ---------------- EMAIL ----------------
def send_email(post):
    cuerpo = f"""📰 Nueva publicación en el Blog CIIN

📅 {post['fecha_autor']}

🗞️ Contenido:
{post['contenido']}

🔗 Enlace: {post['link']}
"""
    msg = MIMEText(cuerpo)
    msg["Subject"] = "Nuevo post en el Blog CIIN"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
    print("📩 Correo enviado con la nueva publicación.")


# ---------------- MAIN ----------------
def main():
    session = get_logged_session() if USE_LOGIN else requests.Session()
    session.headers.update(HEADERS)

    latest = get_latest_post(session)

    print("\nÚltima noticia leída:")
    print(f"- Fecha/Autor: {latest['fecha_autor']}")
    print(f"- Contenido (primeros 200 chars): {latest['contenido'][:200]!r}")

    if os.path.exists(LAST_FILE):
        old = json.load(open(LAST_FILE, encoding="utf-8"))
        if latest["fecha_autor"] != old.get("fecha_autor"):
            send_email(latest)
        else:
            print("No hay nuevas publicaciones (coincide con last_post.json).")
    else:
        # si no existe last file, lo enviamos la primera vez (opcional)
        print("No existe last_post.json: se enviará la primera publicación encontrada.")
        send_email(latest)

    json.dump(latest, open(LAST_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n🔴 ERROR:", e)
        sys.exit(1)
