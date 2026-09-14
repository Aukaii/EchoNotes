# transcreveTexto

App de desktop para **Windows 10+** que escuta todo o áudio que sai do seu
computador (navegador, videoconferência, players, qualquer app), transcreve
em tempo real e, ao final, gera automaticamente uma nota `.md` resumida e
compatível com o **Obsidian**.

100% local: a transcrição roda com [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
e o resumo com um modelo local via [Ollama](https://ollama.com) — nenhum áudio
ou texto é enviado para a internet, e não há custo de API.

## Como funciona

1. **Captura**: grava o áudio de saída do Windows em modo *loopback* (WASAPI),
   ou seja, tudo que sai pelo alto-falante/fone — inclui o navegador e
   qualquer outro programa.
2. **Segmentação**: um detector de silêncio (VAD por energia) agrupa o áudio
   em frases/trechos de fala.
3. **Transcrição**: cada trecho é transcrito localmente com faster-whisper
   (modelo Whisper otimizado para CPU/GPU) e aparece na tela em tempo real.
4. **Resumo**: ao clicar em "Parar e salvar", a transcrição completa é
   enviada para um modelo local rodando no Ollama, que gera um resumo
   estruturado em Markdown.
5. **Arquivo final**: um `.md` com front matter YAML (título, data, tags) +
   resumo + transcrição completa com timestamps é salvo na pasta que você
   escolher — aponte direto para uma pasta dentro do seu vault do Obsidian.

## Pré-requisitos (Windows 10 ou superior)

1. **Python 3.10+** — instale pelo [python.org](https://www.python.org/downloads/windows/)
   (marque "Add python.exe to PATH" no instalador). *Não* use a versão da
   Microsoft Store: ela costuma vir sem o Tkinter, usado na interface gráfica.
2. **Ollama** — instale em [ollama.com/download](https://ollama.com/download)
   e baixe um modelo, por exemplo:
   ```powershell
   ollama pull llama3.1
   ```
   Deixe o Ollama rodando em segundo plano (ele inicia um serviço local
   automaticamente após a instalação).

## Instalação do app

```powershell
git clone <este-repositorio>
cd transcreveTexto
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Na primeira execução, o `faster-whisper` baixa automaticamente o modelo
escolhido (ex.: `small`, ~250 MB) e o guarda em cache local.

## Uso

```powershell
python run.py
```

Na janela:

1. Defina o **título da aula**.
2. Escolha a **pasta de destino** (idealmente uma pasta dentro do seu vault
   do Obsidian).
3. Escolha o **modelo Whisper** (`small` é um bom equilíbrio entre
   velocidade e precisão em CPU; `medium`/`large-v3` são mais precisos mas
   exigem GPU NVIDIA para rodar em tempo real confortavelmente).
4. Clique em **Iniciar gravação** e reproduza o vídeo/aula normalmente no
   navegador (ou qualquer outro app).
5. Ao terminar, clique em **Parar e salvar** — o app gera o resumo e salva o
   arquivo `.md`.

## Limitações conhecidas / próximos passos

- O VAD por energia é simples (baseado em volume); em áudio com música de
  fundo alta ou volume muito baixo pode cortar frases de forma imprecisa.
  Ajustável em `transcrevetexto/config.py` (`energy_threshold`).
- Não há separação de falantes (diarização) — a transcrição não identifica
  "quem" está falando.
- CPUs mais fracas podem transcrever com atraso perceptível usando modelos
  maiores que `small`; se tiver GPU NVIDIA, mude `whisper_device` para
  `"cuda"` e `whisper_compute_type` para `"float16"` em
  `~/.transcrevetexto/config.json` (gerado após o primeiro uso) para ganho
  de velocidade.
- Para gerar um `.exe` standalone (sem precisar instalar Python), use o
  [PyInstaller](https://pyinstaller.org/): `pyinstaller --onefile --noconsole run.py`.

## Rodando os testes

Os testes cobrem a lógica pura (segmentação de fala e geração do Markdown),
sem depender de hardware de áudio ou dos modelos:

```powershell
pip install pytest
pytest
```
