#!/usr/bin/env python3.10
"""
Podcast Note Viewer — FastAPI backend
資料來源：Obsidian 投資筆記（.md）+ data/episodes（音頻、逐字稿）
"""

import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cache_store import init_cache_db
from podcast_routes import router as podcast_router
from reading_routes import router as reading_router
from remote import _prefetch_all_remote
from settings import SERVER_HOST, SERVER_PORT, STATIC_DIR
from youtube_routes import router as youtube_router, start_youtube_auto_transcript_worker
from youtube_services import _backfill_avatars

app = FastAPI(title="Podcast Note Viewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(podcast_router)
app.include_router(reading_router)
app.include_router(youtube_router)


@app.on_event("startup")
async def on_startup():
    init_cache_db()
    threading.Thread(target=_backfill_avatars, daemon=True).start()
    threading.Thread(target=_prefetch_all_remote, daemon=True).start()
    start_youtube_auto_transcript_worker()


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)

