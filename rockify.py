# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 17:16:42 2026

@author: corin
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from collections import deque
import os
import shutil
import re
import secrets
import hashlib
import json
import time
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ==============================
# CONFIG
# ==============================

DATABASE_URL = "sqlite:///./rockyfi.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"])

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15
ACCESS_SESSION_HOURS = 12
REFRESH_SESSION_DAYS = 14

RADIO_BROWSER_BASE_URL = os.getenv("RADIO_BROWSER_BASE_URL", "https://all.api.radio-browser.info")
RADIO_CACHE_TTL_SECONDS = 300
RADIO_CACHE = {}

# Security defaults: can be overridden in Render env vars.
DEFAULT_CORS_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000"
CORS_ALLOW_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if origin.strip()]
TRUSTED_HOSTS = [host.strip() for host in os.getenv("TRUSTED_HOSTS", "127.0.0.1,localhost,.onrender.com").split(",") if host.strip()]

# Simple in-memory limiter. Good baseline for single-instance deployment.
RATE_LIMIT_STATE = {}
RATE_LIMIT_LOCK = Lock()

app = FastAPI(
    title="Rockyfi API",
    docs_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=TRUSTED_HOSTS,
)

DOCS_CUSTOM_CSS = """
body {
    background: radial-gradient(circle at 10% 10%, #ffe0ef 0%, transparent 28%),
                radial-gradient(circle at 90% 90%, #ffe9d6 0%, transparent 30%),
                #f7f2ea;
}

.swagger-ui .topbar {
    background: linear-gradient(120deg, #dd5e89, #f7bb97);
    border-bottom: 1px solid #f3c6d8;
}

.swagger-ui .topbar .download-url-wrapper { display: none; }

.swagger-ui .info {
    margin: 18px 0;
    padding: 20px;
    border: 1px solid #e9dfd1;
    border-radius: 14px;
    background: #fffdfa;
    box-shadow: 0 10px 28px rgba(31, 41, 64, 0.08);
}

.swagger-ui .info .title {
    color: #1f2940;
    font-weight: 700;
}

.swagger-ui .scheme-container {
    border-radius: 12px;
    border: 1px solid #e9dfd1;
    background: #fffdfa;
}

.swagger-ui .opblock {
    border-radius: 12px;
    border-width: 1px;
    box-shadow: 0 8px 22px rgba(31, 41, 64, 0.05);
}

.swagger-ui .opblock .opblock-summary-method {
    font-weight: 700;
}

.swagger-ui .opblock-get {
    border-color: #d8b074 !important;
    background: rgba(245, 208, 145, 0.18) !important;
}

.swagger-ui .opblock-get .opblock-summary-method {
    background: #c38b2b !important;
    color: #fff !important;
}

.swagger-ui .opblock-post {
    border-color: #d47898 !important;
    background: rgba(221, 94, 137, 0.14) !important;
}

.swagger-ui .opblock-post .opblock-summary-method {
    background: #b34b72 !important;
    color: #fff !important;
}

.swagger-ui .opblock-put {
    border-color: #cf8b56 !important;
    background: rgba(214, 136, 72, 0.14) !important;
}

.swagger-ui .opblock-put .opblock-summary-method {
    background: #b4682e !important;
    color: #fff !important;
}

.swagger-ui .opblock-delete {
    border-color: #cf7a7a !important;
    background: rgba(201, 98, 98, 0.14) !important;
}

.swagger-ui .opblock-delete .opblock-summary-method {
    background: #b94f4f !important;
    color: #fff !important;
}

.swagger-ui .opblock .opblock-summary-path,
.swagger-ui .opblock .opblock-summary-description {
    color: #3f2f4f;
}

.swagger-ui .btn.try-out__btn {
    border-color: #b34b72;
    color: #b34b72;
}

.swagger-ui .btn.cancel {
    border-color: #9c6a3a;
    color: #9c6a3a;
}

.swagger-ui .btn.execute {
    background: linear-gradient(120deg, #dd5e89, #f7bb97);
    border-color: #dd5e89;
}

.swagger-ui input,
.swagger-ui textarea,
.swagger-ui select {
    border-radius: 10px;
}

.swagger-ui .responses-inner h4,
.swagger-ui .responses-inner h5 {
    color: #1f2940;
}

#rockify-docs-hero {
    margin: 16px 0 20px;
    padding: 16px 18px;
    border: 1px solid #e9dfd1;
    border-radius: 12px;
    background: #fff;
    box-shadow: 0 8px 20px rgba(31, 41, 64, 0.06);
    color: #5d6a84;
    font-size: 14px;
    line-height: 1.45;
}

#rockify-docs-hero strong {
    color: #1f2940;
}
"""

