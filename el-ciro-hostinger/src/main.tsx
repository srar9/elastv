import {createRoot} from 'react-dom/client';
import App from './App';
import {initTelegram} from './telegram';
initTelegram();
createRoot(document.getElementById('app')!).render(<App/>);
