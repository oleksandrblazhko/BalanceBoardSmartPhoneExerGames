1) Є вебсервер, який надає дані за адресою http://192.168.0.103:8080/get?accX&accY
з акселерометра смартфона, які отримані програмою phyphox   
2) JSON-приклад відповіді вебсервера, де accX = 1.2705001E-1, accY = -1.1895001E-1
{"buffer":{
"accX":{"size":0,"updateMode":"single", "buffer":[1.2705001E-1]},
"accY":{"size":0,"updateMode":"single", "buffer":[-1.1895001E-1]}
},
"status":{
"session":"348afd", "measuring":true, "timedRun":false, "countDown":0
}
}

3) треба створити python-програму з назвою http2websocket.py, яка:
- періодично кожні 0.02 секунди, надсилає запит до серверу за вказаним прикладом
- отримує значення змінних accX = 1.2705001E-1, accY = -1.1895001E-1
- створює websocket-сервер
- перетворює значення accX, accY у градуси angle_x, angle_y
- передає через websocket-сервер значення angle_x, angle_y

