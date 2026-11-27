# Brawl Guides — видео-гайды на бравлеров

Вертикальные ролики 1080×1920 до 30 секунд для TikTok и YouTube Shorts: вступление → гаджеты → пассивки →
снаряжение → режимы → «кого разобрать следующим». Стиль в духе Brawl Stars (шрифты Days One и Nunito),
бит-заглушка и звуковые эффекты, без озвучки.

## Как заказать ролик
Открой сессию Claude Code с этим репозиторием и напиши:

```
/guide Эдгар
```

Claude сам найдёт актуальную информацию (вики Brawl Stars + гайды), скачает иконки, напишет тексты,
отрендерит видео и пришлёт его. Подробности процесса — в `.claude/skills/guide/SKILL.md`.

## Вручную
```bash
bash tools/setup.sh
python3 tools/build.py mortis --stills   # контрольные кадры
python3 tools/build.py mortis            # out/mortis/mortis.mp4
```
Время показа каждого блока — словарь `HOLD` в `tools/build.py`.

## Устройство
- `guides/<slug>/guide.json` — всё содержимое ролика (тексты, оценки, иконки с вики)
- `template/video.html` — анимация (HTML/CSS/JS, кадр задаётся функцией `seek(t)`)
- `tools/build.py` — иконки → тайминги → рендер → звук → MP4
- `tools/render.js` — покадровый рендер через Playwright
- `tools/audio.py` — музыка и звуковые эффекты

Иконки и рендеры бравлеров — собственность Supercell, берутся с вики Brawl Stars (Fandom) для фан-контента.
