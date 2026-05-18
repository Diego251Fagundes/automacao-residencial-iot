import network
import time
import dht
import ujson
import usocket as socket
import ssl
import ubinascii
import ntptime
import urequests
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

# Configurações do email e planilha
EMAIL_REMETENTE = "diegoafagundess@gmail.com"
EMAIL_SENHA_APP = "ebevsgcqicwiprzr"
EMAIL_DESTINO = "diegoafagundess+01@gmail.com"
URL_PLANILHA = "https://script.google.com/macros/s/AKfycbyNJ_Wb7YMORWvRJRKSqPBHveyqQbSfhLr_NpbID5QO6X2afNgYsR_YNdAfKkoKiycRwg/exec"

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
sensor_ldr.atten(ADC.ATTN_11DB)

# Variaveis de controle e estado
estado_luz = False
estado_ar = False
estado_persiana = False
estado_alarme = False

# Travas Anti-Spam para Alertas
alerta_mov_enviado = False
alerta_portao_enviado = False

ultimo_envio_mqtt = 0
intervalo_mqtt = 2000 # Envia dados a cada 2 segundos

# Função para conectar na rede WiFi e sincronizar o relógio
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
    
    # Sincroniza o relógio para os alertas
    try:
        ntptime.settime()
        print("Relógio sincronizado!")
    except:
        pass
    time.sleep(1)

# Função para obter data e hora formatada (Fuso de Brasília - UTC-3)
def obtem_data_hora():
    try:
        t = time.time() - 10800 # Fuso de Brasília (UTC-3)
        tm = time.localtime(t)
        return f"{tm[2]:02d}/{tm[1]:02d}/{tm[0]} {tm[3]:02d}:{tm[4]:02d}:{tm[5]:02d}"
    except:
        return "Data Indisponivel"

# Função para atualizar os atuadores com base nos estados atuais
def atualiza_atuadores():
    rele_luz.value(1 if estado_luz else 0)
    for i in range(NUM_LEDS):
        anel_ar[i] = (0, 0, 255) if estado_ar else (0, 0, 0)
    anel_ar.write()
    servo_persiana.duty(115 if estado_persiana else 40)
    buzzer_alarme.value(1 if estado_alarme else 0)

# Função para receber comandos via MQTT e atualizar os estados dos atuadores
def callback_mqtt(topic, msg):
    global estado_luz, estado_ar, estado_persiana, estado_alarme
    comando = msg.decode('utf-8')
    print("Comando MQTT:", comando)
    
    if comando == "LUZ_ON": estado_luz = True
    elif comando == "LUZ_OFF": estado_luz = False
    elif comando == "AR_ON": estado_ar = True
    elif comando == "AR_OFF": estado_ar = False
    elif comando == "PERSIANA_ON": estado_persiana = True
    elif comando == "PERSIANA_OFF": estado_persiana = False
    elif comando == "ALARME_ON": estado_alarme = True
    elif comando == "ALARME_OFF": estado_alarme = False
    
    atualiza_atuadores()

# Função para conectar ao broker MQTT e configurar o callback
def conecta_mqtt():
    try:
        client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, keepalive=60)
        client.set_callback(callback_mqtt)
        client.connect()
        client.subscribe(MQTT_TOPIC_SUB)
        print("MQTT Conectado")
        return client
    except Exception as e:
        print("Erro MQTT:", e)
        return None

# Função para enviar alertas por email e registrar na planilha do Google Sheets
def envia_alerta(mensagem_alerta, temp, luz, mov, portao):
    data_hora = obtem_data_hora()
    print(f"\n[!!!] DISPARANDO ALERTA: {mensagem_alerta}")
    
    # 1. Envia para Planilha
    try:
        payload = ujson.dumps({
            "dataHora": data_hora, 
            "alerta": mensagem_alerta, 
            "temperatura": temp, 
            "luminosidade": luz
        })
        res = urequests.post(URL_PLANILHA, data=payload, headers={'Content-Type': 'application/json'})
        print("Planilha OK")
        res.close()
    except Exception as e:
        print("Erro Planilha:", e)

    # 2. Envia Email
    try:
        LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1j4Y3QnFlaA6JrRT0lNVoYHaLCEzJGYTAEFEVZnds6nQ/edit?gid=0#gid=0"

        server = "smtp.gmail.com"
        port = 465
        
        # Cabeçalhos do Email
        corpo = f"Subject: ALERTA DE SEGURANCA - Quarto IoT\n"
        corpo += "Content-Type: text/plain; charset=utf-8\n\n"
        
        # Corpo do Email Organizado
        corpo += f"ATENÇÃO! Ocorrência de segurança registrada.\n\n"
        corpo += f"DETALHES DO EVENTO:\n"
        corpo += f"----------------------------------------\n"
        corpo += f"EVENTO: {mensagem_alerta}\n"
        corpo += f"DATA/HORA: {data_hora}\n\n"
        
        corpo += f"STATUS DOS SENSORES E ATUADORES (Tempo Real):\n"
        corpo += f"----------------------------------------\n"
        corpo += f"Temperatura: {temp:.1f}ºC\n"
        corpo += f"Luminosidade: {luz} ADC\n"
        corpo += f"Sensor de Presença: {'Detectou Movimento' if mov == 1 else 'Sem Movimento'}\n"
        corpo += f"Portão Principal: {'ABERTO' if portao else 'FECHADO'}\n\n"
        
        corpo += f"Luz do Quarto: {'LIGADA' if estado_luz else 'DESLIGADA'}\n"
        corpo += f"Ar Condicionado: {'LIGADO' if estado_ar else 'DESLIGADO'}\n"
        corpo += f"Persiana: {'ABERTA' if estado_persiana else 'FECHADA'}\n"
        corpo += f"Alarme (Buzzer): {'ATIVADO' if estado_alarme else 'DESATIVADO'}\n\n"
        
        corpo += f"HISTÓRICO COMPLETO:\n"
        corpo += f"Acesse a planilha de monitoramento aqui:\n"
        corpo += f"{LINK_PLANILHA}\n\n"
        corpo += f"Sistema de Automação Residencial - UMC\n"
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(socket.getaddrinfo(server, port)[0][-1])
        ssl_sock = ssl.wrap_socket(sock)
        
        ssl_sock.write(b"EHLO esp32\r\n")
        time.sleep(0.5)
        ssl_sock.write(b"AUTH LOGIN\r\n")
        time.sleep(0.5)
        ssl_sock.write(ubinascii.b2a_base64(EMAIL_REMETENTE.encode())[:-1] + b"\r\n")
        time.sleep(0.5)
        ssl_sock.write(ubinascii.b2a_base64(EMAIL_SENHA_APP.encode())[:-1] + b"\r\n")
        time.sleep(0.5)
        ssl_sock.write(b"MAIL FROM:<" + EMAIL_REMETENTE.encode() + b">\r\n")
        time.sleep(0.5)
        ssl_sock.write(b"RCPT TO:<" + EMAIL_DESTINO.encode() + b">\r\n")
        time.sleep(0.5)
        ssl_sock.write(b"DATA\r\n")
        time.sleep(0.5)
        ssl_sock.write(corpo.encode('utf-8') + b"\r\n.\r\n")
        time.sleep(1)
        ssl_sock.write(b"QUIT\r\n")
        ssl_sock.close()
        print("Email enviado com sucesso!\n")
    except Exception as e:
        print("Erro Email:", e)

