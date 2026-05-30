import { state } from './state.js';
import { TRANSLATIONS } from './i18n.js';

window.myCharts = window.myCharts || {};

export const getChartColor = (name) => {
    const colors = {
        zograf: '#62ae92',
        roerich: '#c59a56',
        total: '#a78bfa'
    };
    return colors[name] || '#fff';
};

export const destroyChart = (id) => {
    if (window.myCharts[id]) {
        if (typeof window.myCharts[id].destroy === 'function') {
            window.myCharts[id].destroy();
        } else if (typeof window.myCharts[id].remove === 'function') {
            window.myCharts[id].remove(); // For Leaflet Map
        }
    }
};


export function renderGrowthChart() {
            const ctx = document.getElementById('canvas-growth').getContext('2d');
            destroyChart('growth');
            const data = CONFERENCE_DATA.stats;
            const t = TRANSLATIONS[state.currentLang];
            
            const gradientTotal = ctx.createLinearGradient(0, 0, 0, 350);
            gradientTotal.addColorStop(0, 'rgba(167, 139, 250, 0.4)');
            gradientTotal.addColorStop(1, 'rgba(167, 139, 250, 0)');

            window.myCharts['growth'] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => d.year),
                    datasets: [
                        {
                            label: t.chartLegendTotal,
                            data: data.map(d => d.total),
                            borderColor: getChartColor('total'),
                            backgroundColor: gradientTotal,
                            fill: true,
                            tension: 0.4,
                            borderWidth: 2
                        },
                        {
                            label: t.chartLegendZograf,
                            data: data.map(d => d.zograf),
                            borderColor: getChartColor('zograf'),
                            tension: 0.4,
                            borderWidth: 2,
                            fill: false
                        },
                        {
                            label: t.chartLegendRoerich,
                            data: data.map(d => d.roerich),
                            borderColor: getChartColor('roerich'),
                            tension: 0.4,
                            borderWidth: 2,
                            fill: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#e7ece8' } }
                    },
                    scales: {
                        x: { ticks: { color: '#87938c' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { ticks: { color: '#87938c' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });
        }

export function renderCohortDistribution() {
            const ctx = document.getElementById('canvas-affinity').getContext('2d');
            destroyChart('affinity');
            const t = TRANSLATIONS[state.currentLang];
            
            const zCount = CONFERENCE_DATA.scholars.filter(s => s.zograf_talks > 0 && s.roerich_talks === 0).length;
            const rCount = CONFERENCE_DATA.scholars.filter(s => s.roerich_talks > 0 && s.zograf_talks === 0).length;
            const oCount = CONFERENCE_DATA.scholars.filter(s => s.zograf_talks > 0 && s.roerich_talks > 0).length;

            window.myCharts['affinity'] = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: [t.spbCohort.replace(' ({count})', ''), t.overlapCohort.replace(' ({count})', ''), t.moscowCohort.replace(' ({count})', '')],
                    datasets: [{
                        data: [zCount, oCount, rCount],
                        backgroundColor: [getChartColor('zograf'), '#8b5cf6', getChartColor('roerich')],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#e7ece8' } }
                    },
                    cutout: '70%'
                }
            });
        }

export function renderGeoChart() {
            const mapContainer = document.getElementById('map-geo');
            if (!mapContainer) return;
            
            destroyChart('geo');
            const geoData = (CONFERENCE_DATA.geography_stats || []).filter(d => d.count > 0 && d.lat && d.lon);
            
            const map = L.map('map-geo', {
                zoomControl: true,
                attributionControl: false
            }).setView([55.0, 50.0], 3);
            
            window.myCharts['geo'] = map;
            
            // CartoDB Dark Matter tiles
            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                subdomains: 'abcd',
                maxZoom: 19
            }).addTo(map);
            
            if (geoData.length === 0) return;
            const maxCount = Math.max(...geoData.map(d => d.count));
            
            geoData.forEach(d => {
                const radius = Math.max(5, (d.count / maxCount) * 20);
                
                const circle = L.circleMarker([d.lat, d.lon], {
                    radius: radius,
                    fillColor: '#8b5cf6',
                    color: '#c4b5fd',
                    weight: 1,
                    opacity: 0.8,
                    fillOpacity: 0.6
                }).addTo(map);
                
                const cityName = state.currentLang === 'ru' ? d.ru : d.en;
                const countLabel = state.currentLang === 'ru' ? 'Докладов' : 'Talks';
                
                circle.bindTooltip(`<strong>${cityName}</strong><br>${countLabel}: ${d.count}`, {
                    direction: 'top',
                    className: 'geo-tooltip'
                });
            });
        }

export function renderAgeChart() {
            const ctx = document.getElementById('canvas-age').getContext('2d');
            destroyChart('age');
            const data = (CONFERENCE_DATA.generation_stats || []);
            
            window.myCharts['age'] = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => state.currentLang === 'ru' ? d.label_ru : d.label_en),
                    datasets: [{
                        label: state.currentLang === 'ru' ? 'Ученые' : 'Scholars',
                        data: data.map(d => d.count),
                        backgroundColor: '#10b981',
                        borderRadius: 4
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: '#87938c' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { ticks: { color: '#87938c' }, grid: { display: false } }
                    }
                }
            });
        }

export function renderGenderChart() {
            const ctx = document.getElementById('canvas-gender').getContext('2d');
            destroyChart('gender');
            const genderStats = CONFERENCE_DATA.gender_stats || { M: 0, F: 0 };
            const t = TRANSLATIONS[state.currentLang];
            
            window.myCharts['gender'] = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: [state.currentLang === 'ru' ? 'Мужчины' : 'Males', state.currentLang === 'ru' ? 'Женщины' : 'Females'],
                    datasets: [{
                        data: [genderStats.M, genderStats.F],
                        backgroundColor: [getChartColor('zograf'), getChartColor('roerich')],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom', labels: { color: '#e7ece8' } } }
                }
            });
        }

