# Макеты редизайна · IndologyScholars

_Created: 11-07-2026 · Last updated: 11-07-2026_

Неразрушающие дизайн-макеты по программе
[H563](https://github.com/gasyoun/Uprava/blob/main/handoffs/H563-Fable_Uprava_dashboard-redesign-4-directions_11.07.26.md)
(поверхность IndologyScholars —
[H660](https://github.com/gasyoun/Uprava/blob/main/handoffs/archive/H660-Fable_IndologyScholars_landing-sustainable-mockup_11.07.26.md)).
Рабочие страницы не изменяются, пока человек не выберет победителя.

| Файл | Направление | Что внутри |
|---|---|---|
| [sustainable.html](https://github.com/gasyoun/IndologyScholars/blob/main/mockups/sustainable.html) | Sustainable web design | Главный дашборд (`index.html`) с полной живой логикой и данными: разметка тела и [assets/js/main.js](https://github.com/gasyoun/IndologyScholars/blob/main/assets/js/main.js) не тронуты, поверх [assets/index.css](https://github.com/gasyoun/IndologyScholars/blob/main/assets/index.css) наложен [sustainable.css](https://github.com/gasyoun/IndologyScholars/blob/main/mockups/sustainable.css) — токеновая «пересадка кожи»: светлая схема «мох и глина» по умолчанию + тёмная из настроек системы (`prefers-color-scheme`; рабочая страница — только тёмная), системные шрифты вместо Google Fonts (−3 внешних запроса), убран vanilla-tilt (декор, в main.js есть guard). Библиотеки данных (Chart.js, Leaflet, vis-network, Fuse) сохранены — они несущие. |

Изменения только в `<head>` (проверено скриптом: тело байт-в-байт совпадает с
рабочей страницей) + `<base href="../">`, чтобы относительные `fetch`
(`site_data_*.json`) из `main.js` разрешались от корня; якорей `href="#…"` на
странице нет, так что `<base>` безопасен.

Направление назначено картой H563: «много публичных страниц — низкоуглеродное
окупается». Просмотр: с GitHub Pages
([mockups/sustainable.html](https://gasyoun.github.io/IndologyScholars/mockups/sustainable.html))
или локальным сервером из корня репозитория; двойным щелчком данные не
подгрузятся (fetch требует http).

_Dr. Mārcis Gasūns_
