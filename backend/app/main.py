from fastapi import FastAPI

from app.routers import admin, bookings, hotel, rooms

app = FastAPI(
    title="API гостиницы Kivana",
    description="JSON API сайта гостиницы: данные отеля, каталог номеров, заявки на бронирование и их обработка.",
    version="1.0.0",
)

app.include_router(hotel.router)
app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