# Inicialização das conexões
conecta_wifi()
mqtt_client = conecta_mqtt()
atualiza_atuadores()

# Mantemos o socket da porta 80 ativo devolvendo 204 (Requisito Web Local)
servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
servidor.bind(('0.0.0.0', 80)) 
servidor.listen(5)
servidor.settimeout(0.2) 

print("Sistema de Automacao rodando!")

# Loop principal: Lê sensores, atualiza display, envia MQTT e aguarda comandos
while True:
    tempo_atual = time.ticks_ms()
    
    if mqtt_client:
        try: mqtt_client.check_msg()
        except: pass
            
    try:
        conn, addr = servidor.accept()
        conn.settimeout(0.5)
        request = conn.recv(1024).decode('utf-8')
        
        # Pagina web recebe chamadas simulando painel auto-hospedado
        if '/?luz=on' in request: estado_luz = True
        elif '/?luz=off' in request: estado_luz = False
        elif '/?ar=on' in request: estado_ar = True
        elif '/?ar=off' in request: estado_ar = False
        elif '/?persiana=on' in request: estado_persiana = True
        elif '/?persiana=off' in request: estado_persiana = False
        elif '/?alarme=on' in request: estado_alarme = True
        elif '/?alarme=off' in request: estado_alarme = False
        
        atualiza_atuadores()
        
        conn.send(b'HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n')
        conn.close()
    except OSError: pass 
    except Exception as e:
        try: conn.close()
        except: pass

    if tempo_atual - ultimo_envio_mqtt > intervalo_mqtt:
        try:
            sensor_dht.measure()
            t = sensor_dht.temperature()
        except:
            t = 0.0
            
        luz_val = sensor_ldr.read()
        mov = sensor_pir.value()
        portao = True if sensor_portao.value() == 0 else False 
        
        # GATILHO DE ALERTAS (ANTI-SPAM)
        if mov == 1 and not alerta_mov_enviado:
            envia_alerta("PRESENCA DETECTADA NO CORREDOR", t, luz_val, mov, portao)
            alerta_mov_enviado = True
        elif mov == 0:
            alerta_mov_enviado = False # Rearma o sistema quando a pessoa sair
            
        if portao and not alerta_portao_enviado:
            envia_alerta("PORTAO PRINCIPAL VIOLADO (ABERTO)", t, luz_val, mov, portao)
            alerta_portao_enviado = True
        elif not portao:
            alerta_portao_enviado = False # Rearma quando fechar a porta

        # Display OLED
        oled.fill(0)
        oled.text("CASA INTELIGENTE", 0, 0)
        oled.text(f"Temp: {t}C", 0, 16)
        oled.text(f"Luz: {luz_val}", 0, 26)
        oled.text(f"Mov: {'SIM' if mov else 'NAO'}", 0, 36)
        oled.text(f"Portao: {'ABERTO' if portao else 'FECHADO'}", 0, 46)
        oled.show()
        
        # Envio de dados para a Dashboard (Node-RED)
        payload = ujson.dumps({
            "temperatura": t,
            "luminosidade": luz_val,
            "movimento": mov,
            "portao_aberto": portao
        })
        
        if mqtt_client:
            try:
                mqtt_client.publish(MQTT_TOPIC_PUB, payload)
            except Exception as e:
                mqtt_client = conecta_mqtt()
                
        ultimo_envio_mqtt = tempo_atual

    time.sleep(0.1)