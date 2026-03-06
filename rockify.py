# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 17:16:42 2026

@author: corin
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from passlib.context import CryptContext
from datetime import datetime
import os
import shutil

# ==============================
# CONFIG
# ==============================

DATABASE_URL = "sqlite:///./rockyfi.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"])

app = FastAPI(title="Rockyfi API")

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

# ==============================
# ROUTES
# ==============================

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
def register(username: str = Form(...),
             email: str = Form(...),
             password: str = Form(...),
             role: str = Form("user"),
             db: Session = Depends(get_db)):

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=username,
        email=email,
        password=hash_password(password),
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User created successfully"}

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