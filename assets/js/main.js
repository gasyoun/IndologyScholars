import { state } from './state.js';
import { TRANSLATIONS } from './i18n.js';
import { renderGrowthChart, renderCohortDistribution, renderGeoChart, renderSankeyChart, renderAgeChart, renderGenderChart, renderInstChart, renderWordCloud } from './charts.js';


        // Kick off critical path data fetch immediately (preload tag in <head> ensures it starts even earlier)
        const _dataPromise = fetch('site_data_summary.json?v=1.8.5').then(r => r.json());

        let timelinePromise = null;
        let networkPromise = null;
        let scholarsPromise = null;
        /* moved state.fullScholarsLoaded to state */
        /* moved state.timelineLoaded to state */
        /* moved state.networkLoaded to state */

        // Language state
        
        
        // Fuzzy search setup with Fuse.js (hoisted to avoid memory leak)
        let scholarFuse = null;
        
        const initFuse = () => {
            if (!scholarFuse && window.Fuse && window.CONFERENCE_DATA && window.CONFERENCE_DATA.scholars) {
                scholarFuse = new Fuse(window.CONFERENCE_DATA.scholars, {
                    keys: ['full_name_ru', 'full_name_en'],
                    threshold: 0.3,
                    ignoreLocation: true
                });
            }
        };

        // Hide dropdowns on outside click - attached once globally
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-wrapper')) {
                const scAuto = document.getElementById('scholars-autocomplete');
                const tkAuto = document.getElementById('talks-autocomplete');
                if(scAuto) scAuto.hidden = true;
                if(tkAuto) tkAuto.hidden = true;
            }
        });

