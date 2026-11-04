'use strict';
window.normalizeSearch = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');
document.addEventListener('DOMContentLoaded', () => {
    const tg = window.Telegram?.WebApp;
    try {
        if(tg) {
            tg.ready(); tg.expand(); tg.setHeaderColor('#f5f5f7'); tg.setBackgroundColor('#f5f5f7');
            if(location.pathname !== '/') { tg.BackButton?.show(); tg.BackButton?.onClick(() => history.length>1?history.back():location.assign('/')); }
            else tg.BackButton?.hide();
        }
    } catch (_) {}
    try {
        if(tg?.initData) sessionStorage.setItem('elciro_init', tg.initData);
        let session = sessionStorage.getItem('elciro_app_session');
        if(!session) { session = 'a_' + (crypto.randomUUID ? crypto.randomUUID() : Date.now() + Math.random().toString(36).slice(2)); sessionStorage.setItem('elciro_app_session', session); }
        fetch('/api/audience', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:session,match_id:'__app__',title:'Mini App',playing:false})}).catch(() => {});
        const auth = tg?.initData || sessionStorage.getItem('elciro_init') || '';
        if(auth) fetch('/api/admin/statistics',{headers:{'X-Telegram-Init-Data':auth},cache:'no-store'}).then(response => {
            const link = document.getElementById('ownerLink'); if(response.ok && link) link.hidden = false;
        }).catch(() => {});
    } catch (_) {}
});