export function renderSankeyChart() {
    const canvas = document.getElementById('canvas-sankey');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    destroyChart('sankey');

    const scholars = window.CONFERENCE_DATA?.scholars || [];
    
    // Build flows: Generation -> Conference -> Theme
    const linksMap = new Map();
    const addLink = (source, target, value) => {
        const key = `${source}|${target}`;
        linksMap.set(key, (linksMap.get(key) || 0) + value);
    };

    scholars.forEach(s => {
        let gen = s.generation_label_ru || 'Неизвестно';
        if (state.currentLang === 'en') {
            gen = s.generation_label_en || 'Unknown';
        }
        if (!gen) gen = 'Неизвестно';
        
        // Aggregate conference participations
        let zografVal = s.zograf_talks || 0;
        let roerichVal = s.roerich_talks || 0;
        
        const cZograf = state.currentLang === 'ru' ? 'Зографские' : 'Zograf Readings';
        const cRoerich = state.currentLang === 'ru' ? 'Рериховские' : 'Roerich Readings';
        
        if (zografVal > 0) addLink(gen, cZograf, zografVal);
        if (roerichVal > 0) addLink(gen, cRoerich, roerichVal);
        
        // Then link conferences to theme
        const themeCode = s.dominant_theme || 'unspecified';
        let themeName = themeCode;
        if (window.TRANSLATIONS && window.TRANSLATIONS[state.currentLang] && window.TRANSLATIONS[state.currentLang].themes) {
            themeName = window.TRANSLATIONS[state.currentLang].themes[themeCode] || themeCode;
        }
        
        if (zografVal > 0) addLink(cZograf, themeName, zografVal);
        if (roerichVal > 0) addLink(cRoerich, themeName, roerichVal);
    });

    const dataPoints = Array.from(linksMap.entries()).map(([key, value]) => {
        const [source, target] = key.split('|');
        return { from: source, to: target, flow: value };
    });

    if (dataPoints.length === 0) return;

    window.myCharts['sankey'] = new Chart(ctx, {
        type: 'sankey',
        data: {
            datasets: [{
                label: state.currentLang === 'ru' ? 'Связи' : 'Flows',
                data: dataPoints,
                colorFrom: c => getChartColor('total'),
                colorTo: c => '#8b5cf6',
                colorMode: 'gradient',
                alpha: 0.6,
                size: 'max',
                labels: { color: '#ffffff', font: { family: 'Inter', size: 11 } }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } }
        }
    });
}

export function renderInstChart() {
            const tbody = document.getElementById('inst-tbody');
            if (!tbody) return;
            tbody.innerHTML = '';

            const instData = CONFERENCE_DATA.institutions_stats || [];
            
            // Top 10 institutions
            const displayData = instData.slice(0, 10);
            
            displayData.forEach(d => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                tr.innerHTML = `
                    <td style="padding: 0.75rem 0.5rem; color: #ffffff; font-weight: 500;">
                        <span style="color: var(--accent-secondary); cursor: pointer; border-bottom: 1px dashed rgba(236,72,153,0.4);" onclick="switchTab('scholars'); setDashboardSearch('${d.name.replace(/'/g, "\\'")}')">
                            ${window.translateAffiliation ? window.translateAffiliation(d.name) : d.name}
                        </span>
                    </td>
                    <td style="padding: 0.75rem 0.5rem; color: var(--text-secondary);">${d.unique_scholars}</td>
                    <td style="padding: 0.75rem 0.5rem; color: var(--accent-primary); font-weight: 700;">${d.total_talks}</td>
                `;
                tbody.appendChild(tr);
            });
        }

export function renderWordCloud() {
            const container = document.getElementById('chart-words');
            if (!container) return;
            container.innerHTML = '';
            
            const wordsData = CONFERENCE_DATA.word_cloud || [];
            if (wordsData.length === 0) return;
            
            const maxWeight = Math.max(...wordsData.map(w => w.weight));
            const minWeight = Math.min(...wordsData.map(w => w.weight));
            
            // Generate spans
            wordsData.forEach(w => {
                const span = document.createElement('span');
                
                // Scale font size linearly between 0.8rem and 2.5rem
                const normalizedWeight = (w.weight - minWeight) / (maxWeight - minWeight);
                const fontSize = 0.8 + normalizedWeight * 1.7;
                
                // Color gradient based on weight
                const opacity = 0.4 + normalizedWeight * 0.6;
                
                span.textContent = w.text;
                span.style.fontSize = fontSize + 'rem';
                span.style.color = `rgba(139, 92, 246, ${opacity})`;
                span.style.lineHeight = '1';
                span.style.fontWeight = normalizedWeight > 0.5 ? '700' : '400';
                span.style.cursor = 'pointer';
                span.style.transition = '0.2s';
                span.style.whiteSpace = 'nowrap';
                
                // Interactive highlight on hover
                span.onmouseover = () => {
                    span.style.color = '#ffffff';
                    span.style.textShadow = '0 0 10px rgba(139, 92, 246, 0.8)';
                };
                span.onmouseout = () => {
                    span.style.color = `rgba(139, 92, 246, ${opacity})`;
                    span.style.textShadow = 'none';
                };
                
                // Click to search
                span.onclick = () => {
                    if (window.switchTab) window.switchTab('scholars');
                    const talksSearch = document.getElementById('talks-search');
                    if (talksSearch) {
                        talksSearch.value = w.text;
                        if (window.handleFilterChange) window.handleFilterChange();
                    }
                };
                
                container.appendChild(span);
            });
        }

