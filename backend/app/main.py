from fastapi import FastAPI

from app.routers import bookings, hotel, rooms

app = FastAPI(
    title="API гостиницы «Тихая гавань»",
    description="JSON API сайта гостиницы: данные отеля, каталог номеров, заявки на бронирование.",
    version="1.0.0",
)

app.include_router(hotel.router)
app.include_router(rooms.router)
app.include_router(bookings.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
