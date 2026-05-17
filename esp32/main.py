import network
import socket
from machine import Pin, ADC, PWM, SoftI2C
import dht
import neopixel
import ssd1306
import time
import json
from umqtt.simple import MQTTClient

# ==========================================
# 1. CONFIGURAÇÃO DE PINOS E COMPONENTES
# ==========================================
sensor_dht = dht.DHT22(Pin(15))
sensor_pir = Pin(13, Pin.IN)
sensor_ldr = ADC(Pin(34))
sensor_ldr.atten(ADC.ATTN_11DB)
sensor_portao = Pin(12, Pin.IN, Pin.PULL_UP)

rele_luz = Pin(14, Pin.OUT)
buzzer_alarme = Pin(25, Pin.OUT)
servo_persiana = PWM(Pin(26), freq=50)

NUM_LEDS = 6
anel_ar = neopixel.NeoPixel(Pin(27), NUM_LEDS)

i2c = SoftI2C(scl=Pin(22), sda=Pin(21))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# ==========================================
# 2. CONEXÃO WI-FI
# ==========================================
print("Conectando ao Wi-Fi Wokwi-GUEST...")
rede = network.WLAN(network.STA_IF)
rede.active(True)
rede.connect('Wokwi-GUEST', '')

while not rede.isconnected():
    print(".", end="")
    time.sleep(0.1)
    
print("\nConectado com sucesso!")
print("Endereço IP:", rede.ifconfig()[0])

# ==========================================
# 3. CONFIGURAÇÕES DO MQTT (HiveMQ)
# ==========================================
MQTT_CLIENT_ID = "diego_umc_esp32_quarto"
MQTT_BROKER    = "broker.hivemq.com"
MQTT_TOPIC_PUB = "diego/quarto/sensores"
MQTT_TOPIC_SUB = "diego/quarto/comandos"

estado_luz = False
estado_ar = False
estado_persiana = False
estado_alarme = False

COMANDOS_MQTT = {
    "LUZ_ON": ("estado_luz", True),
    "LUZ_OFF": ("estado_luz", False),
    "AR_ON": ("estado_ar", True),
    "AR_OFF": ("estado_ar", False),
    "PERSIANA_ON": ("estado_persiana", True),
    "PERSIANA_OFF": ("estado_persiana", False),
    "ALARME_ON": ("estado_alarme", True),
    "ALARME_OFF": ("estado_alarme", False),
}

def atualizar_atuadores():
    rele_luz.value(1 if estado_luz else 0)
    for i in range(NUM_LEDS):
        anel_ar[i] = (0, 0, 255) if estado_ar else (0, 0, 0)
    anel_ar.write()
    servo_persiana.duty(115 if estado_persiana else 40)
    buzzer_alarme.value(1 if estado_alarme else 0)

def mqtt_callback(topic, msg):
    global estado_luz, estado_ar, estado_persiana, estado_alarme
    comando = msg.decode('utf-8')
    print("Comando MQTT recebido: {}".format(comando))

    acao = COMANDOS_MQTT.get(comando)
    if acao:
        nome_estado, valor = acao
        if nome_estado == "estado_luz":
            estado_luz = valor
        elif nome_estado == "estado_ar":
            estado_ar = valor
        elif nome_estado == "estado_persiana":
            estado_persiana = valor
        elif nome_estado == "estado_alarme":
            estado_alarme = valor
    
    atualizar_atuadores()

print("Conectando ao broker MQTT...")
client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, keepalive=60)
client.set_callback(mqtt_callback)
client.connect()
client.subscribe(MQTT_TOPIC_SUB)
print("MQTT Conectado e inscrito em:", MQTT_TOPIC_SUB)

# ==========================================
# 4. PÁGINA HTML (Servidor Web)
# ==========================================
def gerar_html():
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

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 80)) 
s.listen(5)
s.settimeout(0.2) 

atualizar_atuadores()
tempo_ultima_leitura = time.ticks_ms()
print("Servidor Web rodando! Aguardando comandos...")
print("==========================================")

# ==========================================
# 5. LOOP PRINCIPAL
# ==========================================
while True:
    # A) Verifica mensagens MQTT recebidas
    try:
        client.check_msg()
    except:
        pass
        
    # B) Servidor Web Local
    try:
        conn, addr = s.accept()
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
        
        atualizar_atuadores()
        
        resposta = gerar_html()
        conn.send(b'HTTP/1.1 200 OK\nContent-Type: text/html\nConnection: close\n\n')
        conn.send(resposta.encode('utf-8'))
        conn.close()
    except OSError:
        pass 
    except Exception as e:
        try: conn.close()
        except: pass

    # C) Leitura de Sensores e Envio via MQTT a cada 2 segundos
    if time.ticks_diff(time.ticks_ms(), tempo_ultima_leitura) > 2000:
        try:
            sensor_dht.measure()
            temp = sensor_dht.temperature()
            umid = sensor_dht.humidity()
            luz = sensor_ldr.read()
            movimento = sensor_pir.value()
            portao = True if sensor_portao.value() == 0 else False 
            
            oled.fill(0)
            oled.text("CASA INTELIGENTE", 0, 0)
            oled.text("Temp: {}C U: {}%".format(temp, umid), 0, 16)
            oled.text("Luz: {}".format(luz), 0, 26)
            oled.text("Mov: {}".format('SIM' if movimento else 'NAO'), 0, 36)
            oled.text("Portao: {}".format('ABERTO' if portao else 'FECHADO'), 0, 46)
            oled.show()
            
            dados_json = json.dumps({
                "temperatura": temp,
                "umidade": umid,
                "luminosidade": luz,
                "movimento": movimento,
                "portao_aberto": portao
            })
            client.publish(MQTT_TOPIC_PUB, dados_json)
            print("Enviado MQTT: {}".format(dados_json))
            
        except Exception as e:
            pass
            
        tempo_ultima_leitura = time.ticks_ms()