DOCS_CUSTOM_JS = """
window.addEventListener('load', function () {
  const infoBlock = document.querySelector('.swagger-ui .information-container .info');
  if (!infoBlock || document.getElementById('rockify-docs-hero')) return;

  const hero = document.createElement('div');
  hero.id = 'rockify-docs-hero';
  hero.innerHTML =
    '<strong>Rockify Docs</strong><br>' +
    'Suggerimento: usa il filtro in alto per cercare endpoint, poi clicca "Try it out" per test veloci. ' +
    'Inizia da <code>GET /songs</code> e <code>POST /register</code>.';

  infoBlock.appendChild(hero);
});
"""

# Create upload folders
os.makedirs("uploads/songs", exist_ok=True)
os.makedirs("uploads/images", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ==============================
# DATABASE MODELS
# ==============================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    password = Column(String)
    role = Column(String, default="user")  # user or artist


class Artist(Base):
    __tablename__ = "artists"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    bio = Column(Text)
    country = Column(String)
    genre = Column(String)

    user = relationship("User")
    songs = relationship("Song", back_populates="artist")


class Song(Base):
    __tablename__ = "songs"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    file_path = Column(String)
    cover_path = Column(String)
    artist_id = Column(Integer, ForeignKey("artists.id"))

    artist = relationship("Artist", back_populates="songs")


class Radio(Base):
    __tablename__ = "radios"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    country = Column(String)
    city = Column(String)
    stream_url = Column(String)
    genre = Column(String)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    artist_name = Column(String)
    location = Column(String)
    country = Column(String)
    date = Column(DateTime)


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    image_path = Column(String)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class LoginGuard(Base):
    __tablename__ = "login_guards"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token_hash = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token_hash = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

# ==============================
# DEPENDENCY
# ==============================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================
# UTILS
# ==============================

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_password_strength(password: str) -> bool:
    # Minimum 8 chars with upper/lower/digit/special to reduce weak credentials.
    if len(password) < 8:
        return False
    checks = [
        r"[A-Z]",
        r"[a-z]",
        r"\d",
        r"[^A-Za-z0-9]",
    ]
    return all(re.search(pattern, password) for pattern in checks)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def enforce_ip_rate_limit(request: Request, bucket: str, max_requests: int, window_seconds: int):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    key = (bucket, ip)

    with RATE_LIMIT_LOCK:
        entries = RATE_LIMIT_STATE.get(key)
        if entries is None:
            entries = deque()
            RATE_LIMIT_STATE[key] = entries

        while entries and entries[0] <= now - window_seconds:
            entries.popleft()

        if len(entries) >= max_requests:
            retry_after = int(window_seconds - (now - entries[0])) if entries else window_seconds
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Retry in about {max(retry_after, 1)} seconds",
            )

        entries.append(now)


