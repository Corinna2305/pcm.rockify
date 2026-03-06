# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 17:16:42 2026

@author: corin
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

@app.get("/")
def root():
    return {"message": "Welcome to Rockyfi 🎸"}

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