import asyncio
import json
import math
import websockets
import aiohttp

# --- Глобальні змінні та налаштування ---

# Множина для зберігання всіх підключених клієнтів WebSocket
CONNECTED_CLIENTS = set()

# Словник для зберігання останніх даних з сенсорів, включаючи розраховані кути
SENSOR_DATA = {
    "accX": 0,
    "accY": 0,
    "angle_x": 0,
    "angle_y": 0
}

# URL-адреса HTTP-сервера, звідки беруться дані
HTTP_SERVER_URL = "http://192.168.0.103:8080/get?accX&accY"

# Коефіцієнт масштабування для перетворення значень акселерометра в кути
SCALING_FACTOR = 7.1

def clamp(value, min_val, max_val):
    """Допоміжна функція, що обмежує значення в заданому діапазоні [min_val, max_val]."""
    return max(min_val, min(value, max_val))

async def register_client(websocket):
    """
    Реєструє нового клієнта, що підключився, 
    і утримує з'єднання відкритим до його закриття.
    """
    CONNECTED_CLIENTS.add(websocket)
    print(f"Новий клієнт підключився. Всього клієнтів: {len(CONNECTED_CLIENTS)}")
    try:
        # Очікуємо, поки клієнт не від'єднається
        await websocket.wait_closed()
    finally:
        # Видаляємо клієнта з множини після від'єднання
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Клієнт від'єднався. Всього клієнтів: {len(CONNECTED_CLIENTS)}")

async def data_loop():
    """
    Головний цикл програми: періодично запитує дані з HTTP-сервера,
    обчислює кути нахилу та транслює їх усім підключеним клієнтам.
    """
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Запит даних з сенсора по HTTP
                async with session.get(HTTP_SERVER_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        accX = data.get("buffer", {}).get("accX", {}).get("buffer", [0])[0]
                        accY = data.get("buffer", {}).get("accY", {}).get("buffer", [0])[0]

                        # Обчислення кутів
                        # Обмежуємо співвідношення діапазоном [-1.0, 1.0] для коректної роботи asin
                        ratio_x = clamp(accX / SCALING_FACTOR, -1.0, 1.0)
                        ratio_y = clamp(accY / SCALING_FACTOR, -1.0, 1.0)
                        
                        angle_x = math.degrees(math.asin(ratio_x))
                        angle_y = math.degrees(math.asin(ratio_y))

                        # Оновлення глобального словника з даними
                        SENSOR_DATA["accX"] = accX
                        SENSOR_DATA["accY"] = accY
                        SENSOR_DATA["angle_x"] = angle_x
                        SENSOR_DATA["angle_y"] = angle_y
                    else:
                        print(f"Помилка отримання даних: HTTP {response.status}")
            except aiohttp.ClientError as e:
                print(f"Помилка підключення до HTTP-сервера: {e}")
            except json.JSONDecodeError:
                print("Помилка: не вдалося розкодувати JSON.")
            
            # Трансляція даних (лише кутів) усім клієнтам
            if CONNECTED_CLIENTS:
                angles_to_send = {
                    "angle_x": SENSOR_DATA["angle_x"],
                    "angle_y": SENSOR_DATA["angle_y"]
                }
                message = json.dumps(angles_to_send)
                # Асинхронно надсилаємо повідомлення всім клієнтам
                await asyncio.wait([client.send(message) for client in CONNECTED_CLIENTS])
            
            # Пауза перед наступною ітерацією циклу (0.02 секунди)
            await asyncio.sleep(0.02)

async def main():
    """Основна функція, яка запускає WebSocket-сервер та цикл обробки даних."""
    server = await websockets.serve(register_client, "localhost", 8767)
    data_task = asyncio.create_task(data_loop())

    print("WebSocket-сервер запущено на ws://localhost:8767")
    
    # Очікуємо завершення роботи сервера
    await server.wait_closed()
    data_task.cancel()


# Точка входу в програму
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограму зупинено користувачем.")
    except Exception as e:
        print(f"Виникла неочікувана помилка: {e}")
