"""
cabo preto = terra
cabo vermelho = energia
cabo azul = sda do ssd1306
cabo verde = scl do ssd1306
cabo azul claro = dht22
cabo amarelo = ldr
cabo roxo = pir
cabo cinza = slide-switch
cabo rosa = servo motor
cabo verde claro = neopixel
cabo laranja = relay
cabo branco = buzzer
"""
import network
import time
import dht
import ujson
import usocket as socket
from machine import Pin, ADC, PWM, SoftI2C
import neopixel
from umqtt.simple import MQTTClient
import ssd1306

# Configuração do wi-fi
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASS = ""

# Configuração do MQTT
MQTT_BROKER = "broker.hivemq.com"
MQTT_CLIENT_ID = "diego_umc_esp32_quarto"
MQTT_TOPIC_PUB = "diego/quarto/sensores"
MQTT_TOPIC_SUB = "diego/quarto/comandos"

# Pinagens
sensor_dht = dht.DHT22(Pin(15))
sensor_pir = Pin(13, Pin.IN)
sensor_ldr = ADC(Pin(34))
sensor_portao = Pin(12, Pin.IN, Pin.PULL_UP)

rele_luz = Pin(14, Pin.OUT)
buzzer_alarme = Pin(25, Pin.OUT)
servo_persiana = PWM(Pin(26), freq=50)
NUM_LEDS = 6
anel_ar = neopixel.NeoPixel(Pin(27), NUM_LEDS)

i2c = SoftI2C(scl=Pin(22), sda=Pin(21))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Configura a leitura analógica para ler 3.3V
sensor_ldr.atten(ADC.ATTN_11DB)

# Variaveis de controle e estado
estado_luz = False
estado_ar = False
estado_persiana = False
estado_alarme = False

ultimo_envio_mqtt = 0
intervalo_mqtt = 2000 # Envia dados a cada 2 segundos

# Função para conectar o wi-fi
def conecta_wifi():
    oled.fill(0)
    oled.text("Conectando WiFi...", 0, 10)
    oled.show()
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    while not wlan.isconnected():
        time.sleep(0.5)
    oled.fill(0)
    oled.text("WiFi Conectado!", 0, 10)
    oled.show()
    print("Endereço IP:", wlan.ifconfig()[0])
    time.sleep(1)

# Função para acionar os pinos fisicos
def atualiza_atuadores():
    rele_luz.value(1 if estado_luz else 0)
    for i in range(NUM_LEDS):
        anel_ar[i] = (0, 0, 255) if estado_ar else (0, 0, 0)
    anel_ar.write()
    servo_persiana.duty(115 if estado_persiana else 40)
    buzzer_alarme.value(1 if estado_alarme else 0)

# Recebe os comandos do Node-RED
def callback_mqtt(topic, msg):
    global estado_luz, estado_ar, estado_persiana, estado_alarme
    comando = msg.decode('utf-8')
    print("Comando MQTT:", comando)
    
    if comando == "LUZ_ON":
        estado_luz = True
    elif comando == "LUZ_OFF":
        estado_luz = False
    elif comando == "AR_ON":
        estado_ar = True
    elif comando == "AR_OFF":
        estado_ar = False
    elif comando == "PERSIANA_ON":
        estado_persiana = True
    elif comando == "PERSIANA_OFF":
        estado_persiana = False
    elif comando == "ALARME_ON":
        estado_alarme = True
    elif comando == "ALARME_OFF":
        estado_alarme = False
    
    atualiza_atuadores()

# Função para conectar com o MQTT
def conecta_mqtt():
    try:
        client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, keepalive=60)
        client.set_callback(callback_mqtt)
        client.connect()
        client.subscribe(MQTT_TOPIC_SUB)
        print("MQTT Conectado e inscrito no topico")
        return client
    except Exception as e:
        print("Erro MQTT:", e)
        return None

