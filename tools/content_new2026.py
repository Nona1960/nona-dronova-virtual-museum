# -*- coding: utf-8 -*-
"""New acquisitions: paintings by Nona Dronova written in her garden in 2026.
Titles, months and technique as given by the artist (02.11.2026). Missing data = None, not invented.
Images: public/img/new-2026/<file>.webp (prepared by tools/new2026_images.py)."""

PATH = "/new-2026/"
TITLE_RU = "Новые поступления. Живопись Ноны Дроновой, 2026 год"
TITLE_EN = "New Acquisitions. Paintings by Nona Dronova, 2026"
LEAD_RU = "Новые картины, написанные Ноной Дроновой в 2026 году в её саду."
LEAD_EN = "New paintings by Nona Dronova, written in her garden in 2026."

# (file, title_ru, title_en, technique: True = oil on canvas / None = not stated, month_ru, month_en)
SECTIONS = [
  dict(id="roads", ru="Дороги в саду", en="Roads in the Garden",
       sub_ru="Серия. Нона Дронова, 2026 год", sub_en="Series. Nona Dronova, 2026",
       works=[
         ("nona-dronova-roads-in-the-garden-1-2026", "Дороги в саду. I", "Roads in the Garden. I", None, None, None),
         ("nona-dronova-roads-in-the-garden-2-2026", "Дороги в саду. II", "Roads in the Garden. II", None, None, None),
         ("nona-dronova-roads-in-the-garden-3-2026", "Дороги в саду. III", "Roads in the Garden. III", None, None, None),
         ("nona-dronova-roads-in-the-garden-4-2026", "Дороги в саду. IV", "Roads in the Garden. IV", None, None, None),
       ]),
  dict(id="seasons", ru="Сезоны в саду", en="Seasons in the Garden",
       sub_ru="Нона Дронова, 2026 год", sub_en="Nona Dronova, 2026",
       works=[
         ("nona-dronova-rodgersia-2026", "Роджерсия", "Rodgersia", True, "май", "May"),
         ("nona-dronova-yellow-daylilies-2026", "Жёлтые лилейники", "Yellow Daylilies", True, "июнь", "June"),
         ("nona-dronova-red-poppies-2026", "Красные маки", "Red Poppies", True, "июнь", "June"),
         ("nona-dronova-siberian-irises-in-the-mist-2026", "Сибирские ирисы в тумане", "Siberian Irises in the Mist", True, "июнь", "June"),
         ("nona-dronova-bellflowers-2026", "Колокольчики", "Bellflowers", True, None, None),
         ("nona-dronova-meadowsweet-in-a-forest-glade-2026", "Таволга на лесной поляне", "Meadowsweet in a Forest Glade", True, None, None),
         ("nona-dronova-astilbe-in-bloom-2026", "Астильба цветёт", "Astilbe in Bloom", True, "август", "August"),
         ("nona-dronova-gladioli-2026", "Гладиолусы", "Gladioli", True, "август", "August"),
       ]),
]
