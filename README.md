# Radar Setup

MVP local para garimpar promocoes de hardware e itens de setup, salvar historico de precos em SQLite e enviar alertas por Discord Webhook quando o preco cair abaixo do normal. Os alertas podem ser roteados para canais separados de hardware, setup e promocoes absurdas.

## O que monitora

Categorias iniciais:

- placa de video
- processador
- memoria RAM
- SSD
- fonte
- monitor
- braco articulado de monitor
- light bar
- teclado
- mouse
- suporte de headset
- decoracao de setup
- organizadores de mesa
- LEDs e acessorios de setup

Lojas iniciais:

- Kabum
- Pichau
- Terabyte
- Amazon Brasil
- Mercado Livre
- Magazine Luiza
- AliExpress Brasil

Quando a pagina listar frete ou imposto/taxa de importacao junto do card, o Radar Setup soma esses valores ao preco usado no score. Se a loja nao expuser esses campos no HTML, o preco exibido pela loja e usado como fallback.

## Instalar

Requisitos:

- Python 3.11+
- pip

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Instale as dependencias:

```bash
pip install -r requirements.txt
```

Se quiser usar fallback com navegador para paginas muito dinamicas:

```bash
python -m playwright install chromium
```

## Configurar `.env`

Copie `.env.example` para `.env` e preencha os valores:

```env
DISCORD_WEBHOOK_HARDWARE=
DISCORD_WEBHOOK_SETUP=
DISCORD_WEBHOOK_ABSURDAS=
DISCORD_WEBHOOK_URL=
DATABASE_URL=sqlite:///data/radar_setup.sqlite3
MIN_DISCOUNT_PERCENT=25
MIN_SCORE=70
REQUEST_TIMEOUT_SECONDS=20
MAX_RESULTS_PER_STORE=5
USE_PLAYWRIGHT_FALLBACK=true
MAX_RETRIES=2
VERBOSE_LOGS=true
```

`DISCORD_WEBHOOK_URL` e opcional e continua funcionando como fallback geral para instalacoes antigas. Se algum webhook especifico estiver vazio, o sistema apenas registra um aviso e segue sem quebrar.

Nenhum token, webhook ou segredo deve ser colocado no codigo.

## Criar 3 Webhooks do Discord

1. Abra o servidor no Discord.
2. Crie ou escolha estes canais: `promos-hardware`, `promos-setup` e `promos-absurdas`.
3. Entre em `Configuracoes do canal` para `promos-hardware`.
4. Va em `Integracoes` > `Webhooks`.
5. Clique em `Novo webhook`.
6. Nomeie o webhook, copie a URL e cole em `DISCORD_WEBHOOK_HARDWARE` no `.env`.
7. Repita o processo em `promos-setup` e cole a URL em `DISCORD_WEBHOOK_SETUP`.
8. Repita o processo em `promos-absurdas` e cole a URL em `DISCORD_WEBHOOK_ABSURDAS`.

Exemplo de `.env`:

```env
DISCORD_WEBHOOK_HARDWARE=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_SETUP=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_ABSURDAS=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_URL=
DATABASE_URL=sqlite:///data/radar_setup.sqlite3
MIN_DISCOUNT_PERCENT=25
MIN_SCORE=70
REQUEST_TIMEOUT_SECONDS=20
MAX_RESULTS_PER_STORE=5
USE_PLAYWRIGHT_FALLBACK=true
MAX_RETRIES=2
VERBOSE_LOGS=true
```

## Roteamento dos alertas

- `promos-absurdas`: recebe ofertas com score maior ou igual a 90 ou desconto maior ou igual a 40%.
- `promos-hardware`: recebe categorias como placa de video, GPU, processador, CPU, memoria RAM, RAM, SSD, NVMe, fonte e placa mae.
- `promos-setup`: recebe categorias como monitor, braco articulado, light bar, teclado, mouse, mousepad, headset, suporte headset, decoracao, LED e organizador.
- Uma mesma promocao pode ir para mais de um canal quando cumprir mais de uma regra, mas nao e enviada duas vezes para o mesmo canal durante a mesma execucao.
- Se uma variavel especifica estiver vazia e `DISCORD_WEBHOOK_URL` estiver configurado, o fallback geral e usado.

## Criar Webhook unico legado

Para manter uma configuracao antiga com um so canal:

1. Abra o servidor no Discord.
2. Entre em `Configuracoes do canal`.
3. Va em `Integracoes` > `Webhooks`.
4. Clique em `Novo webhook`.
5. Escolha o canal que recebera os alertas.
6. Copie a URL do webhook.
7. Cole em `DISCORD_WEBHOOK_URL` no `.env`.