# String do site
def cria_pagina_web():
    html = """<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Painel IoT - Quarto</title>
    <style>
        body { font-family: Arial; text-align: center; margin: 0; background-color: #f4f4f9; }
        h2 { color: #333; margin-top: 20px; }
        .card { background: white; padding: 20px; margin: 10px auto; width: 80%; max-width: 400px; border-radius: 10px; box-shadow: 0px 4px 8px rgba(0,0,0,0.2); }
        .btn { border: none; padding: 10px 20px; color: white; font-size: 16px; margin: 5px; cursor: pointer; border-radius: 5px; }
        .on { background-color: #4CAF50; }
        .off { background-color: #f44336; }
    </style></head><body>
    <h2>🏡 Controle do Quarto Inteligente</h2>"""
    
    html += '<div class="card"><h3>💡 Luz do Corredor</h3>'
    html += '<p>Status: <b>{}</b></p>'.format('LIGADA' if estado_luz else 'DESLIGADA')
    html += '<a href="/?luz=on"><button class="btn on">Ligar</button></a>'
    html += '<a href="/?luz=off"><button class="btn off">Desligar</button></a></div>'
    
    html += '<div class="card"><h3>❄️ Ar-Condicionado</h3>'
    html += '<p>Status: <b>{}</b></p>'.format('LIGADO' if estado_ar else 'DESLIGADO')
    html += '<a href="/?ar=on"><button class="btn on">Ligar</button></a>'
    html += '<a href="/?ar=off"><button class="btn off">Desligar</button></a></div>'
    
    html += '<div class="card"><h3>🪟 Persiana</h3>'
    html += '<p>Status: <b>{}</b></p>'.format('ABERTA' if estado_persiana else 'FECHADA')
    html += '<a href="/?persiana=on"><button class="btn on">Abrir</button></a>'
    html += '<a href="/?persiana=off"><button class="btn off">Fechar</button></a></div>'
    
    html += '<div class="card"><h3>🚨 Alarme (Buzzer)</h3>'
    html += '<p>Status: <b>{}</b></p>'.format('TOCANDO' if estado_alarme else 'SILENCIADO')
    html += '<a href="/?alarme=on"><button class="btn on">Tocar</button></a>'
    html += '<a href="/?alarme=off"><button class="btn off">Silenciar</button></a></div>'
    
    html += '</body></html>'
    return html

# Inicialização
conecta_wifi()
mqtt_client = conecta_mqtt()
atualiza_atuadores()

# Configura Servidor Web local
servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
servidor.bind(('0.0.0.0', 80)) 
servidor.listen(5)
servidor.settimeout(0.2) 

print("Sistema de Automacao rodando!")

# Loop Principal
while True:
    tempo_atual = time.ticks_ms()
    
    # Verifica comandos MQTT
    if mqtt_client:
        try:
            mqtt_client.check_msg()
        except:
            pass
            
    # Verifica acessos na pagina web
    try:
        conn, addr = servidor.accept()
        conn.settimeout(1.0)
        request = conn.recv(1024).decode('utf-8')
        
        if '/?luz=on' in request:
            estado_luz = True
        elif '/?luz=off' in request:
            estado_luz = False
        elif '/?ar=on' in request:
            estado_ar = True
        elif '/?ar=off' in request:
            estado_ar = False
        elif '/?persiana=on' in request:
            estado_persiana = True
        elif '/?persiana=off' in request:
            estado_persiana = False
        elif '/?alarme=on' in request:
            estado_alarme = True
        elif '/?alarme=off' in request:
            estado_alarme = False
        
        atualiza_atuadores()
        resposta = cria_pagina_web()
        conn.send(b'HTTP/1.1 200 OK\nContent-Type: text/html\nConnection: close\n\n')
        conn.send(resposta.encode('utf-8'))
        conn.close()
    except OSError:
        pass 
    except Exception as e:
        try:
            conn.close()
        except:
            pass

    # Envio MQTT e atualizacao do display
    if tempo_atual - ultimo_envio_mqtt > intervalo_mqtt:
        try:
            sensor_dht.measure()
            t = sensor_dht.temperature()
            h = sensor_dht.humidity()
        except:
            t, h = 0.0, 0.0
            
        luz_val = sensor_ldr.read()
        mov = sensor_pir.value()
        portao = True if sensor_portao.value() == 0 else False 
        
        oled.fill(0)
        oled.text("CASA INTELIGENTE", 0, 0)
        oled.text(f"Temp: {t}C U: {h}%", 0, 16)
        oled.text(f"Luz: {luz_val}", 0, 26)
        oled.text(f"Mov: {'SIM' if mov else 'NAO'}", 0, 36)
        oled.text(f"Portao: {'ABERTO' if portao else 'FECHADO'}", 0, 46)
        oled.show()
        
        payload = ujson.dumps({
            "temperatura": t,
            "umidade": h,
            "luminosidade": luz_val,
            "movimento": mov,
            "portao_aberto": portao
        })
        
        if mqtt_client:
            try:
                mqtt_client.publish(MQTT_TOPIC_PUB, payload)
                print("Publicado MQTT:", payload)
            except Exception as e:
                print("Falha ao enviar MQTT. Reconectando...")
                mqtt_client = conecta_mqtt()
                
        ultimo_envio_mqtt = tempo_atual

    time.sleep(0.1)
