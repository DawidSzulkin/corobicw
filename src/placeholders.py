import hashlib
from urllib.parse import quote

# Palety barw (start, stop, akcent)
COLOR_PALETTES = [
    ("#1e3c72", "#2a5298", "#4facfe"),  # Głęboki błękit / Navy
    ("#3a1c71", "#d76d77", "#ffaf7b"),  # Sunset / Fiolet-Pomarańcz
    ("#11998e", "#38ef7d", "#00f2fe"),  # Szmaragd / Mięta
    ("#8e2de2", "#4a00e0", "#f72585"),  # Neon Magenta / Cyber
    ("#232526", "#414345", "#00c6ff"),  # Ciemny grafit / Akcent Cyan
    ("#ee0979", "#ff6a00", "#ffd200"),  # Energetyczny ogień
    ("#4b6cb7", "#182848", "#00d2ff"),  # Nocne niebo
    ("#2c3e50", "#3498db", "#ecf0f1"),  # Klasyczny modern
]

CATEGORY_ICONS = {
    "Sport": '<path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8zm4-9h-3V8a1 1 0 0 0-2 0v3H8a1 1 0 0 0 0 2h3v3a1 1 0 0 0 2 0v-3h3a1 1 0 0 0 0-2z" fill="white" opacity="0.9"/>',
    "Koncert": '<path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" fill="white" opacity="0.9"/>',
    "Kino": '<path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" fill="white" opacity="0.9"/>',
    "Dla Dzieci": '<path d="M12 2l2.4 7.4h7.6l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z" fill="white" opacity="0.9"/>',
    "Kultura": '<path d="M12 3c-4.97 0-9 4.03-9 9 0 2.12.74 4.07 1.97 5.61L4.35 19.4c-.39.39-.39 1.02 0 1.41.39.39 1.02.39 1.41 0l1.9-1.9C9.28 19.58 10.59 20 12 20c4.97 0 9-4.03 9-9s-4.03-9-9-9zm0 15c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6z" fill="white" opacity="0.9"/>'
}


def generate_event_placeholder(title: str, category: str = "Kultura") -> str:
    """Generuje deterministyczny, dynamiczny plakat SVG w formacie Data URI."""
    # Wyliczenie hasha z tytułu do powtarzalnego doboru kolorów i kształtów
    hash_val = int(hashlib.md5(title.encode("utf-8")).hexdigest(), 16)
    
    palette = COLOR_PALETTES[hash_val % len(COLOR_PALETTES)]
    c_start, c_stop, c_accent = palette

    # Zmienne geometryczne
    r1 = 120 + (hash_val % 100)
    r2 = 180 + ((hash_val >> 4) % 120)
    cx1 = 200 + ((hash_val >> 8) % 300)
    cy1 = 150 + ((hash_val >> 12) % 200)
    cx2 = 900 - ((hash_val >> 16) % 250)
    cy2 = 450 - ((hash_val >> 20) % 180)

    icon_svg = CATEGORY_ICONS.get(category, CATEGORY_ICONS["Kultura"])

    svg_markup = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c_start}"/>
      <stop offset="100%" stop-color="{c_stop}"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{c_accent}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="{c_accent}" stop-opacity="0"/>
    </radialGradient>
    <filter id="blur">
      <feGaussianBlur stdDeviation="60"/>
    </filter>
  </defs>

  <!-- Tło bazowe -->
  <rect width="100%" height="100%" fill="url(#bg)"/>

  <!-- Abstrakcyjne plamy świetlne / Mesh -->
  <circle cx="{cx1}" cy="{cy1}" r="{r1}" fill="url(#glow)" filter="url(#blur)"/>
  <circle cx="{cx2}" cy="{cy2}" r="{r2}" fill="url(#glow)" filter="url(#blur)"/>

  <!-- Subtelna siatka dekoracyjna -->
  <g opacity="0.06" stroke="#ffffff" stroke-width="1.5">
    <line x1="0" y1="157.5" x2="1200" y2="157.5"/>
    <line x1="0" y1="315" x2="1200" y2="315"/>
    <line x1="0" y1="472.5" x2="1200" y2="472.5"/>
    <line x1="300" y1="0" x2="300" y2="630"/>
    <line x1="600" y1="0" x2="600" y2="630"/>
    <line x1="900" y1="0" x2="900" y2="630"/>
  </g>

  <!-- Centralna kapsuła z ikoną -->
  <g transform="translate(600, 315)">
    <circle r="76" fill="#ffffff" fill-opacity="0.12" stroke="#ffffff" stroke-width="2" stroke-opacity="0.25"/>
    <g transform="translate(-40, -40) scale(3.33)">
      {icon_svg}
    </g>
  </g>
</svg>"""

    # Format Data URI bezpieczny dla atrybutu src i CSS
    return f"data:image/svg+xml;utf8,{quote(svg_markup)}"