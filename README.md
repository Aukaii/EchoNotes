# EchoNotes

App de desktop para **Windows 10+** que escuta todo o áudio que sai do seu
computador (navegador, videoconferência, players, qualquer app), transcreve
em tempo real e, ao final, gera automaticamente uma nota `.md` resumida e
compatível com o **Obsidian**.

100% local e gratuito: a transcrição roda com
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) e o resumo com um
modelo de linguagem pequeno rodando **dentro do próprio app**
(`llama.cpp`/`llama-cpp-python`) — nenhum áudio ou texto é enviado para a
internet, não há custo de API e **não é preciso instalar nada separado**
(nada de instalar Python, Ollama, etc. na versão empacotada).

## Como funciona

1. **Captura**: grava o áudio de saída do Windows em modo *loopback* (WASAPI),
   ou seja, tudo que sai pelo alto-falante/fone — inclui o navegador e
   qualquer outro programa.
2. **Segmentação**: um detector de silêncio (VAD por energia) agrupa o áudio
   em frases/trechos de fala.
3. **Transcrição**: cada trecho é transcrito localmente com faster-whisper
   e aparece na tela em tempo real.
4. **Resumo**: ao clicar em "Parar e salvar", a transcrição completa é
   resumida por um LLM local (Qwen 2.5, quantizado, roda em CPU).
5. **Arquivo final**: um `.md` com front matter YAML (título, data, tags) +
   resumo + transcrição completa com timestamps é salvo na pasta que você
   escolher — aponte direto para uma pasta dentro do seu vault do Obsidian.

Na **primeira execução**, o próprio app baixa o modelo de resumo (~1-2 GB,
uma vez só, com barra de progresso) e prepara o modelo de transcrição.
Depois disso funciona 100% offline.

## Usando a versão pronta (recomendado)

1. Baixe `EchoNotes.exe` na aba
   [Releases](https://github.com/Aukaii/transcreveTexto/releases) deste
   repositório e execute.
2. Na primeira vez, aguarde o download automático dos modelos (tela de
   progresso).
3. Pronto — a interface principal só tem: título da aula, pasta de destino e
   o botão **Iniciar/Parar gravação**. Configurações técnicas (tamanho dos
   modelos, sensibilidade do detector de fala) ficam em "⚙ Configurações".

O app verifica sozinho, periodicamente, se há uma versão nova publicada no
GitHub e mostra um aviso com um botão "Atualizar agora" — que baixa e troca
o `.exe` automaticamente.

> **Aviso sobre o instalador:** como o `.exe` não é assinado digitalmente
> (certificados de assinatura de código são pagos), o Windows SmartScreen ou
> o antivírus podem exibir um aviso na primeira execução de cada versão nova.
> Isso é uma limitação de distribuir um app gratuito sem certificado — não
> tem como evitar sem comprar um certificado de assinatura.

## Rodando a partir do código-fonte (para desenvolvimento)

```powershell
git clone https://github.com/Aukaii/transcreveTexto
cd transcreveTexto
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Use **Python 3.10+ do python.org** (marque "Add python.exe to PATH" no
instalador). Evite a versão da Microsoft Store: ela costuma vir sem o
Tkinter, usado na interface gráfica. Rodando a partir do código-fonte, a
atualização automática só avisa que há versão nova — a troca de arquivo só
funciona no `.exe` empacotado (use `git pull` para atualizar).

## Gerando o `.exe` você mesmo

Um push de tag `vX.Y.Z` neste repositório dispara o workflow
`.github/workflows/build-windows.yml`, que compila o `.exe` num runner
Windows do GitHub Actions e publica como Release automaticamente (é assim
que o auto-updater encontra novas versões). Para gerar localmente:

```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole --name EchoNotes run.py
```

O executável fica em `dist/EchoNotes.exe`.

## Limitações conhecidas

- O VAD por energia é simples (baseado em volume); em áudio com música de
  fundo alta ou volume muito baixo pode cortar frases de forma imprecisa.
  Ajustável em "⚙ Configurações" (sensibilidade de detecção de fala).
- Não há separação de falantes (diarização) — a transcrição não identifica
  "quem" está falando.
- O LLM local de resumo (Qwen 2.5, 1.5B ou 3B) é bem mais limitado que
  modelos como GPT/Claude; a qualidade do resumo reflete isso. É possível
  trocar o tamanho do modelo em "⚙ Configurações".
- CPUs mais fracas podem transcrever com atraso perceptível usando modelos
  Whisper maiores que `small`. Com GPU NVIDIA, é possível editar
  `~/.echonotes/config.json` (gerado após o primeiro uso) para usar
  `"whisper_device": "cuda"` e `"whisper_compute_type": "float16"`.
- A atualização automática exige que o Release no GitHub contenha um arquivo
  chamado exatamente `EchoNotes.exe` (é o nome usado pelo workflow).

## Rodando os testes

Os testes cobrem a lógica pura (segmentação de fala e geração do Markdown),
sem depender de hardware de áudio ou dos modelos:

```powershell
pip install pytest
pytest
```
