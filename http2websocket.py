import asyncio
import json
import math
import websockets
import aiohttp
import threading
import time
import keyboard
import numpy as np
import os
import signal
import winsound

# --- Глобальні змінні та налаштування ---

# Змінні для калібрування
delta_accX = 0.0
delta_accY = 0.0

# Стан калібрування
class CalibrationState:
    IDLE = 0
    CALIBRATING = 1
    DONE = 2

calibration_state = CalibrationState.IDLE
calibration_data = []

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
HTTP_SERVER_URL = "http://192.168.0.100:8080/get?accX&accY"

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
    global calibration_state, delta_accX, delta_accY, calibration_data

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(HTTP_SERVER_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        accX = data.get("buffer", {}).get("accX", {}).get("buffer", [0])[0]
                        accY = data.get("buffer", {}).get("accY", {}).get("buffer", [0])[0]

                        if calibration_state == CalibrationState.CALIBRATING:
                            calibration_data.append((accX, accY))
                            continue 

                        if calibration_state == CalibrationState.DONE:
                            accX -= delta_accX
                            accY -= delta_accY

                        ratio_x = clamp(accX / SCALING_FACTOR, -1.0, 1.0)
                        ratio_y = clamp(accY / SCALING_FACTOR, -1.0, 1.0)
                        
                        angle_x = math.degrees(math.asin(ratio_x))
                        angle_y = math.degrees(math.asin(ratio_y))

                        SENSOR_DATA.update({
                            "accX": accX, "accY": accY,
                            "angle_x": angle_x, "angle_y": angle_y
                        })
                    else:
                        print(f"Помилка отримання даних: HTTP {response.status}")
            except aiohttp.ClientError as e:
                print(f"Помилка підключення до HTTP-сервера: {e}")
            except json.JSONDecodeError:
                print("Помилка: не вдалося розкодувати JSON.")
            
            if CONNECTED_CLIENTS:
                message = json.dumps({"angle_x": SENSOR_DATA["angle_x"], "angle_y": SENSOR_DATA["angle_y"]})
                # Використовуємо gather з return_exceptions=True, щоб уникнути падіння циклу,
                # якщо один з клієнтів від'єднався.
                await asyncio.gather(*[client.send(message) for client in CONNECTED_CLIENTS], return_exceptions=True)
            
            await asyncio.sleep(0.02)

def calibration_thread():
    """
    Потік для виконання калібрування.
    """
    global calibration_state, delta_accX, delta_accY, calibration_data
    
    print("Режим калібрування. Тримайте смартфон у стані спокою впродовж 5 секунд")
    calibration_data = []
    calibration_state = CalibrationState.CALIBRATING
    
    for i in range(5, 0, -1):
        print(f"{i}...")
        if i == 1:
            winsound.Beep(1000, 600)
        else:
            winsound.Beep(1000, 200)
        time.sleep(1)
        
    if calibration_data:
        accX_data, accY_data = zip(*calibration_data)
        delta_accX = np.mean(accX_data)
        delta_accY = np.mean(accY_data)
        print(f"Калібрування завершено: delta_accX={delta_accX:.2f}, delta_accY={delta_accY:.2f}")
    else:
        print("Не вдалося отримати дані для калібрування.")

    calibration_state = CalibrationState.DONE

import os
import signal

def input_handler():
    """
    Обробник введення з клавіатури для керування програмою.
    """
    global calibration_state
    
    while True:
        key = keyboard.read_key()
        if key == 'c' or key == 'C':
            if calibration_state != CalibrationState.CALIBRATING:
                cal_thread = threading.Thread(target=calibration_thread)
                cal_thread.start()
        elif key == 'q' or key == 'Q':
            print("Завершення роботи...")
            os.kill(os.getpid(), signal.SIGINT)
            break
        time.sleep(0.1)


async def main_async():
    """Основна функція, яка запускає WebSocket-сервер та цикл обробки даних."""
    
    server = await websockets.serve(register_client, "localhost", 8767)
    data_task = asyncio.create_task(data_loop())

    print("WebSocket-сервер запущено на ws://localhost:8767")
    print("Клавіші керування: C - калібрування стану спокою, Q - завершення роботи")
    
    try:
        await data_task
    except asyncio.CancelledError:
        pass
    finally:
        server.close()
        await server.wait_closed()

def main():
    input_thread = threading.Thread(target=input_handler)
    input_thread.daemon = True
    input_thread.start()
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        print("\nПрограму зупинено.")
    finally:
        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            task.cancel()
        
        # Збираємо всі задачі, щоб вони завершилися з CancelledError
        group = asyncio.gather(*tasks, return_exceptions=True)
        loop.run_until_complete(group)
        loop.close()


# Точка входу в програму
if __name__ == "__main__":
    main()
