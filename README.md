# ivbaby-media

Автоматизация соцсетей Ivbaby (@ivbaby_official): посты и Reels в Instagram и Telegram, ежедневные сторис, таблица продвижения.

- `bot/plan.json` — контент-план постов, `bot/stories.json` — план сторис
- `bot/ivbaby-promo.xlsx` — таблица продвижения (подписчики, охваты)
- `bot/top.json` — топ товаров WB за 30 дней (обновляется по понедельникам)
- `bot/keys.enc` — ключи API в зашифрованном виде (пароль — секрет `KEYS_PASSWORD`)
- `reels/`, `stories/` — готовые ролики и картинки сторис

Расписание (GitHub Actions, вкладка Actions):
- «Посты Instagram и Telegram» — пн, ср, пт, вс ≈ 18:40–19:00 МСК
- «Сторис Instagram» — ежедневно ≈ 11:45–12:00 МСК
- «Данные WB и Ozon» — по понедельникам ≈ 07:00 МСК
