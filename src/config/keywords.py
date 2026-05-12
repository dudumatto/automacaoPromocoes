KEYWORDS_BY_CATEGORY = {
    "braco articulado de monitor": [
        "braço articulado monitor",
        "braco articulado monitor",
    ],
    "light bar": ["light bar monitor"],
    "monitor": ["monitor 144hz", "monitor 165hz"],
    "placa de video": ["rtx 3060", "rtx 4060", "rx 6600"],
    "processador": ["ryzen 5", "intel core i5"],
    "SSD": ["ssd nvme 1tb"],
    "memoria RAM": ["memoria ram ddr4 16gb"],
    "fonte": ["fonte 550w 80 plus"],
    "teclado": ["teclado mecanico", "teclado gamer"],
    "mouse": ["mouse gamer", "mouse sem fio"],
    "suporte de headset": ["suporte headset"],
    "decoracao de setup": ["decoracao setup", "luminaria setup"],
    "organizadores de mesa": ["organizadores setup"],
    "LEDs e acessorios de setup": ["led rgb setup", "fita led setup"],
}


INITIAL_KEYWORDS = [
    keyword
    for keywords in KEYWORDS_BY_CATEGORY.values()
    for keyword in keywords
]


CATEGORY_ALIASES = {
    "placa de video": ["rtx", "radeon", "rx ", "geforce", "placa de video"],
    "processador": ["ryzen", "intel core", "processador", "cpu"],
    "memoria RAM": ["memoria ram", "ddr4", "ddr5", "16gb", "32gb"],
    "SSD": ["ssd", "nvme", "m.2"],
    "fonte": ["fonte", "80 plus", "550w", "650w", "750w"],
    "monitor": ["monitor", "144hz", "165hz", "240hz"],
    "braco articulado de monitor": ["braco articulado", "suporte articulado"],
    "light bar": ["light bar", "barra de luz"],
    "teclado": ["teclado", "keyboard"],
    "mouse": ["mouse"],
    "suporte de headset": ["suporte headset", "headset stand"],
    "decoracao de setup": ["decoracao setup", "figura", "luminaria"],
    "organizadores de mesa": ["organizador", "organizadores setup", "mesa"],
    "LEDs e acessorios de setup": ["led", "rgb", "acessorios setup"],
}