def parse_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_world_radios(name: str, country: str, tag: str, limit: int, https_only: bool):
    cache_key = (name.strip().lower(), country.strip().lower(), tag.strip().lower(), limit, https_only)
    now = time.time()
    cache_entry = RADIO_CACHE.get(cache_key)
    if cache_entry and cache_entry["expires_at"] > now:
        return cache_entry["data"]

    params = {
        "name": name.strip(),
        "country": country.strip(),
        "tag": tag.strip(),
        "hidebroken": "true",
        "order": "clickcount",
        "reverse": "true",
        "limit": str(limit),
    }

    query = urlencode({k: v for k, v in params.items() if v})
    url = f"{RADIO_BROWSER_BASE_URL}/json/stations/search?{query}"

    req = Request(
        url,
        headers={
            "User-Agent": "Rockify/1.0 (+https://render.com)",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(req, timeout=12) as response:
            stations = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"Radio service unavailable: {exc}")

    normalized = []
    for station in stations:
        stream_url = station.get("url_resolved") or station.get("url") or ""
        if https_only and not stream_url.lower().startswith("https://"):
            continue

        lat = parse_float(station.get("geo_lat"))
        lon = parse_float(station.get("geo_long"))
        if lat is None or lon is None:
            continue

        normalized.append(
            {
                "id": station.get("stationuuid"),
                "name": station.get("name") or "Unknown station",
                "country": station.get("country") or "Unknown",
                "state": station.get("state") or "",
                "city": station.get("city") or "",
                "tags": station.get("tags") or "",
                "language": station.get("language") or "",
                "favicon": station.get("favicon") or "",
                "stream_url": stream_url,
                "homepage": station.get("homepage") or "",
                "codec": station.get("codec") or "",
                "bitrate": station.get("bitrate") or 0,
                "votes": station.get("votes") or 0,
                "lat": lat,
                "lon": lon,
            }
        )

    RADIO_CACHE[cache_key] = {
        "expires_at": now + RADIO_CACHE_TTL_SECONDS,
        "data": normalized,
    }
    return normalized


def issue_session_token(user_id: int, db: Session):
    plain_token = secrets.token_urlsafe(32)
    session = UserSession(
        user_id=user_id,
        token_hash=hash_session_token(plain_token),
        expires_at=datetime.utcnow() + timedelta(hours=ACCESS_SESSION_HOURS),
        revoked=False,
    )
    db.add(session)
    db.commit()
    return plain_token, session.expires_at


def issue_refresh_token(user_id: int, db: Session):
    plain_token = secrets.token_urlsafe(48)
    session = RefreshSession(
        user_id=user_id,
        token_hash=hash_session_token(plain_token),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_SESSION_DAYS),
        revoked=False,
    )
    db.add(session)
    db.commit()
    return plain_token, session.expires_at


