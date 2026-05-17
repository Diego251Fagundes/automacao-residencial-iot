# Automação Residencial com IoT

## Passo a passo para rodar o projeto

1. Clone este repositório e abra o VS Code.

	```powershell
	git clone https://github.com/Diego251Fagundes/automacao-residencial-iot.git
	```

2. No VS Code, instale a extensão **Wokwi Simulator**.
3. Pressione `F1` no VS Code, digite `Wokwi: Start Simulator` e selecione essa opção para abrir o simulador.
4. Abra um terminal na pasta do projeto e execute o comando abaixo para enviar o `main.py` local para o ESP32:

	```powershell
	python scripts/upload_and_run.py --local esp32/main.py --remote main.py
	```