document.addEventListener('DOMContentLoaded', () => {
            // Restore language if it's 'en' (since HTML defaults to RU)
            if (state.currentLang === 'en') {
                state.currentLang = 'ru'; // set back so toggle swaps it correctly
                toggleLanguage();
            }
            toggleViewMode(state.viewMode);
        });

        /* moved state.currentLang to state */
        window.myCharts = {}; // Store chart instances

        

        // Pagination state
        /* moved state.currentPage to state */
        /* moved state.pageSize to state */
        /* moved state.filteredScholars to state */
        /* moved state.viewMode to state */

        
        // Initialize Vanilla Tilt
        function initTilt() {
            if (window.VanillaTilt) {
                VanillaTilt.init(document.querySelectorAll('.stat-card, .insight-card, .chart-card'), {
                    max: 3,
                    speed: 400,
                    glare: true,
                    "max-glare": 0.05
                });
            }
        }
        
        // Setup Intersection Observer for reveal
        const revealObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.1 });
        
        function observeReveals() {
            document.querySelectorAll('.stat-card, .insight-card, .chart-card, .timeline-talk-card').forEach(el => {
                el.classList.add('reveal');
                revealObserver.observe(el);
            });
        }

        function updateSummaryStats() {
            const summary = CONFERENCE_DATA.summary || {};
            const scholarsCount = summary.total_scholars || (CONFERENCE_DATA.scholars ? CONFERENCE_DATA.scholars.length : 0);
            const talksCount = summary.total_presentations || 0;
            const yearsCount = summary.years_covered || (CONFERENCE_DATA.stats ? CONFERENCE_DATA.stats.length : 0);
            const overlapCount = summary.overlap_scholars || 0;
            document.getElementById('stat-scholars-count').textContent = scholarsCount;
            document.getElementById('stat-talks-count').textContent = talksCount;
            document.getElementById('stat-years-count').textContent = yearsCount;
            document.getElementById('stat-overlap-count').textContent = overlapCount;
            if (summary.start_year && summary.end_year) {
                document.getElementById('stat-years-desc').textContent = state.currentLang === 'ru'
                    ? `Период с ${summary.start_year} по ${summary.end_year} годы`
                    : `Period from ${summary.start_year} to ${summary.end_year}`;
            }
        }

        // Toggle language in real-time
        function toggleLanguage() {
            state.currentLang = state.currentLang === 'ru' ? 'en' : 'ru';
            localStorage.setItem('indology_lang', state.currentLang);
            
            // Update button label
            document.getElementById('lang-switch-btn').textContent = state.currentLang === 'ru' ? 'EN' : 'RU';
            const exportHeader = document.getElementById('export-md-btn-header');
            if (exportHeader) exportHeader.textContent = state.currentLang === 'ru' ? 'Экспорт' : 'Export';
            const exportTable = document.getElementById('export-md-btn');
            if (exportTable) exportTable.textContent = state.currentLang === 'ru' ? 'Экспорт' : 'Export';
            
            // Translate static elements
            const t = TRANSLATIONS[state.currentLang];
            document.getElementById('main-heading').textContent = t.mainHeading;
            document.getElementById('sub-heading').textContent = t.subHeading;
            document.querySelectorAll('.publication-links [data-ru][data-en]').forEach(element => {
                element.textContent = element.dataset[state.currentLang];
            });
            
            // Metrics
            document.getElementById('stat-scholars-label').textContent = t.statScholars;
            document.getElementById('stat-scholars-desc').textContent = t.statScholarsDesc;
            document.getElementById('stat-talks-label').textContent = t.statTalks;
            document.getElementById('stat-talks-desc').textContent = t.statTalksDesc;
            document.getElementById('stat-years-label').textContent = t.statYears;
            document.getElementById('stat-years-desc').textContent = t.statYearsDesc;
            document.getElementById('stat-overlap-label').textContent = t.statOverlap;
            document.getElementById('stat-overlap-desc').textContent = t.statOverlapDesc;
            document.getElementById('stat-youtube-label').textContent = t.statYoutube;
            document.getElementById('stat-youtube-desc').textContent = t.statYoutubeDesc;
            document.getElementById('findings-eyebrow').textContent = t.findingsEyebrow;
            document.getElementById('findings-heading').textContent = t.findingsHeading;
            document.getElementById('findings-lead').textContent = t.findingsLead;
            document.getElementById('findings-corpus-note').textContent = t.findingsCorpusNote;
            document.getElementById('findings-cta').textContent = t.findingsCta;
            document.getElementById('insight-overlap-title').textContent = t.insightOverlapTitle;
            document.getElementById('insight-overlap-text').textContent = t.insightOverlapText;
            document.getElementById('insight-theme-title').textContent = t.insightThemeTitle;
            document.getElementById('insight-theme-text').textContent = t.insightThemeText;
            document.getElementById('insight-micro-title').textContent = t.insightMicroTitle;
            document.getElementById('insight-micro-text').textContent = t.insightMicroText;
            document.getElementById('insight-video-title').textContent = t.insightVideoTitle;
            document.getElementById('insight-video-text').textContent = t.insightVideoText;
            document.getElementById('generations-page-link').textContent = t.generationsPageLink;

            // Navigation
            document.getElementById('tab-scholars').textContent = t.tabScholars;
            document.getElementById('tab-timeline').textContent = t.tabTimeline;
            document.getElementById('tab-charts').textContent = t.tabCharts;

            // Search placeholder
            document.getElementById('label-scholars-search').textContent = t.labelScholarSearch;
            document.getElementById('label-talks-search').textContent = t.labelTalkSearch;
            document.getElementById('label-series').textContent = t.labelSeries;
            document.getElementById('label-sort').textContent = t.labelSort;
            document.getElementById('scholars-search').placeholder = t.searchPlaceholder;
            const talksSearch = document.getElementById('talks-search');
            if (talksSearch) talksSearch.placeholder = t.searchTalksPlaceholder;

            // Filters
            document.getElementById('opt-all').textContent = t.filterAll;
            document.getElementById('opt-zograf').textContent = t.filterZograf;
            document.getElementById('opt-roerich').textContent = t.filterRoerich;
            document.getElementById('opt-both').textContent = t.filterBoth;
            document.getElementById('opt-never-zograf').textContent = t.filterNeverZograf;
            document.getElementById('opt-never-roerich').textContent = t.filterNeverRoerich;

            document.getElementById('opt-talks-desc').textContent = t.sortTalksDesc;
            document.getElementById('opt-talks-asc').textContent = t.sortTalksAsc;
            document.getElementById('opt-name-asc').textContent = t.sortNameAsc;
            document.getElementById('opt-name-desc').textContent = t.sortNameDesc;

            // Table headers
            document.getElementById('th-name').textContent = t.colName;
            document.getElementById('th-total').textContent = t.colTotal;
            document.getElementById('th-zograf').textContent = t.colZograf;
            document.getElementById('th-roerich').textContent = t.colRoerich;
            document.getElementById('th-years').textContent = t.colYears;

            // Schema
            document.getElementById('db-title').textContent = t.dbTitle;
            document.getElementById('db-desc').textContent = t.dbDesc;

            // Footer
            document.getElementById('footer-copyright').textContent = t.footerCopyright;

            // Re-render dynamic content
            updateSummaryStats();
            renderScholarsTable();
            renderMatchingTalks(document.getElementById('talks-search').value.trim());
            initTimeline();
            if (document.getElementById('sec-charts').classList.contains('active')) {
                document.getElementById('chart-geo-title').textContent = t.chartGeoTitle;
                document.getElementById('chart-age-title').textContent = t.chartAgeTitle;
                document.getElementById('chart-gender-title').textContent = t.chartGenderTitle;
                document.getElementById('chart-network-title').textContent = t.chartNetworkTitle;
                document.getElementById('net-reset-btn').textContent = t.netResetBtn;
                document.getElementById('net-pause-btn').textContent = isNetPhysicsRunning ? t.netPauseBtn : t.netResumeBtn;
                document.getElementById('chart-inst-title').textContent = t.chartInstTitle;
                document.getElementById('chart-words-title').textContent = t.chartWordsTitle;
                const teaserTextEl = document.getElementById('network-teaser-text');
                if (teaserTextEl) teaserTextEl.textContent = t.networkTeaserText;
                const teaserLinkEl = document.getElementById('network-teaser-link');
                if (teaserLinkEl) teaserLinkEl.textContent = t.networkTeaserLink;
                document.querySelectorAll('#inst-table th')[0].textContent = t.thAffil;
                document.querySelectorAll('#inst-table th')[1].textContent = t.thScholars;
                document.querySelectorAll('#inst-table th')[2].textContent = t.thTalks;
                renderGrowthChart();
                renderCohortDistribution();
                renderGeoChart();
                renderSankeyChart();
                renderAgeChart();
                renderGenderChart();
                renderInstChart();
                renderWordCloud();
            }
        }

        // Tab switcher
        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => {
                const selected = btn.id === 'tab-' + tabId;
                btn.classList.toggle('active', selected);
                btn.setAttribute('aria-selected', String(selected));
                btn.tabIndex = selected ? 0 : -1;
            });

            document.querySelectorAll('.dashboard-section').forEach(sec => {
                const selected = sec.id === 'sec-' + tabId;
                sec.classList.toggle('active', selected);
                sec.hidden = !selected;
            });
            const activeSec = document.getElementById('sec-' + tabId);
            if (!activeSec) return;
            
            // Re-render SVG charts when switching to statistical insights tab
            if (tabId === 'charts') {
                const t = TRANSLATIONS[state.currentLang];
                document.getElementById('chart-geo-title').textContent = t.chartGeoTitle;
                document.getElementById('chart-age-title').textContent = t.chartAgeTitle;
                document.getElementById('chart-gender-title').textContent = t.chartGenderTitle;
                document.getElementById('chart-network-title').textContent = t.chartNetworkTitle;
                document.getElementById('net-reset-btn').textContent = t.netResetBtn;
                document.getElementById('net-pause-btn').textContent = isNetPhysicsRunning ? t.netPauseBtn : t.netResumeBtn;
                document.getElementById('chart-inst-title').textContent = t.chartInstTitle;
                document.getElementById('chart-words-title').textContent = t.chartWordsTitle;
                const teaserTextEl = document.getElementById('network-teaser-text');
                if (teaserTextEl) teaserTextEl.textContent = t.networkTeaserText;
                const teaserLinkEl = document.getElementById('network-teaser-link');
                if (teaserLinkEl) teaserLinkEl.textContent = t.networkTeaserLink;
                document.querySelectorAll('#inst-table th')[0].textContent = t.thAffil;
                document.querySelectorAll('#inst-table th')[1].textContent = t.thScholars;
                document.querySelectorAll('#inst-table th')[2].textContent = t.thTalks;
                renderGrowthChart();
                renderCohortDistribution();
                renderGeoChart();
                renderSankeyChart();
                renderAgeChart();
                renderGenderChart();
                renderInstChart();
                renderWordCloud();
                startNetworkGraph();
            } else {
                stopNetworkGraph();
            }
        }

        document.getElementById('dashboard-controls').addEventListener('keydown', event => {
            const tabs = [...document.querySelectorAll('#dashboard-controls .tab-btn')];
            const current = tabs.indexOf(document.activeElement);
            if (current < 0 || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            let next = current;
            if (event.key === 'ArrowRight') next = (current + 1) % tabs.length;
            if (event.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length;
            if (event.key === 'Home') next = 0;
            if (event.key === 'End') next = tabs.length - 1;
            tabs[next].focus();
            tabs[next].click();
        });

        // Accordion year toggler with lazy load of individual years
        function toggleYear(year) {
            const card = document.getElementById('yc-' + year);
            if (!card) return;

            const isOpening = !card.classList.contains('active');
            card.classList.toggle('active');

            if (isOpening) {
                // Initialize timeline object in CONFERENCE_DATA if missing
                if (!CONFERENCE_DATA.timeline) {
                    CONFERENCE_DATA.timeline = {};
                }

                // If not yet loaded, lazy fetch it!
                if (!CONFERENCE_DATA.timeline[year]) {
                    fetch(`site_data_timeline_${year}.json?v=1.8.5`)
                        .then(r => r.json())
                        .then(yearData => {
                            CONFERENCE_DATA.timeline[year] = yearData;
                            renderYearContent(year);
                        })
                        .catch(err => {
                            console.error("Error loading timeline year:", err);
                            const body = document.getElementById('yb-' + year);
                            if (body) {
                                body.innerHTML = `<div style="text-align: center; color: var(--accent2); padding: 2rem;">
                                    ${state.currentLang === 'ru' ? 'Ошибка загрузки данных' : 'Failed to load data'}
                                </div>`;
                            }
                        });
                }
            }
        }

        function renderTalkCard(talk, t, seriesClass) {
            const dayName = talk.day_of_week ? talk.day_of_week[state.currentLang] : (state.currentLang === 'ru' ? 'Не указан' : 'Not specified');
            
            // Rank/order badge
            let orderPillHtml = `<span class="badge" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-secondary); font-size: 0.65rem; text-transform: none; margin-left: 0.5rem; padding: 0.15rem 0.4rem;"># ${t.orderTalkBadge.replace('{num}', talk.order_in_session).replace('{total}', talk.total_in_session)}</span>`;
            if (talk.is_first_talk) {
                orderPillHtml += `<span class="badge badge-zograf" style="font-size: 0.65rem; text-transform: none; margin-left: 0.5rem; padding: 0.15rem 0.4rem;">🥇 ${t.firstTalkBadge}</span>`;
            }
            if (talk.is_last_talk) {
                orderPillHtml += `<span class="badge badge-roerich" style="font-size: 0.65rem; text-transform: none; margin-left: 0.5rem; padding: 0.15rem 0.4rem;">🎖️ ${t.lastTalkBadge}</span>`;
            }

            let presenterBadges = '';
            if (talk.is_student) presenterBadges += `<span class="badge badge-roerich" style="font-size: 0.65rem; text-transform: none; margin-left: 0.5rem; padding: 0.15rem 0.4rem;">🎓 ${t.studentBadge}</span>`;
            if (talk.is_independent) presenterBadges += `<span class="badge badge-zograf" style="font-size: 0.65rem; text-transform: none; margin-left: 0.5rem; padding: 0.15rem 0.4rem;">💼 ${t.independentBadge}</span>`;

            return `
                <div class="timeline-talk-card">
                    <div class="timeline-talk-title">
                        «${talk.title}»
                        ${orderPillHtml}
                    </div>
                    <div class="timeline-talk-speaker">
                        <strong>${talk.speaker}</strong> 
                        ${talk.affiliation ? `<span class="badge ${seriesClass}" style="font-size: 0.7rem;">${translateAffiliation(talk.affiliation)}</span>` : ''}
                        ${talk.is_online ? `<span class="badge badge-online">${t.onlineBadge}</span>` : ''}
                        ${talk.videos && talk.videos.length ? `<span class="badge badge-video">${t.videoBadge}</span>` : ''}
                        ${presenterBadges}
                    </div>
                    <div class="timeline-talk-meta" style="margin-top: 0.75rem;">
                        <span>🏛️ <strong>${t.venue}</strong>: ${translateAffiliation(talk.venue)}</span>
                        <span>💬 <strong>${t.session}</strong>: ${talk.session || (state.currentLang === 'ru' ? 'Научное заседание' : 'Scientific Session')}</span>
                    </div>
                    <div class="timeline-talk-meta" style="margin-top: 0.25rem; font-size: 0.78rem; color: var(--text-muted);">
                        <span>📅 <strong>${t.day}</strong>: ${dayName} (${talk.date || ''})</span>
                        <span>⏰ <strong>${t.timeLabel}</strong>: ${talk.time_interval}</span>
                    </div>
                </div>
            `;
        }

        function renderYearContent(year) {
            const body = document.getElementById('yb-' + year);
            if (!body) return;

            const t = TRANSLATIONS[state.currentLang];
            const yearData = CONFERENCE_DATA.timeline[year];
            if (!yearData) return;

            const zTalks = yearData["Zograf"] || [];
            const rTalks = yearData["Roerich"] || [];

            body.innerHTML = `
                ${zTalks.length > 0 ? `
                    <div class="series-block">
                        <div class="series-title-header">${t.zografReadingsLabel}</div>
                        <div class="talks-timeline-list">
                            ${zTalks.map(talk => renderTalkCard(talk, t, 'badge-zograf')).join('')}
                        </div>
                    </div>
                ` : ''}
                ${rTalks.length > 0 ? `
                    <div class="series-block">
                        <div class="series-title-header roerich">${t.roerichReadingsLabel}</div>
                        <div class="talks-timeline-list">
                            ${rTalks.map(talk => renderTalkCard(talk, t, 'badge-roerich')).join('')}
                        </div>
                    </div>
                ` : ''}
            `;
        }

        // Format dates/labels helper
        function formatDayLabel(label) {
            if (!label) return state.currentLang === 'ru' ? 'не указан' : 'unspecified';
            // Translate day word if English
            let dayText = label.replace(/\s+/g, ' ');
            if (state.currentLang === 'en') {
                dayText = dayText.replace(/Понедельник/g, 'Monday')
                                 .replace(/Вторник/g, 'Tuesday')
                                 .replace(/Среда/g, 'Wednesday')
                                 .replace(/Четверг/g, 'Thursday')
                                 .replace(/Пятница/g, 'Friday')
                                 .replace(/Суббота/g, 'Saturday')
                                 .replace(/Воскресенье/g, 'Sunday')
                                 .replace(/мая/g, 'May')
                                 .replace(/декабря/g, 'December');
            }
            return dayText;
        }

        // Translate dynamic values
        function translateAffiliation(val) {
            if (!val) return state.currentLang === 'ru' ? 'не указана' : 'unspecified';
            if (state.currentLang === 'en') {
                return val.replace(/СПб/g, 'SPb')
                          .replace(/СПбГУ/g, 'SPbSU')
                          .replace(/ИВР РАН/g, 'IOM RAS')
                          .replace(/ИВ РАН/g, 'IOS RAS')
                          .replace(/МГУ/g, 'MSU')
                          .replace(/РГГУ/g, 'RSUH')
                          .replace(/ВШЭ/g, 'HSE')
                          .replace(/ИНД/g, 'IND')
                          .replace(/МОСКВА/g, 'MOSCOW');
            }
            return val;
        }

        // Initialize scholars directory
        function initScholars() {
            state.filteredScholars = [...CONFERENCE_DATA.scholars];
            renderScholarsTable();
        }

        // Click-to-filter helper for affiliations and cities on dashboard
        function setDashboardSearch(keyword) {
            const searchInput = document.getElementById('scholars-search');
            searchInput.value = keyword;
            handleFilterChange();
        }

        function escapeHtml(value) {
            return String(value || '').replace(/[&<>"']/g, ch => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[ch]));
        }

        function normalizedTalkToken(token) {
            if (/^рамаян[а-яё]*$/i.test(token)) return 'рамаян';
            if (/^махабхарат[а-яё]*$/i.test(token)) return 'махабхарат';
            return token.toLowerCase();
        }

        function publicTagLabel(tag) {
            const labels = {
                'рамаян': 'Рамаяна',
                'махабхарат': 'Махабхарата',
                'индия': 'Индия',
                'южная_индия': 'Южная Индия'
            };
            return labels[String(tag || '').toLowerCase()] || tag;
        }

        function talkQueryTokens(query) {
            return query.toLowerCase().trim().split(/\s+/).filter(Boolean).map(normalizedTalkToken);
        }

        function titleMatchesTalkQuery(title, query) {
            const titleValue = String(title || '').toLowerCase();
            const tokens = talkQueryTokens(query);
            return tokens.length > 0 && tokens.every(token => titleValue.includes(token));
        }

        function namedTopicForQuery(query) {
            const tokens = talkQueryTokens(query);
            if (tokens.includes('рамаян')) return { href: 'topics/ramayana.html', ru: 'Страница сюжета «Рамаяна»', en: 'Ramayana topic page' };
            if (tokens.includes('махабхарат')) return { href: 'topics/mahabharata.html', ru: 'Страница сюжета «Махабхарата»', en: 'Mahabharata topic page' };
            return null;
        }

        function talkPageHref(talk) {
            if (talk.public_path) return talk.public_path;
            const prefix = talk.series && talk.series.includes('Zograf') ? 'zograf' : 'roerich';
            return `conferences/${prefix}-${talk.year}.html`;
        }

        function matchingTalks(query) {
            const matches = new Map();
            CONFERENCE_DATA.scholars.forEach(scholar => {
                (scholar.talks || []).forEach(talk => {
                    if (!titleMatchesTalkQuery(talk.title, query)) return;
                    if (!matches.has(talk.presentation_id)) {
                        matches.set(talk.presentation_id, { talk, authors: [] });
                    }
                    const name = state.currentLang === 'ru' ? scholar.full_name_ru : scholar.full_name_en;
                    if (name && !matches.get(talk.presentation_id).authors.includes(name)) {
                        matches.get(talk.presentation_id).authors.push(name);
                    }
                });
            });
            return [...matches.values()].sort((left, right) => right.talk.year - left.talk.year || left.talk.title.localeCompare(right.talk.title, state.currentLang === 'ru' ? 'ru' : 'en'));
        }

        function syncDashboardUrl() {
            const url = new URL(window.location.href);
            const query = document.getElementById('scholars-search').value.trim();
            const talksQuery = document.getElementById('talks-search').value.trim();
            const series = document.getElementById('filter-series').value;
            const sort = document.getElementById('filter-sort').value;
            query ? url.searchParams.set('search', query) : url.searchParams.delete('search');
            talksQuery ? url.searchParams.set('talks', talksQuery) : url.searchParams.delete('talks');
            series !== 'all' ? url.searchParams.set('series', series) : url.searchParams.delete('series');
            sort !== 'talks-desc' ? url.searchParams.set('sort', sort) : url.searchParams.delete('sort');
            history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`);
            return url;
        }

        function renderMatchingTalks(query) {
            const panel = document.getElementById('talk-query-results');
            if (!query) {
                panel.hidden = true;
                return;
            }
            const t = TRANSLATIONS[state.currentLang];
            const matches = matchingTalks(query);
            const url = new URL(window.location.href);
            const topic = namedTopicForQuery(query);
            document.getElementById('talk-query-heading').textContent = t.queryResultsTitle.replace('{query}', query);
            document.getElementById('talk-query-summary').textContent = t.queryResultsSummary.replace('{count}', matches.length);
            const permalink = document.getElementById('talk-query-permalink');
            permalink.href = url.toString();
            permalink.textContent = t.queryPermalink;
            const topicLink = document.getElementById('talk-query-topic-link');
            topicLink.hidden = !topic;
            if (topic) {
                topicLink.href = topic.href;
                topicLink.textContent = state.currentLang === 'ru' ? topic.ru : topic.en;
            }
            document.getElementById('talk-query-list').innerHTML = matches.map(item => {
                const talk = item.talk;
                const series = talk.series.includes('Zograf') ? t.zografReadingsLabel : t.roerichReadingsLabel;
                return `<article class="query-talk">
                    <div class="query-year">${escapeHtml(talk.year)}</div>
                    <div>
                        <a class="query-title" href="${talkPageHref(talk)}">${escapeHtml(talk.title)}</a>
                        <div class="query-meta">${escapeHtml(series)} · ${escapeHtml(item.authors.join('; '))}${talk.is_online ? ` · <span class="badge badge-online">${escapeHtml(t.onlineBadge)}</span>` : ''}${talk.videos && talk.videos.length ? ` · <span class="badge badge-video">${escapeHtml(t.videoBadge)}</span>` : ''}</div>
                    </div>
                </article>`;
            }).join('');
            panel.hidden = false;
        }

        // Translate theme code dynamically
        function translateThemeCode(code) {
            const themes = {
                AcademicHistory: { ru: "История науки и архивы", en: "History of Scholarship" },
                Linguistics: { ru: "Лингвистика и филология", en: "Linguistics & Philology" },
                Philosophy: { ru: "Философия и религия", en: "Philosophy & Religion" },
                Art: { ru: "Искусство и литература", en: "Art & Literature" },
                History: { ru: "История и этнография", en: "History & Ethnography" }
            };
            return themes[code] ? themes[code][state.currentLang] : (state.currentLang === 'ru' ? 'История и этнография' : 'History & Ethnography');
        }

        // Handle filters and sort changes
        function handleFilterChange() {

            


            // Autocomplete logic
            const buildAutocomplete = (inputId, dropdownId, getMatches, renderItem) => {
                const input = document.getElementById(inputId);
                const dropdown = document.getElementById(dropdownId);
                const query = input.value.trim().toLowerCase();
                
                if (query.length < 2) {
                    dropdown.hidden = true;
                    return;
                }
                
                const matches = getMatches(query).slice(0, 5);
                if (matches.length === 0) {
                    dropdown.hidden = true;
                    return;
                }
                
                dropdown.innerHTML = '';
                matches.forEach(match => {
                    const li = document.createElement('li');
                    li.className = 'autocomplete-item';
                    li.innerHTML = renderItem(match);
                    li.onclick = () => {
                        input.value = match.text;
                        dropdown.hidden = true;
                        handleFilterChange();
                    };
                    dropdown.appendChild(li);
                });
                dropdown.hidden = false;
            };

            // Scholar autocomplete (Fuzzy)
            buildAutocomplete('scholars-search', 'scholars-autocomplete', 
                q => {
                    initFuse();
                    if (scholarFuse) {
                        return scholarFuse.search(q).map(result => ({ text: state.currentLang === 'ru' ? result.item.full_name_ru : result.item.full_name_en }));
                    } else {
                        // Fallback
                        return CONFERENCE_DATA.scholars
                            .filter(s => (s.full_name_ru || '').toLowerCase().includes(q) || (s.full_name_en || '').toLowerCase().includes(q))
                            .map(s => ({ text: state.currentLang === 'ru' ? s.full_name_ru : s.full_name_en }));
                    }
                },
                match => match.text
            );




            const searchVal = document.getElementById('scholars-search').value.toLowerCase().trim();
            const talksSearchInput = document.getElementById('talks-search');
            const talksSearchVal = talksSearchInput ? talksSearchInput.value.toLowerCase().trim() : '';
            const seriesFilter = document.getElementById('filter-series').value;
            const sortFilter = document.getElementById('filter-sort').value;

            // Apply search & conference affinity filters
            state.filteredScholars = CONFERENCE_DATA.scholars.filter(s => {
                const matchesSearch = s.name.toLowerCase().includes(searchVal) ||
                                      s.original_fullname.toLowerCase().includes(searchVal) ||
                                      (s.full_name_ru && s.full_name_ru.toLowerCase().includes(searchVal)) ||
                                      (s.full_name_en && s.full_name_en.toLowerCase().includes(searchVal)) ||
                                      s.all_affiliations.some(aff => aff.toLowerCase().includes(searchVal)) ||
                                      (s.sessions || s.talks).some(talk => 
                                          talk.title.toLowerCase().includes(searchVal) || 
                                          (talk.geography && talk.geography.ru.toLowerCase().includes(searchVal)) ||
                                          (talk.geography && talk.geography.en.toLowerCase().includes(searchVal))
                                      );
                
                let matchesTalksSearch = true;
                if (talksSearchVal) {
                    matchesTalksSearch = (s.sessions || s.talks).some(talk => titleMatchesTalkQuery(talk.title, talksSearchVal));
                }
                
                let matchesSeries = true;
                if (seriesFilter === 'zograf') {
                    matchesSeries = s.zograf_talks > 0 && s.roerich_talks === 0;
                } else if (seriesFilter === 'roerich') {
                    matchesSeries = s.roerich_talks > 0 && s.zograf_talks === 0;
                } else if (seriesFilter === 'both') {
                    matchesSeries = s.zograf_talks > 0 && s.roerich_talks > 0;
                } else if (seriesFilter === 'never-zograf') {
                    matchesSeries = s.zograf_talks === 0;
                } else if (seriesFilter === 'never-roerich') {
                    matchesSeries = s.roerich_talks === 0;
                }

                return matchesSearch && matchesTalksSearch && matchesSeries;
            });

            // Apply Sorting
            if (sortFilter === 'talks-desc') {
                state.filteredScholars.sort((a, b) => b.total_talks - a.total_talks);
            } else if (sortFilter === 'talks-asc') {
                state.filteredScholars.sort((a, b) => a.total_talks - b.total_talks);
            } else if (sortFilter === 'name-asc') {
                state.filteredScholars.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
            } else if (sortFilter === 'name-desc') {
                state.filteredScholars.sort((a, b) => b.name.localeCompare(a.name, 'ru'));
            }

            state.currentPage = 1;
            syncDashboardUrl();
            renderMatchingTalks(talksSearchVal);
            renderScholarsTable();
        }

        // Render scholars table rows
        
        function toggleViewMode(mode) {
            state.viewMode = mode;
            localStorage.setItem('indology_view', mode);
            document.getElementById('btn-view-table').classList.toggle('active', mode === 'table');
            document.getElementById('btn-view-grid').classList.toggle('active', mode === 'grid');
            
            document.getElementById('scholars-table-container').hidden = (mode === 'grid');
            document.getElementById('scholars-grid-container').hidden = (mode === 'table');
            
            renderScholarsTable(); // Re-render in the new view
        }

        function renderScholarsTable() {
            const tbody = document.getElementById('scholars-tbody');
            tbody.innerHTML = '';


            const t = TRANSLATIONS[state.currentLang];
            const totalItems = state.filteredScholars.length;
            const totalPages = Math.ceil(totalItems / state.pageSize) || 1;

            // Boundary checks
            if (state.currentPage > totalPages) state.currentPage = totalPages;
            if (state.currentPage < 1) state.currentPage = 1;

            // Update Pagination display
            document.getElementById('prev-page-btn').disabled = state.currentPage === 1;
            document.getElementById('next-page-btn').disabled = state.currentPage === totalPages;
            
            document.getElementById('prev-page-btn').textContent = t.btnPrev;
            document.getElementById('next-page-btn').textContent = t.btnNext;
            document.getElementById('page-indicator').textContent = t.pageIndicator
                .replace('{current}', state.currentPage)
                .replace('{total}', totalPages)
                .replace('{count}', totalItems);

            const startIdx = (state.currentPage - 1) * state.pageSize;
            const endIdx = Math.min(startIdx + state.pageSize, totalItems);

            const displayList = state.filteredScholars.slice(startIdx, endIdx);


            if (state.viewMode === 'grid') {
                const gridContainer = document.getElementById('scholars-grid-container');
                gridContainer.innerHTML = '';
                
                if (displayList.length === 0) {
                    gridContainer.innerHTML = `<div style="text-align: center; color: var(--text-muted); width: 100%; grid-column: 1 / -1; padding: 3rem;">${t.emptySearch}</div>`;
                    return;
                }
                
                displayList.forEach(scholar => {
                    const card = document.createElement('div');
                    card.className = 'scholar-grid-card reveal';
                    
                    const name = state.currentLang === 'ru' ? scholar.full_name_ru : scholar.full_name_en;
                    const years = scholar.years_active ? `${scholar.years_active.start}–${scholar.years_active.end}` : '';
                    
                    card.innerHTML = `
                        <h4 class="scholar-grid-name">${name}</h4>
                        <div class="scholar-grid-stats">
                            <span class="badge" style="background: rgba(255,255,255,0.1)">📚 ${scholar.total_talks} ${t.thTalks}</span>
                            ${scholar.zograf_talks > 0 ? `<span class="badge badge-zograf">Зографские: ${scholar.zograf_talks}</span>` : ''}
                            ${scholar.roerich_talks > 0 ? `<span class="badge badge-roerich">Рериховские: ${scholar.roerich_talks}</span>` : ''}
                            ${years ? `<span class="badge" style="background: rgba(255,255,255,0.05)">📅 ${years}</span>` : ''}
                        </div>
                    `;
                    gridContainer.appendChild(card);
                });
                
                // Initialize VanillaTilt for grid cards
                if (window.VanillaTilt) {
                    VanillaTilt.init(document.querySelectorAll('.scholar-grid-card'), {
                        max: 5,
                        speed: 400,
                        glare: true,
                        "max-glare": 0.1
                    });
                }
                
                // Trigger reveal
                setTimeout(() => {
                    document.querySelectorAll('.scholar-grid-card.reveal').forEach(el => el.classList.add('visible'));
                }, 50);
                
                return; // skip table rendering
            }

            if (displayList.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 3rem;">${t.emptySearch}</td></tr>`;
                return;
            }

            displayList.forEach(s => {
                let badgeClass = 'badge-both';
                let badgeLabel = t.filterBoth;
                if (s.zograf_talks > 0 && s.roerich_talks === 0) {
                    badgeClass = 'badge-zograf';
                    badgeLabel = t.zografReadingsLabel;
                } else if (s.roerich_talks > 0 && s.zograf_talks === 0) {
                    badgeClass = 'badge-roerich';
                    badgeLabel = t.roerichReadingsLabel;
                }

                // Master row
                const row = document.createElement('tr');
                row.style.cursor = 'pointer';
                row.onclick = () => toggleRowDetail(s.id);
                
                // Localized display name and years of life formatting
                const displayName = state.currentLang === 'ru' ? s.full_name_ru : s.full_name_en;
                let lifeYears = '';
                if (s.birth_year) {
                    if (s.death_year) {
                        lifeYears = ` (${s.birth_year}–${s.death_year})`;
                    } else {
                        lifeYears = state.currentLang === 'ru' ? ` (род. {birth_year})`.replace('{birth_year}', s.birth_year) : ` (b. {birth_year})`.replace('{birth_year}', s.birth_year);
                    }
                }
                
                row.innerHTML = `
                    <td class="scholar-primary">
                        <div style="font-weight: 600; color: #ffffff;">
                            <a href="s/${s.url_slug}.html" style="color: #ffffff; text-decoration: none; border-bottom: 1px dashed rgba(255,255,255,0.4); transition: var(--transition);" onmouseover="this.style.color='var(--accent-primary)'; this.style.borderColor='var(--accent-primary)'" onmouseout="this.style.color='#ffffff'; this.style.borderColor='rgba(255,255,255,0.4)'" onclick="event.stopPropagation();">
                                ${displayName}
                            </a>
                            <span style="color: var(--text-secondary); font-weight: 400; font-size: 0.85rem; margin-left: 0.4rem;">${lifeYears}</span>
                        </div>
                        <span class="badge ${badgeClass}" style="margin-top: 0.25rem;">${badgeLabel}</span>
                    </td>
                    <td data-label="${t.colTotal}" style="font-weight: 700; color: var(--accent-primary); font-size: 1.1rem;">${s.total_talks}</td>
                    <td data-label="${t.colZograf}">${s.zograf_talks}</td>
                    <td data-label="${t.colRoerich}">${s.roerich_talks}</td>
                    <td data-label="${t.colYears}" style="font-family: var(--font-display); font-weight: 500;">${s.first_year === s.last_year ? s.first_year : s.first_year + '–' + s.last_year}</td>
                `;
                tbody.appendChild(row);

                // Detail row
                const detailRow = document.createElement('tr');
                detailRow.id = 'detail-' + s.id;
                detailRow.className = 'scholar-row-detail';
                
                // Add scholarly badges
                let academicBadgesHtml = '';
                if (s.is_student) {
                    academicBadgesHtml += `<span class="badge badge-roerich" style="margin-right: 0.5rem; margin-bottom: 0.5rem; text-transform: none; font-size: 0.8rem;">🎓 ${t.studentBadge}</span>`;
                }
                if (s.is_independent) {
                    academicBadgesHtml += `<span class="badge badge-zograf" style="margin-right: 0.5rem; margin-bottom: 0.5rem; text-transform: none; font-size: 0.8rem;">💼 ${t.independentBadge}</span>`;
                }
                
                let affiliationHistoryHtml = '';
                if (s.has_changed_affiliations && s.all_affiliations.length > 1) {
                    const mappedAffHtml = s.all_affiliations.map(aff => {
                        return `<span style="color: var(--accent-secondary); cursor: pointer; border-bottom: 1px dashed rgba(236,72,153,0.4);" onclick="event.stopPropagation(); setDashboardSearch('${aff.replace(/'/g, "\\'")}')">${translateAffiliation(aff)}</span>`;
                    }).join(' → ');
                    affiliationHistoryHtml += `
                        <div style="margin-top: 0.5rem; margin-bottom: 1rem; font-size: 0.85rem; color: var(--text-secondary); background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); padding: 0.5rem 1rem; border-radius: 6px;">
                            <strong>${t.changedAffilLabel}</strong> ${mappedAffHtml}
                        </div>
                    `;
                }
                
                if (!s.talks) {
                    // Full scholars data not yet loaded – show placeholder
                    detailRow.innerHTML = `
                        <td colspan="5">
                            <div class="detail-wrapper" style="text-align:center; color:var(--text-secondary); padding:1.5rem 1rem;">
                                <div style="margin-bottom:0.5rem; font-size:0.85rem;">
                                    ${state.currentLang === 'ru' ? 'Загрузка докладов…' : 'Loading presentations…'}
                                </div>
                            </div>
                        </td>
                    `;
                } else {
                let talksListHtml = s.talks.map(talk => {
                    const translatedSeries = talk.series.includes('Zograf') ? t.zografReadingsLabel : t.roerichReadingsLabel;
                    const dayName = talk.day_of_week ? talk.day_of_week[state.currentLang] : (state.currentLang === 'ru' ? 'Не указан' : 'Not specified');
                    
                    // Order pills
                    let orderPillHtml = `<span class="badge" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-secondary); font-size: 0.7rem; text-transform: none; margin-left: 0.5rem;"># ${t.orderTalkBadge.replace('{num}', talk.order_in_session).replace('{total}', talk.total_in_session)}</span>`;
                    if (talk.is_first_talk) {
                        orderPillHtml += `<span class="badge badge-zograf" style="font-size: 0.7rem; text-transform: none; margin-left: 0.5rem;">🥇 ${t.firstTalkBadge}</span>`;
                    }
                    if (talk.is_last_talk) {
                        orderPillHtml += `<span class="badge badge-roerich" style="font-size: 0.7rem; text-transform: none; margin-left: 0.5rem;">🎖️ ${t.lastTalkBadge}</span>`;
                    }
                    
                    const talkThemeCode = talk.theme ? talk.theme.code : 'unspecified';
                    const talkThemeName = talk.theme ? talk.theme[state.currentLang] : (state.currentLang === 'ru' ? 'Разное' : 'Other');
                    const themeBadgeHtml = `<span class="badge badge-theme theme-${talkThemeCode}" style="font-size: 0.7rem; text-transform: none; margin-left: 0.5rem; font-weight: 600;">${talkThemeName}</span>`;

                    // Gumilyov scale badge
                    const gScale = Number.isInteger(talk.gumilyov_scale) ? talk.gumilyov_scale : 0;
                    let gScaleName = "";
                    let gScaleColor = "";
                    if (gScale === 0) {
                        gScaleName = state.currentLang === 'ru' ? 'Не размечен' : 'Unclassified';
                        gScaleColor = '#6b7280'; // gray
                    } else if (gScale === 1) {
                        gScaleName = state.currentLang === 'ru' ? 'Микро' : 'Micro';
                        gScaleColor = '#4b5563'; // gray
                    } else if (gScale === 2) {
                        gScaleName = state.currentLang === 'ru' ? 'Региональный' : 'Regional';
                        gScaleColor = '#3b82f6'; // blue
                    } else {
                        gScaleName = state.currentLang === 'ru' ? 'Глобальный' : 'Global';
                        gScaleColor = '#8b5cf6'; // purple
                    }
                    const gumilyovBadgeHtml = `<span class="badge" title="Уровень обобщения по Л.Н. Гумилеву" style="font-size: 0.7rem; text-transform: none; margin-left: 0.5rem; font-weight: 600; background: ${gScaleColor}22; color: ${gScaleColor}; border: 1px solid ${gScaleColor}44;">L${gScale} ${gScaleName}</span>`;

                    // Clickable city tag
                    let cityHtml = '';
                    if (talk.geography && talk.geography[state.currentLang] !== 'Не указана' && talk.geography[state.currentLang] !== 'Not specified') {
                        cityHtml = `
                            <span style="margin-left: 1.5rem;">
                                📍 <strong>${state.currentLang === 'ru' ? 'Город' : 'City'}</strong>: 
                                <span style="color: var(--accent-primary); cursor: pointer; border-bottom: 1px dashed rgba(139,92,246,0.4);" onclick="event.stopPropagation(); setDashboardSearch('${talk.geography[state.currentLang].replace(/'/g, "\\'")}')">
                                    ${talk.geography[state.currentLang]}
                                </span>
                            </span>
                        `;
                    }
                    
                    const talksSearchInput = document.getElementById('talks-search');
                    const talksSearchVal = talksSearchInput ? talksSearchInput.value.trim() : '';
                    let displayTitle = talk.title;
                    if (talksSearchVal !== '') {
                        // escape regex characters just in case
                        const safeSearch = talksSearchVal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                        const regex = new RegExp(`(${safeSearch})`, 'gi');
                        displayTitle = displayTitle.replace(regex, '<mark style="background-color: rgba(139, 92, 246, 0.5); color: #fff; padding: 0 2px; border-radius: 2px;">$1</mark>');
                    }
                    
                    let tagsHtml = '';
                    if (talk.tags && talk.tags.length > 0) {
                        tagsHtml = `<div style="margin-top: 0.5rem; display: flex; flex-wrap: wrap; gap: 0.25rem;">
                            ${talk.tags.map(tag => `<span style="font-size: 0.65rem; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 0.1rem 0.4rem; border-radius: 4px; color: var(--text-secondary);">#${publicTagLabel(tag)}</span>`).join('')}
                        </div>`;
                    }

                    let videoHtml = '';
                    if (talk.videos && talk.videos.length > 0) {
                        const links = talk.videos.map((video, idx) => {
                            const label = talk.videos.length === 1 ? 'YouTube' : `YouTube ${idx + 1}`;
                            return `<a href="${video.url}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation();" style="color: var(--accent-primary); border-bottom: 1px dashed rgba(139,92,246,0.4);">${label}</a>`;
                        }).join(' · ');
                        videoHtml = `<div class="talk-meta" style="margin-top: 0.35rem; font-size: 0.78rem; color: var(--text-muted);">▶ <strong>${state.currentLang === 'ru' ? 'Видео' : 'Video'}</strong>: ${links}</div>`;
                    }
                    const affiliationHtml = talk.affiliation ? `
                                <span style="margin-left: 1rem;">
                                    🏢 ${state.currentLang === 'ru' ? 'Аффилиация' : 'Affiliation'}:
                                    <em style="color: var(--accent-secondary); cursor: pointer; border-bottom: 1px dashed rgba(236,72,153,0.4);" onclick="event.stopPropagation(); setDashboardSearch('${talk.affiliation.replace(/'/g, "\\'")}')">
                                        ${translateAffiliation(talk.affiliation)}
                                    </em>
                                </span>` : '';

                    return `
                        <div class="talk-item">
                            <div class="talk-title">
                                «${displayTitle}» 
                                ${talk.is_online ? `<span class="badge badge-online">${t.onlineBadge}</span>` : ''}
                                ${talk.videos && talk.videos.length ? `<span class="badge badge-video">${t.videoBadge}</span>` : ''}
                                ${orderPillHtml}
                                ${themeBadgeHtml}
                                ${gumilyovBadgeHtml}
                            </div>
                            <div class="talk-meta" style="margin-top: 0.5rem;">
                                <span>🏛️ ${state.currentLang === 'ru' ? 'Выступление на' : 'Presented at'} <strong>${translatedSeries}</strong> (${talk.year})</span>
                                ${affiliationHtml}
                            </div>
                            <div class="talk-meta" style="margin-top: 0.25rem; font-size: 0.78rem; color: var(--text-muted);">
                                <span>📅 <strong>${t.day}</strong>: ${dayName}</span>
                                <span style="margin-left: 1.5rem;">⏰ <strong>${t.timeLabel}</strong>: ${talk.time_interval}</span>
                                <span style="margin-left: 1.5rem;">💬 <strong>${t.session}</strong>: ${talk.session_title}</span>
                                ${cityHtml}
                            </div>
                            ${videoHtml}
                            ${tagsHtml}
                        </div>
                    `;
                }).join('');

                detailRow.innerHTML = `
                    <td colspan="5">
                        <div class="detail-wrapper">
                            <div style="display: flex; flex-wrap: wrap; align-items: center; margin-bottom: 0.5rem;">
                                ${academicBadgesHtml}
                            </div>
                            ${affiliationHistoryHtml}
                            
                            <!-- Premium Careers & Analytics Panel -->
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-top: 0.5rem; margin-bottom: 1rem;">
                                <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); padding: 0.8rem; border-radius: 8px;">
                                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">
                                        ${t.zografReadingsLabel}
                                    </div>
                                    <div style="font-family: var(--font-display); font-weight: 600; font-size: 0.95rem; color: #ffffff;">
                                        ${s.zograf_first ? `${state.currentLang === 'ru' ? 'Впервые' : 'First'}: ${s.zograf_first} | ${state.currentLang === 'ru' ? 'Последний раз' : 'Last'}: ${s.zograf_last}` : (state.currentLang === 'ru' ? 'Никогда не выступал' : 'Never presented')}
                                    </div>
                                </div>
                                <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); padding: 0.8rem; border-radius: 8px;">
                                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">
                                        ${t.roerichReadingsLabel}
                                    </div>
                                    <div style="font-family: var(--font-display); font-weight: 600; font-size: 0.95rem; color: #ffffff;">
                                        ${s.roerich_first ? `${state.currentLang === 'ru' ? 'Впервые' : 'First'}: ${s.roerich_first} | ${state.currentLang === 'ru' ? 'Последний раз' : 'Last'}: ${s.roerich_last}` : (state.currentLang === 'ru' ? 'Никогда не выступал' : 'Never presented')}
                                    </div>
                                </div>
                                <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); padding: 0.8rem; border-radius: 8px;">
                                    <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">
                                        ${state.currentLang === 'ru' ? 'Профиль исследований' : 'Research Profile'}
                                    </div>
                                    <div style="font-family: var(--font-display); font-weight: 600; font-size: 0.95rem; color: #ffffff;">
                                        ${s.thematic_breadth === 'Interdisciplinary' ? (state.currentLang === 'ru' ? 'Междисциплинарный исследователь' : 'Interdisciplinary Scholar') : (state.currentLang === 'ru' ? 'Узкий специалист' : 'Specialized Specialist')}
                                        ${s.dominant_theme ? `<span class="badge theme-${s.dominant_theme}" style="margin-left: 0.4rem; padding: 0.1rem 0.4rem; font-size: 0.7rem; text-transform: none; font-weight: 600;">${translateThemeCode(s.dominant_theme)}</span>` : ''}
                                    </div>
                                </div>
                            </div>

                            <div class="detail-title">${t.detailsTitle.replace('{count}', s.talks.length)}</div>
                            ${talksListHtml}
                        </div>
                    </td>
                `;
                } // end if (s.talks)
                tbody.appendChild(detailRow);
            });
        } // end renderScholarsTable

        // Toggle row expander
        function toggleRowDetail(id) {
            const detail = document.getElementById('detail-' + id);
            if (detail) {
                const isVisible = detail.style.display === 'table-row';
                // Close all details first
                document.querySelectorAll('.scholar-row-detail').forEach(d => d.style.display = 'none');
                
                // Toggle clicked
                detail.style.display = isVisible ? 'none' : 'table-row';
            }
        }

        // Change page
        function changePage(direction) {
            state.currentPage += direction;
            renderScholarsTable();
        }

        // Initialize timeline accordions
        function initTimeline() {
            const container = document.getElementById('timeline-accordion');
            container.innerHTML = '';

            const t = TRANSLATIONS[state.currentLang];
            if (!CONFERENCE_DATA || !CONFERENCE_DATA.stats) {
                container.innerHTML = `<div style="text-align: center; padding: 3rem; color: var(--text-secondary);">
                    <div class="loader" style="margin: 0 auto 1rem; border: 3px solid rgba(255,255,255,0.1); border-radius: 50%; border-top: 3px solid var(--accent); width: 30px; height: 30px;"></div>
                    ${state.currentLang === 'ru' ? 'Загрузка хронологии...' : 'Loading timeline...'}
                </div>`;
                return;
            }

            const statsList = [...CONFERENCE_DATA.stats].sort((a, b) => b.year - a.year);

            statsList.forEach(stat => {
                const year = stat.year;
                const zCount = stat.zograf;
                const rCount = stat.roerich;

                if (zCount === 0 && rCount === 0) return;

                const card = document.createElement('div');
                card.id = 'yc-' + year;
                card.className = 'year-card';

                let yearBadgeHtml = '';
                if (zCount > 0) yearBadgeHtml += `<span class="badge badge-zograf" style="margin-right: 0.5rem;">${t.colZograf}: ${zCount}</span>`;
                if (rCount > 0) yearBadgeHtml += `<span class="badge badge-roerich">${t.colRoerich}: ${rCount}</span>`;

                card.innerHTML = `
                    <div class="year-header" onclick="toggleYear('${year}')">
                        <div class="year-title">
                            ${year} ${state.currentLang === 'ru' ? 'г.' : ''}
                            <div style="display: inline-flex;">${yearBadgeHtml}</div>
                        </div>
                        <div class="year-indicator">
                            <!-- Arrow down SVG -->
                            <svg width="12" height="8" viewBox="0 0 12 8" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M1 1L6 6L11 1" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                            </svg>
                        </div>
                    </div>
                    <div class="year-body" id="yb-${year}">
                        <div style="text-align: center; padding: 2rem; color: var(--text-secondary);">
                            <div class="loader" style="margin: 0 auto 1rem; border: 3px solid rgba(255,255,255,0.1); border-radius: 50%; border-top: 3px solid var(--accent); width: 24px; height: 24px;"></div>
                            ${state.currentLang === 'ru' ? 'Загрузка докладов...' : 'Loading presentations...'}
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        // Draw Interactive SVG Growth Chart
        


        

        

        

        

        

        

        // Draw Interactive Word Cloud
        

        // ==========================================
        // Interactive Collaboration Graph (Network)
        // ==========================================
        let networkInstance = null;
        let nodesDataset = null;
        let edgesDataset = null;
        let isNetPhysicsRunning = true;

        function initNetwork() {
            if (networkInstance) return;
            const container = document.getElementById('chart-network-container');
            if (!container) return;

            // Replace the old canvas with a div for vis.js if it exists
            const canvas = document.getElementById('canvas-network');
            if (canvas) {
                const newDiv = document.createElement('div');
                newDiv.id = 'canvas-network';
                newDiv.style.width = '100%';
                newDiv.style.height = '100%';
                canvas.parentNode.replaceChild(newDiv, canvas);
            }

            const data = CONFERENCE_DATA.network;
            if (!data) {
                const target = document.getElementById('canvas-network');
                if (target) {
                    target.innerHTML = `<div style="height:100%;display:grid;place-items:center;color:var(--text-secondary);font-size:0.95rem;">
                        <div style="text-align: center;">
                            <div class="loader" style="margin: 0 auto 1rem; border: 3px solid rgba(255,255,255,0.1); border-radius: 50%; border-top: 3px solid var(--accent); width: 30px; height: 30px;"></div>
                            ${state.currentLang === 'ru' ? 'Загрузка графа связей...' : 'Loading collaboration graph...'}
                        </div>
                    </div>`;
                }
                return;
            }
            if (typeof vis === 'undefined') {
                const target = document.getElementById('canvas-network');
                if (target) {
                    target.innerHTML = `<div style="height:100%;display:grid;place-items:center;color:var(--text-secondary);font-size:0.95rem;">Не удалось загрузить библиотеку сетевого графа</div>`;
                }
                return;
            }

            const repeatedLinks = data.links.filter(l => l.weight >= 2);
            const linksSource = repeatedLinks.length >= 50 ? repeatedLinks : data.links;
            const linkedIds = new Set();
            linksSource.forEach(l => {
                linkedIds.add(l.source);
                linkedIds.add(l.target);
            });
            const topNodeIds = new Set(
                [...data.nodes]
                    .sort((a, b) => b.talks - a.talks)
                    .slice(0, 40)
                    .map(n => n.id)
            );
            const nodeIds = new Set([...linkedIds, ...topNodeIds]);

            const THEME_COLORS = {
                AcademicHistory: '#8b5cf6', // Violet
                Linguistics: '#3b82f6',     // Blue
                Philosophy: '#10b981',      // Green
                Art: '#ec4899',             // Pink
                History: '#f59e0b'          // Orange
            };

            const nodes = data.nodes.filter(n => nodeIds.has(n.id)).map(n => {
                const color = THEME_COLORS[n.theme] || THEME_COLORS.History;
                const scaleSize = 8 + Math.sqrt(n.talks) * 3;
                return {
                    id: n.id,
                    label: n.name,
                    size: scaleSize,
                    color: {
                        background: color,
                        border: 'rgba(255, 255, 255, 0.35)',
                        highlight: { background: color, border: '#ffffff' },
                        hover: { background: color, border: '#ffffff' }
                    },
                    shape: 'dot',
                    font: { color: '#f3f4f6', face: 'Inter', size: 10, strokeWidth: 2, strokeColor: '#0a0e1a' },
                    title: `${n.name} (${state.currentLang === 'ru' ? 'Докладов' : 'Talks'}: ${n.talks})`
                };
            });

            const edges = linksSource.filter(l => nodeIds.has(l.source) && nodeIds.has(l.target)).map(l => {
                return {
                    from: l.source,
                    to: l.target,
                    value: l.weight,
                    color: { color: 'rgba(255, 255, 255, 0.12)', opacity: 0.2, highlight: 'rgba(139, 92, 246, 0.75)' },
                    width: 1 + l.weight * 0.5
                };
            });

            nodesDataset = new vis.DataSet(nodes);
            edgesDataset = new vis.DataSet(edges);

            const visData = {
                nodes: nodesDataset,
                edges: edgesDataset
            };

            const options = {
                layout: {
                    improvedLayout: false
                },
                nodes: {
                    borderWidth: 1.5,
                    shadow: { enabled: true, color: 'rgba(0,0,0,0.5)', size: 4, x: 2, y: 2 }
                },
                edges: {
                    smooth: false,
                    shadow: { enabled: false }
                },
                interaction: {
                    hover: true,
                    tooltipDelay: 150,
                    hideEdgesOnDrag: true,
                    hideEdgesOnZoom: true
                },
                physics: {
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {
                        gravitationalConstant: -120,
                        centralGravity: 0.015,
                        springLength: 120,
                        springConstant: 0.05,
                        damping: 0.4,
                        avoidOverlap: 0.95
                    },
                    stabilization: {
                        enabled: true,
                        iterations: 50,
                        updateInterval: 10,
                        fit: true
                    }
                }
            };

            networkInstance = new vis.Network(document.getElementById('canvas-network'), visData, options);
            networkInstance.once('stabilizationIterationsDone', function() {
                networkInstance.setOptions({ physics: { enabled: false } });
                isNetPhysicsRunning = false;
                const t = TRANSLATIONS[state.currentLang];
                const pauseBtn = document.getElementById('net-pause-btn');
                if (pauseBtn) pauseBtn.textContent = t.netResumeBtn;
            });
            setTimeout(() => {
                if (networkInstance && isNetPhysicsRunning) {
                    networkInstance.setOptions({ physics: { enabled: false } });
                    isNetPhysicsRunning = false;
                    const t = TRANSLATIONS[state.currentLang];
                    const pauseBtn = document.getElementById('net-pause-btn');
                    if (pauseBtn) pauseBtn.textContent = t.netResumeBtn;
                }
            }, 1600);

            // Add navigation on click!
            networkInstance.on('click', function(params) {
                if (params.nodes.length > 0) {
                    const nodeId = params.nodes[0];
                    const node = nodesDataset.get(nodeId);
                    if (node) {
                        switchTab('scholars');
                        setDashboardSearch(node.label);
                    }
                }
            });
        }

        function startNetworkGraph() {
            initNetwork();
            if (networkInstance) {
                networkInstance.setOptions({ physics: { enabled: isNetPhysicsRunning } });
            }
        }

        function stopNetworkGraph() {
            if (networkInstance) {
                networkInstance.setOptions({ physics: { enabled: false } });
            }
        }

        function resetNetworkPhysics() {
            if (networkInstance) {
                networkInstance.physics.stabilize();
                networkInstance.fit({ animation: { duration: 600 } });
            }
        }

        function toggleNetworkPhysics() {
            isNetPhysicsRunning = !isNetPhysicsRunning;
            if (networkInstance) {
                networkInstance.setOptions({ physics: { enabled: isNetPhysicsRunning } });
            }
            const t = TRANSLATIONS[state.currentLang];
            document.getElementById('net-pause-btn').textContent = isNetPhysicsRunning ? t.netPauseBtn : t.netResumeBtn;
        }

        function exportToMarkdown() {
            const isRu = state.currentLang === 'ru';
            let content = isRu ? `# Выборка исследователей-индологов\n` : `# Selected Indology Scholars\n`;
            content += isRu ? `*Сгенерировано платформой IndologyScholars: ${new Date().toISOString().split('T')[0]}*\n` : `*Generated by IndologyScholars Platform: ${new Date().toISOString().split('T')[0]}*\n`;
            content += isRu ? `*Найдено ученых: ${state.filteredScholars.length}*\n\n---\n\n` : `*Scholars Found: ${state.filteredScholars.length}*\n\n---\n\n`;

            state.filteredScholars.forEach(s => {
                content += `## ${s.name}\n`;
                content += isRu ? `* **Докладов**: ${s.total_talks} (Зографские: ${s.zograf_talks}, Рериховские: ${s.roerich_talks})\n` : `* **Total Talks**: ${s.total_talks} (Zograf: ${s.zograf_talks}, Roerich: ${s.roerich_talks})\n`;
                
                const yearsList = [...new Set(s.sessions.map(sess => sess.year))].sort();
                const yearsStr = yearsList.length > 0 ? (yearsList.length === 1 ? `${yearsList[0]}` : `${yearsList[0]} - ${yearsList[yearsList.length - 1]}`) : 'N/A';
                content += isRu ? `* **Годы активности**: ${yearsStr}\n` : `* **Active Years**: ${yearsStr}\n`;
                content += isRu ? `* **Доминирующая тема**: ${translateThemeCode(s.dominant_theme)}\n\n` : `* **Dominant Theme**: ${translateThemeCode(s.dominant_theme)}\n\n`;
                
                content += isRu ? `### Список докладов:\n` : `### Presentations List:\n`;
                s.sessions.sort((a, b) => b.year - a.year).forEach((sess, idx) => {
                    const venueStr = sess.series === 'Zograf' ? (isRu ? 'Зографские' : 'Zograf Readings') : (isRu ? 'Рериховские' : 'Roerich Readings');
                    content += `${idx + 1}. ${sess.title} (${sess.year}, ${venueStr})\n`;
                });
                content += `\n---\n\n`;
            });

            const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `indology_export_${new Date().toISOString().split('T')[0]}.md`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        // Initialize Application — wait for both DOM and data fetch
        const _domReady = new Promise(resolve => window.addEventListener('DOMContentLoaded', resolve));
        Promise.all([_dataPromise, _domReady]).then(([data]) => {
            window.CONFERENCE_DATA = data;
            updateSummaryStats();
            initTilt();
            observeReveals();
            initScholars();
            initTimeline();

            const lazyLoadData = () => {
                timelinePromise = fetch('site_data_timeline.json?v=1.8.5').then(r => r.json());
                networkPromise = fetch('site_data_network.json?v=1.8.5').then(r => r.json());
                scholarsPromise = fetch('site_data_scholars.json?v=1.8.5').then(r => r.json());

                timelinePromise.then(timelineData => {
                    window.CONFERENCE_DATA.timeline = timelineData;
                    state.timelineLoaded = true;
                    initTimeline();
                });

                networkPromise.then(networkData => {
                    window.CONFERENCE_DATA.network = networkData;
                    state.networkLoaded = true;
                    if (document.getElementById('sec-charts').classList.contains('active')) {
                        startNetworkGraph();
                    }
                });

                scholarsPromise.then(fullScholars => {
                    const scholarMap = new Map(fullScholars.map(s => [s.id, s]));
                    window.CONFERENCE_DATA.scholars.forEach(s => {
                        const full = scholarMap.get(s.id);
                        if (full) {
                            s.talks = full.talks;
                            s.sessions = full.talks;
                        }
                    });
                    state.fullScholarsLoaded = true;
                    handleFilterChange();
                });
            };

            if (window.requestIdleCallback) {
                window.requestIdleCallback(() => lazyLoadData(), { timeout: 2000 });
            } else {
                setTimeout(lazyLoadData, 1000);
            }

            // Check for search parameter in URL
            const urlParams = new URLSearchParams(window.location.search);
            const searchQuery = urlParams.get('search');
            const talksQuery = urlParams.get('talks');
            const seriesQuery = urlParams.get('series');
            const sortQuery = urlParams.get('sort');
            if (searchQuery) document.getElementById('scholars-search').value = searchQuery;
            if (talksQuery) document.getElementById('talks-search').value = talksQuery;
            if (seriesQuery && [...document.getElementById('filter-series').options].some(option => option.value === seriesQuery)) {
                document.getElementById('filter-series').value = seriesQuery;
            }
            if (sortQuery && [...document.getElementById('filter-sort').options].some(option => option.value === sortQuery)) {
                document.getElementById('filter-sort').value = sortQuery;
            }
            if (searchQuery || talksQuery || seriesQuery || sortQuery) handleFilterChange();
        });
    
        // Expose functions globally to window for HTML event handlers and cross-module calls
        window.toggleLanguage = toggleLanguage;
        window.switchTab = switchTab;
        window.exportToMarkdown = exportToMarkdown;
        window.toggleViewMode = toggleViewMode;
        window.changePage = changePage;
        window.toggleYear = toggleYear;
        window.setDashboardSearch = setDashboardSearch;
        window.handleFilterChange = handleFilterChange;
        window.translateAffiliation = translateAffiliation;
        window.resetNetworkPhysics = resetNetworkPhysics;
        window.toggleNetworkPhysics = toggleNetworkPhysics;