def get_user_from_bearer(authorization: str, db: Session):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    raw_token = authorization.split(" ", 1)[1].strip()
    if not raw_token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    token_hash = hash_session_token(raw_token)
    session = (
        db.query(UserSession)
        .filter(
            UserSession.token_hash == token_hash,
            UserSession.revoked == False,
            UserSession.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found for this session")
    return user, session


def get_user_from_refresh_token(refresh_token: str, db: Session):
    if not refresh_token or not refresh_token.strip():
        raise HTTPException(status_code=401, detail="Missing refresh token")

    token_hash = hash_session_token(refresh_token.strip())
    refresh_session = (
        db.query(RefreshSession)
        .filter(
            RefreshSession.token_hash == token_hash,
            RefreshSession.revoked == False,
            RefreshSession.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not refresh_session:
        raise HTTPException(status_code=401, detail="Refresh token expired or invalid")

    user = db.query(User).filter(User.id == refresh_session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found for this refresh token")
    return user, refresh_session

# ==============================
# ROUTES
# ==============================

@app.get("/docs", include_in_schema=False)
def custom_swagger_docs():
    response = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Rockify API Docs",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_ui_parameters={
            "docExpansion": "list",
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "filter": True,
            "persistAuthorization": True,
            "tryItOutEnabled": True,
            "syntaxHighlight.theme": "monokai",
        },
    )

    html = response.body.decode("utf-8")
    html = html.replace("</head>", f"<style>{DOCS_CUSTOM_CSS}</style></head>")
    html = html.replace("</body>", f"<script>{DOCS_CUSTOM_JS}</script></body>")
    return HTMLResponse(html)


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
def swagger_redirect():
    return get_swagger_ui_oauth2_redirect_html()

@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rockify API</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #f7f2ea;
                --ink: #1f2940;
                --ink-soft: #5d6a84;
                --card: #fffdfa;
                --line: #e9dfd1;
                --accent: #dd5e89;
                --accent-2: #f7bb97;
            }

            * { box-sizing: border-box; }

            body {
                margin: 0;
                min-height: 100vh;
                font-family: "Space Grotesk", sans-serif;
                color: var(--ink);
                background:
                    radial-gradient(circle at 10% 15%, #ffd7df 0%, transparent 30%),
                    radial-gradient(circle at 90% 90%, #ffe8d4 0%, transparent 30%),
                    var(--bg);
                padding: 24px;
                display: grid;
                place-items: center;
            }

            .layout {
                width: 100%;
                max-width: 980px;
                display: grid;
                grid-template-columns: 1.05fr 0.95fr;
                gap: 18px;
            }

            .hero, .panel {
                background: var(--card);
                border: 1px solid var(--line);
                border-radius: 20px;
                box-shadow: 0 12px 35px rgba(31, 41, 64, 0.08);
            }

            .hero {
                padding: 28px;
                position: relative;
                overflow: hidden;
            }

            .hero::after {
                content: "";
                position: absolute;
                width: 170px;
                height: 170px;
                right: -35px;
                top: -35px;
                border-radius: 50%;
                background: linear-gradient(120deg, var(--accent), var(--accent-2));
                opacity: 0.25;
            }

            .kicker {
                display: inline-block;
                font-size: 12px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: #8d365d;
                background: #ffe7f0;
                border: 1px solid #ffc8da;
                border-radius: 999px;
                padding: 6px 10px;
                margin-bottom: 14px;
            }

            h1 {
                margin: 0;
                font-size: clamp(32px, 5vw, 50px);
                line-height: 1.03;
                max-width: 11ch;
            }

            p {
                margin: 14px 0 0;
                color: var(--ink-soft);
                line-height: 1.5;
                font-size: 15px;
                max-width: 46ch;
            }

            .tags {
                margin-top: 20px;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }

            .tag {
                font-size: 12px;
                border: 1px solid var(--line);
                background: #fff;
                border-radius: 999px;
                padding: 6px 10px;
            }

            .panel {
                padding: 24px;
            }

            .panel h2 {
                margin: 0 0 10px;
                font-size: 24px;
            }

            .cta-list {
                display: grid;
                gap: 10px;
                margin-top: 14px;
            }

            .cta {
                display: block;
                width: 100%;
                text-decoration: none;
                color: #fff;
                font-weight: 700;
                border-radius: 12px;
                padding: 12px 14px;
                background: linear-gradient(120deg, var(--accent), var(--accent-2));
            }

            .cta.secondary {
                color: var(--ink);
                background: #fff;
                border: 1px solid var(--line);
            }

            ul {
                margin: 14px 0 0;
                padding-left: 18px;
                color: var(--ink-soft);
                font-size: 14px;
                line-height: 1.55;
            }

            @media (max-width: 860px) {
                .layout { grid-template-columns: 1fr; }
                .hero, .panel { border-radius: 16px; }
            }
        </style>
    </head>
    <body>
        <main class="layout">
            <section class="hero">
                <span class="kicker">Music platform API</span>
                <h1>Rockify</h1>
                <p>
                    Backend per artisti, brani, radio, eventi e post: tutto in un unico servizio FastAPI.
                    Questa pagina e` la porta di ingresso, mentre la documentazione interattiva ti guida endpoint per endpoint.
                </p>
                <div class="tags">
                    <span class="tag">Upload Song</span>
                    <span class="tag">Artist Profile</span>
                    <span class="tag">Events</span>
                    <span class="tag">Community Posts</span>
                </div>
            </section>

            <section class="panel">
                <h2>Vai Subito</h2>
                <div class="cta-list">
                    <a class="cta" href="/docs">Apri Swagger Docs</a>
                    <a class="cta secondary" href="/redoc">Apri ReDoc</a>
                    <a class="cta secondary" href="/world-radio">Mappa 3D Radio Mondo</a>
                    <a class="cta secondary" href="/songs">Test rapido: GET /songs</a>
                </div>

                <ul>
                    <li>Se vedi una lista vuota su <code>/songs</code>, e` normale: non ci sono ancora brani caricati.</li>
                    <li>Per testare i POST usa i form direttamente in <code>/docs</code>.</li>
                    <li>Gli upload vengono serviti sotto il path <code>/uploads</code>.</li>
                </ul>
            </section>
        </main>
    </body>
    </html>
    """

# ------------------------------
# USER REGISTRATION
# ------------------------------

@app.post("/register")
def register(request: Request,
             username: str = Form(...),
             email: str = Form(...),
             password: str = Form(...),
             role: str = Form("user"),
             db: Session = Depends(get_db)):

    enforce_ip_rate_limit(request, "register", max_requests=15, window_seconds=60)

    email_norm = normalize_email(email)
    existing = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if not validate_password_strength(password):
        raise HTTPException(
            status_code=400,
            detail="Weak password: use at least 8 chars with upper, lower, number and symbol",
        )

    role_norm = role.strip().lower()
    if role_norm not in {"user", "artist"}:
        raise HTTPException(status_code=400, detail="Invalid role. Allowed: user, artist")

    user = User(
        username=username,
        email=email_norm,
        password=hash_password(password),
        role=role_norm
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created successfully"}


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    enforce_ip_rate_limit(request, "login", max_requests=20, window_seconds=60)

    email_norm = normalize_email(email)
    now = datetime.utcnow()

    guard = db.query(LoginGuard).filter(LoginGuard.email == email_norm).first()
    if not guard:
        guard = LoginGuard(email=email_norm, failed_attempts=0, locked_until=None)
        db.add(guard)
        db.commit()
        db.refresh(guard)

    if guard.locked_until and guard.locked_until > now:
        remaining = int((guard.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(status_code=423, detail=f"Account temporarily locked. Retry in {remaining} min")

    user = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if not user or not verify_password(password, user.password):
        guard.failed_attempts += 1
        if guard.failed_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            guard.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            guard.failed_attempts = 0
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    guard.failed_attempts = 0
    guard.locked_until = None
    access_token, access_expires_at = issue_session_token(user.id, db)
    refresh_token, refresh_expires_at = issue_refresh_token(user.id, db)
    db.refresh(guard)
    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": access_expires_at.isoformat(),
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_expires_at.isoformat(),
    }


@app.post("/refresh-token")
def refresh_token(request: Request, refresh_token: str = Form(...), db: Session = Depends(get_db)):
    enforce_ip_rate_limit(request, "refresh", max_requests=40, window_seconds=60)

    user, current_refresh_session = get_user_from_refresh_token(refresh_token, db)

    # Rotate refresh token: old one is revoked immediately.
    current_refresh_session.revoked = True
    db.commit()

    access_token, access_expires_at = issue_session_token(user.id, db)
    new_refresh_token, refresh_expires_at = issue_refresh_token(user.id, db)

    return {
        "message": "Token refreshed",
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": access_expires_at.isoformat(),
        "refresh_token": new_refresh_token,
        "refresh_expires_at": refresh_expires_at.isoformat(),
    }


@app.get("/me")
def me(authorization: str = Header(None, alias="Authorization"), db: Session = Depends(get_db)):
    user, session = get_user_from_bearer(authorization or "", db)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "session_expires_at": session.expires_at.isoformat(),
    }


@app.post("/logout")
def logout(authorization: str = Header(None, alias="Authorization"), db: Session = Depends(get_db)):
    _, session = get_user_from_bearer(authorization, db)
    session.revoked = True
    db.commit()
    return {"message": "Logout successful"}


@app.post("/logout-all")
def logout_all(authorization: str = Header(None, alias="Authorization"), db: Session = Depends(get_db)):
    user, _ = get_user_from_bearer(authorization, db)

    db.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.revoked == False,
    ).update({"revoked": True}, synchronize_session=False)

    db.query(RefreshSession).filter(
        RefreshSession.user_id == user.id,
        RefreshSession.revoked == False,
    ).update({"revoked": True}, synchronize_session=False)

    db.commit()
    return {"message": "All sessions revoked"}

# ------------------------------
# CREATE ARTIST PROFILE
# ------------------------------

@app.post("/create-artist")
def create_artist(user_id: int = Form(...),
                  bio: str = Form(...),
                  country: str = Form(...),
                  genre: str = Form(...),
                  db: Session = Depends(get_db)):

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    artist = Artist(
        user_id=user_id,
        bio=bio,
        country=country,
        genre=genre
    )

    db.add(artist)
    db.commit()
    return {"message": "Artist profile created"}

# ------------------------------
# UPLOAD SONG
# ------------------------------

@app.post("/upload-song")
def upload_song(title: str = Form(...),
                artist_id: int = Form(...),
                song_file: UploadFile = File(...),
                cover_file: UploadFile = File(...),
                db: Session = Depends(get_db)):

    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    song_path = f"uploads/songs/{song_file.filename}"
    cover_path = f"uploads/images/{cover_file.filename}"

    with open(song_path, "wb") as buffer:
        shutil.copyfileobj(song_file.file, buffer)

    with open(cover_path, "wb") as buffer:
        shutil.copyfileobj(cover_file.file, buffer)

    song = Song(
        title=title,
        file_path=song_path,
        cover_path=cover_path,
        artist_id=artist_id
    )

    db.add(song)
    db.commit()

    return {"message": "Song uploaded successfully"}

# ------------------------------
# LIST SONGS
# ------------------------------

@app.get("/songs")
def list_songs(db: Session = Depends(get_db)):
    songs = db.query(Song).all()
    return songs

# ------------------------------
# ADD RADIO
# ------------------------------

@app.post("/add-radio")
def add_radio(name: str = Form(...),
              country: str = Form(...),
              city: str = Form(...),
              stream_url: str = Form(...),
              genre: str = Form(...),
              db: Session = Depends(get_db)):

    radio = Radio(
        name=name,
        country=country,
        city=city,
        stream_url=stream_url,
        genre=genre
    )

    db.add(radio)
    db.commit()
    return {"message": "Radio added"}

# ------------------------------
# LIST RADIOS
# ------------------------------

@app.get("/radios")
def list_radios(db: Session = Depends(get_db)):
    return db.query(Radio).all()


@app.get("/api/world-radios")
def world_radios(
    request: Request,
    name: str = "",
    country: str = "",
    tag: str = "",
    limit: int = 200,
    https_only: bool = True,
):
    enforce_ip_rate_limit(request, "world_radios", max_requests=60, window_seconds=60)

    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

    stations = fetch_world_radios(
        name=name,
        country=country,
        tag=tag,
        limit=limit,
        https_only=https_only,
    )
    return {
        "count": len(stations),
        "filters": {
            "name": name,
            "country": country,
            "tag": tag,
            "limit": limit,
            "https_only": https_only,
        },
        "stations": stations,
    }


@app.get("/world-radio", response_class=HTMLResponse)
def world_radio_page():
    return """
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rockify World Radio</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-1: #00111f;
                --bg-2: #13334e;
                --panel: rgba(3, 16, 31, 0.72);
                --line: rgba(151, 214, 242, 0.35);
                --ink: #e9f7ff;
                --muted: #9ab7c8;
                --accent: #5ad8ff;
                --accent-2: #ffd166;
                --danger: #ff7b72;
            }

            * { box-sizing: border-box; }

            body {
                margin: 0;
                min-height: 100vh;
                color: var(--ink);
                font-family: "Sora", sans-serif;
                background:
                    radial-gradient(circle at 12% 18%, rgba(90, 216, 255, 0.20), transparent 36%),
                    radial-gradient(circle at 88% 82%, rgba(255, 209, 102, 0.16), transparent 32%),
                    linear-gradient(150deg, var(--bg-1), var(--bg-2));
            }

            .wrap {
                max-width: 1380px;
                margin: 0 auto;
                padding: 20px;
                display: grid;
                grid-template-columns: 380px minmax(0, 1fr);
                gap: 16px;
            }

            .panel {
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 20px;
                backdrop-filter: blur(8px);
                box-shadow: 0 16px 34px rgba(0, 0, 0, 0.24);
            }

            .controls {
                padding: 18px;
                display: grid;
                gap: 12px;
                align-content: start;
                max-height: calc(100vh - 40px);
                overflow: auto;
            }

            .title {
                margin: 0;
                font-size: 24px;
                line-height: 1.1;
            }

            .subtitle {
                margin: 0;
                color: var(--muted);
                font-size: 13px;
                line-height: 1.45;
            }

            .grid {
                display: grid;
                gap: 8px;
            }

            label {
                font-size: 12px;
                color: var(--muted);
                letter-spacing: 0.03em;
            }

            input {
                width: 100%;
                border: 1px solid var(--line);
                background: rgba(8, 31, 52, 0.75);
                color: var(--ink);
                border-radius: 10px;
                padding: 10px;
                font: inherit;
            }

            input:focus {
                outline: none;
                border-color: var(--accent);
                box-shadow: 0 0 0 3px rgba(90, 216, 255, 0.2);
            }

            .actions {
                display: flex;
                gap: 8px;
            }

            button {
                flex: 1;
                border: none;
                border-radius: 10px;
                padding: 11px;
                font: inherit;
                font-weight: 700;
                cursor: pointer;
                color: #082439;
                background: linear-gradient(120deg, var(--accent), #9fe7ff);
            }

            button.secondary {
                background: linear-gradient(120deg, var(--accent-2), #ffedab);
            }

            .status {
                font-size: 12px;
                color: var(--muted);
                min-height: 18px;
            }

            .status.error { color: var(--danger); }

            .player {
                border: 1px solid var(--line);
                border-radius: 12px;
                background: rgba(9, 27, 46, 0.75);
                padding: 10px;
                display: grid;
                gap: 6px;
            }

            .station-name {
                font-size: 16px;
                font-weight: 700;
                line-height: 1.2;
            }

            .station-meta {
                font-size: 12px;
                color: var(--muted);
            }

            audio {
                width: 100%;
                height: 36px;
            }

            .list {
                margin: 0;
                padding: 0;
                list-style: none;
                display: grid;
                gap: 8px;
                max-height: 44vh;
                overflow: auto;
            }

            .list button {
                width: 100%;
                text-align: left;
                color: var(--ink);
                background: rgba(13, 38, 60, 0.8);
                border: 1px solid var(--line);
                padding: 10px;
                font-weight: 600;
            }

            .list button:hover { border-color: var(--accent); }

            .list .line {
                display: block;
                font-size: 11px;
                font-weight: 400;
                color: var(--muted);
                margin-top: 3px;
            }

            .globe-panel {
                position: relative;
                height: calc(100vh - 40px);
                min-height: 560px;
                overflow: hidden;
            }

            #globe {
                width: 100%;
                height: 100%;
                min-height: 100%;
            }

            #globe canvas {
                display: block;
            }

            .legend {
                position: absolute;
                right: 14px;
                bottom: 14px;
                border: 1px solid var(--line);
                border-radius: 10px;
                padding: 8px 10px;
                background: rgba(5, 19, 33, 0.72);
                font-size: 12px;
                color: var(--muted);
            }

            @media (max-width: 1020px) {
                .wrap {
                    grid-template-columns: 1fr;
                    padding: 12px;
                }

                .controls {
                    max-height: none;
                }

                .globe-panel {
                    height: 62vh;
                    min-height: 430px;
                }
            }
        </style>
    </head>
    <body>
        <main class="wrap">
            <section class="panel controls">
                <h1 class="title">World Radio Globe</h1>
                <p class="subtitle">
                    Cerca emittenti gratis da tutto il mondo usando Radio Browser,
                    clicca un punto sul globo e ascolta subito lo stream.
                </p>

                <div class="grid">
                    <label for="country">Paese</label>
                    <input id="country" type="text" placeholder="Es: Italy, Japan, Brazil">
                </div>

                <div class="grid">
                    <label for="name">Nome radio</label>
                    <input id="name" type="text" placeholder="Es: Rock, Jazz FM, BBC">
                </div>

                <div class="grid">
                    <label for="tag">Genere/Tag</label>
                    <input id="tag" type="text" placeholder="Es: rock, pop, classical">
                </div>

                <div class="actions">
                    <button id="searchBtn">Cerca</button>
                    <button id="randomBtn" class="secondary" type="button">Random</button>
                </div>

                <div id="status" class="status"></div>

                <section class="player">
                    <div id="stationName" class="station-name">Nessuna radio selezionata</div>
                    <div id="stationMeta" class="station-meta">Seleziona un punto sul globo o dalla lista.</div>
                    <audio id="audio" controls preload="none"></audio>
                </section>

                <ul id="stationList" class="list"></ul>
            </section>

            <section class="panel globe-panel">
                <div id="globe"></div>
                <div class="legend">Punti luminosi: stazioni disponibili via HTTPS</div>
            </section>
        </main>

        <script src="https://unpkg.com/globe.gl"></script>
        <script>
            const globeContainer = document.getElementById('globe');
            const countryInput = document.getElementById('country');
            const nameInput = document.getElementById('name');
            const tagInput = document.getElementById('tag');
            const statusEl = document.getElementById('status');
            const stationListEl = document.getElementById('stationList');
            const stationNameEl = document.getElementById('stationName');
            const stationMetaEl = document.getElementById('stationMeta');
            const audioEl = document.getElementById('audio');

            let stations = [];

            const globe = Globe()(globeContainer)
                .globeImageUrl('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
                .bumpImageUrl('https://unpkg.com/three-globe/example/img/earth-topology.png')
                .backgroundColor('rgba(0,0,0,0)')
                .showAtmosphere(true)
                .atmosphereColor('#6ecbff')
                .atmosphereAltitude(0.18)
                .pointLat('lat')
                .pointLng('lon')
                .pointLabel((d) => `${d.name}<br>${d.country}${d.city ? ' - ' + d.city : ''}`)
                .pointAltitude(0.013)
                .pointRadius(0.34)
                .pointColor(() => '#5ad8ff')
                .pointResolution(8)
                .onPointClick((station) => {
                    if (station) {
                        playStation(station);
                    }
                });

            function syncGlobeSize() {
                globe.width(globeContainer.clientWidth);
                globe.height(globeContainer.clientHeight);
            }

            syncGlobeSize();
            window.addEventListener('resize', syncGlobeSize);

            globe.controls().autoRotate = true;
            globe.controls().autoRotateSpeed = 0.35;
            globe.controls().enablePan = false;
            globe.controls().zoomSpeed = 1.2;
            globe.controls().minDistance = 120;
            globe.controls().maxDistance = 700;
            globe.pointOfView({ lat: 16, lng: 9, altitude: 1.65 }, 0);

            function setStatus(text, isError = false) {
                statusEl.textContent = text;
                statusEl.classList.toggle('error', isError);
            }

            function renderList(max = 25) {
                stationListEl.innerHTML = '';
                stations.slice(0, max).forEach((station) => {
                    const li = document.createElement('li');
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.innerHTML =
                        `${station.name}<span class="line">${station.country} ${station.city ? ' - ' + station.city : ''} ${station.tags ? ' - ' + station.tags : ''}</span>`;
                    btn.addEventListener('click', () => playStation(station));
                    li.appendChild(btn);
                    stationListEl.appendChild(li);
                });
            }

            function playStation(station) {
                stationNameEl.textContent = station.name;
                stationMetaEl.textContent = `${station.country}${station.city ? ' - ' + station.city : ''}${station.tags ? ' - ' + station.tags : ''}`;
                audioEl.src = station.stream_url;
                audioEl.play().catch(() => {
                    setStatus('Play bloccato dal browser: clicca Play nel player audio.', false);
                });
            }

            async function searchStations() {
                const params = new URLSearchParams({
                    country: countryInput.value.trim(),
                    name: nameInput.value.trim(),
                    tag: tagInput.value.trim(),
                    limit: '220',
                    https_only: 'true',
                });

                setStatus('Ricerca stazioni globali in corso...');

                try {
                    const response = await fetch(`/api/world-radios?${params.toString()}`);
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }

                    const payload = await response.json();
                    stations = payload.stations || [];

                    globe.pointsData(stations);
                    renderList();

                    if (stations.length === 0) {
                        setStatus('Nessuna stazione trovata con questi filtri.', true);
                    } else {
                        setStatus(`Trovate ${stations.length} stazioni (con stream HTTPS).`);
                    }
                } catch (err) {
                    console.error(err);
                    setStatus('Errore durante la ricerca radio. Riprova tra poco.', true);
                }
            }

            document.getElementById('searchBtn').addEventListener('click', searchStations);

            document.getElementById('randomBtn').addEventListener('click', () => {
                if (!stations.length) {
                    setStatus('Prima fai una ricerca, poi puoi usare Random.', true);
                    return;
                }
                const randomStation = stations[Math.floor(Math.random() * stations.length)];
                playStation(randomStation);
            });

            [countryInput, nameInput, tagInput].forEach((input) => {
                input.addEventListener('keydown', (event) => {
                    if (event.key === 'Enter') {
                        searchStations();
                    }
                });
            });

            tagInput.value = 'rock';
            searchStations();
        </script>
    </body>
    </html>
    """

# ------------------------------
# CREATE EVENT
# ------------------------------

@app.post("/create-event")
def create_event(artist_name: str = Form(...),
                 location: str = Form(...),
                 country: str = Form(...),
                 date: str = Form(...),
                 db: Session = Depends(get_db)):

    event = Event(
        artist_name=artist_name,
        location=location,
        country=country,
        date=datetime.fromisoformat(date)
    )

    db.add(event)
    db.commit()
    return {"message": "Event created"}

# ------------------------------
# LIST EVENTS
# ------------------------------

@app.get("/events")
def list_events(db: Session = Depends(get_db)):
    return db.query(Event).all()

# ------------------------------
# CREATE POST
# ------------------------------

@app.post("/create-post")
def create_post(user_id: int = Form(...),
                event_id: int = Form(...),
                description: str = Form(...),
                image: UploadFile = File(...),
                db: Session = Depends(get_db)):

    image_path = f"uploads/images/{image.filename}"

    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    post = Post(
        user_id=user_id,
        event_id=event_id,
        description=description,
        image_path=image_path
    )
    db.add(post)
    db.commit()

    return {"message": "Post created"}

# ------------------------------
# LIST POSTS
# ------------------------------

@app.get("/posts")
def list_posts(db: Session = Depends(get_db)):
    return db.query(Post).all()