## Rodar

Executar varredura:

```bash
python main.py scan
```

Diagnosticar uma loja e keyword especificas:

```bash
python main.py debug-store --store amazon --keyword "monitor 144hz"
```

O comando mostra URL pesquisada, status HTTP, quantidade de cards encontrados,
seletores usados e salva um HTML parcial em `data/debug/` para inspecao.

Enviar alerta de teste:

```bash
python main.py test-alert
```

Se nenhum webhook aplicavel estiver configurado, o modo `test-alert` mostra um preview no terminal.

Rodar testes locais:

```bash
python -m unittest discover -s tests
```

Validar sintaxe dos arquivos Python:

```bash
python -m compileall main.py src tests
```

## Memoria do projeto

Use estes comandos quando estiver trabalhando nesta pasta para registrar,
aprender ou carregar o contexto do projeto `garimpoAUTOMACAO` no second-brain.
Eles ajudam a manter um historico curto das decisoes, ajustes e estado atual
do projeto entre sessoes.

Salvar uma memoria nova:

```powershell
powershell -ExecutionPolicy Bypass -File E:\second-brain\scripts\save-memory.ps1 -Project garimpoAUTOMACAO -Text "sua memoria aqui"
```

Aprender o projeto atual:

```powershell
powershell -ExecutionPolicy Bypass -File E:\second-brain\scripts\learn-project.ps1
```

Carregar memorias do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File E:\second-brain\scripts\load-memory.ps1 -Project garimpoAUTOMACAO
```

## Banco de dados

O SQLite e criado automaticamente em `data/radar_setup.sqlite3`, com as tabelas:

- `stores`
- `products`
- `price_history`
- `deals`

Cada oferta registrada considera:

- nome do produto
- categoria
- loja
- preco atual
- preco medio estimado
- porcentagem de queda
- link
- data/hora
- score de 0 a 100
- motivo do alerta

## Score de promocao

Regra base:

- queda abaixo de 20%: ignorar
- queda entre 20% e 30%: promocao comum
- queda entre 30% e 40%: promocao forte
- queda acima de 40%: promocao absurda

O score tambem:

- prioriza lojas confiaveis
- penaliza marketplaces ou sellers suspeitos
- usa historico local de precos quando existir
- usa preco original listado pela loja quando disponivel

Alertas so sao enviados quando passam por `MIN_DISCOUNT_PERCENT` e `MIN_SCORE`.

## Adicionar novas palavras-chave

Edite `src/config/keywords.py`.

Exemplo:

```python
KEYWORDS_BY_CATEGORY = {
    "teclado": ["teclado mecanico abnt2", "teclado low profile"],
}
```

O arquivo ja inclui as palavras-chave pedidas no MVP e termos extras para cobrir processadores, teclado, mouse, decoracao e LEDs.

## Adicionar novas lojas

1. Adicione a loja em `src/config/stores.py`.
2. Crie uma classe em `src/scrapers/stores.py` herdando de `BaseStoreScraper`.
3. Configure seletores CSS com `ScraperSelectors`.
4. Registre a classe em `src/scrapers/registry.py`.

Exemplo:

```python
class MinhaLojaScraper(BaseStoreScraper):
    selectors = ScraperSelectors(
        card=".produto",
        title=".nome",
        price=".preco",
        link="a[href]",
        old_price=".preco-antigo",
    )
```

Se o scraping direto for instavel, o scraper ainda tenta JSON-LD e fallback generico por links com preco. Para lojas muito dinamicas ou com bloqueio frequente, habilite `USE_PLAYWRIGHT_FALLBACK=true`. O fallback com Playwright e aplicado apenas nas lojas configuradas para isso, hoje Pichau, Amazon Brasil e Magazine Luiza.

## Preparado para evoluir

A estrutura foi separada para permitir:

- dashboard React
- bot Telegram
- ranking de melhores promocoes
- afiliados
- graficos de historico de precos

Pontos de extensao:

- `src/notifiers/telegram.py`
- `src/services/scoring.py`
- `src/database/repository.py`
- `src/scrapers/`

## Observacoes

Scraping de e-commerce muda com frequencia e pode ser bloqueado por anti-bot, renderizacao client-side ou variacoes de HTML. Por isso cada loja tem adaptador separado e o scanner segue funcionando mesmo se uma loja falhar.

Amazon Brasil costuma bloquear scraping automatizado com 503/anti-bot. Se o bloqueio persistir mesmo com Playwright, monitore Amazon por API oficial/afiliados, RSS ou fontes terceiras confiaveis, ou mantenha fallback manual. O bloqueio da Amazon nao deve quebrar o scan das outras lojas.
