import logging

from fastapi import FastAPI

from app.routers import account, admin, admin_crm, admin_rooms, admin_services, auth, bookings, hotel, rooms, services

# Логгеры приложения (например, console-почта) пишут в тот же поток, что и uvicorn: его видно в docker compose logs.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

app = FastAPI(
    title="API гостиницы Kivana",
    description="JSON API сайта гостиницы: данные отеля, каталог номеров, заявки на бронирование и их обработка.",
    version="1.0.0",
)

app.include_router(hotel.router)
app.include_router(rooms.router)
app.include_router(bookings.router)
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(admin.router)
app.include_router(admin_crm.router)
app.include_router(admin_rooms.router)
app.include_router(services.router)
app.include_router(admin_services.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
