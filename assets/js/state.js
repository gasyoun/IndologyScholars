export const state = {
    currentLang: localStorage.getItem('indology_lang') || 'ru',
    viewMode: localStorage.getItem('indology_view') || 'table',
    filteredScholars: [],
    currentPage: 1,
    pageSize: 12,
    fullScholarsLoaded: false,
    timelineLoaded: false,
    networkLoaded: false
};
